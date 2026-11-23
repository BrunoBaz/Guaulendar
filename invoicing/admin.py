from django import forms
from django.contrib import admin

from .models import (
    Emisor,
    EmisorMember,
    Invoice,
    InvoiceLine,
    VerifactuConfig,
    VerifactuRecord,
    VerifactuSession,
)


class VerifactuConfigForm(forms.ModelForm):
    """Pide la contraseña sin volver a mostrarla; en blanco, se mantiene la actual."""

    password = forms.CharField(
        label="Contraseña en VeriFactu",
        required=False,
        strip=False,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={"autocomplete": "new-password"},
        ),
        help_text="Se guarda cifrada. Déjala en blanco para no cambiarla.",
    )

    class Meta:
        model = VerifactuConfig
        fields = ("email", "password")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._password_guardada = self.instance.password

    def save(self, commit=True):
        config = super().save(commit=False)
        config.password = self.cleaned_data.get("password") or self._password_guardada
        if commit:
            config.save()
        return config


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


class VerifactuConfigInline(admin.StackedInline):
    model = VerifactuConfig
    form = VerifactuConfigForm
    extra = 0
    fields = ("email", "password", "is_connected", "last_login_at", "last_error")
    readonly_fields = ("last_login_at", "last_error")


class EmisorMemberInline(admin.TabularInline):
    model = EmisorMember
    extra = 0
    fields = ("user", "role")


@admin.register(Emisor)
class EmisorAdmin(admin.ModelAdmin):
    list_display = ("name", "trade_name", "nif", "taxpayer_type", "series_prefix", "is_active")
    list_filter = ("is_active", "taxpayer_type")
    search_fields = ("name", "trade_name", "nif")
    readonly_fields = ("created_at",)
    inlines = [VerifactuConfigInline, EmisorMemberInline]


@admin.register(EmisorMember)
class EmisorMemberAdmin(admin.ModelAdmin):
    list_display = ("user", "emisor", "role", "created_at")
    list_filter = ("role", "emisor")
    search_fields = ("user__username", "emisor__name", "emisor__nif")
    readonly_fields = ("created_at",)


@admin.register(VerifactuConfig)
class VerifactuConfigAdmin(admin.ModelAdmin):
    form = VerifactuConfigForm
    list_display = ("emisor", "email", "is_connected", "last_login_at")
    search_fields = ("emisor__name", "emisor__nif", "email")
    readonly_fields = ("last_login_at", "last_error", "updated_at")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "issue_date", "recipient_name", "total", "status", "registro_estado")
    list_filter = ("status", "emisor", "issue_date")
    search_fields = ("number", "recipient_name", "recipient_nif")
    readonly_fields = ("created_at",)
    inlines = [InvoiceLineInline]

    @admin.display(description="Estado en la AEAT")
    def registro_estado(self, obj):
        record = getattr(obj, "verifactu", None)
        return record.get_estado_display() if record else "Sin enviar"


@admin.register(VerifactuRecord)
class VerifactuRecordAdmin(admin.ModelAdmin):
    list_display = ("invoice", "registro_id", "estado", "sent_at", "last_checked_at")
    list_filter = ("estado",)
    search_fields = ("invoice__number", "=registro_id")
    readonly_fields = (
        "invoice",
        "registro_id",
        "estado",
        "codigo_error",
        "descripcion_error",
        "qr_image",
        "url_qr",
        "sent_at",
        "last_checked_at",
        "raw_response",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(VerifactuSession)
class VerifactuSessionAdmin(admin.ModelAdmin):
    list_display = ("emisor", "expires_at", "updated_at")
    readonly_fields = ("emisor", "expires_at", "updated_at")
    exclude = ("session_id",)

    def has_add_permission(self, request):
        return False
