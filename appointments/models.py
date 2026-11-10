from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction

from .choices import DISCOUNT_TYPES, PAYMENT_METHOD_CHOICES, SERVICES_CHOICES, STATUS_CHOICES
from .pricing import calculate_pricing, legacy_discount


class Appointment(models.Model):
	DISCOUNT_TYPES = DISCOUNT_TYPES
	SERVICES_CHOICES = SERVICES_CHOICES
	STATUS_CHOICES = STATUS_CHOICES
	PAYMENT_METHOD_CHOICES = PAYMENT_METHOD_CHOICES

	dog = models.ForeignKey(
		"dogs.Dog",
		on_delete=models.CASCADE,
		related_name="appointments",
	)
	service_type = models.CharField(max_length=50, choices=SERVICES_CHOICES, default="BAÑO")
	price = models.DecimalField(
		max_digits=10,
		decimal_places=2,
		default=Decimal("0.00"),
		validators=[MinValueValidator(Decimal("0.00"))],
		verbose_name="Precio aproximado (IVA incluido, €)",
	)
	discount_type = models.CharField(
		max_length=10,
		choices=DISCOUNT_TYPES,
		default="PERCENTAGE",
		verbose_name="Tipo de descuento",
	)
	discount_value = models.DecimalField(
		max_digits=10,
		decimal_places=2,
		default=Decimal("0.00"),
		validators=[MinValueValidator(Decimal("0.00"))],
		verbose_name="Descuento (%, o € según tipo)",
	)
	discounts = models.JSONField(default=list, blank=True)
	tax_rate = models.DecimalField(
		max_digits=5,
		decimal_places=2,
		default=Decimal("21.00"),
		validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
		verbose_name="IVA (%)",
	)
	date = models.DateTimeField()
	notes = models.TextField(blank=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
	payment_method = models.CharField(
		max_length=10,
		choices=PAYMENT_METHOD_CHOICES,
		blank=True,
		default="",
		verbose_name="Método de pago",
	)

	class Meta:
		db_table = "clients_appointment"

	def __str__(self):
		return f"{self.dog.name} - {self.date:%d/%m/%Y}"

	@property
	def taxable_base(self):
		return calculate_pricing(self.price, self.tax_rate, [])["taxable_base"]

	def clean(self):
		super().clean()
		if self.dog_id and not self.dog.is_active:
			raise ValidationError({"dog": "No se pueden asignar citas a un perro inactivo."})
		if self.discount_type == "PERCENTAGE" and self.discount_value > Decimal("100.00"):
			raise ValidationError({"discount_value": "El descuento porcentual no puede superar el 100 %."})
		if self.discount_type == "FIXED" and self.discount_value > self.taxable_base:
			raise ValidationError({"discount_value": "El descuento no puede superar la base imponible."})
		if self.discounts:
			try:
				calculate_pricing(self.price, self.tax_rate, self.discounts)
			except (KeyError, TypeError, ValueError) as error:
				raise ValidationError({"discounts": str(error)}) from error

	def _dog_snapshot(self):
		dog = self.dog
		return {
			"id": dog.pk,
			"name": dog.name,
			"breed": dog.breed.name if dog.breed else "",
			"sex": dog.get_sex_display() if dog.sex else "",
			"coat_type": dog.coat_type,
			"color": dog.color,
			"owners": list(
				dog.owners.order_by("name", "pk").values("pk", "name", "phone")
			),
		}

	def _audit_data(self):
		return {
			"dog": self._dog_snapshot(),
			"service_type": self.service_type,
			"date": str(self.date),
			"price": str(self.price),
			"discount_type": self.discount_type,
			"discount_value": str(self.discount_value),
			"discounts": self.discounts,
			"tax_rate": str(self.tax_rate),
			"notes": self.notes,
			"status": self.status,
			"payment_method": self.payment_method,
		}

	@transaction.atomic
	def save(self, *args, actor=None, **kwargs):
		if not self.dog.is_active:
			raise ValidationError({"dog": "No se pueden asignar citas a un perro inactivo."})

		before = type(self).objects.filter(pk=self.pk).first() if self.pk else None
		before_data = before._audit_data() if before else None
		pricing = None
		history = None
		if self.status in {"COMPLETED", "CANCELLED"}:
			discounts = self.discounts or legacy_discount(
				self.discount_type,
				self.discount_value,
			)
			try:
				pricing = calculate_pricing(self.price, self.tax_rate, discounts)
			except (KeyError, TypeError, ValueError) as error:
				raise ValidationError({"discounts": str(error)}) from error
			if self.status == "COMPLETED":
				self.discounts = pricing["discounts"]
				self.discount_type = "FIXED"
				self.discount_value = pricing["discount_amount"]

		super().save(*args, **kwargs)
		if self.status in {"COMPLETED", "CANCELLED"}:
			from historial.models import ServiceHistory

			zero = Decimal("0.00")
			if self.status == "COMPLETED":
				taxable_base = pricing["taxable_base"]
				discount_amount = pricing["discount_amount"]
				tax_amount = pricing["tax_amount"]
				total_price = pricing["total_price"]
			else:
				taxable_base = pricing["taxable_base"]
				discount_amount = total_price = zero
				tax_amount = zero

			history = ServiceHistory.objects.create(
				dog_id=self.dog_id,
				date=self.date,
				dog_snapshot=self._dog_snapshot(),
				price=self.price,
				taxable_base=taxable_base,
				service_type=self.service_type,
				status=self.status,
				discount_type=self.discount_type,
				discount_value=self.discount_value,
				discount_amount=discount_amount,
				tax_rate=self.tax_rate,
				tax_amount=tax_amount,
				total_price=total_price,
				notes=self.notes,
				discounts=self.discounts,
				payment_method=self.payment_method if self.status == "COMPLETED" else "",
			)

		after_data = self._audit_data()
		if before_data is None:
			action = (
				self.status
				if self.status in {"COMPLETED", "CANCELLED"}
				else "CREATED"
			)
		else:
			changes = {
				field: {"before": before_data[field], "after": after_data[field]}
				for field in after_data
				if before_data[field] != after_data[field]
			}
			action = self.status if self.status in {"COMPLETED", "CANCELLED"} else "UPDATED"

		if history:
			after_data["history_id"] = history.pk

		if before_data is None:
			changes = {"snapshot": after_data}
		elif history:
			changes["history_id"] = {"before": None, "after": history.pk}

		if before_data is None or changes:
			dog_snapshot = after_data["dog"]
			AppointmentAuditEvent.objects.create(
				appointment_id=self.pk,
				dog_id=self.dog_id,
				dog_name=dog_snapshot["name"],
				action=action,
				actor=actor if getattr(actor, "is_authenticated", False) else None,
				changes=changes,
			)

		if self.status in {"COMPLETED", "CANCELLED"}:
			self.delete()


class AppointmentAuditEvent(models.Model):
	ACTION_CHOICES = [
		("CREATED", "Creada"),
		("UPDATED", "Modificada"),
		("COMPLETED", "Completada"),
		("CANCELLED", "Cancelada"),
	]

	appointment_id = models.PositiveBigIntegerField()
	dog_id = models.PositiveBigIntegerField(null=True, blank=True)
	dog_name = models.CharField(max_length=150)
	action = models.CharField(max_length=20, choices=ACTION_CHOICES)
	changed_at = models.DateTimeField(auto_now_add=True)
	actor = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="appointment_audit_events",
	)
	changes = models.JSONField(default=dict)

	class Meta:
		ordering = ("-changed_at", "-pk")

	def __str__(self):
		return f"Cita #{self.appointment_id} · {self.get_action_display()}"
