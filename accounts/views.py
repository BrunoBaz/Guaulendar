from urllib.parse import urlsplit

from django.contrib import messages
from django.contrib.auth import login, views as auth_views
from django.shortcuts import redirect, render
from django.urls import Resolver404, reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.defaults import page_not_found as default_page_not_found

from .forms import RegisterForm

HOME_URL_NAME = "appointments"


def register(request):
    """Registro público: la cuenta y su negocio emisor se crean en un solo paso."""
    if request.user.is_authenticated:
        return redirect(HOME_URL_NAME)

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(
            request,
            "Cuenta creada. Tu negocio ya está configurado para emitir facturas.",
        )
        return redirect(HOME_URL_NAME)

    return render(request, "accounts/register.html", {"form": form})


class PasswordChangeView(auth_views.PasswordChangeView):
    """Cambio de contraseña de la cuenta que tiene la sesión abierta."""

    template_name = "accounts/password_change.html"
    success_url = reverse_lazy(HOME_URL_NAME)

    def form_valid(self, form):
        messages.success(self.request, "Contraseña actualizada.")
        return super().form_valid(form)


def offline(request):
    """Aviso que muestra el service worker cuando no hay conexión."""
    return render(request, "accounts/offline.html")


def page_not_found(request, exception):
    """404 de una dirección que no existe: se avisa y se vuelve a una pantalla válida.

    Solo actúa cuando la URL no resuelve (`Resolver404`). Los 404 que lanza una vista
    (un perro de otro negocio, una cuenta sin negocio asignado) siguen siendo un 404.
    """
    if not isinstance(exception, Resolver404):
        return default_page_not_found(request, exception)

    if not request.user.is_authenticated:
        return redirect("login")

    messages.error(request, "No se pudo acceder a esa página: la dirección no existe.")
    return redirect(_return_url(request))


def _return_url(request):
    """Pantalla desde la que se intentó el acceso y, si no se sabe, la pantalla general."""
    referer = request.META.get("HTTP_REFERER", "")
    allowed = {request.get_host()}
    if referer and url_has_allowed_host_and_scheme(
        referer, allowed, require_https=request.is_secure()
    ):
        if urlsplit(referer).path != request.path:
            return referer
    return reverse(HOME_URL_NAME)
