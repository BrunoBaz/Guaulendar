from django.contrib import admin

from .models import Breed, Dog


@admin.register(Dog)
class DogAdmin(admin.ModelAdmin):
	search_fields = ["name", "breed__name"]
	list_display = ["name", "breed", "sex"]
	list_filter = ["breed", "sex"]


@admin.register(Breed)
class BreedAdmin(admin.ModelAdmin):
	search_fields = ["name"]
