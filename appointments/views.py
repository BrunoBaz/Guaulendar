from datetime import timedelta

from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from clients.models import Contacts
from dogs.models import Dog
from .forms import AppointmentForm
from .models import Appointment

CALENDAR_APPOINTMENT_DURATION = timedelta(minutes=90)
SERVICE_CLASS_NAMES = {
	"BAÑO": "service-bano",
	"COMPLETO": "service-completo",
}


def appointments(request):
	appointment_id = request.POST.get("appointment_id") if request.method == "POST" else None
	quick_status = request.POST.get("quick_status") if request.method == "POST" else None
	if quick_status:
		if quick_status not in {"PENDING", "CONFIRMED", "CANCELLED"}:
			raise Http404("Estado de cita no válido.")
		appointment = get_object_or_404(Appointment, pk=appointment_id)
		appointment.status = quick_status
		if quick_status == "CANCELLED":
			appointment.discounts = []
		appointment.save(
			actor=request.user if request.user.is_authenticated else None,
		)
		return redirect("appointments")

	selected_dog = None
	if request.method == "GET" and request.GET.get("dog_id"):
		selected_dog = get_object_or_404(
			Dog,
			pk=request.GET["dog_id"],
			is_active=True,
		)
	instance = (
		get_object_or_404(Appointment, pk=appointment_id)
		if appointment_id
		else None
	)
	form = AppointmentForm(
		request.POST or None,
		instance=instance,
		initial={"dog": selected_dog.pk} if selected_dog else None,
	)
	if request.method == "POST" and form.is_valid():
		appointment = form.save(commit=False)
		if instance is None:
			appointment.status = "PENDING"
		appointment.save(
			actor=request.user if request.user.is_authenticated else None,
		)
		return redirect("appointments")

	appointments = (
		Appointment.objects.filter(dog__is_active=True)
		.select_related("dog")
		.prefetch_related(
			Prefetch(
				"dog__owners",
				queryset=Contacts.objects.filter(is_active=True),
			)
		)
		.order_by("date")
	)
	service_labels = dict(Appointment.SERVICES_CHOICES)
	status_labels = dict(Appointment.STATUS_CHOICES)
	calendar_events = []
	status_counts = {status: 0 for status, _ in Appointment.STATUS_CHOICES}

	for appointment in appointments:
		start = timezone.localtime(appointment.date)
		owners = [
			{
				"name": owner.name,
				"phone": owner.phone,
				"descartable": owner.descartable,
			}
			for owner in appointment.dog.owners.all()
		]
		owner_names = [owner["name"] for owner in owners]
		service = service_labels.get(appointment.service_type, appointment.service_type)
		calendar_events.append({
			"id": str(appointment.pk),
			"title": f"{service} · {appointment.dog.name}",
			"start": start.isoformat(),
			"end": (start + CALENDAR_APPOINTMENT_DURATION).isoformat(),
			"classNames": [
				f"status-{appointment.status.lower()}",
				SERVICE_CLASS_NAMES.get(appointment.service_type, "service-otro"),
			],
			"extendedProps": {
				"dogId": appointment.dog_id,
				"service": service,
				"serviceType": appointment.service_type,
				"dog": appointment.dog.name,
				"dogLabel": (
					f"{appointment.dog.name} · {', '.join(owner_names)}"
					if owner_names else f"{appointment.dog.name} · Sin responsable"
				),
				"owners": owners,
				"status": appointment.status,
				"statusLabel": status_labels.get(appointment.status, appointment.status),
				"paymentMethod": appointment.payment_method,
				"price": f"€{appointment.price:.2f}",
				"priceValue": str(appointment.price),
				"taxRate": str(appointment.tax_rate),
				"dateInput": start.strftime("%Y-%m-%dT%H:%M"),
				"discounts": appointment.discounts,
				"notes": appointment.notes,
			},
		})
		status_counts[appointment.status] = status_counts.get(appointment.status, 0) + 1

	return render(request, "appointments/appointments.html", {
		"calendar_events": calendar_events,
		"appointment_count": len(calendar_events),
		"status_counts": status_counts,
		"appointment_form": form,
		"appointment_id": instance.pk if instance else appointment_id or "",
		"original_status": (
			request.POST.get("original_status", instance.status if instance else "PENDING")
		),
		"tax_rate": str(instance.tax_rate if instance else "21.00"),
		"calendar_timezone": timezone.get_current_timezone_name(),
		"open_create_dialog": selected_dog is not None,
	})
