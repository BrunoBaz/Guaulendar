import os

from django.conf import settings
from django.db import migrations

DATA_MODELS = (
    ("dogs", "Dog"),
    ("clients", "Contacts"),
    ("appointments", "Appointment"),
    ("historial", "ServiceHistory"),
)


def assign_initial_emisor(apps, schema_editor):
    """Vincula con un negocio inicial todo lo que se dio de alta antes del multitenancy.

    El negocio toma el nombre y el NIF de VERIFACTU_EMISOR_* si no hay ninguno
    creado todavía. En una base de datos nueva no se crea nada.
    """
    Emisor = apps.get_model("invoicing", "Emisor")
    EmisorMember = apps.get_model("invoicing", "EmisorMember")
    VerifactuConfig = apps.get_model("invoicing", "VerifactuConfig")
    models = [apps.get_model(app_label, name) for app_label, name in DATA_MODELS]

    emisor = Emisor.objects.order_by("pk").first()
    if emisor is None:
        if not any(model.objects.exists() for model in models):
            return
        emisor = Emisor.objects.create(
            name=os.environ.get("VERIFACTU_EMISOR_NAME") or "Mi peluquería",
            nif=os.environ.get("VERIFACTU_EMISOR_NIF") or "SIN-NIF",
            series_prefix=os.environ.get("VERIFACTU_SERIES_PREFIX") or "FAC",
        )

    VerifactuConfig.objects.get_or_create(
        emisor=emisor,
        defaults={"email": os.environ.get("VERIFACTU_EMAIL", "")},
    )

    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    for user in User.objects.all():
        EmisorMember.objects.get_or_create(
            emisor=emisor,
            user=user,
            defaults={"role": "OWNER"},
        )

    for model in models:
        model.objects.filter(emisor__isnull=True).update(emisor=emisor)


def unassign_initial_emisor(apps, schema_editor):
    """Vuelve a dejar los datos sin negocio; no se elimina ninguna fila."""
    for app_label, name in DATA_MODELS:
        apps.get_model(app_label, name).objects.update(emisor=None)


class Migration(migrations.Migration):

    dependencies = [
        ("invoicing", "0002_remove_emisor_verifactu_email_and_more"),
        ("dogs", "0004_dog_emisor"),
        ("clients", "0009_contacts_emisor"),
        ("appointments", "0006_appointment_emisor"),
        ("historial", "0006_servicehistory_emisor"),
    ]

    operations = [
        migrations.RunPython(assign_initial_emisor, unassign_initial_emisor),
    ]
