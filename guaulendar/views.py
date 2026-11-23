"""Vistas del proyecto que no pertenecen a ninguna aplicación concreta."""

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string


def service_worker(request):
    """Sirve el service worker desde la raíz para que controle toda la aplicación.

    El navegador solo deja que un service worker controle las rutas que cuelgan de
    su propia carpeta: servido en `/sw.js` su alcance es la web entera, no solo
    `/static/`.
    """
    content = render_to_string("sw.js", {"asset_version": settings.ASSET_VERSION})
    response = HttpResponse(content, content_type="application/javascript")
    # El navegador tiene que poder detectar cada versión nueva: nunca se cachea.
    response["Cache-Control"] = "no-cache"
    return response
