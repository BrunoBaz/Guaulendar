from decimal import Decimal

from django.db import models

from appointments.choices import (
	DISCOUNT_TYPES,
	PAYMENT_METHOD_CHOICES,
	SERVICES_CHOICES,
	STATUS_CHOICES,
)


class ServiceHistory(models.Model):
	dog = models.ForeignKey(
		"dogs.Dog",
		on_delete=models.PROTECT,
		related_name="service_history",
	)
	date = models.DateTimeField()
	price = models.DecimalField(
		max_digits=10,
		decimal_places=2,
		default=Decimal("0.00"),
		verbose_name="Precio con IVA (€)",
	)
	taxable_base = models.DecimalField(
		max_digits=10,
		decimal_places=2,
		default=Decimal("0.00"),
		verbose_name="Base imponible (€)",
	)
	service_type = models.CharField(max_length=50, choices=SERVICES_CHOICES, default="BAÑO")
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="COMPLETED")
	dog_snapshot = models.JSONField(default=dict, blank=True)
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
		verbose_name="Descuento configurado",
	)
	discounts = models.JSONField(default=list, blank=True)
	discount_amount = models.DecimalField(
		max_digits=10,
		decimal_places=2,
		default=Decimal("0.00"),
		verbose_name="Descuento aplicado (€)",
	)
	tax_rate = models.DecimalField(
		max_digits=5,
		decimal_places=2,
		default=Decimal("21.00"),
		verbose_name="IVA (%)",
	)
	tax_amount = models.DecimalField(
		max_digits=10,
		decimal_places=2,
		default=Decimal("0.00"),
		verbose_name="IVA (€)",
	)
	total_price = models.DecimalField(
		max_digits=10,
		decimal_places=2,
		default=Decimal("0.00"),
		verbose_name="Total cobrado (€)",
	)
	payment_method = models.CharField(
		max_length=10,
		choices=PAYMENT_METHOD_CHOICES,
		blank=True,
		default="",
		verbose_name="Método de pago",
	)
	notes = models.TextField(blank=True)

	class Meta:
		db_table = "clients_servicehistory"

	def __str__(self):
		return f"{self.dog.name} - {self.date:%d/%m/%Y}"
