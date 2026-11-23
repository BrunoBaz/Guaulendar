import uuid
from decimal import Decimal
from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clients.models import Contacts
from dogs.models import Dog
from invoicing.models import Emisor, EmisorMember
from .models import ServiceHistory


class ServiceHistoryPageTests(TestCase):
	def setUp(self):
		self.emisor = Emisor.objects.create(name="Peluquería Guau", nif="B12345678")
		user = get_user_model().objects.create_user(username="tester", password="clave")
		EmisorMember.objects.create(emisor=self.emisor, user=user)
		self.client.force_login(user)

	def test_history_cards_show_full_price_breakdown(self):
		dog = Dog.objects.create(name="Luna", emisor=self.emisor)
		ServiceHistory.objects.create(
			emisor=self.emisor,
			dog=dog,
			date=timezone.now(),
			price=Decimal("100.00"),
			taxable_base=Decimal("82.64"),
			service_type="BAÑO",
			status="COMPLETED",
			discount_type="PERCENTAGE",
			discount_value=Decimal("10.00"),
			discount_amount=Decimal("8.26"),
			tax_rate=Decimal("21.00"),
			tax_amount=Decimal("17.36"),
			total_price=Decimal("91.74"),
		)

		response = self.client.get(reverse("service_history"))

		self.assertContains(response, 'class="history-card"')
		self.assertContains(response, "Luna")
		self.assertContains(response, "100,00 €")
		self.assertContains(response, "82,64 €")
		self.assertContains(response, "8,26 €")
		self.assertContains(response, "17,36 €")
		self.assertContains(response, "91,74 €")
		self.assertEqual(response.context["total_collected"], Decimal("91.74"))

	def test_history_can_be_filtered_with_inclusive_date_range(self):
		dog = Dog.objects.create(name="Luna", emisor=self.emisor)
		in_range = ServiceHistory.objects.create(
			emisor=self.emisor,
			dog=dog,
			date=timezone.make_aware(datetime(2026, 11, 10, 12, 0)),
			price=Decimal("25.00"),
			total_price=Decimal("25.00"),
		)
		ServiceHistory.objects.create(
			emisor=self.emisor,
			dog=dog,
			date=timezone.make_aware(datetime(2026, 11, 9, 23, 59)),
			price=Decimal("10.00"),
			total_price=Decimal("10.00"),
		)
		ServiceHistory.objects.create(
			emisor=self.emisor,
			dog=dog,
			date=timezone.make_aware(datetime(2026, 11, 11, 0, 0)),
			price=Decimal("40.00"),
			total_price=Decimal("40.00"),
		)

		response = self.client.get(
			reverse("service_history"),
			{"date_from": "2026-11-10", "date_to": "2026-11-10"},
		)

		self.assertEqual(list(response.context["service_history"]), [in_range])
		self.assertEqual(response.context["total_collected"], Decimal("25.00"))
		self.assertContains(response, 'value="2026-11-10"')

	def test_invalid_history_date_filter_is_reported(self):
		response = self.client.get(
			reverse("service_history"),
			{"date_from": "not-a-date"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Introduce fechas válidas")
		self.assertTrue(response.context["date_filter_error"])

	def test_history_record_links_to_its_detail(self):
		dog = Dog.objects.create(name="Luna", emisor=self.emisor)
		service = ServiceHistory.objects.create(
			emisor=self.emisor,
			dog=dog,
			date=timezone.now(),
			service_type="BAÑO",
		)

		response = self.client.get(reverse("service_history"))

		self.assertContains(
			response,
			f'href="{reverse("service_history_detail", args=[service.public_id])}">Luna</a>',
		)

	def test_history_detail_shows_its_pricing_and_related_records(self):
		dog = Dog.objects.create(name="Luna", emisor=self.emisor)
		owner = Contacts.objects.create(name="Ana Ruiz", phone="555-0101", emisor=self.emisor)
		owner.dogs.add(dog)
		service = ServiceHistory.objects.create(
			emisor=self.emisor,
			dog=dog,
			date=timezone.now(),
			price=Decimal("100.00"),
			taxable_base=Decimal("82.64"),
			service_type="BAÑO",
			status="COMPLETED",
			discount_type="PERCENTAGE",
			discount_value=Decimal("10.00"),
			discount_amount=Decimal("8.26"),
			tax_rate=Decimal("21.00"),
			tax_amount=Decimal("17.36"),
			total_price=Decimal("91.74"),
			notes="Corte de uñas incluido",
		)

		response = self.client.get(
			reverse("service_history_detail", args=[service.public_id])
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["service"], service)
		self.assertContains(response, "Luna")
		self.assertContains(response, "Ana Ruiz")
		self.assertContains(response, "100,00 €")
		self.assertContains(response, "82,64 €")
		self.assertContains(response, "91,74 €")
		self.assertContains(response, "Corte de uñas incluido")
		self.assertContains(
			response,
			f'href="{reverse("dog_detail", args=[dog.public_id])}"',
		)

	def test_history_detail_prefers_snapshotted_dog_and_owners(self):
		dog = Dog.objects.create(name="Luna actual", emisor=self.emisor)
		Contacts.objects.create(name="Ana actual", phone="555-0202", emisor=self.emisor).dogs.add(dog)
		service = ServiceHistory.objects.create(
			emisor=self.emisor,
			dog=dog,
			date=timezone.now(),
			dog_snapshot={
				"name": "Luna anterior",
				"breed": "Caniche",
				"sex": "Hembra",
				"owners": [
					{"pk": 42, "name": "Ana anterior", "phone": "555-0101"},
				],
			},
		)

		response = self.client.get(
			reverse("service_history_detail", args=[service.public_id])
		)

		self.assertContains(response, "Luna anterior")
		self.assertContains(response, "Caniche")
		self.assertContains(response, "Hembra")
		self.assertContains(response, "Ana anterior")
		self.assertNotContains(response, "Ana actual")

	def test_history_detail_returns_404_for_unknown_record(self):
		response = self.client.get(
			reverse("service_history_detail", args=[uuid.uuid4()])
		)

		self.assertEqual(response.status_code, 404)

	def test_history_detail_can_add_notes_afterwards(self):
		dog = Dog.objects.create(name="Luna", emisor=self.emisor)
		service = ServiceHistory.objects.create(
			emisor=self.emisor,
			dog=dog,
			date=timezone.now(),
			price=Decimal("100.00"),
			taxable_base=Decimal("82.64"),
			tax_amount=Decimal("17.36"),
			total_price=Decimal("100.00"),
		)
		url = reverse("service_history_detail", args=[service.public_id])

		response = self.client.post(
			url,
			{"history_action": "update_notes", "notes": "  Baño y corte de uñas  "},
		)

		self.assertRedirects(response, url)
		service.refresh_from_db()
		self.assertEqual(service.notes, "Baño y corte de uñas")
		self.assertEqual(service.total_price, Decimal("100.00"))
		self.assertEqual(service.taxable_base, Decimal("82.64"))

		detail = self.client.get(url)
		self.assertContains(detail, "Baño y corte de uñas")

	def test_history_detail_can_clear_notes(self):
		dog = Dog.objects.create(name="Luna", emisor=self.emisor)
		service = ServiceHistory.objects.create(
			emisor=self.emisor,
			dog=dog,
			date=timezone.now(),
			notes="Nota antigua",
		)
		url = reverse("service_history_detail", args=[service.public_id])

		response = self.client.post(
			url,
			{"history_action": "update_notes", "notes": ""},
		)

		self.assertRedirects(response, url)
		service.refresh_from_db()
		self.assertEqual(service.notes, "")

	def test_empty_history_has_an_empty_state(self):
		response = self.client.get(reverse("service_history"))

		self.assertContains(response, "Aún no hay servicios en el histórico")
