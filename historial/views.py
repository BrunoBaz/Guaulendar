from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from invoicing.models import emisor_for_user

from .models import ServiceHistory


@login_required
def service_history(request):
	emisor = emisor_for_user(request.user)
	if emisor is None:
		raise Http404("La cuenta no tiene ningún negocio asignado.")
	date_from_value = request.GET.get("date_from", "")
	date_to_value = request.GET.get("date_to", "")
	date_from = parse_date(date_from_value) if date_from_value else None
	date_to = parse_date(date_to_value) if date_to_value else None
	date_filter_error = (
		"Introduce fechas válidas para filtrar el histórico."
		if (date_from_value and date_from is None) or (date_to_value and date_to is None)
		else ""
	)
	queryset = ServiceHistory.objects.filter(emisor=emisor).select_related("dog")
	if date_from:
		queryset = queryset.filter(date__date__gte=date_from)
	if date_to:
		queryset = queryset.filter(date__date__lte=date_to)
	service_history = list(queryset.order_by("-date", "-pk"))
	return render(request, "historial/service_history.html", {
		"service_history": service_history,
		"service_count": len(service_history),
		"date_from": date_from_value,
		"date_to": date_to_value,
		"date_filter_error": date_filter_error,
		"total_collected": sum(
			(service.total_price for service in service_history),
			Decimal("0.00"),
		),
	})


@login_required
def service_history_detail(request, public_id):
	emisor = emisor_for_user(request.user)
	if emisor is None:
		raise Http404("La cuenta no tiene ningún negocio asignado.")
	service = get_object_or_404(
		ServiceHistory.objects.filter(emisor=emisor).select_related("dog").prefetch_related(
			"dog__owners",
		),
		public_id=public_id,
	)
	if request.method == "POST" and request.POST.get("history_action") == "update_notes":
		service.notes = request.POST.get("notes", "").strip()
		service.save(update_fields=["notes"])
		return redirect("service_history_detail", public_id=service.public_id)
	return render(
		request,
		"historial/service_history_detail.html",
		{"service": service},
	)
