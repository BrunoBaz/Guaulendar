from django.contrib import admin

from .models import ServiceHistory


@admin.register(ServiceHistory)
class ServiceHistoryAdmin(admin.ModelAdmin):
	list_display = [
		"dog",
		"date",
		"service_type",
		"status",
		"price",
		"taxable_base",
		"discount_amount",
		"tax_amount",
		"total_price",
	]
