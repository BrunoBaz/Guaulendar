import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Prefetch

from clients.models import Contacts
from dogs.models import Dog
from .models import Appointment
from .pricing import calculate_pricing


class DogChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, dog):
        owners = ", ".join(
            f"{owner.name} (no priorizar)" if owner.descartable else owner.name
            for owner in dog.owners.all()
        )
        if owners:
            return f"{dog.name} · {owners}"
        return f"{dog.name} · Sin responsable"


class AppointmentForm(forms.ModelForm):
    discounts_json = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Appointment
        fields = (
            "dog",
            "service_type",
            "date",
            "price",
            "notes",
            "status",
            "payment_method",
        )
        widgets = {
            "service_type": forms.Select(attrs={"class": "appointment-create-dialog__input"}),
            "date": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={
                    "type": "datetime-local",
                    "class": "appointment-create-dialog__input",
                    "step": "1800",
                },
            ),
            "price": forms.NumberInput(
                attrs={
                    "class": "appointment-create-dialog__input",
                    "min": "0",
                    "step": "0.01",
                }
            ),
            "status": forms.Select(attrs={"class": "appointment-create-dialog__input"}),
            "payment_method": forms.HiddenInput(),
            "notes": forms.Textarea(
                attrs={
                    "class": "appointment-create-dialog__input",
                    "rows": 3,
                    "placeholder": "Detalles que conviene tener en cuenta",
                }
            ),
        }
        labels = {
            "service_type": "Servicio",
            "date": "Fecha y hora",
            "price": "Precio aproximado (€)",
            "notes": "Notas",
            "status": "Estado",
            "payment_method": "Método de pago",
        }

    dog = DogChoiceField(
        queryset=Dog.objects.none(),
        label="Perro · responsable",
        empty_label=None,
        widget=forms.Select(
            attrs={
                "class": "appointment-create-dialog__input appointment-dog-select",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["dog"].queryset = (
            Dog.objects.filter(is_active=True)
            .prefetch_related(
                Prefetch(
                    "owners",
                    queryset=Contacts.objects.filter(is_active=True).order_by("name"),
                )
            )
            .order_by("name", "pk")
        )
        self.fields["price"].required = False
        self.fields["price"].initial = self.fields["price"].initial or "0.00"
        self.fields["notes"].required = False
        self.fields["status"].required = False
        if not self.instance.pk:
            self.fields["status"].initial = "PENDING"
        self.fields["discounts_json"].initial = json.dumps(
            self.instance.discounts if self.instance.pk else [],
        )

    def clean_price(self):
        return self.cleaned_data.get("price") or self.instance.price or 0

    def clean_status(self):
        return self.cleaned_data.get("status") or self.instance.status or "PENDING"

    def clean_discounts_json(self):
        raw_discounts = self.cleaned_data.get("discounts_json") or "[]"
        try:
            discounts = json.loads(raw_discounts)
        except json.JSONDecodeError as error:
            raise ValidationError("La lista de descuentos no tiene un formato válido.") from error

        if not isinstance(discounts, list):
            raise ValidationError("La lista de descuentos no tiene un formato válido.")

        cleaned_discounts = []
        for discount in discounts:
            if not isinstance(discount, dict) or discount.get("type") not in {"PERCENTAGE", "FIXED"}:
                raise ValidationError("Hay un tipo de descuento no válido.")
            try:
                value = Decimal(str(discount.get("value", "")))
                value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            except InvalidOperation as error:
                raise ValidationError("Indica un importe válido para cada descuento.") from error
            if not value.is_finite() or value < 0:
                raise ValidationError("Los descuentos deben ser importes positivos.")
            if discount["type"] == "PERCENTAGE" and value > Decimal("100.00"):
                raise ValidationError("Un descuento porcentual no puede superar el 100 %.")
            description = discount.get("description", "")
            if not isinstance(description, str):
                raise ValidationError("La descripción del descuento debe ser texto.")
            cleaned_discounts.append({
                "type": discount["type"],
                "value": format(value, "f"),
                "description": description.strip()[:200],
            })
        return cleaned_discounts

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("status") == "COMPLETED":
            if not cleaned_data.get("payment_method"):
                self.add_error("payment_method", "Selecciona si el pago fue en efectivo o con tarjeta.")
            discounts = cleaned_data.get("discounts_json", [])
            try:
                calculate_pricing(
                    cleaned_data.get("price") or self.instance.price or 0,
                    self.instance.tax_rate or Decimal("21.00"),
                    discounts,
                )
            except (KeyError, TypeError, ValueError) as error:
                self.add_error(None, str(error))
        return cleaned_data

    def save(self, commit=True):
        appointment = super().save(commit=False)
        appointment.discounts = (
            [] if appointment.status == "CANCELLED"
            else self.cleaned_data.get("discounts_json", [])
        )
        if appointment.status == "COMPLETED":
            pricing = calculate_pricing(
                appointment.price,
                appointment.tax_rate,
                appointment.discounts,
            )
            appointment.discount_type = "FIXED"
            appointment.discount_value = pricing["discount_amount"]
        if commit:
            appointment.save()
            self.save_m2m()
        return appointment
