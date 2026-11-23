"""Alta de facturas en Guaulendar y envío a la AEAT a través de VeriFactu."""

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from clients.models import Contacts

from ..models import (
    Invoice,
    InvoiceLine,
    InvoiceSequence,
    VerifactuRecord,
    aeat_status_code,
)
from .verifactu import VerifactuError


class InvoicingError(RuntimeError):
    """No se pudo completar la facturación."""


def get_client(emisor):
    """Punto único de creación del cliente (las pruebas lo sustituyen por uno simulado)."""
    from .verifactu import VerifactuClient

    if settings.DEBUG and settings.VERIFACTU_FAKE_API:
        from .fake_api import fake_transport

        return VerifactuClient(emisor, transport=fake_transport())
    return VerifactuClient(emisor)


def invoice_for_service(service, emisor):
    """Devuelve la factura del servicio y la crea la primera vez, para no duplicarla en reintentos."""
    existing = Invoice.objects.filter(service_history=service).first()
    if existing is not None:
        return existing
    if service.status != "COMPLETED":
        raise InvoicingError("Solo se pueden facturar servicios completados.")

    # Factura simplificada: la AEAT no exige identificar al cliente, así que el NIF
    # es opcional. El responsable del perro se anota solo como referencia interna.
    owner = (
        Contacts.objects.filter(dogs=service.dog, emisor=emisor)
        .order_by("name", "pk")
        .first()
    )
    issue_date = timezone.localdate()
    description = (
        f"{service.get_service_type_display()} · "
        f"{service.dog_snapshot.get('name') or service.dog.name} "
        f"({service.date:%d/%m/%Y})"
    )

    with transaction.atomic():
        number = f"{emisor.series_prefix}/{issue_date.year}/{InvoiceSequence.reserve_next(emisor, issue_date.year):04d}"
        invoice = Invoice.objects.create(
            emisor=emisor,
            service_history=service,
            number=number,
            issue_date=issue_date,
            description=description,
            recipient_name=owner.name if owner else "",
            recipient_nif=owner.nif if owner else "",
            base_total=service.taxable_base,
            tax_total=service.tax_amount,
            total=service.total_price,
        )
        InvoiceLine.objects.create(
            invoice=invoice,
            description=description,
            base=service.taxable_base,
            tax_rate=service.tax_rate,
            tax_amount=service.tax_amount,
            total=service.total_price,
        )
    return invoice


def build_payload(invoice):
    """Traduce la factura guardada al objeto Invoice que espera VeriFactu."""
    return {
        "Status": "POST",
        "InvoiceType": invoice.invoice_type,
        "InvoiceID": invoice.number,
        "InvoiceDate": invoice.issue_date.isoformat(),
        "SellerID": invoice.emisor.nif,
        "CompanyName": invoice.emisor.name,
        "Text": invoice.description,
        # Factura simplificada (F2): no se identifica al destinatario.
        "TaxItems": [
            {
                "Tax": "01",
                "TaxScheme": "01",
                "TaxType": "S1",
                "TaxRate": float(line.tax_rate),
                "TaxBase": float(line.base),
                "TaxAmount": float(line.tax_amount),
            }
            for line in invoice.lines.all()
        ],
    }


def send_invoice(invoice, client=None):
    """Envía la factura a la AEAT. Si falla, la factura se conserva para reintentar."""
    record, _ = VerifactuRecord.objects.get_or_create(invoice=invoice)
    try:
        item = (client or get_client(invoice.emisor)).registrar_factura(build_payload(invoice))
    except VerifactuError as error:
        record.estado = "PENDING"
        record.descripcion_error = str(error)
        record.save(update_fields=["estado", "descripcion_error"])
        raise InvoicingError(str(error)) from error

    _store_api_item(record, item)
    return record


def refresh_invoice(invoice, client=None):
    """Consulta el estado del registro en la AEAT (polling manual)."""
    record = getattr(invoice, "verifactu", None)
    if record is None or not record.sent_at:
        raise InvoicingError("La factura todavía no se ha enviado a la AEAT.")
    try:
        item = (client or get_client(invoice.emisor)).consultar_estado(invoice)
    except VerifactuError as error:
        raise InvoicingError(str(error)) from error

    if not item:
        raise InvoicingError("La AEAT no tiene ningún envío con ese número de factura.")
    _store_api_item(record, item)
    return record


def _store_api_item(record, item):
    """Vuelca la respuesta de VeriFactu en el registro fiscal."""
    extern_key = item.get("ExternKey")
    if extern_key:
        record.registro_id = str(extern_key)
    record.estado = "INCORRECTO" if item.get("ErrorCode") else aeat_status_code(item.get("StatusResponse"))
    record.codigo_error = str(item.get("ErrorCode") or "")
    record.descripcion_error = str(item.get("ErrorDescription") or "")
    for source_field in ("QrCode", "QrCodeUrl"):
        key = "qr_image" if source_field == "QrCode" else "url_qr"
        if item.get(source_field):
            setattr(record, key, str(item[source_field]))
    record.sent_at = record.sent_at or timezone.now()
    record.last_checked_at = timezone.now()
    record.raw_response = item
    record.save()
