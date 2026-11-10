from django.test import TestCase
from django.urls import reverse

from appointments.models import Appointment
from clients.templatetags.contact_filters import whatsapp_phone
from dogs.models import Breed, Dog
from historial.models import ServiceHistory
from .models import Contacts


class ContactsPageTests(TestCase):
    def test_whatsapp_phone_adds_spain_prefix_and_removes_formatting(self):
        self.assertEqual(whatsapp_phone("600 111-222"), "34600111222")
        self.assertEqual(whatsapp_phone("+34 600 111 222"), "34600111222")
        self.assertEqual(whatsapp_phone("0034 600 111 222"), "34600111222")
        self.assertEqual(whatsapp_phone(""), "")

    def test_contact_card_links_to_whatsapp_and_keeps_call_link(self):
        contact = Contacts.objects.create(name="Ana Ruiz", phone="600 111-222")

        response = self.client.get(reverse("contacts"))

        self.assertContains(response, 'href="tel:600 111-222"')
        self.assertContains(response, 'href="https://wa.me/34600111222"')
        self.assertContains(
            response,
            'aria-label="Abrir WhatsApp con Ana Ruiz"',
        )

    def test_contact_search_suggests_names_without_restricting_input(self):
        contact = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")
        contact.dogs.add(Dog.objects.create(name="Nube"))

        response = self.client.get(reverse("contacts"))

        self.assertContains(response, 'type="search"')
        self.assertContains(response, 'list="contacts-filter-options"')
        self.assertContains(response, 'data-directory-filter="contacts-grid"')
        self.assertContains(response, '<option value="Ana Ruiz">')
        self.assertContains(response, '<option value="Nube">')
        self.assertContains(response, 'id="contacts-filter" type="search"')

    def test_appointment_create_button_is_not_rendered(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="open-appointment-dialog"')

    def test_contacts_page_shows_a_non_functional_contact_dialog(self):
        response = self.client.get(reverse("contacts"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="open-contact-dialog"')
        self.assertContains(response, 'aria-controls="contact-dialog"')
        self.assertContains(response, '<dialog class="contact-dialog" id="contact-dialog"')
        self.assertContains(response, 'name="name" id="contact-name"')
        self.assertContains(response, 'name="phone" id="contact-phone"')
        self.assertContains(response, "Nombre completo")
        self.assertContains(response, "Teléfono")
        self.assertContains(response, 'id="save-contact-dialog"')
        self.assertContains(response, 'id="contact-registration-form"')

    def test_contact_dialog_post_creates_contact(self):
        response = self.client.post(
            reverse("contacts"),
            {
                "name": "Ana Ruiz",
                "phone": "555-0101",
                "is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("contacts"))
        contact = Contacts.objects.get(name="Ana Ruiz")
        self.assertEqual(contact.phone, "555-0101")
        self.assertTrue(contact.is_active)
        self.assertFalse(contact.descartable)

    def test_invalid_contact_post_renders_errors_and_reopens_dialog(self):
        response = self.client.post(
            reverse("contacts"),
            {"name": "", "phone": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertContains(response, 'data-open-on-load="true"')

    def test_contacts_page_shows_active_and_inactive_contacts_by_default(self):
        breed, _ = Breed.objects.get_or_create(name="Caniche")
        contact = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")
        contact.dogs.add(
            Dog.objects.create(name="Nube", breed=breed, sex="F", color="Blanco"),
            Dog.objects.create(name="Milo", breed=breed, sex="M", color="Crema"),
        )
        inactive_contact = Contacts.objects.create(
            name="Contacto inactivo",
            phone="555-0102",
            is_active=False,
        )
        inactive_contact.dogs.add(Dog.objects.create(name="No mostrar"))

        response = self.client.get(reverse("contacts"))

        self.assertContains(response, "Ana Ruiz")
        self.assertContains(response, "Nube")
        self.assertContains(response, "Milo")
        self.assertContains(response, "Caniche")
        self.assertContains(response, "Blanco")
        self.assertContains(response, "Contacto inactivo")
        self.assertContains(response, "No mostrar")
        self.assertContains(response, 'class="contact-card"')

    def test_contacts_page_only_lists_active_dogs(self):
        contact = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")
        active_dog = Dog.objects.create(name="Nube")
        inactive_dog = Dog.objects.create(name="Luna", is_active=False)
        contact.dogs.add(active_dog, inactive_dog)

        response = self.client.get(reverse("contacts"))

        self.assertContains(response, "Nube")
        self.assertNotContains(response, "Luna")
        self.assertContains(response, "perro activo")

    def test_contact_detail_shows_only_related_dogs_appointments_and_history(self):
        contact = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")
        other_contact = Contacts.objects.create(name="Luis Pérez", phone="555-0102")
        active_dog = Dog.objects.create(name="Nube")
        inactive_dog = Dog.objects.create(name="Luna", is_active=False)
        unrelated_dog = Dog.objects.create(name="Toby")
        contact.dogs.add(active_dog, inactive_dog)
        other_contact.dogs.add(unrelated_dog)

        appointment = Appointment.objects.create(
            dog=active_dog,
            date="2026-11-10T10:00:00Z",
            service_type="BAÑO",
        )
        Appointment.objects.create(
            dog=unrelated_dog,
            date="2026-11-10T11:00:00Z",
            service_type="CORTE",
        )
        ServiceHistory.objects.create(
            dog=active_dog,
            date="2026-11-01T10:00:00Z",
            service_type="BAÑO",
        )
        ServiceHistory.objects.create(
            dog=inactive_dog,
            date="2026-10-01T10:00:00Z",
            service_type="CORTE",
        )
        ServiceHistory.objects.create(
            dog=unrelated_dog,
            date="2026-10-02T10:00:00Z",
            service_type="COMPLETO",
        )

        response = self.client.get(reverse("contact_detail", args=[contact.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["dogs"]), [active_dog])
        self.assertEqual(list(response.context["appointments"]), [appointment])
        self.assertEqual(
            {service.dog_id for service in response.context["service_history"]},
            {active_dog.pk, inactive_dog.pk},
        )
        self.assertContains(response, "Nube")
        self.assertContains(response, "Luna")
        self.assertNotContains(response, "Toby")
        self.assertContains(response, "Citas")
        self.assertContains(response, "Histórico")

    def test_contact_card_name_links_to_client_detail(self):
        contact = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")

        response = self.client.get(reverse("contacts"))

        self.assertContains(
            response,
            f'href="{reverse("contact_detail", args=[contact.pk])}">Ana Ruiz</a>',
        )

    def test_discardable_contact_has_a_subtle_warning_badge(self):
        Contacts.objects.create(
            name="No prioritario",
            phone="555-0103",
            descartable=True,
        )
        Contacts.objects.create(name="Cliente habitual", phone="555-0104")

        response = self.client.get(reverse("contacts"))

        self.assertContains(response, "No priorizar")
        self.assertContains(
            response,
            'title="Cliente marcado como no prioritario para futuras visitas"',
        )
        self.assertEqual(response.content.count(b'class="discardable-badge"'), 1)

    def test_contacts_can_be_filtered_by_status(self):
        Contacts.objects.create(name="Activa", phone="555-0101")
        Contacts.objects.create(name="Inactiva", phone="555-0102", is_active=False)

        active_response = self.client.get(reverse("contacts"), {"status": "active"})
        inactive_response = self.client.get(reverse("contacts"), {"status": "inactive"})

        self.assertContains(active_response, "Activa")
        self.assertNotContains(active_response, "Inactiva")
        self.assertContains(inactive_response, "Inactiva")
        self.assertNotContains(inactive_response, "Activa")

    def test_contact_can_be_edited_without_changing_status_or_dog_relations(self):
        contact = Contacts.objects.create(
            name="Ana Ruiz",
            phone="555-0101",
            is_active=False,
            descartable=True,
        )
        dog = Dog.objects.create(name="Nube")
        contact.dogs.add(dog)

        response = self.client.post(
            reverse("contacts"),
            {
                "contact_id": contact.pk,
                "contact_action": "edit",
                "name": "Ana García",
                "phone": "555-0109",
                "descartable": "",
            },
        )

        self.assertRedirects(response, reverse("contacts"))
        contact.refresh_from_db()
        self.assertEqual(contact.name, "Ana García")
        self.assertEqual(contact.phone, "555-0109")
        self.assertFalse(contact.is_active)
        self.assertFalse(contact.descartable)
        self.assertIn(dog, contact.dogs.all())

    def test_contact_can_be_activated_or_deactivated(self):
        contact = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")

        deactivate_response = self.client.post(
            reverse("contacts"),
            {"contact_id": contact.pk, "contact_action": "deactivate"},
        )
        contact.refresh_from_db()
        self.assertRedirects(deactivate_response, reverse("contacts"))
        self.assertFalse(contact.is_active)

        activate_response = self.client.post(
            reverse("contacts"),
            {"contact_id": contact.pk, "contact_action": "activate"},
        )
        contact.refresh_from_db()
        self.assertRedirects(activate_response, reverse("contacts"))
        self.assertTrue(contact.is_active)

    def test_deactivating_contacts_deactivates_dogs_without_another_active_owner(self):
        contact = Contacts.objects.create(name="Ana Ruiz", phone="555-0101")
        dog = Dog.objects.create(name="Nube")
        contact.dogs.add(dog)

        response = self.client.post(
            reverse("contacts"),
            {"contact_id": contact.pk, "contact_action": "deactivate"},
        )

        self.assertRedirects(response, reverse("contacts"))
        dog.refresh_from_db()
        self.assertFalse(dog.is_active)
        self.assertIn(dog, contact.dogs.all())
