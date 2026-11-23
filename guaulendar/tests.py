"""Tests del envío de correo por la API HTTP de Brevo."""

import os
from unittest.mock import patch

import httpx
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings

from guaulendar.mailers import BREVO_ENDPOINT, BrevoEmailBackend
from guaulendar.settings import mailer


def brevo_backend(**kwargs):
    """Backend con una clave de prueba, como la tendría en producción."""
    with patch.dict(os.environ, {"BREVO_API_KEY": "clave-de-prueba"}):
        return BrevoEmailBackend(**kwargs)


class BrevoEmailBackendTests(SimpleTestCase):
    def test_sends_the_message_through_the_brevo_api(self):
        message = EmailMessage(
            subject="Recupera tu contraseña",
            body="Enlace: https://guaulendar.test/accounts/password-reset/x/y/",
            from_email="Guaulendar <guaulendar@gmail.com>",
            to=["teresa@peluqueria.test"],
        )

        with patch("guaulendar.mailers.httpx.post") as post:
            sent = brevo_backend().send_messages([message])

        self.assertEqual(sent, 1)
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], BREVO_ENDPOINT)
        self.assertEqual(post.call_args.kwargs["headers"]["api-key"], "clave-de-prueba")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(
            payload["sender"], {"email": "guaulendar@gmail.com", "name": "Guaulendar"}
        )
        self.assertEqual(payload["to"], [{"email": "teresa@peluqueria.test"}])
        self.assertEqual(payload["subject"], "Recupera tu contraseña")
        self.assertEqual(payload["textContent"], message.body)
        self.assertNotIn("htmlContent", payload)

    @override_settings(DEFAULT_FROM_EMAIL="Guaulendar <no-reply@guaulendar.test>")
    def test_the_sender_comes_from_the_settings_when_the_message_does_not_set_one(self):
        message = EmailMessage(subject="Hola", body="Cuerpo", to=["teresa@peluqueria.test"])

        with patch("guaulendar.mailers.httpx.post") as post:
            brevo_backend().send_messages([message])

        self.assertEqual(
            post.call_args.kwargs["json"]["sender"],
            {"email": "no-reply@guaulendar.test", "name": "Guaulendar"},
        )

    def test_the_html_version_is_attached_when_the_message_has_one(self):
        message = EmailMultiAlternatives(
            subject="Recupera tu contraseña",
            body="Enlace",
            from_email="Guaulendar <guaulendar@gmail.com>",
            to=["teresa@peluqueria.test"],
        )
        message.attach_alternative("<p>Enlace</p>", "text/html")

        with patch("guaulendar.mailers.httpx.post") as post:
            brevo_backend().send_messages([message])

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["textContent"], "Enlace")
        self.assertEqual(payload["htmlContent"], "<p>Enlace</p>")

    def test_a_failed_request_is_not_swallowed(self):
        message = EmailMessage(subject="Hola", body="Cuerpo", to=["teresa@peluqueria.test"])

        with patch(
            "guaulendar.mailers.httpx.post",
            side_effect=httpx.ConnectError("sin salida"),
        ):
            with self.assertRaises(httpx.ConnectError):
                brevo_backend().send_messages([message])

    def test_fail_silently_returns_zero_instead_of_raising(self):
        message = EmailMessage(subject="Hola", body="Cuerpo", to=["teresa@peluqueria.test"])

        with patch(
            "guaulendar.mailers.httpx.post",
            side_effect=httpx.ConnectError("sin salida"),
        ):
            sent = brevo_backend(fail_silently=True).send_messages([message])

        self.assertEqual(sent, 0)


class MailerSelectionTests(SimpleTestCase):
    def test_the_brevo_key_selects_the_http_backend(self):
        with patch.dict(os.environ, {"BREVO_API_KEY": "clave-de-prueba"}):
            self.assertEqual(mailer()["BACKEND"], "guaulendar.mailers.BrevoEmailBackend")

    def test_a_smtp_host_is_used_when_there_is_no_brevo_key(self):
        with patch.dict(
            os.environ,
            {"BREVO_API_KEY": "", "EMAIL_HOST": "smtp.gmail.com"},
        ):
            self.assertEqual(
                mailer()["BACKEND"], "django.core.mail.backends.smtp.EmailBackend"
            )

    def test_without_credentials_the_mail_goes_to_the_console(self):
        with patch.dict(os.environ, {"BREVO_API_KEY": "", "EMAIL_HOST": ""}):
            self.assertEqual(
                mailer()["BACKEND"],
                "django.core.mail.backends.console.EmailBackend",
            )
