import json
from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clients.models import Contacts
from dogs.models import Dog
from historial.models import ServiceHistory
from .models import Appointment, AppointmentAuditEvent


class AppointmentServiceHistoryTests(TestCase):
	def test_create_appointment_post_saves_fields_and_redirects(self):
		dog = Dog.objects.create(name="Luna")
		start = timezone.localtime(timezone.now() + timedelta(days=1)).replace(
			second=0,
			microsecond=0,
		)

		response = self.client.post(
			reverse("appointments"),
			{
				"dog": dog.pk,
				"service_type": "BAÑO",
				"date": start.strftime("%Y-%m-%dT%H:%M"),
				"price": "45.50",
				"notes": "Corte y baño",
			},
		)

		self.assertRedirects(response, reverse("appointments"))
		appointment = Appointment.objects.get(dog=dog)
		self.assertEqual(appointment.service_type, "BAÑO")
		self.assertEqual(appointment.date, start)
		self.assertEqual(appointment.price, Decimal("45.50"))
		self.assertEqual(appointment.notes, "Corte y baño")
		self.assertEqual(appointment.status, "PENDING")
		event = AppointmentAuditEvent.objects.get(appointment_id=appointment.pk)
		self.assertEqual(event.action, "CREATED")
		self.assertEqual(event.changes["snapshot"]["status"], "PENDING")

	def test_invalid_appointment_post_reopens_form_with_errors(self):
		response = self.client.post(
			reverse("appointments"),
			{
				"dog": "9999",
				"service_type": "INVALID",
				"date": "",
				"price": "-1",
				"notes": "",
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.context["appointment_form"].errors)
		self.assertContains(response, 'data-open-on-load="true"')
		self.assertEqual(Appointment.objects.count(), 0)

	def test_update_appointment_post_saves_editable_fields(self):
		dog = Dog.objects.create(name="Luna")
		appointment = Appointment.objects.create(
			dog=dog,
			date=timezone.now(),
			status="PENDING",
		)
		updated_date = timezone.localtime(timezone.now() + timedelta(days=2)).replace(
			second=0,
			microsecond=0,
		)

		response = self.client.post(
			reverse("appointments"),
			{
				"appointment_id": appointment.pk,
				"original_status": "PENDING",
				"dog": dog.pk,
				"service_type": "COMPLETO",
				"date": updated_date.strftime("%Y-%m-%dT%H:%M"),
				"price": "80.00",
				"notes": "Cambio de horario",
				"status": "CONFIRMED",
				"discounts_json": "[]",
			},
		)

		self.assertRedirects(response, reverse("appointments"))
		appointment.refresh_from_db()
		self.assertEqual(appointment.service_type, "COMPLETO")
		self.assertEqual(appointment.date, updated_date)
		self.assertEqual(appointment.price, Decimal("80.00"))
		self.assertEqual(appointment.notes, "Cambio de horario")
		self.assertEqual(appointment.status, "CONFIRMED")
		self.assertEqual(ServiceHistory.objects.count(), 0)
		event = AppointmentAuditEvent.objects.filter(
			appointment_id=appointment.pk,
		).latest("changed_at")
		self.assertEqual(event.action, "UPDATED")
		self.assertEqual(event.changes["status"]["after"], "CONFIRMED")

	def test_completing_appointment_stores_sequential_discounts_and_final_price(self):
		dog = Dog.objects.create(name="Luna")
		owner = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")
		owner.dogs.add(dog)
		appointment = Appointment.objects.create(
			dog=dog,
			date=timezone.now(),
			price=Decimal("121.00"),
		)

		response = self.client.post(
			reverse("appointments"),
			{
				"appointment_id": appointment.pk,
				"original_status": "PENDING",
				"dog": dog.pk,
				"service_type": "BAÑO",
				"date": timezone.localtime(appointment.date).strftime("%Y-%m-%dT%H:%M"),
				"price": "121.00",
				"notes": "",
				"status": "COMPLETED",
				"payment_method": "CARD",
				"discounts_json": json.dumps([
					{"type": "PERCENTAGE", "value": "10", "description": "Descuento de fidelidad"},
					{"type": "FIXED", "value": "5", "description": "Promoción de temporada"},
				]),
			},
		)

		self.assertRedirects(response, reverse("appointments"))
		self.assertFalse(Appointment.objects.filter(pk=appointment.pk).exists())
		history = ServiceHistory.objects.get(dog=dog)
		self.assertEqual(history.dog_snapshot["name"], "Luna")
		self.assertEqual(history.dog_snapshot["owners"], [
			{"pk": owner.pk, "name": "Ana Ruiz", "phone": "555-0101"},
		])
		audit_event = AppointmentAuditEvent.objects.get(
			appointment_id=appointment.pk,
			action="COMPLETED",
		)
		self.assertEqual(
			audit_event.changes["history_id"]["after"],
			history.pk,
		)
		self.assertEqual(history.taxable_base, Decimal("100.00"))
		self.assertEqual(history.discounts, [
			{
				"type": "PERCENTAGE",
				"value": "10.00",
				"amount": "10.00",
				"description": "Descuento de fidelidad",
			},
			{
				"type": "FIXED",
				"value": "5.00",
				"amount": "5.00",
				"description": "Promoción de temporada",
			},
		])
		self.assertEqual(history.discount_amount, Decimal("15.00"))
		self.assertEqual(history.tax_amount, Decimal("21.00"))
		self.assertEqual(history.total_price, Decimal("106.00"))
		self.assertEqual(history.payment_method, "CARD")
		history_response = self.client.get(reverse("service_history"))
		self.assertContains(history_response, "Descuento 10,00%")
		self.assertContains(history_response, "Descuento de fidelidad")
		self.assertContains(history_response, "Descuento 5,00 €")
		self.assertContains(history_response, "Promoción de temporada")
		self.assertContains(history_response, "106,00 €")
		self.assertContains(history_response, "Tarjeta")

		dog.name = "Luna nueva"
		dog.save()
		owner.name = "Ana nueva"
		owner.save()
		detail_response = self.client.get(
			reverse("service_history_detail", args=[history.pk])
		)
		self.assertContains(detail_response, "Luna")
		self.assertContains(detail_response, "Ana Ruiz")
		self.assertContains(detail_response, "Tarjeta")
		self.assertNotContains(detail_response, "Ana nueva")

	def test_completed_appointment_rejects_discounts_over_remaining_taxable_base(self):
		dog = Dog.objects.create(name="Luna")
		appointment = Appointment.objects.create(
			dog=dog,
			date=timezone.now(),
			price=Decimal("121.00"),
		)

		response = self.client.post(
			reverse("appointments"),
			{
				"appointment_id": appointment.pk,
				"original_status": "PENDING",
				"dog": dog.pk,
				"service_type": "BAÑO",
				"date": timezone.localtime(appointment.date).strftime("%Y-%m-%dT%H:%M"),
				"price": "121.00",
				"notes": "",
				"status": "COMPLETED",
				"payment_method": "CASH",
				"discounts_json": json.dumps([
					{"type": "FIXED", "value": "90"},
					{"type": "FIXED", "value": "20"},
				]),
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Los descuentos no pueden superar la base imponible restante.")
		self.assertTrue(Appointment.objects.filter(pk=appointment.pk, status="PENDING").exists())
		self.assertEqual(ServiceHistory.objects.count(), 0)

	def test_completing_appointment_requires_payment_method(self):
		dog = Dog.objects.create(name="Luna")
		appointment = Appointment.objects.create(
			dog=dog,
			date=timezone.now(),
			price=Decimal("121.00"),
		)

		response = self.client.post(
			reverse("appointments"),
			{
				"appointment_id": appointment.pk,
				"original_status": "PENDING",
				"dog": dog.pk,
				"service_type": "BAÑO",
				"date": timezone.localtime(appointment.date).strftime("%Y-%m-%dT%H:%M"),
				"price": "121.00",
				"notes": "",
				"status": "COMPLETED",
				"discounts_json": "[]",
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Selecciona si el pago fue en efectivo o con tarjeta.")
		self.assertTrue(Appointment.objects.filter(pk=appointment.pk, status="PENDING").exists())
		self.assertEqual(ServiceHistory.objects.count(), 0)

	def test_quick_status_actions_confirm_or_cancel_appointments(self):
		dog = Dog.objects.create(name="Luna")
		appointment = Appointment.objects.create(dog=dog, date=timezone.now())

		response = self.client.post(
			reverse("appointments"),
			{"appointment_id": appointment.pk, "quick_status": "CONFIRMED"},
		)

		self.assertRedirects(response, reverse("appointments"))
		appointment.refresh_from_db()
		self.assertEqual(appointment.status, "CONFIRMED")

		response = self.client.post(
			reverse("appointments"),
			{"appointment_id": appointment.pk, "quick_status": "CANCELLED"},
		)

		self.assertRedirects(response, reverse("appointments"))
		self.assertFalse(Appointment.objects.filter(pk=appointment.pk).exists())
		self.assertEqual(ServiceHistory.objects.get(dog=dog).status, "CANCELLED")

	def test_appointment_page_renders_creation_dialog_and_active_dog_choices(self):
		dog = Dog.objects.create(name="Luna")
		owner = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")
		owner.dogs.add(dog)

		response = self.client.get(reverse("appointments"))

		self.assertContains(response, 'id="appointment-create-dialog"')
		self.assertContains(response, 'data-timezone=')
		self.assertContains(response, 'type="datetime-local"')
		self.assertContains(response, "appointment-dog-select")
		self.assertContains(response, f'<option value="{dog.pk}">Luna · Ana Ruiz</option>')
		self.assertContains(response, 'id="appointments-filter" type="search"')
		self.assertContains(response, 'id="appointments-filter-options"')
		self.assertIsNone(response.context["appointment_form"].fields["dog"].empty_label)
		self.assertEqual(
			response.context["appointment_form"].fields["service_type"].choices,
			Appointment.SERVICES_CHOICES,
		)

	def test_appointment_page_opens_creation_dialog_with_selected_dog(self):
		dog = Dog.objects.create(name="Luna")

		response = self.client.get(
			reverse("appointments"),
			{"dog_id": dog.pk},
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["appointment_form"]["dog"].value(), dog.pk)
		self.assertContains(response, 'data-open-on-load="true"')
		self.assertContains(
			response,
			f'<option value="{dog.pk}" selected>Luna · Sin responsable</option>',
		)

	def test_inactive_dog_cannot_be_preselected_for_a_new_appointment(self):
		dog = Dog.objects.create(name="Luna", is_active=False)

		response = self.client.get(
			reverse("appointments"),
			{"dog_id": dog.pk},
		)

		self.assertEqual(response.status_code, 404)

	def test_appointment_model_rejects_inactive_dogs(self):
		dog = Dog.objects.create(name="Luna", is_active=False)
		appointment = Appointment(
			dog=dog,
			date=timezone.now(),
		)

		with self.assertRaises(ValidationError):
			appointment.save()

	def test_calendar_hides_legacy_appointments_for_inactive_dogs(self):
		dog = Dog.objects.create(name="Luna", is_active=False)
		Appointment.objects.bulk_create([
			Appointment(dog=dog, date=timezone.now()),
		])

		response = self.client.get(reverse("appointments"))

		self.assertEqual(response.context["calendar_events"], [])
		self.assertEqual(response.context["appointment_count"], 0)
		self.assertNotContains(response, "Luna")

	def test_dog_choice_marks_discardable_owner(self):
		dog = Dog.objects.create(name="Luna")
		owner = Contacts.objects.create(
			name="Ana Ruiz",
			phone="555-0101",
			descartable=True,
		)
		owner.dogs.add(dog)

		response = self.client.get(reverse("appointments"))

		self.assertContains(
			response,
			f'<option value="{dog.pk}">Luna · Ana Ruiz (no priorizar)</option>',
		)

	def test_calendar_includes_time_task_owner_and_status(self):
		dog = Dog.objects.create(name="Luna")
		contact = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")
		contact.dogs.add(dog)
		appointment = Appointment.objects.create(
			dog=dog,
			date=timezone.now(),
			service_type="BAÑO",
			status="CONFIRMED",
		)

		response = self.client.get(reverse("appointments"))

		self.assertEqual(response.status_code, 200)
		event = response.context["calendar_events"][0]
		self.assertEqual(event["title"], "Baño · Luna")
		self.assertEqual(
			event["classNames"],
			["status-confirmed", "service-bano"],
		)
		self.assertEqual(event["extendedProps"]["dogLabel"], "Luna · Ana Ruiz")
		self.assertEqual(event["extendedProps"]["owners"], [
			{"name": "Ana Ruiz", "phone": "555-0101", "descartable": False},
		])
		self.assertEqual(event["start"], timezone.localtime(appointment.date).isoformat())
		self.assertEqual(
			event["end"],
			(timezone.localtime(appointment.date) + timedelta(minutes=90)).isoformat(),
		)

	def test_calendar_owner_data_includes_discardable_status(self):
		dog = Dog.objects.create(name="Luna")
		contact = Contacts.objects.create(
			name="Ana Ruiz",
			phone="555-0101",
			descartable=True,
		)
		contact.dogs.add(dog)
		Appointment.objects.create(
			dog=dog,
			date=timezone.now(),
			service_type="BAÑO",
			status="CONFIRMED",
		)

		response = self.client.get(reverse("appointments"))

		self.assertTrue(response.context["calendar_events"][0]["extendedProps"]["owners"][0]["descartable"])

	def test_terminal_appointments_are_archived_and_deleted(self):
		for status in ("COMPLETED", "CANCELLED"):
			with self.subTest(status=status):
				dog = Dog.objects.create(name=f"Luna {status}")
				appointment_date = timezone.now()
				appointment = Appointment.objects.create(
					dog=dog,
					date=appointment_date,
					service_type="COMPLETO",
					price=Decimal("100.00"),
					discount_type="PERCENTAGE",
					discount_value=Decimal("10.00"),
					tax_rate=Decimal("21.00"),
					notes="Corte de uñas",
				)
				appointment_id = appointment.pk
				appointment.status = status
				appointment.save()

				self.assertFalse(Appointment.objects.filter(pk=appointment_id).exists())
				history = ServiceHistory.objects.get(dog=dog, date=appointment_date)
				self.assertEqual(history.service_type, "COMPLETO")
				self.assertEqual(history.status, status)
				self.assertEqual(history.notes, "Corte de uñas")
				self.assertEqual(history.price, Decimal("100.00"))
				self.assertEqual(history.taxable_base, Decimal("82.64"))
				if status == "COMPLETED":
					self.assertEqual(history.discount_amount, Decimal("8.26"))
					self.assertEqual(history.tax_amount, Decimal("17.36"))
					self.assertEqual(history.total_price, Decimal("91.74"))
				else:
					self.assertEqual(history.discount_amount, Decimal("0.00"))
					self.assertEqual(history.tax_amount, Decimal("0.00"))
					self.assertEqual(history.total_price, Decimal("0.00"))

		self.assertEqual(ServiceHistory.objects.count(), 2)

	def test_fixed_discount_is_applied_before_tax(self):
		dog = Dog.objects.create(name="Nala")
		appointment = Appointment.objects.create(
			dog=dog,
			date=timezone.now(),
			price=Decimal("50.00"),
			discount_type="FIXED",
			discount_value=Decimal("5.00"),
		)
		appointment.status = "COMPLETED"
		appointment.save()

		history = ServiceHistory.objects.get(dog=dog)
		self.assertEqual(history.taxable_base, Decimal("41.32"))
		self.assertEqual(history.discount_amount, Decimal("5.00"))
		self.assertEqual(history.tax_amount, Decimal("8.68"))
		self.assertEqual(history.total_price, Decimal("45.00"))

	def test_admin_can_save_terminal_appointment(self):
		user = get_user_model().objects.create_superuser(
			username="admin",
			email="admin@example.com",
			password="test-password",
		)
		self.client.force_login(user)
		dog = Dog.objects.create(name="Toby")
		appointment = Appointment.objects.create(dog=dog, date=timezone.now())

		response = self.client.post(
			reverse("admin:appointments_appointment_change", args=[appointment.pk]),
			{
				"dog": dog.pk,
				"service_type": "COMPLETO",
				"price": "75.00",
				"discount_type": "FIXED",
				"discount_value": "5.00",
				"tax_rate": "21.00",
				"date_0": "2026-11-09",
				"date_1": "12:00:00",
				"notes": "Baño y corte",
				"status": "COMPLETED",
				"_save": "Save",
			},
		)

		self.assertEqual(response.status_code, 302)
		self.assertFalse(Appointment.objects.filter(pk=appointment.pk).exists())
		history = ServiceHistory.objects.get(dog=dog)
		self.assertEqual(history.status, "COMPLETED")
		self.assertEqual(history.service_type, "COMPLETO")
		self.assertEqual(history.price, Decimal("75.00"))
		self.assertEqual(history.taxable_base, Decimal("61.98"))
		self.assertEqual(history.discount_amount, Decimal("5.00"))
		self.assertEqual(history.tax_amount, Decimal("13.02"))
		self.assertEqual(history.total_price, Decimal("70.00"))
		audit_event = AppointmentAuditEvent.objects.get(
			appointment_id=appointment.pk,
			action="COMPLETED",
		)
		self.assertEqual(audit_event.actor, user)
