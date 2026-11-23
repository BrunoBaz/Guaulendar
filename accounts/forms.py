from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from invoicing.models import (
    TAXPAYER_TYPE_CHOICES,
    Emisor,
    EmisorMember,
    VerifactuConfig,
    emisor_heredado,
)


class EmailAuthenticationForm(AuthenticationForm):
    """Acceso con el email: es el nombre de usuario de la cuenta."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email"
        self.fields["username"].widget.attrs.update(
            {"autofocus": True, "autocomplete": "email"}
        )


class RegisterForm(forms.ModelForm):
    """Alta pública: crea la cuenta de acceso y el negocio que emitirá las facturas.

    Al guardar quedan vinculados el usuario, su identidad fiscal (Emisor) y su
    conexión con VeriFactu (VerifactuConfig), sin un segundo alta manual.
    """

    password1 = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Repite la contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    business_name = forms.CharField(
        max_length=150,
        required=False,
        label="Nombre o razón social",
    )
    first_name = forms.CharField(max_length=75, required=False, label="Nombre")
    last_name = forms.CharField(max_length=75, required=False, label="Apellidos")
    trade_name = forms.CharField(
        max_length=150,
        required=False,
        label="Nombre comercial",
    )
    nif = forms.CharField(max_length=20, label="NIF")
    taxpayer_type = forms.ChoiceField(
        choices=TAXPAYER_TYPE_CHOICES,
        initial="INDIVIDUAL",
        label="Tipo de persona",
    )
    fiscal_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Domicilio fiscal",
    )

    class Meta:
        model = get_user_model()
        fields = ("email",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "Email"
        self.fields["email"].required = True

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if get_user_model().objects.filter(username=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con ese email.")
        return email

    def clean_nif(self):
        nif = (self.cleaned_data.get("nif") or "").strip().upper()
        existing = Emisor.objects.filter(nif=nif)
        heredado = emisor_heredado()
        if heredado is not None:
            # El negocio heredado se reclama al registrarse: no cuenta como duplicado.
            existing = existing.exclude(pk=heredado.pk)
        if existing.exists():
            raise forms.ValidationError("Ya hay un negocio dado de alta con ese NIF.")
        return nif

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password1")
        if password and password != cleaned_data.get("password2"):
            self.add_error("password2", "Las dos contraseñas no coinciden.")
        elif password:
            try:
                validate_password(password, self.instance)
            except forms.ValidationError as error:
                self.add_error("password1", error)

        # La AEAT exige el nombre completo de la persona física, separado del NIF,
        # para poder validarlo; en personas jurídicas vale la razón social.
        if cleaned_data.get("taxpayer_type") == "INDIVIDUAL":
            if not cleaned_data.get("first_name"):
                self.add_error("first_name", "Indica el nombre de la persona física.")
            if not cleaned_data.get("last_name"):
                self.add_error("last_name", "Indica los apellidos de la persona física.")
        elif not cleaned_data.get("business_name"):
            self.add_error("business_name", "Indica la razón social del negocio.")
        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        user.set_password(self.cleaned_data["password1"])
        if not commit:
            return user

        user.save()
        if self.cleaned_data["taxpayer_type"] == "INDIVIDUAL":
            # El emisor de una persona física se identifica con nombre y apellidos.
            emisor_name = " ".join(
                part
                for part in (
                    self.cleaned_data["first_name"].strip(),
                    self.cleaned_data["last_name"].strip(),
                )
                if part
            )
        else:
            emisor_name = self.cleaned_data["business_name"].strip()
        emisor = emisor_heredado()
        if emisor is None:
            emisor = Emisor.objects.create(
                name=emisor_name,
                trade_name=self.cleaned_data["trade_name"],
                nif=self.cleaned_data["nif"],
                taxpayer_type=self.cleaned_data["taxpayer_type"],
                fiscal_address=self.cleaned_data["fiscal_address"],
                series_prefix=settings.VERIFACTU_SERIES_PREFIX,
            )
        else:
            # El primer registro reclama el negocio que ya tenía los datos: se
            # actualizan sus datos fiscales en lugar de crear uno nuevo.
            emisor.name = emisor_name
            emisor.trade_name = self.cleaned_data["trade_name"]
            emisor.nif = self.cleaned_data["nif"]
            emisor.taxpayer_type = self.cleaned_data["taxpayer_type"]
            emisor.fiscal_address = self.cleaned_data["fiscal_address"]
            emisor.series_prefix = settings.VERIFACTU_SERIES_PREFIX
            emisor.save()
        EmisorMember.objects.create(emisor=emisor, user=user, role="OWNER")
        VerifactuConfig.objects.get_or_create(
            emisor=emisor,
            defaults={"email": self.cleaned_data["email"]},
        )
        return user
