"""Cliente HTTP de la API REST gratuita de VeriFactu (Irene Solutions).

Documentación: https://facturae.irenesolutions.com/verifactu/go

La autenticación va en dos pasos: primero se pide una sesión a `Sessions.Create`
enviando la ServiceKey en base64 de "usuario:contraseña"; después, cada petición
lleva en el cuerpo la ServiceKey en base64 de esa sesión.
"""

import base64
from datetime import timedelta

import httpx
from django.conf import settings
from django.utils import timezone

from ..models import VerifactuConfig, VerifactuSession

# Rutas relativas a VERIFACTU_BASE_URL.
# El login exige la operación en la URL (`?op=`); sin ella la petición no responde.
SESSION_PATH = "/Server/Security/?op=Sessions.Create"
INVOICE_CREATE_PATH = "/Taxes/Verifactu/Invoices/Create"
INVOICE_LIST_PATH = "/Taxes/Verifactu/Invoices/GetFilteredList"

# Código con el que la API avisa de que la sesión enviada ya no existe.
SESSION_EXPIRED_CODE = 603


class VerifactuError(RuntimeError):
    """Fallo de red o error devuelto por VeriFactu."""


class SessionExpired(VerifactuError):
    """La sesión enviada ya no es válida en VeriFactu: hay que pedir otra."""


def _service_key(value):
    """La API espera la ServiceKey como base64 del texto que identifica la petición."""
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


class VerifactuClient:
    """Cliente síncrono.

    El transporte es inyectable para poder usar `httpx.MockTransport` en las pruebas.
    """

    def __init__(self, emisor, base_url=None, timeout=None, transport=None):
        self.emisor = emisor
        self.base_url = (base_url or settings.VERIFACTU_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.VERIFACTU_TIMEOUT
        self.transport = transport

    def _post(self, path, body):
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
                headers=headers,
            ) as client:
                response = client.post(path, json=body)
        except httpx.HTTPError as error:
            raise VerifactuError(f"Error de red al llamar a VeriFactu: {error}") from error

        try:
            data = response.json()
        except ValueError as error:
            raise VerifactuError("VeriFactu devolvió una respuesta que no es JSON.") from error

        code = data.get("ResultCode")
        if code != 0:
            message = data.get("ResultMessage") or (
                f"VeriFactu devolvió el código {response.status_code}."
            )
            if code == SESSION_EXPIRED_CODE:
                raise SessionExpired(message)
            raise VerifactuError(message)
        return data

    def login(self):
        """Pide una sesión nueva y la guarda para las siguientes llamadas."""
        config = self._config()
        try:
            data = self._post(
                SESSION_PATH,
                {"ServiceKey": _service_key(f"{config.email}:{config.password}")},
            )
        except VerifactuError as error:
            config.is_connected = False
            config.last_error = str(error)
            config.save(update_fields=["is_connected", "last_error", "updated_at"])
            raise

        session_id = str(data.get("Return") or "")
        if not session_id:
            raise VerifactuError("VeriFactu no devolvió ninguna sesión en el login.")
        VerifactuSession.objects.update_or_create(
            emisor=self.emisor,
            defaults={
                "session_id": session_id,
                "expires_at": timezone.now()
                + timedelta(seconds=settings.VERIFACTU_SESSION_LIFETIME),
            },
        )
        config.is_connected = True
        config.last_login_at = timezone.now()
        config.last_error = ""
        config.save(
            update_fields=["is_connected", "last_login_at", "last_error", "updated_at"]
        )
        return session_id

    def _config(self):
        """Credenciales de VeriFactu del negocio, creadas si aún no existen."""
        config, _ = VerifactuConfig.objects.get_or_create(emisor=self.emisor)
        if not config.email or not config.password:
            raise VerifactuError(
                "Falta configurar las credenciales de VeriFactu del negocio."
            )
        return config

    def session(self):
        """Sesión vigente: reutiliza la guardada y solo entra en Sessions.Create si caducó."""
        cached = VerifactuSession.objects.filter(emisor=self.emisor).first()
        if cached and cached.is_valid(margin_seconds=settings.VERIFACTU_SESSION_MARGIN):
            return cached.session_id
        return self.login()

    def _authenticated(self, path, body):
        """Envía una operación con la sesión vigente.

        Si VeriFactu responde que la sesión ya no existe (`Unknown SessionID`),
        se descarta la guardada, se pide otra nueva y se reintenta una sola vez.
        """
        try:
            return self._post(path, {"ServiceKey": _service_key(self.session()), **body})
        except SessionExpired:
            VerifactuSession.objects.filter(emisor=self.emisor).delete()
            return self._post(path, {"ServiceKey": _service_key(self.login()), **body})

    def registrar_factura(self, payload):
        """Envía el registro de facturación y devuelve el resultado con su estado y su QR."""
        data = self._authenticated(INVOICE_CREATE_PATH, payload)
        return data.get("Return") or {}

    def consultar_estado(self, invoice):
        """Busca en los envíos ya realizados el que corresponde a esta factura."""
        data = self._authenticated(
            INVOICE_LIST_PATH,
            {
                "Offset": 0,
                "Count": -1,
                "Filters": [
                    {
                        "FieldName": "InvoiceID",
                        "Operator": "LIKE",
                        "Value": f"'{invoice.number}'",
                    },
                ],
            },
        )
        items = data.get("Items") or []
        return items[0] if items else {}
