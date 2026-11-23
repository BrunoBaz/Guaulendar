from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from historial.models import ServiceHistory

from .models import emisor_for_user
from .services.invoices import (
    InvoicingError,
    invoice_for_service,
    refresh_invoice,
    send_invoice,
)


@login_required
@require_POST
def invoice_service(request, public_id):
    """Factura el servicio del histórico o consulta el estado de su registro en la AEAT."""
    emisor = emisor_for_user(request.user)
    if emisor is None:
        raise Http404("La cuenta no tiene ningún negocio asignado.")
    service = get_object_or_404(
        ServiceHistory.objects.select_related("dog"),
        public_id=public_id,
        emisor=emisor,
    )
    detail = redirect("service_history_detail", public_id=service.public_id)

    if request.POST.get("invoice_action") == "refresh":
        invoice = getattr(service, "invoice", None)
        if invoice is None:
            messages.error(request, "Este servicio todavía no tiene factura.")
            return detail
        try:
            record = refresh_invoice(invoice)
        except InvoicingError as error:
            messages.error(request, f"No se pudo consultar el estado: {error}")
        else:
            messages.success(request, f"Estado en la AEAT: {record.get_estado_display()}.")
        return detail

    try:
        invoice = invoice_for_service(service, emisor)
        send_invoice(invoice)
    except InvoicingError as error:
        messages.error(request, f"No se pudo facturar: {error}")
    else:
        messages.success(request, f"Factura {invoice.number} enviada a la AEAT.")
    return detail
