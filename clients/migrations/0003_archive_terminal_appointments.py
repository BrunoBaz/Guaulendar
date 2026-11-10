from django.db import migrations, models
import django.db.models.deletion


def copy_appointment_fields_to_history(apps, schema_editor):
    ServiceHistory = apps.get_model("clients", "ServiceHistory")
    for history in ServiceHistory.objects.select_related("appointment").all():
        if history.appointment_id:
            history.service_type = history.appointment.service_type
            history.status = history.appointment.status
            history.save(update_fields=["service_type", "status"])


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0002_appointment_service_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicehistory",
            name="service_type",
            field=models.CharField(
                choices=[("BAÑO", "Baño"), ("CORTE", "Corte"), ("COMPLETO", "Completo"), ("OTRO", "Otro")],
                default="BAÑO",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="servicehistory",
            name="status",
            field=models.CharField(
                choices=[("PENDING", "Pending"), ("CONFIRMED", "Confirmed"), ("COMPLETED", "Completed"), ("CANCELLED", "Cancelled")],
                default="COMPLETED",
                max_length=20,
            ),
        ),
        migrations.RunPython(copy_appointment_fields_to_history, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="servicehistory",
            name="appointment",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="service_history",
                to="clients.appointment",
            ),
        ),
    ]