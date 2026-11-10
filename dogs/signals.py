from django.db import transaction
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from clients.models import Contacts

from .models import Dog


def remove_appointments_for_inactive_dog(dog_id):
    from appointments.models import Appointment

    Appointment.objects.filter(dog_id=dog_id).delete()


def deactivate_if_no_active_owners(dog_id):
    dogs_without_active_owners = (
        Dog.objects.filter(pk=dog_id, is_active=True)
        .exclude(owners__is_active=True)
    )
    if dogs_without_active_owners.update(is_active=False):
        remove_appointments_for_inactive_dog(dog_id)


@receiver(m2m_changed, sender=Dog.owners.through)
def deactivate_dog_without_owners(sender, instance, action, **kwargs):
    if action not in {"post_add", "post_remove", "post_clear"} or not instance.pk:
        return

    def deactivate_if_unowned():
        if not Contacts.objects.filter(dogs__pk=instance.pk, is_active=True).exists():
            deactivate_if_no_active_owners(instance.pk)
            instance.is_active = False

    transaction.on_commit(deactivate_if_unowned)


@receiver(post_save, sender=Contacts)
def deactivate_dogs_without_active_owners(sender, instance, **kwargs):
    if instance.is_active:
        return

    dog_ids = Dog.objects.filter(
        owners=instance,
        is_active=True,
    ).values_list("pk", flat=True)
    for dog_id in dog_ids:
        deactivate_if_no_active_owners(dog_id)


@receiver(post_save, sender=Dog)
def remove_appointments_when_dog_is_inactive(sender, instance, **kwargs):
    if not instance.is_active:
        remove_appointments_for_inactive_dog(instance.pk)
