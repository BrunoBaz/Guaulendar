from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django.urls import reverse

from dogs.models import Dog
from invoicing.models import Emisor, EmisorMember, VerifactuConfig

User = get_user_model()

REGISTER_DATA = {
    "email": "nueva@peluqueria.test",
    "password1": "ClaveSegura-2026",
    "password2": "ClaveSegura-2026",
    "business_name": "Peluquería Nueva",
    "trade_name": "Guau Studio",
    "nif": "B87654321",
    "taxpayer_type": "COMPANY",
    "fiscal_address": "Calle Mayor 1",
}


class RegisterViewTests(TestCase):
    def test_register_links_user_business_and_verifactu_config(self):
        response = self.client.post(reverse("register"), REGISTER_DATA)

        self.assertRedirects(response, reverse("appointments"))
        user = User.objects.get(username="nueva@peluqueria.test")
        self.assertTrue(user.check_password("ClaveSegura-2026"))
        emisor = Emisor.objects.get(nif="B87654321")
        self.assertEqual(emisor.name, "Peluquería Nueva")
        self.assertEqual(emisor.trade_name, "Guau Studio")
        self.assertEqual(emisor.taxpayer_type, "COMPANY")
        self.assertTrue(
            EmisorMember.objects.filter(
                emisor=emisor,
                user=user,
                role="OWNER",
            ).exists()
        )
        self.assertEqual(VerifactuConfig.objects.get(emisor=emisor).email, REGISTER_DATA["email"])
        # La cuenta queda con sesión iniciada.
        self.assertEqual(self.client.get(reverse("appointments")).status_code, 200)

    def test_register_of_an_individual_uses_the_full_name_as_the_issuer(self):
        response = self.client.post(
            reverse("register"),
            {
                **REGISTER_DATA,
                "email": "particular@peluqueria.test",
                "nif": "12345678Z",
                "taxpayer_type": "INDIVIDUAL",
                "business_name": "",
                "first_name": "Bruno",
                "last_name": "Baz Álvarez",
            },
        )

        self.assertRedirects(response, reverse("appointments"))
        emisor = Emisor.objects.get(nif="12345678Z")
        self.assertEqual(emisor.name, "Bruno Baz Álvarez")
        self.assertEqual(emisor.taxpayer_type, "INDIVIDUAL")

    def test_register_of_an_individual_without_a_name_is_rejected(self):
        response = self.client.post(
            reverse("register"),
            {
                **REGISTER_DATA,
                "email": "sin-nombre@peluqueria.test",
                "nif": "12345678Z",
                "taxpayer_type": "INDIVIDUAL",
                "business_name": "",
                "first_name": "",
                "last_name": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].has_error("first_name"))
        self.assertFalse(Emisor.objects.filter(nif="12345678Z").exists())

    def test_register_rejects_a_duplicate_email(self):
        User.objects.create_user(username="repetida@peluqueria.test", password="x")

        response = self.client.post(
            reverse("register"),
            {**REGISTER_DATA, "email": "Repetida@Peluqueria.test"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].has_error("email"))
        self.assertFalse(Emisor.objects.filter(nif="B87654321").exists())

    def test_register_rejects_a_duplicate_nif(self):
        Emisor.objects.create(name="Otra peluquería", nif="B87654321")

        response = self.client.post(reverse("register"), REGISTER_DATA)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].has_error("nif"))
        self.assertFalse(User.objects.filter(username=REGISTER_DATA["email"]).exists())

    def test_register_adopts_the_business_that_already_has_data(self):
        heredado = Emisor.objects.create(name="Mi peluquería", nif="SIN-NIF")
        Dog.objects.create(name="Luna", emisor=heredado)

        response = self.client.post(reverse("register"), REGISTER_DATA)

        self.assertRedirects(response, reverse("appointments"))
        # No se crea un negocio nuevo: se reclama el que ya tenía los datos.
        self.assertEqual(Emisor.objects.count(), 1)
        emisor = Emisor.objects.get()
        self.assertEqual(emisor.pk, heredado.pk)
        self.assertEqual(emisor.name, "Peluquería Nueva")
        self.assertEqual(emisor.nif, "B87654321")
        user = User.objects.get(username=REGISTER_DATA["email"])
        self.assertTrue(
            EmisorMember.objects.filter(
                emisor=emisor,
                user=user,
                role="OWNER",
            ).exists()
        )
        # Los datos anteriores se conservan y quedan visibles para la cuenta.
        self.assertContains(self.client.get(reverse("dogs_list")), "Luna")

    def test_register_accepts_the_nif_of_the_inherited_business(self):
        heredado = Emisor.objects.create(name="Mi peluquería", nif="B87654321")
        Dog.objects.create(name="Luna", emisor=heredado)

        response = self.client.post(reverse("register"), REGISTER_DATA)

        self.assertRedirects(response, reverse("appointments"))
        self.assertEqual(Emisor.objects.count(), 1)

    def test_register_rejects_mismatched_passwords(self):
        response = self.client.post(
            reverse("register"),
            {**REGISTER_DATA, "password2": "OtraClave-2027"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].has_error("password2"))
        self.assertFalse(User.objects.filter(username=REGISTER_DATA["email"]).exists())

    def test_authenticated_user_is_sent_to_the_app(self):
        user = User.objects.create_user(username="yo@peluqueria.test", password="x")
        self.client.force_login(user)

        response = self.client.get(reverse("register"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("appointments"))


class LoginViewTests(TestCase):
    def test_login_with_the_email_reaches_the_app(self):
        user = User.objects.create_user(
            username="acceso@peluqueria.test",
            email="acceso@peluqueria.test",
            password="ClaveSegura-2026",
        )
        emisor = Emisor.objects.create(name="Peluquería Guau", nif="B12345678")
        EmisorMember.objects.create(emisor=emisor, user=user)

        response = self.client.post(
            reverse("login"),
            {"username": "acceso@peluqueria.test", "password": "ClaveSegura-2026"},
        )

        self.assertRedirects(response, reverse("appointments"))
        self.assertEqual(self.client.get(reverse("appointments")).status_code, 200)


class EmisorIsolationTests(TestCase):
    def setUp(self):
        self.emisor_a = Emisor.objects.create(name="Peluquería A", nif="B11111111")
        self.user_a = User.objects.create_user(
            username="a@peluqueria.test",
            password="ClaveSegura-2026",
        )
        EmisorMember.objects.create(emisor=self.emisor_a, user=self.user_a)

        self.emisor_b = Emisor.objects.create(name="Peluquería B", nif="B22222222")
        self.dog_b = Dog.objects.create(name="PerroDeB", emisor=self.emisor_b)

    def test_user_only_sees_the_dogs_of_their_business(self):
        Dog.objects.create(name="PerroDeA", emisor=self.emisor_a)
        self.client.force_login(self.user_a)

        response = self.client.get(reverse("dogs_list"))

        self.assertContains(response, "PerroDeA")
        self.assertNotContains(response, "PerroDeB")

    def test_user_cannot_open_a_dog_of_another_business(self):
        self.client.force_login(self.user_a)

        response = self.client.get(reverse("dog_detail", args=[self.dog_b.public_id]))

        self.assertEqual(response.status_code, 404)

    def test_user_without_a_business_gets_404(self):
        user = User.objects.create_user(username="sin@peluqueria.test", password="x")
        self.client.force_login(user)

        self.assertEqual(self.client.get(reverse("dogs_list")).status_code, 404)


class UnknownAddressTests(TestCase):
    UNKNOWN = "/direccion-que-no-existe/"

    def setUp(self):
        self.user = User.objects.create_user(
            username="conocido@peluqueria.test",
            password="ClaveSegura-2026",
        )

    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get(self.UNKNOWN)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("login"))

    def test_logged_in_user_returns_to_the_previous_screen_with_a_warning(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.UNKNOWN,
            headers={"referer": "http://testserver/dogs/"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "http://testserver/dogs/")
        avisos = " ".join(str(m) for m in get_messages(response.wsgi_request))
        self.assertIn("no existe", avisos)

    def test_logged_in_user_without_a_previous_screen_goes_home(self):
        self.client.force_login(self.user)

        response = self.client.get(self.UNKNOWN)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("appointments"))

    @override_settings(DEBUG=True)
    def test_unknown_address_redirects_in_debug_too(self):
        """En local (DEBUG) Django omite el handler404; el middleware lo suple."""
        self.client.force_login(self.user)

        response = self.client.get(self.UNKNOWN)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("appointments"))
