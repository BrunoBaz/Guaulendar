
from django.db import models


class Contacts(models.Model):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    descartable = models.BooleanField(default=False)

    dogs = models.ManyToManyField(
        "dogs.Dog",
        related_name="owners",
        blank=True
    )

    def __str__(self):
        return self.name
