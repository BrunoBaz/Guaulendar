"""VeriFactu simulada, solo para probar el flujo en local sin credenciales reales.

Se activa con VERIFACTU_FAKE_API=1 y DEBUG=True (ver `invoices.get_client`).
Nunca debe usarse en producción: el ajuste queda desactivado cuando DEBUG es False.
"""

import base64
import struct
import zlib

import httpx

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _fake_qr_png(size=180, module=6):
    """Devuelve un PNG en base64 con un patrón tipo QR, para que la pantalla muestre algo."""
    cells = size // module
    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            cx, cy = x // module, y // module
            border = cx in (0, cells - 1) or cy in (0, cells - 1)
            dark = border or (cx * 7 + cy * 13 + (cx ^ cy)) % 3 == 0
            row += b"\x00\x00\x00" if dark else b"\xff\xff\xff"
        rows.append(b"\x00" + bytes(row))
    raw = b"".join(rows)

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    png = _PNG_SIGNATURE + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    return base64.b64encode(png).decode("ascii")


def fake_transport(register_estado="Correcto", status_estado="Correcto"):
    """Transporte de httpx que imita a VeriFactu sin salir a la red.

    Responde con la misma forma que la API real: un objeto `Result` cuyo `Return`
    lleva el resultado de la operación, y `Items` en las consultas.
    """
    counter = {"last_id": 0}
    qr_image = _fake_qr_png()

    def result(estado):
        counter["last_id"] += 1
        return {
            "ExternKey": f"FAKE-{counter['last_id']:06d}",
            "StatusResponse": estado,
            "ErrorCode": None,
            "ErrorDescription": None,
            "CSV": "FAKE-CSV",
            "QrCode": qr_image,
            "QrCodeUrl": "https://example.test/verifactu.bmp",
            "ValidationUrl": "https://example.test/validar",
        }

    def handler(request):
        if request.url.path.endswith("/Server/Security/"):
            return httpx.Response(200, json={"ResultCode": 0, "ResultMessage": "OK", "Return": "FAKE-SESSION"})
        if request.url.path.endswith("/Invoices/GetFilteredList"):
            return httpx.Response(
                200,
                json={"ResultCode": 0, "ResultMessage": "OK", "Items": [result(status_estado)]},
            )
        return httpx.Response(
            200,
            json={"ResultCode": 0, "ResultMessage": "OK", "Return": result(register_estado)},
        )

    return httpx.MockTransport(handler)
