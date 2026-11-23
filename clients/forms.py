from django import forms

class createNewContactForm(forms.Form):
    name = forms.CharField(
        label="Nombre completo",
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "id": "contact-name",
                "placeholder": "Ej. Ana García",
                "autocomplete": "name",
            }
        ),
    )
    phone = forms.CharField(
        label="Teléfono",
        max_length=20,
        widget=forms.TelInput(
            attrs={
                "id": "contact-phone",
                "placeholder": "Ej. 600 123 456",
                "autocomplete": "tel",
            }
        ),
    )

    nif = forms.CharField(
        label="NIF",
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "id": "contact-nif",
                "placeholder": "Ej. 12345678Z",
                "autocomplete": "off",
            }
        ),
    )

    descartable = forms.BooleanField(label="Contacto descartable", required=False)

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)
        if instance is not None:
            self.initial.update({
                "name": instance.name,
                "phone": instance.phone,
                "nif": instance.nif,
                "is_active": instance.is_active,
                "descartable": instance.descartable,
            })