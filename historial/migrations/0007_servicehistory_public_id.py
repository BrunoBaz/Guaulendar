import uuid

from django.db import migrations, models


def set_public_ids(apps, schema_editor):
    ServiceHistory = apps.get_model("historial", "ServiceHistory")
    for service in ServiceHistory.objects.filter(public_id__isnull=True):
        service.public_id = uuid.uuid4()
        service.save(update_fields=["public_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("historial", "0006_servicehistory_emisor"),
    ]

    operations = [
        # Primero se añade sin unicidad para poder rellenar cada fila con un valor propio.
        migrations.AddField(
            model_name="servicehistory",
            name="public_id",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(set_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="servicehistory",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
