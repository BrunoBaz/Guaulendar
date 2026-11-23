import uuid

from django.db import migrations, models


def set_public_ids(apps, schema_editor):
    Contacts = apps.get_model("clients", "Contacts")
    for contact in Contacts.objects.filter(public_id__isnull=True):
        contact.public_id = uuid.uuid4()
        contact.save(update_fields=["public_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0009_contacts_emisor"),
    ]

    operations = [
        # Primero se añade sin unicidad para poder rellenar cada fila con un valor propio.
        migrations.AddField(
            model_name="contacts",
            name="public_id",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(set_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="contacts",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
