import base64
import hashlib
from decimal import Decimal
from datetime import timedelta

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models
from django.utils import timezone

INVOICE_STATUS_CHOICES = [
    ("ISSUED", "Emitida"),
    ("CANCELLED", "Anulada"),
]

TAXPAYER_TYPE_CHOICES = [
    ("INDIVIDUAL", "Persona física"),
    ("COMPANY", "Persona jurídica"),
]

MEMBER_ROLE_CHOICES = [
    ("OWNER", "Propietario"),
    ("STAFF", "Empleado"),
]

REGISTRO_STATUS_CHOICES = [
    ("PENDING", "Pendiente de envío"),
    ("NO_REGISTRADO", "No registrado"),
    ("PENDIENTE", "Pendiente en la AEAT"),
    ("INCORRECTO", "Incorrecto"),
    ("CORRECTO", "Correcto"),
]

# VeriFactu devuelve el estado en texto; se traduce al código interno.
AEAT_ESTADOS = {
    "no registrado": "NO_REGISTRADO",
    "pendiente": "PENDIENTE",
    "incorrecto": "INCORRECTO",
    "correcto": "CORRECTO",
}


def aeat_status_code(value):
    """Traduce el estado textual que devuelve la API al código guardado."""
    return AEAT_ESTADOS.get(str(value or "").strip().lower(), "PENDIENTE")


class Emisor(models.Model):
    """Negocio que emite las facturas: la identidad fiscal que va en los registros.

    Admite varias peluquerías y varios usuarios por peluquería (ver EmisorMember).
    Las credenciales de VeriFactu viven aparte, en VerifactuConfig.
    """

    name = models.CharField(max_length=150, verbose_name="Razón social")
    trade_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
        verbose_name="Nombre comercial",
    )
    nif = models.CharField(max_length=20, unique=True, verbose_name="NIF")
    taxpayer_type = models.CharField(
        max_length=10,
        choices=TAXPAYER_TYPE_CHOICES,
        default="INDIVIDUAL",
        verbose_name="Tipo de persona",
    )
    fiscal_address = models.TextField(
        blank=True,
        default="",
        verbose_name="Domicilio fiscal",
    )
    series_prefix = models.CharField(
        max_length=20,
        default="FAC",
        verbose_name="Prefijo de serie",
    )
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "emisor"
        verbose_name_plural = "emisores"
        ordering = ("name", "pk")

    def __str__(self):
        return f"{self.name} ({self.nif})"


def _fernet():
    """Clave de cifrado derivada de SECRET_KEY: si esta cambia, no se descifra."""
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


class EncryptedTextField(models.TextField):
    """Texto cifrado en la base de datos: el código lo maneja siempre en claro."""

    def get_prep_value(self, value):
        if not value:
            return value
        return _fernet().encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        try:
            return _fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            return ""


class VerifactuConfig(models.Model):
    """Conexión con VeriFactu: credenciales y estado, separadas de los datos fiscales."""

    emisor = models.OneToOneField(
        Emisor,
        on_delete=models.CASCADE,
        related_name="verifactu",
    )
    email = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="Usuario en VeriFactu",
    )
    password = EncryptedTextField(
        blank=True,
        default="",
        verbose_name="Contraseña en VeriFactu",
    )
    is_connected = models.BooleanField(default=False, verbose_name="Conectado")
    last_login_at = models.DateTimeField(null=True, blank=True, verbose_name="Último acceso")
    last_error = models.TextField(blank=True, default="", verbose_name="Último error")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "configuración de VeriFactu"
        verbose_name_plural = "configuraciones de VeriFactu"

    def __str__(self):
        return f"VeriFactu · {self.emisor.nif}"


class EmisorMember(models.Model):
    """Usuario que administra un negocio."""

    emisor = models.ForeignKey(
        Emisor,
        on_delete=models.CASCADE,
        related_name="members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="emisor_memberships",
    )
    role = models.CharField(
        max_length=10,
        choices=MEMBER_ROLE_CHOICES,
        default="OWNER",
        verbose_name="Rol",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "miembro"
        verbose_name_plural = "miembros"
        ordering = ("emisor", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=["emisor", "user"],
                name="invoicing_unique_member_per_emisor",
            ),
        ]

    def __str__(self):
        return f"{self.user} · {self.emisor}"


def emisor_for_user(user):
    """Negocio activo del usuario: el primero del que es miembro."""
    if not getattr(user, "is_authenticated", False):
        return None
    membership = (
        EmisorMember.objects.filter(user=user, emisor__is_active=True)
        .select_related("emisor")
        .order_by("emisor_id")
        .first()
    )
    return membership.emisor if membership else None


def emisor_heredado():
    """Negocio anterior al multitenancy: todavía sin usuarios y con datos ya creados.

    Es el que deja la migración que reparte los datos previos entre negocios. El
    primer registro que llega lo reclama en lugar de crear uno nuevo, para que no
    se pierda nada de lo que ya había.
    """
    return (
        Emisor.objects.filter(members__isnull=True)
        .filter(
            models.Q(dogs__isnull=False)
            | models.Q(contacts__isnull=False)
            | models.Q(appointments__isnull=False)
            | models.Q(service_history__isnull=False)
        )
        .order_by("pk")
        .first()
    )


class InvoiceSequence(models.Model):
    """Contador de numeración por emisor y año."""

    emisor = models.ForeignKey(
        Emisor,
        on_delete=models.CASCADE,
        related_name="sequences",
    )
    year = models.PositiveIntegerField(verbose_name="Año")
    last_number = models.PositiveIntegerField(default=0, verbose_name="Último número")

    class Meta:
        verbose_name = "serie"
        verbose_name_plural = "series"
        constraints = [
            models.UniqueConstraint(
                fields=["emisor", "year"],
                name="invoicing_unique_sequence_per_emisor_year",
            ),
        ]

    def __str__(self):
        return f"{self.emisor.nif} · {self.year}"

    @classmethod
    def reserve_next(cls, emisor, year):
        """Reserva el siguiente número de la serie. Debe llamarse dentro de una transacción."""
        sequence, _ = cls.objects.get_or_create(emisor=emisor, year=year)
        locked = cls.objects.select_for_update().get(pk=sequence.pk)
        locked.last_number += 1
        locked.save(update_fields=["last_number"])
        return locked.last_number


class Invoice(models.Model):
    """Factura emitida por un emisor. Su estado fiscal vive en VerifactuRecord."""

    emisor = models.ForeignKey(Emisor, on_delete=models.PROTECT, related_name="invoices")
    service_history = models.OneToOneField(
        "historial.ServiceHistory",
        on_delete=models.PROTECT,
        related_name="invoice",
        null=True,
        blank=True,
    )
    number = models.CharField(max_length=40, verbose_name="Número de factura")
    issue_date = models.DateField(verbose_name="Fecha de expedición")
    invoice_type = models.CharField(
        max_length=4,
        default="F2",
        verbose_name="Tipo de factura",
    )
    description = models.CharField(max_length=300, verbose_name="Descripción de la operación")
    recipient_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
        verbose_name="Cliente (informativo)",
    )
    recipient_nif = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="NIF del cliente (informativo)",
    )
    base_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Base imponible (€)",
    )
    tax_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Cuota de IVA (€)",
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Importe total (€)",
    )
    status = models.CharField(
        max_length=10,
        choices=INVOICE_STATUS_CHOICES,
        default="ISSUED",
        verbose_name="Estado de la factura",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "factura"
        verbose_name_plural = "facturas"
        ordering = ("-issue_date", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=["emisor", "number"],
                name="invoicing_unique_number_per_emisor",
            ),
        ]

    def __str__(self):
        return self.number


class InvoiceLine(models.Model):
    """Concepto facturado. El desglose fiscal enviado a la AEAT sale de estas líneas."""

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=300, verbose_name="Concepto")
    base = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Base imponible (€)",
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("21.00"),
        verbose_name="IVA (%)",
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Cuota de IVA (€)",
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Importe total (€)",
    )

    class Meta:
        verbose_name = "línea de factura"
        verbose_name_plural = "líneas de factura"
        ordering = ("pk",)

    def __str__(self):
        return self.description


class VerifactuRecord(models.Model):
    """Registro de la factura ante la AEAT, enviado a través de VeriFactu."""

    invoice = models.OneToOneField(
        Invoice,
        on_delete=models.CASCADE,
        related_name="verifactu",
    )
    registro_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name="Identificador del registro",
    )
    estado = models.CharField(
        max_length=20,
        choices=REGISTRO_STATUS_CHOICES,
        default="PENDING",
        verbose_name="Estado en la AEAT",
    )
    codigo_error = models.CharField(max_length=100, blank=True, default="")
    descripcion_error = models.TextField(blank=True, default="")
    qr_image = models.TextField(blank=True, default="")
    url_qr = models.TextField(blank=True, default="")
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Enviado")
    last_checked_at = models.DateTimeField(null=True, blank=True, verbose_name="Última consulta")
    raw_response = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "registro VeriFactu"
        verbose_name_plural = "registros VeriFactu"
        ordering = ("-pk",)

    def __str__(self):
        return f"{self.invoice.number} · {self.get_estado_display()}"

    @property
    def qr_image_src(self):
        """La API devuelve el QR como mapa de bits en base64, o ya como URL."""
        if not self.qr_image:
            return self.url_qr or ""
        if self.qr_image.startswith(("http://", "https://", "data:")):
            return self.qr_image
        # La API oficial devuelve .bmp; el simulador local genera .png.
        mime = "image/png" if self.qr_image.startswith("iVBORw0KGgo") else "image/bmp"
        return f"data:{mime};base64,{self.qr_image}"


class VerifactuSession(models.Model):
    """Sesión emitida por VeriFactu al autenticarse: se reutiliza mientras siga vigente."""

    emisor = models.OneToOneField(
        Emisor,
        on_delete=models.CASCADE,
        related_name="session",
    )
    session_id = models.TextField()
    expires_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "sesión de VeriFactu"
        verbose_name_plural = "sesiones de VeriFactu"

    def __str__(self):
        return f"Sesión de {self.emisor.nif}"

    def is_valid(self, margin_seconds=0):
        return bool(self.session_id) and self.expires_at - timedelta(
            seconds=margin_seconds
        ) > timezone.now()
