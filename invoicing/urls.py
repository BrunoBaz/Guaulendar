from django.urls import path

from . import views

urlpatterns = [
    path(
        "invoicing/services/<uuid:public_id>/",
        views.invoice_service,
        name="invoice_service",
    ),
]
