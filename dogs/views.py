from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render

from appointments.forms import AppointmentForm
from appointments.models import Appointment
from clients.forms import createNewContactForm
from clients.models import Contacts
from historial.models import ServiceHistory

from .forms import createNewDogForm
from .models import Dog


def dogs_list(request):
    status_filter = request.GET.get("status", "all")
    if status_filter not in {"all", "active", "inactive"}:
        status_filter = "all"
    dogs = Dog.objects.select_related("breed")
    if status_filter == "active":
        dogs = dogs.filter(is_active=True)
    elif status_filter == "inactive":
        dogs = dogs.filter(is_active=False)
    dogs = (
        dogs
        .prefetch_related(
            Prefetch(
                "owners",
                queryset=Contacts.objects.filter(is_active=True),
            ),
            Prefetch(
                "owners",
                queryset=Contacts.objects.order_by("name", "pk"),
                to_attr="all_owners",
            ),
        )
        .order_by("name", "pk")
    )
    form = createNewDogForm()
    contact_form = createNewContactForm()
    edit_dog = None
    if request.method == "POST":
        dog_id = request.POST.get("dog_id")
        edit_dog = get_object_or_404(Dog, pk=dog_id) if dog_id else None
        if edit_dog and request.POST.get("dog_action") == "deactivate":
            edit_dog.is_active = False
            edit_dog.save(update_fields=["is_active"])
            return redirect("dogs_list")

        form = createNewDogForm(request.POST, instance=edit_dog)
        if form.is_valid():
            with transaction.atomic():
                dog = edit_dog or Dog()
                dog.name = form.cleaned_data["name"]
                dog.breed = form.cleaned_data["breed"]
                dog.color = form.cleaned_data["color"]
                dog.sex = form.cleaned_data["sex"]
                dog.coat_type = form.cleaned_data["coat_type"]
                dog.dog_notes = form.cleaned_data["dog_notes"]
                dog.dog_issues = form.cleaned_data["dog_issues"]
                dog.is_active = form.cleaned_data["is_active"] if edit_dog else True
                dog.save()
                dog.owners.set(form.cleaned_data["owners"])

                if form.cleaned_data["new_owner_name"]:
                    new_owner = Contacts.objects.create(
                        name=form.cleaned_data["new_owner_name"],
                        phone=form.cleaned_data["new_owner_phone"],
                    )
                    dog.owners.add(new_owner)

                if not dog.owners.exists() and dog.is_active:
                    dog.is_active = False
                    dog.save(update_fields=["is_active"])

            return redirect("dogs_list")

    return render(
        request,
        "dogs/dogs_list.html",
        {
            "dogs": dogs,
            "form": form,
            "contact_form": contact_form,
            "edit_dog": edit_dog,
            "status_filter": status_filter,
        },
    )


def dog_detail(request, dog_id):
    dog = get_object_or_404(
        Dog.objects.select_related("breed").prefetch_related(
            Prefetch(
                "owners",
                queryset=Contacts.objects.order_by("name", "pk"),
            )
        ),
        pk=dog_id,
    )
    appointments = dog.appointments.filter(
        dog__is_active=True,
    ).order_by("-date", "-pk")
    service_history = dog.service_history.order_by("-date", "-pk")
    is_editing_dog = (
        request.method == "POST"
        and request.POST.get("dog_action") == "edit"
    )
    dog_form = createNewDogForm(
        request.POST if is_editing_dog else None,
        instance=dog,
    )
    appointment_form = AppointmentForm(
        request.POST if request.method == "POST" and not is_editing_dog else None,
        initial={"dog": dog.pk},
    )
    appointment_form.fields["dog"].queryset = Dog.objects.filter(
        pk=dog.pk,
        is_active=True,
    )
    if is_editing_dog:
        if dog_form.is_valid():
            if (
                dog_form.cleaned_data["is_active"]
                and not dog.owners.filter(is_active=True).exists()
            ):
                dog_form.add_error(
                    "is_active",
                    "Para activar el perro, asocia primero al menos un responsable activo.",
                )
            else:
                with transaction.atomic():
                    dog.name = dog_form.cleaned_data["name"]
                    dog.breed = dog_form.cleaned_data["breed"]
                    dog.color = dog_form.cleaned_data["color"]
                    dog.sex = dog_form.cleaned_data["sex"]
                    dog.coat_type = dog_form.cleaned_data["coat_type"]
                    dog.dog_notes = dog_form.cleaned_data["dog_notes"]
                    dog.dog_issues = dog_form.cleaned_data["dog_issues"]
                    dog.is_active = dog_form.cleaned_data["is_active"]
                    dog.save()
                return redirect("dog_detail", dog_id=dog.pk)
    elif request.method == "POST":
        if not dog.is_active:
            appointment_form.add_error(
                None,
                "No se puede crear una cita para un perro inactivo.",
            )
        elif appointment_form.is_valid():
            appointment = appointment_form.save(commit=False)
            appointment.dog = dog
            appointment.status = "PENDING"
            appointment.save(
                actor=request.user if request.user.is_authenticated else None,
            )
            return redirect("dog_detail", dog_id=dog.pk)

    return render(
        request,
        "dogs/dog_detail.html",
        {
            "dog": dog,
            "appointments": appointments,
            "service_history": service_history,
            "appointment_form": appointment_form,
            "dog_form": dog_form,
        },
    )
