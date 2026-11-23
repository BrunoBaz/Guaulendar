import base64
import json
from decimal import Decimal
from unittest.mock import patch

import httpx
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clients.models import Contacts
from dogs.models import Dog
from historial.models import ServiceHistory

from .admin import VerifactuConfigForm
from .models import (
    Emisor,
    EmisorMember,
    Invoice,
    VerifactuConfig,
    VerifactuRecord,
    emisor_for_user,
)
from .services import invoices as invoice_services
from .services.verifactu import VerifactuClient

PASSWORD = "secreto-de-pruebas"


def create_emisor(**overrides):
    defaults = {
        "name": "Peluquería Guau",
        "nif": "B12345678",
        "series_prefix": "FAC",
    }
    defaults.update(overrides)
    emisor = Emisor.objects.create(**defaults)
    VerifactuConfig.objects.create(
        emisor=emisor,
        email="facturacion@example.test",
        password=PASSWORD,
    )
    return emisor


def create_member(emisor, username="facturacion"):
    user = get_user_model().objects.create_user(
        username=username,
        email=f"{username}@example.test",
        password="clave-de-pruebas",
    )
    EmisorMember.objects.create(emisor=emisor, user=user, role="OWNER")
    return user


def create_service(**overrides):
    dog = overrides.pop("dog", None)
    if dog is None:
        dog = Dog.objects.create(
            name="Luna",
            emisor=overrides.pop("emisor", None) or create_emisor(),
        )
    defaults = {
        "dog": dog,
        "date": timezone.now(),
        "price": Decimal("121.00"),
        "taxable_base": Decimal("100.00"),
        "service_type": "BAÑO",
        "status": "COMPLETED",
        "tax_rate": Decimal("21.00"),
        "tax_amount": Decimal("21.00"),
        "total_price": Decimal("121.00"),
    }
    defaults.update(overrides)
    return ServiceHistory.objects.create(emisor=dog.emisor, **defaults)


def api_transport(calls, register_item=None, status_item=None):
    """Transporte simulado de httpx: hace de VeriFactu sin salir a la red.

    Reproduce la forma real de la API: `ResultCode`/`ResultMessage` con el
    resultado en `Return` para las operaciones y en `Items` para los listados.
    """

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/Server/Security/"):
            return httpx.Response(
                200,
                json={"ResultCode": 0, "ResultMessage": "OK", "Return": "SESSION-1"},
            )
        if request.url.path.endswith("/Invoices/GetFilteredList"):
            item = status_item or {
                "ExternKey": "FAKE-000055",
                "StatusResponse": "Correcto",
                "ErrorCode": None,
                "ErrorDescription": None,
            }
            return httpx.Response(
                200, json={"ResultCode": 0, "ResultMessage": "OK", "Items": [item]}
            )
        item = register_item or {
            "ExternKey": "FAKE-000055",
            "StatusResponse": "Correcto",
            "ErrorCode": None,
            "ErrorDescription": None,
            "QrCode": "iVBORw0KGgoAAAANSUhEUg==",
            "QrCodeUrl": "https://example.test/verifactu.bmp",
        }
        return httpx.Response(
            200, json={"ResultCode": 0, "ResultMessage": "OK", "Return": item}
        )

    return httpx.MockTransport(handler)


class InvoicePayloadTests(TestCase):
    def setUp(self):
        self.emisor = create_emisor()
        self.service = create_service(emisor=self.emisor)

    def test_payload_builds_a_simplified_invoice(self):
        Contacts.objects.create(emisor=self.emisor, name="Ana Ruiz", phone="555-0101", nif="39707287H").dogs.add(
            self.service.dog
        )

        invoice = invoice_services.invoice_for_service(self.service, self.emisor)
        payload = invoice_services.build_payload(invoice)

        self.assertEqual(payload["Status"], "POST")
        self.assertEqual(payload["SellerID"], "B12345678")
        self.assertEqual(payload["CompanyName"], "Peluquería Guau")
        self.assertEqual(payload["InvoiceID"], invoice.number)
        self.assertEqual(payload["InvoiceDate"], timezone.localdate().isoformat())
        self.assertEqual(payload["InvoiceType"], "F2")
        self.assertEqual(payload["TaxItems"], [{
            "Tax": "01",
            "TaxScheme": "01",
            "TaxType": "S1",
            "TaxRate": 21.0,
            "TaxBase": 100.0,
            "TaxAmount": 21.0,
        }])

    def test_invoice_numbering_is_sequential_per_year(self):
        Contacts.objects.create(emisor=self.emisor, name="Ana Ruiz", phone="555-0101", nif="39707287H").dogs.add(
            self.service.dog
        )
        second = create_service(dog=self.service.dog)

        first_invoice = invoice_services.invoice_for_service(self.service, self.emisor)
        second_invoice = invoice_services.invoice_for_service(second, self.emisor)

        year = timezone.localdate().year
        self.assertEqual(first_invoice.number, f"FAC/{year}/0001")
        self.assertEqual(second_invoice.number, f"FAC/{year}/0002")

    def test_invoice_is_not_duplicated_when_repeated(self):
        Contacts.objects.create(emisor=self.emisor, name="Ana Ruiz", phone="555-0101", nif="39707287H").dogs.add(
            self.service.dog
        )

        first = invoice_services.invoice_for_service(self.service, self.emisor)
        second = invoice_services.invoice_for_service(self.service, self.emisor)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Invoice.objects.count(), 1)

    def test_simplified_invoice_does_not_need_a_client_nif(self):
        Contacts.objects.create(
            emisor=self.emisor, name="Ana Ruiz", phone="555-0101"
        ).dogs.add(self.service.dog)

        invoice = invoice_services.invoice_for_service(self.service, self.emisor)

        self.assertEqual(invoice.invoice_type, "F2")
        self.assertEqual(invoice.recipient_name, "Ana Ruiz")
        self.assertEqual(invoice.recipient_nif, "")
        self.assertNotIn("RelatedPartyID", invoice_services.build_payload(invoice))

    def test_cancelled_service_cannot_be_invoiced(self):
        cancelled = create_service(dog=self.service.dog, status="CANCELLED")

        with self.assertRaisesMessage(
            invoice_services.InvoicingError,
            "Solo se pueden facturar servicios completados.",
        ):
            invoice_services.invoice_for_service(cancelled, self.emisor)


class SendInvoiceTests(TestCase):
    def setUp(self):
        self.emisor = create_emisor()
        self.service = create_service(emisor=self.emisor)
        Contacts.objects.create(emisor=self.emisor, name="Ana Ruiz", phone="555-0101", nif="39707287H").dogs.add(
            self.service.dog
        )
        self.invoice = invoice_services.invoice_for_service(self.service, self.emisor)

    def client_with(self, calls, **kwargs):
        return lambda emisor: VerifactuClient(emisor, transport=api_transport(calls, **kwargs))

    def test_send_stores_record_and_reuses_the_cached_session(self):
        calls = []
        with patch.object(invoice_services, "get_client", self.client_with(calls)):
            first = invoice_services.send_invoice(self.invoice)
            second_service = create_service(dog=self.service.dog)
            second = invoice_services.send_invoice(
                invoice_services.invoice_for_service(second_service, self.emisor)
            )

        self.assertEqual(first.estado, "CORRECTO")
        self.assertEqual(first.registro_id, "FAKE-000055")
        self.assertEqual(first.qr_image, "iVBORw0KGgoAAAANSUhEUg==")
        self.assertEqual(second.estado, "CORRECTO")
        self.assertEqual(
            sum("/Server/Security/" in call.url.path for call in calls),
            1,
        )

        sent = [call for call in calls if call.method == "POST" and "Invoices/Create" in call.url.path]
        self.assertEqual(len(sent), 2)
        body = json.loads(sent[0].content)
        self.assertEqual(body["Status"], "POST")
        self.assertEqual(body["InvoiceID"], self.invoice.number)
        self.assertEqual(body["TaxItems"][0]["TaxBase"], 100.0)

    def test_login_carries_the_operation_in_the_url(self):
        """La API no responde al login si falta el parámetro `op=Sessions.Create`."""
        calls = []
        with patch.object(invoice_services, "get_client", self.client_with(calls)):
            invoice_services.send_invoice(self.invoice)

        login_call = next(call for call in calls if "/Server/Security/" in call.url.path)
        self.assertEqual(login_call.url.params.get("op"), "Sessions.Create")

    def test_expired_session_is_renewed_and_the_send_is_retried(self):
        """Cuando la AEAT no reconoce la sesión se pide otra y se reintenta una vez."""
        sessions = {"count": 0}

        def handler(request):
            if request.url.path.endswith("/Server/Security/"):
                sessions["count"] += 1
                return httpx.Response(
                    200,
                    json={"ResultCode": 0, "Return": f"SESSION-{sessions['count']}"},
                )
            service_key = base64.b64decode(json.loads(request.content)["ServiceKey"]).decode()
            if service_key == "SESSION-1":
                return httpx.Response(
                    200,
                    json={"ResultCode": 603, "ResultMessage": "Unknown SessionID."},
                )
            return httpx.Response(
                200,
                json={
                    "ResultCode": 0,
                    "Return": {"ExternKey": "REAL-1", "StatusResponse": "Correcto"},
                },
            )

        client = lambda emisor: VerifactuClient(emisor, transport=httpx.MockTransport(handler))
        with patch.object(invoice_services, "get_client", client):
            record = invoice_services.send_invoice(self.invoice)

        self.assertEqual(record.estado, "CORRECTO")
        self.assertEqual(record.registro_id, "REAL-1")
        self.assertEqual(sessions["count"], 2)

    def test_api_error_keeps_the_invoice_for_a_later_retry(self):
        def handler(request):
            if request.url.path.endswith("/Server/Security/"):
                return httpx.Response(200, json={"ResultCode": 0, "Return": "SESSION-1"})
            return httpx.Response(
                200,
                json={"ResultCode": 601, "ResultMessage": "NIF del emisor no válido."},
            )

        client = lambda emisor: VerifactuClient(emisor, transport=httpx.MockTransport(handler))
        with patch.object(invoice_services, "get_client", client):
            with self.assertRaisesMessage(invoice_services.InvoicingError, "NIF del emisor no válido."):
                invoice_services.send_invoice(self.invoice)

        self.assertEqual(Invoice.objects.count(), 1)
        record = VerifactuRecord.objects.get(invoice=self.invoice)
        self.assertEqual(record.estado, "PENDING")
        self.assertEqual(record.descripcion_error, "NIF del emisor no válido.")

    def test_refresh_updates_the_state_from_the_aeat(self):
        calls = []
        with patch.object(invoice_services, "get_client", self.client_with(calls)):
            invoice_services.send_invoice(self.invoice)
        record = VerifactuRecord.objects.get(invoice=self.invoice)
        record.estado = "PENDIENTE"
        record.save(update_fields=["estado"])

        status_item = {
            "StatusResponse": "Incorrecto",
            "ErrorCode": "4102",
            "ErrorDescription": "El NIF no está identificado.",
        }
        with patch.object(invoice_services, "get_client", self.client_with([], status_item=status_item)):
            refreshed = invoice_services.refresh_invoice(self.invoice)

        self.assertEqual(refreshed.estado, "INCORRECTO")
        self.assertEqual(refreshed.codigo_error, "4102")
        self.assertEqual(refreshed.descripcion_error, "El NIF no está identificado.")


class InvoiceViewTests(TestCase):
    def setUp(self):
        self.emisor = create_emisor()
        self.service = create_service(emisor=self.emisor)
        Contacts.objects.create(emisor=self.emisor, name="Ana Ruiz", phone="555-0101", nif="39707287H").dogs.add(
            self.service.dog
        )
        self.client.force_login(create_member(self.emisor))
        self.url = reverse("invoice_service", args=[self.service.public_id])

    def test_facturar_creates_the_invoice_and_redirects(self):
        with patch.object(invoice_services, "get_client", lambda emisor: VerifactuClient(emisor, transport=api_transport([]))):
            response = self.client.post(self.url)

        self.assertRedirects(
            response,
            reverse("service_history_detail", args=[self.service.public_id]),
        )
        invoice = Invoice.objects.get(service_history=self.service)
        self.assertEqual(invoice.verifactu.estado, "CORRECTO")

    def test_facturar_works_without_a_client_nif(self):
        Contacts.objects.filter(name="Ana Ruiz").update(nif="")

        with patch.object(invoice_services, "get_client", lambda emisor: VerifactuClient(emisor, transport=api_transport([]))):
            self.client.post(self.url)

        self.assertEqual(Invoice.objects.count(), 1)

    def test_refresh_action_updates_the_registro_state(self):
        with patch.object(invoice_services, "get_client", lambda emisor: VerifactuClient(emisor, transport=api_transport([]))):
            self.client.post(self.url)
            response = self.client.post(self.url, {"invoice_action": "refresh"}, follow=True)

        self.assertContains(response, "Estado en la AEAT: Correcto")

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)


class EmisorForUserTests(TestCase):
    def test_emisor_for_user_returns_the_business_of_the_member(self):
        emisor = create_emisor()
        user = create_member(emisor)

        self.assertEqual(emisor_for_user(user), emisor)

    def test_emisor_for_user_is_none_without_membership(self):
        user = get_user_model().objects.create_user(username="solo", password="x")

        self.assertIsNone(emisor_for_user(user))


class FakeApiModeTests(TestCase):
    @override_settings(DEBUG=True, VERIFACTU_FAKE_API=True)
    def test_get_client_returns_the_simulated_api_in_debug(self):
        client = invoice_services.get_client(create_emisor())

        item = client.registrar_factura({})

        self.assertIsNotNone(client.transport)
        self.assertEqual(item["StatusResponse"], "Correcto")
        self.assertTrue(item["QrCode"].startswith("iVBORw0KGgo"))

        invoice = Invoice(number="FAC/2026/0001")
        self.assertEqual(client.consultar_estado(invoice)["StatusResponse"], "Correcto")

    @override_settings(DEBUG=False, VERIFACTU_FAKE_API=True)
    def test_simulated_api_is_ignored_outside_debug(self):
        self.assertIsNone(invoice_services.get_client(create_emisor()).transport)


class VerifactuConfigTests(TestCase):
    def test_password_is_encrypted_in_the_database(self):
        emisor = create_emisor()

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT password FROM invoicing_verifactuconfig WHERE emisor_id = %s",
                [emisor.pk],
            )
            guardado = cursor.fetchone()[0]

        self.assertNotIn(PASSWORD, guardado)
        self.assertEqual(emisor.verifactu.password, PASSWORD)

    def test_admin_form_keeps_the_stored_password_when_left_blank(self):
        emisor = create_emisor()

        form = VerifactuConfigForm(
            instance=emisor.verifactu,
            data={"email": "nuevo@example.test", "password": ""},
        )

        self.assertTrue(form.is_valid())
        form.save()

        emisor.verifactu.refresh_from_db()
        self.assertEqual(emisor.verifactu.email, "nuevo@example.test")
        self.assertEqual(emisor.verifactu.password, PASSWORD)
