from django.contrib import admin

# Register your models here.
from dogs.models import Dog

from .models import Contacts


@admin.register(Contacts)
class ContactsAdmin(admin.ModelAdmin):
    search_fields = ["name", "phone"]
    autocomplete_fields = ["dogs"]
