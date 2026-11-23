import uuid

from django.db import models


class Breed(models.Model):
	name = models.CharField(max_length=150, unique=True)
	description = models.TextField(blank=True)
	is_active = models.BooleanField(default=True)

	class Meta:
		db_table = "clients_breed"

	def __str__(self):
		return self.name

	@classmethod
	def get_or_create_by_name(cls, name):
		name = (name or "").strip()
		if not name:
			return None
		return cls.objects.filter(name__iexact=name).first() or cls.objects.create(name=name)


class Dog(models.Model):
	SEX_CHOICES = [("M", "Macho"), ("F", "Hembra")]

	emisor = models.ForeignKey(
		"invoicing.Emisor",
		on_delete=models.CASCADE,
		related_name="dogs",
		null=True,
	)
	# Identificador opaco que se usa en las URLs: no revela el orden global de altas.
	public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
	name = models.CharField(max_length=50)
	breed = models.ForeignKey(
		Breed,
		on_delete=models.PROTECT,
		related_name="dogs",
		null=True,
		blank=True,
	)
	sex = models.CharField(max_length=1, choices=SEX_CHOICES, blank=True)
	coat_type = models.CharField(max_length=150, blank=True)
	color = models.CharField(max_length=200, blank=True)
	dog_notes = models.TextField(blank=True)
	dog_issues = models.TextField(blank=True)
	is_active = models.BooleanField(default=True)

	class Meta:
		db_table = "clients_dog"

	def __str__(self):
		return self.name
