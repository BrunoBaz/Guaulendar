"""Correo saliente por la API HTTP de Brevo.

Vercel no deja abrir sockets SMTP desde el runtime de Python: la conexión muere
con `OSError: [Errno 16] Device or resource busy` antes incluso de negociar TLS.
Por eso el correo de la aplicación (recuperación de contraseña) sale por HTTPS.
"""

import os
from email.utils import parseaddr

import httpx
from django.core.mail.backends.base import BaseEmailBackend

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"
TIMEOUT = 15


class BrevoEmailBackend(BaseEmailBackend):
    """Envía cada mensaje a la API de Brevo.

    La clave va en BREVO_API_KEY y el remitente (DEFAULT_FROM_EMAIL) tiene que
    estar verificado en Brevo, en Senders & Domains, o la API lo rechaza.
    """

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.api_key = os.environ.get("BREVO_API_KEY", "")

    def send_messages(self, email_messages):
        return sum(1 for message in email_messages if self._send(message))

    def _send(self, message):
        try:
            response = httpx.post(
                BREVO_ENDPOINT,
                headers={"api-key": self.api_key, "accept": "application/json"},
                json=self._payload(message),
                timeout=TIMEOUT,
            )
            response.raise_for_status()
        except Exception:
            if not self.fail_silently:
                raise
            return False
        return True

    def _payload(self, message):
        name, address = parseaddr(message.from_email)
        payload = {
            "sender": {"email": address, "name": name or "Guaulendar"},
            "to": [{"email": recipient} for recipient in message.to],
            "subject": message.subject,
        }
        if message.content_subtype == "html":
            payload["htmlContent"] = message.body
        else:
            payload["textContent"] = message.body

        # `alternatives` solo existe en EmailMultiAlternatives (la versión HTML).
        html = [
            body
            for body, mimetype in getattr(message, "alternatives", [])
            if mimetype == "text/html"
        ]
        if html:
            payload["htmlContent"] = html[0]
        return payload
