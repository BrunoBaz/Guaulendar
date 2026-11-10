from django.contrib import admin

from .models import Appointment, AppointmentAuditEvent


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
	autocomplete_fields = ["dog"]
	list_display = ["dog", "date", "status", "price"]
	list_filter = ["status", "date"]
	search_fields = ["dog__name"]
	ordering = ["-date"]

	def save_model(self, request, obj, form, change):
		obj.save(actor=request.user)


@admin.register(AppointmentAuditEvent)
class AppointmentAuditEventAdmin(admin.ModelAdmin):
	list_display = ("changed_at", "action", "appointment_id", "dog_name", "actor")
	list_filter = ("action", "changed_at")
	search_fields = ("dog_name", "=appointment_id", "actor__username")
	readonly_fields = (
		"appointment_id",
		"dog_id",
		"dog_name",
		"action",
		"changed_at",
		"actor",
		"changes",
	)

	def has_add_permission(self, request):
		return False

	def has_delete_permission(self, request, obj=None):
		return False
