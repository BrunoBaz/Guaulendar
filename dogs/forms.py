from django import forms
from django.db.models import Q
from django.utils.html import format_html, format_html_join

from clients.models import Contacts
from .models import Breed


class BreedComboboxWidget(forms.TextInput):
    """Campo de texto con la lista de razas, que se filtra según lo escrito."""

    def render(self, name, value, attrs=None, renderer=None):
        attrs = {**self.attrs, **(attrs or {})}
        options_id = f"{attrs.get('id') or f'id_{name}'}-options"
        attrs.update({
            "autocomplete": "off",
            "role": "combobox",
            "aria-autocomplete": "list",
            "aria-expanded": "false",
            "aria-controls": options_id,
            "data-breed-input": "",
        })
        options = format_html_join(
            "",
            '<li class="breed-combobox__option" role="option" data-breed-option'
            ' data-breed-value="{}">{}</li>',
            ((nombre, nombre) for nombre in Breed.objects.filter(is_active=True)
             .order_by("name").values_list("name", flat=True)),
        )
        return format_html(
            '<div class="breed-combobox" data-breed-combobox>'
            "{}"
            '<ul class="breed-combobox__options" role="listbox" id="{}" hidden>{}</ul>'
            "</div>",
            super().render(name, value, attrs, renderer),
            options_id,
            options,
        )


class ContactChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, contact):
        return f"{contact.name} - {contact.phone}"


class createNewDogForm(forms.Form):
    COAT_CHOICES = [
        ("Corto", "Corto"),
        ("Doble Capa", "Doble Capa"),
        ("Alambre", "Alambre"),
        ("Crecimiento Continuo", "Crecimiento Continuo"),
        ("Spaniel", "Spaniel"),
    ]

    name = forms.CharField(label="Nombre del perro", max_length=50)
    breed = forms.CharField(
        label="Raza",
        max_length=150,
        required=False,
        widget=BreedComboboxWidget(attrs={"placeholder": "Empieza a escribir la raza"}),
    )
    color = forms.CharField(label="Color", max_length=100, required=False)
    sex = forms.ChoiceField(label="Sexo", choices=[("M", "Macho"), ("F", "Hembra")], required=False)
    coat_type = forms.ChoiceField(label="Tipo de pelaje", choices=COAT_CHOICES, required=False)
    dog_notes = forms.CharField(label="Notas", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    dog_issues = forms.CharField(
        label="Observaciones importantes",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    is_active = forms.BooleanField(label="Perro activo", required=False, initial=True)
    owners = ContactChoiceField(
        label="Clientes existentes",
        queryset=Contacts.objects.filter(is_active=True).order_by("name"),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 4}),
    )
    new_owner_name = forms.CharField(
        label="Nombre del nuevo cliente",
        max_length=150,
        required=False,
        widget=forms.HiddenInput(),
    )
    new_owner_phone = forms.CharField(
        label="Teléfono del nuevo cliente",
        max_length=20,
        required=False,
        widget=forms.HiddenInput(),
    )

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)
        if instance is not None:
            self.initial.update({
                "name": instance.name,
                "breed": instance.breed.name if instance.breed_id else "",
                "color": instance.color,
                "sex": instance.sex,
                "coat_type": instance.coat_type,
                "dog_notes": instance.dog_notes,
                "dog_issues": instance.dog_issues,
                "is_active": instance.is_active,
                "owners": instance.owners.values_list("pk", flat=True),
            })
            self.fields["owners"].queryset = Contacts.objects.filter(
                Q(is_active=True) | Q(dogs=instance),
            ).distinct().order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        new_owner_name = cleaned_data.get("new_owner_name")
        new_owner_phone = cleaned_data.get("new_owner_phone")

        if new_owner_name and not new_owner_phone:
            self.add_error("new_owner_phone", "Indica el teléfono del nuevo cliente.")
        elif new_owner_phone and not new_owner_name:
            self.add_error("new_owner_name", "Indica el nombre del nuevo cliente.")
        elif new_owner_name and new_owner_phone and Contacts.objects.filter(
            is_active=True,
            name__iexact=new_owner_name,
            phone=new_owner_phone,
        ).exists():
            self.add_error(
                "new_owner_name",
                "Este cliente ya existe. Selecciónalo en la lista de clientes existentes.",
            )

        return cleaned_data
