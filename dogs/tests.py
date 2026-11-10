from django.test import TestCase
from django.urls import reverse

from appointments.models import Appointment
from clients.models import Contacts
from dogs.models import Breed, Dog
from historial.models import ServiceHistory


class DogsListPageTests(TestCase):
	def test_dog_search_suggests_names_without_restricting_input(self):
		breed, _ = Breed.objects.get_or_create(name="Golden Retriever")
		dog = Dog.objects.create(name="Milo", breed=breed)
		contact = Contacts.objects.create(name="Lucía Pérez", phone="555-0104")
		contact.dogs.add(dog)

		response = self.client.get(reverse("dogs_list"))

		self.assertContains(response, 'type="search"')
		self.assertContains(response, 'list="dogs-filter-options"')
		self.assertContains(response, 'data-directory-filter="dogs-grid"')
		self.assertContains(response, '<option value="Milo">')
		self.assertContains(response, '<option value="Golden Retriever">')
		self.assertContains(response, '<option value="Lucía Pérez">')

	def test_dog_cards_show_details_and_owners(self):
		breed, _ = Breed.objects.get_or_create(name="Golden Retriever")
		dog = Dog.objects.create(
			name="Milo",
			breed=breed,
			sex="M",
			color="Dorado",
			coat_type="Largo",
		)
		contact = Contacts.objects.create(name="Lucía Pérez", phone="555-0104")
		contact.dogs.add(dog)

		response = self.client.get(reverse("dogs_list"))

		self.assertContains(response, 'class="dog-card"')
		self.assertContains(response, "Milo")
		self.assertContains(response, "Golden Retriever")
		self.assertContains(response, "Macho")
		self.assertContains(response, "Dorado")
		self.assertContains(response, "Largo")
		self.assertContains(response, "Lucía Pérez")
		self.assertContains(response, "555-0104")

	def test_dog_card_name_links_to_dog_detail(self):
		dog = Dog.objects.create(name="Milo")

		response = self.client.get(reverse("dogs_list"))

		self.assertContains(
			response,
			f'href="{reverse("dog_detail", args=[dog.pk])}">Milo</a>',
		)

	def test_dog_detail_shows_only_its_related_data(self):
		breed, _ = Breed.objects.get_or_create(name="Caniche")
		dog = Dog.objects.create(name="Nube", breed=breed, color="Blanco")
		other_dog = Dog.objects.create(name="Toby")
		owner = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")
		other_owner = Contacts.objects.create(name="Luis Pérez", phone="555-0102")
		owner.dogs.add(dog)
		other_owner.dogs.add(other_dog)
		appointment = Appointment.objects.create(
			dog=dog,
			date="2026-11-10T10:00:00Z",
			service_type="BAÑO",
		)
		Appointment.objects.create(
			dog=other_dog,
			date="2026-11-10T11:00:00Z",
			service_type="CORTE",
		)
		history = ServiceHistory.objects.create(
			dog=dog,
			date="2026-11-01T10:00:00Z",
			service_type="BAÑO",
		)
		ServiceHistory.objects.create(
			dog=other_dog,
			date="2026-10-01T10:00:00Z",
			service_type="CORTE",
		)

		response = self.client.get(reverse("dog_detail", args=[dog.pk]))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["dog"], dog)
		self.assertEqual(list(response.context["appointments"]), [appointment])
		self.assertEqual(list(response.context["service_history"]), [history])
		self.assertContains(response, "Caniche")
		self.assertContains(response, "Ana Ruiz")
		self.assertContains(response, 'id="dog-owners-filter"')
		self.assertContains(response, 'placeholder="Nombre o teléfono"')
		self.assertContains(response, 'id="dog-owners-grid"')
		self.assertContains(response, 'data-filter-item')
		self.assertContains(response, 'id="open-dog-appointment-dialog"')
		self.assertContains(response, 'id="dog-appointment-dialog"')
		self.assertContains(response, 'id="open-dog-edit-dialog"')
		self.assertContains(response, 'id="dog-edit-dialog"')
		self.assertContains(response, 'name="is_active"')
		self.assertContains(response, "Añadir cita")
		self.assertContains(response, "Citas")
		self.assertContains(response, "Histórico")
		self.assertLess(
			response.content.index(b'id="dog-appointments-title"'),
			response.content.index(b'id="open-dog-appointment-dialog"'),
		)
		self.assertNotContains(response, "Luis Pérez")
		self.assertNotContains(response, "Toby")

	def test_dog_detail_creates_appointment_without_leaving_the_dog_page(self):
		dog = Dog.objects.create(name="Nube")

		response = self.client.post(
			reverse("dog_detail", args=[dog.pk]),
			{
				"dog": dog.pk,
				"service_type": "BAÑO",
				"date": "2026-11-12T10:30",
				"price": "45.00",
				"notes": "Corte de uñas",
				"status": "PENDING",
				"discounts_json": "[]",
			},
		)

		self.assertRedirects(response, reverse("dog_detail", args=[dog.pk]))
		appointment = Appointment.objects.get(dog=dog)
		self.assertEqual(appointment.service_type, "BAÑO")
		self.assertEqual(appointment.price, 45)
		self.assertEqual(appointment.status, "PENDING")
		self.assertEqual(appointment.notes, "Corte de uñas")

	def test_dog_detail_does_not_create_appointment_for_another_dog(self):
		dog = Dog.objects.create(name="Nube")
		other_dog = Dog.objects.create(name="Toby")

		response = self.client.post(
			reverse("dog_detail", args=[dog.pk]),
			{
				"dog": other_dog.pk,
				"service_type": "BAÑO",
				"date": "2026-11-12T10:30",
				"price": "45.00",
				"notes": "",
				"status": "PENDING",
				"discounts_json": "[]",
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.context["appointment_form"].errors)
		self.assertContains(response, 'data-open-on-load="true"')
		self.assertEqual(Appointment.objects.count(), 0)

	def test_inactive_dog_detail_does_not_offer_new_appointment(self):
		dog = Dog.objects.create(name="Nube", is_active=False)

		response = self.client.get(reverse("dog_detail", args=[dog.pk]))

		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, "Añadir cita")

	def test_dog_detail_can_edit_dog_details_and_status(self):
		owner = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")
		dog = Dog.objects.create(name="Nube")
		owner.dogs.add(dog)

		response = self.client.post(
			reverse("dog_detail", args=[dog.pk]),
			{
				"dog_action": "edit",
				"name": "Nube nueva",
				"breed": "",
				"color": "Blanco",
				"sex": "F",
				"coat_type": "Corto",
				"dog_notes": "Nota actualizada",
				"dog_issues": "",
				"is_active": "",
			},
		)

		self.assertRedirects(response, reverse("dog_detail", args=[dog.pk]))
		dog.refresh_from_db()
		self.assertEqual(dog.name, "Nube nueva")
		self.assertEqual(dog.color, "Blanco")
		self.assertEqual(dog.sex, "F")
		self.assertEqual(dog.dog_notes, "Nota actualizada")
		self.assertFalse(dog.is_active)
		self.assertIn(owner, dog.owners.all())

	def test_dog_detail_cannot_reactivate_dog_without_active_owner(self):
		owner = Contacts.objects.create(
			name="Ana Ruiz",
			phone="555-0101",
			is_active=False,
		)
		dog = Dog.objects.create(name="Nube", is_active=False)
		owner.dogs.add(dog)

		response = self.client.post(
			reverse("dog_detail", args=[dog.pk]),
			{
				"dog_action": "edit",
				"name": "Nube",
				"breed": "",
				"color": "",
				"sex": "",
				"coat_type": "",
				"dog_notes": "",
				"dog_issues": "",
				"is_active": "on",
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.context["dog_form"].has_error("is_active"))
		dog.refresh_from_db()
		self.assertFalse(dog.is_active)

	def test_dog_owner_filter_includes_name_and_phone_for_search(self):
		dog = Dog.objects.create(name="Nube")
		owner = Contacts.objects.create(name="Ana Ruiz", phone="555-0199")
		owner.dogs.add(dog)

		response = self.client.get(reverse("dog_detail", args=[dog.pk]))

		self.assertContains(response, "Ana Ruiz")
		self.assertContains(response, "555-0199")
		self.assertContains(
			response,
			'<a class="contact-detail-phone" href="tel:555-0199">555-0199</a>',
		)
		self.assertContains(response, 'href="https://wa.me/345550199"')

	def test_dog_cards_mark_discardable_owners(self):
		dog = Dog.objects.create(name="Milo")
		contact = Contacts.objects.create(
			name="Lucía Pérez",
			phone="555-0104",
			descartable=True,
		)
		contact.dogs.add(dog)

		response = self.client.get(reverse("dogs_list"))

		self.assertContains(response, "Lucía Pérez")
		self.assertContains(response, "No priorizar")

	def test_empty_list_has_an_empty_state(self):
		response = self.client.get(reverse("dogs_list"))

		self.assertContains(response, "Aún no hay perros registrados")

	def test_registration_dialog_renders_dog_and_owner_fields(self):
		breed, _ = Breed.objects.get_or_create(name="Caniche")
		owner = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")

		response = self.client.get(reverse("dogs_list"))

		self.assertContains(response, 'id="open-dog-dialog"')
		self.assertContains(response, '<dialog class="contact-dialog" id="dog-dialog"')
		self.assertContains(response, 'data-breed-value="Caniche"')
		self.assertContains(
			response,
			f'<option value="{owner.pk}">Ana Ruiz - 555-0101</option>',
		)
		self.assertContains(response, 'id="dog-owners-filter"')
		self.assertContains(response, 'placeholder="Nombre o teléfono"')
		self.assertEqual(
			set(response.context["form"].fields),
			{
				"name",
				"breed",
				"color",
				"sex",
				"coat_type",
				"dog_notes",
				"dog_issues",
				"is_active",
				"owners",
				"new_owner_name",
				"new_owner_phone",
			},
		)
		self.assertContains(response, 'data-open-contact-dialog')
		self.assertContains(response, 'id="contact-dialog"')
		self.assertContains(response, 'id="contact-name"')
		self.assertContains(response, 'id="contact-phone"')
		self.assertContains(response, 'id="save-contact-dialog"')
		self.assertContains(response, 'id="dog-selected-owners"')
		self.assertEqual(response.content.count(b'id="id_name"'), 1)

	def test_dog_edit_cards_include_inactive_owner_ids_for_selection(self):
		dog = Dog.objects.create(name="Nube")
		owner = Contacts.objects.create(
			name="Ana Ruiz",
			phone="555-0101",
			is_active=False,
		)
		owner.dogs.add(dog)

		response = self.client.get(reverse("dogs_list"))

		self.assertContains(response, f'data-dog-owner-id="{owner.pk}"')

	def test_dog_registration_post_creates_dog_and_redirects(self):
		breed, _ = Breed.objects.get_or_create(name="Caniche")

		response = self.client.post(
			reverse("dogs_list"),
			{
				"name": "Nube",
				"breed": "Caniche",
				"color": "Blanco",
				"sex": "F",
				"coat_type": "Corto",
			},
		)

		self.assertRedirects(response, reverse("dogs_list"))
		dog = Dog.objects.get(name="Nube")
		self.assertEqual(dog.breed, breed)
		self.assertEqual(dog.color, "Blanco")
		self.assertEqual(dog.sex, "F")
		self.assertEqual(dog.coat_type, "Corto")
		self.assertFalse(dog.is_active)
		self.assertFalse(dog.owners.exists())

	def test_dog_registration_creates_unknown_breed(self):
		response = self.client.post(
			reverse("dogs_list"),
			{
				"name": "Nube",
				"breed": "Raza Inventada",
			},
		)

		self.assertRedirects(response, reverse("dogs_list"))
		dog = Dog.objects.get(name="Nube")
		self.assertEqual(dog.breed.name, "Raza Inventada")

	def test_dog_registration_reuses_existing_breed_ignoring_case(self):
		breed, _ = Breed.objects.get_or_create(name="Caniche")

		self.client.post(
			reverse("dogs_list"),
			{
				"name": "Nube",
				"breed": "caniche",
			},
		)

		self.assertEqual(Breed.objects.filter(name__iexact="caniche").count(), 1)
		self.assertEqual(Dog.objects.get(name="Nube").breed, breed)

	def test_dog_registration_post_associates_existing_owners(self):
		first_owner = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")
		second_owner = Contacts.objects.create(name="Luis Pérez", phone="555-0102")

		response = self.client.post(
			reverse("dogs_list"),
			{
				"name": "Nube",
				"owners": [str(first_owner.pk), str(second_owner.pk)],
			},
		)

		self.assertRedirects(response, reverse("dogs_list"))
		dog = Dog.objects.get(name="Nube")
		self.assertSetEqual(set(dog.owners.all()), {first_owner, second_owner})
		self.assertTrue(dog.is_active)

	def test_dog_list_can_filter_by_status(self):
		Dog.objects.create(name="Activo")
		Dog.objects.create(name="Inactivo", is_active=False)

		active_response = self.client.get(reverse("dogs_list"), {"status": "active"})
		inactive_response = self.client.get(reverse("dogs_list"), {"status": "inactive"})

		self.assertContains(active_response, "Activo")
		self.assertNotContains(active_response, ">Inactivo</a>")
		self.assertContains(inactive_response, ">Inactivo</a>")
		self.assertNotContains(inactive_response, ">Activo</a>")
		self.assertContains(active_response, 'value="active" selected')
		self.assertContains(inactive_response, 'value="inactive" selected')

	def test_dog_edit_without_any_owner_deactivates_dog(self):
		owner = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")
		dog = Dog.objects.create(name="Nube")
		dog.owners.add(owner)

		response = self.client.post(
			reverse("dogs_list"),
			{
				"dog_id": str(dog.pk),
				"name": "Nube",
				"breed": "",
				"color": "",
				"sex": "",
				"coat_type": "",
				"dog_notes": "",
				"dog_issues": "",
				"is_active": "on",
			},
		)

		self.assertRedirects(response, reverse("dogs_list"))
		dog.refresh_from_db()
		self.assertFalse(dog.is_active)
		self.assertFalse(dog.owners.exists())

	def test_removing_last_owner_automatically_deactivates_dog(self):
		owner = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")
		dog = Dog.objects.create(name="Nube")
		dog.owners.add(owner)

		with self.captureOnCommitCallbacks(execute=True):
			dog.owners.clear()

		dog.refresh_from_db()
		self.assertFalse(dog.is_active)

	def test_deactivating_the_only_owner_automatically_deactivates_dog(self):
		owner = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")
		dog = Dog.objects.create(name="Nube")
		dog.owners.add(owner)

		owner.is_active = False
		owner.save(update_fields=["is_active"])

		dog.refresh_from_db()
		self.assertFalse(dog.is_active)
		self.assertQuerySetEqual(dog.owners.all(), [owner])

	def test_deactivating_one_owner_keeps_dog_active_if_another_is_active(self):
		inactive_owner = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")
		active_owner = Contacts.objects.create(name="Luis Pérez", phone="555-0102")
		dog = Dog.objects.create(name="Nube")
		dog.owners.add(inactive_owner, active_owner)

		inactive_owner.is_active = False
		inactive_owner.save(update_fields=["is_active"])

		dog.refresh_from_db()
		self.assertTrue(dog.is_active)
		self.assertQuerySetEqual(
			dog.owners.order_by("pk"),
			[inactive_owner, active_owner],
		)


	def test_dog_registration_post_creates_and_associates_new_owner(self):
		response = self.client.post(
			reverse("dogs_list"),
			{
				"name": "Nube",
				"new_owner_name": "Ana Ruiz",
				"new_owner_phone": "555-0101",
			},
		)

		self.assertRedirects(response, reverse("dogs_list"))
		dog = Dog.objects.get(name="Nube")
		owner = Contacts.objects.get(name="Ana Ruiz", phone="555-0101")
		self.assertQuerySetEqual(dog.owners.all(), [owner])

	def test_dog_edit_updates_details_and_replaces_owners(self):
		old_owner = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")
		new_owner = Contacts.objects.create(name="Luis Pérez", phone="555-0102")
		dog = Dog.objects.create(
			name="Nube",
			color="Blanco",
			dog_notes="Nota anterior",
		)
		dog.owners.add(old_owner)

		response = self.client.post(
			reverse("dogs_list"),
			{
				"dog_id": str(dog.pk),
				"name": "Nube II",
				"breed": "",
				"color": "Negro",
				"sex": "M",
				"coat_type": "Corto",
				"dog_notes": "Nota actualizada",
				"dog_issues": "Necesita descanso",
				"is_active": "on",
				"owners": [str(new_owner.pk)],
			},
		)

		self.assertRedirects(response, reverse("dogs_list"))
		dog.refresh_from_db()
		self.assertEqual(dog.name, "Nube II")
		self.assertEqual(dog.color, "Negro")
		self.assertEqual(dog.sex, "M")
		self.assertEqual(dog.coat_type, "Corto")
		self.assertEqual(dog.dog_notes, "Nota actualizada")
		self.assertEqual(dog.dog_issues, "Necesita descanso")
		self.assertTrue(dog.is_active)
		self.assertQuerySetEqual(dog.owners.all(), [new_owner])

	def test_dog_can_be_deactivated_without_deleting_its_record_or_owners(self):
		owner = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")
		dog = Dog.objects.create(name="Nube")
		dog.owners.add(owner)
		appointment = Appointment.objects.create(
			dog=dog,
			date="2026-11-12T10:00:00Z",
		)

		response = self.client.post(
			reverse("dogs_list"),
			{"dog_id": str(dog.pk), "dog_action": "deactivate"},
		)

		self.assertRedirects(response, reverse("dogs_list"))
		dog.refresh_from_db()
		self.assertFalse(dog.is_active)
		self.assertQuerySetEqual(dog.owners.all(), [owner])
		self.assertFalse(Appointment.objects.filter(pk=appointment.pk).exists())
		detail_response = self.client.get(reverse("dog_detail", args=[dog.pk]))
		self.assertEqual(list(detail_response.context["appointments"]), [])
		self.assertNotContains(detail_response, "Pendiente")
		self.assertContains(self.client.get(reverse("dogs_list")), "Inactivo")

	def test_new_owner_requires_both_name_and_phone(self):
		response = self.client.post(
			reverse("dogs_list"),
			{
				"name": "Nube",
				"new_owner_name": "Ana Ruiz",
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.context["form"].has_error("new_owner_phone"))
		self.assertFalse(Dog.objects.filter(name="Nube").exists())
		self.assertFalse(Contacts.objects.filter(name="Ana Ruiz").exists())

	def test_existing_owner_cannot_be_duplicated_as_new(self):
		Contacts.objects.create(name="Ana Ruiz", phone="555-0101")

		response = self.client.post(
			reverse("dogs_list"),
			{
				"name": "Nube",
				"new_owner_name": "ana ruiz",
				"new_owner_phone": "555-0101",
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.context["form"].has_error("new_owner_name"))
		self.assertFalse(Dog.objects.filter(name="Nube").exists())
		self.assertEqual(Contacts.objects.filter(phone="555-0101").count(), 1)
