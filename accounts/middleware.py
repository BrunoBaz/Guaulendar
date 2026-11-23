"""Ajustes de desarrollo para que el 404 se comporte igual que en producción."""

from django.conf import settings
from django.urls import Resolver404, resolve

from .views import page_not_found


class NotFoundRedirectMiddleware:
    """Con DEBUG activo Django omite `handler404` y muestra su página de depuración.

    Este middleware replica en local el comportamiento de producción: si la
    dirección no existe, se redirige a una pantalla válida con un aviso en lugar
    de mostrar la página de error. Fuera de depuración no hace nada.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not settings.DEBUG or response.status_code != 404:
            return response
        try:
            resolve(request.path_info)
        except Resolver404 as error:
            return page_not_found(request, error)
        return response
