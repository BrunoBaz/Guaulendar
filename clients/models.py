
import uuid

from django.db import models


class Contacts(models.Model):
    emisor = models.ForeignKey(
        "invoicing.Emisor",
        on_delete=models.CASCADE,
        related_name="contacts",
        null=True,
    )
    # Identificador opaco que se usa en las URLs: no revela el orden global de altas.
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    nif = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="NIF",
    )
    is_active = models.BooleanField(default=True)
    descartable = models.BooleanField(default=False)

    dogs = models.ManyToManyField(
        "dogs.Dog",
        related_name="owners",
        blank=True
    )

    def __str__(self):
        return self.name
