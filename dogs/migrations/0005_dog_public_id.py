import uuid

from django.db import migrations, models


def set_public_ids(apps, schema_editor):
    Dog = apps.get_model("dogs", "Dog")
    for dog in Dog.objects.filter(public_id__isnull=True):
        dog.public_id = uuid.uuid4()
        dog.save(update_fields=["public_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("dogs", "0004_dog_emisor"),
    ]

    operations = [
        # Primero se añade sin unicidad para poder rellenar cada fila con un valor propio.
        migrations.AddField(
            model_name="dog",
            name="public_id",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(set_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="dog",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
