from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from appointments.models import Appointment
from dogs.models import Dog
from historial.models import ServiceHistory
from invoicing.models import emisor_for_user

from .forms import createNewContactForm
from .models import Contacts


@login_required
def contacts(request):
    emisor = emisor_for_user(request.user)
    if emisor is None:
        raise Http404("La cuenta no tiene ningún negocio asignado.")
    status_filter = request.GET.get("status", "all")
    if status_filter not in {"all", "active", "inactive"}:
        status_filter = "all"
    contacts = Contacts.objects.filter(emisor=emisor).prefetch_related(
        Prefetch(
            "dogs",
            queryset=Dog.objects.filter(is_active=True).select_related("breed"),
            to_attr="active_dogs",
        )
    ).order_by("name", "pk")
    if status_filter == "active":
        contacts = contacts.filter(is_active=True)
    elif status_filter == "inactive":
        contacts = contacts.filter(is_active=False)

    edit_contact = None
    if request.method == "POST":
        contact_id = request.POST.get("contact_id")
        contact_action = request.POST.get("contact_action")
        edit_contact = (
            get_object_or_404(Contacts, pk=contact_id, emisor=emisor)
            if contact_id and contact_action == "edit"
            else None
        )
        if contact_id and contact_action in {"activate", "deactivate"}:
            contact = get_object_or_404(Contacts, pk=contact_id, emisor=emisor)
            contact.is_active = contact_action == "activate"
            contact.save(update_fields=["is_active"])
            return redirect("contacts")

        form = createNewContactForm(request.POST, instance=edit_contact)
        if form.is_valid():
            contact = edit_contact or Contacts(emisor=emisor)
            contact.name = form.cleaned_data["name"]
            contact.phone = form.cleaned_data["phone"]
            contact.nif = form.cleaned_data["nif"]
            if not edit_contact:
                contact.is_active = True
            contact.descartable = form.cleaned_data["descartable"]
            contact.save()
            return redirect("contacts")
    else:
        form = createNewContactForm()

    return render(
        request,
        "clients/contacts.html",
        {
            "contacts": contacts,
            "form": form,
            "edit_contact": edit_contact,
            "status_filter": status_filter,
        },
    )


@login_required
def contact_detail(request, public_id):
    emisor = emisor_for_user(request.user)
    if emisor is None:
        raise Http404("La cuenta no tiene ningún negocio asignado.")
    contact = get_object_or_404(Contacts, public_id=public_id, emisor=emisor)
    dogs = (
        contact.dogs.filter(is_active=True)
        .select_related("breed")
        .order_by("name", "pk")
    )
    appointments = (
        Appointment.objects.filter(dog__owners__pk=contact.pk)
        .select_related("dog")
        .order_by("-date", "-pk")
    )
    service_history = (
        ServiceHistory.objects.filter(dog__owners__pk=contact.pk)
        .select_related("dog")
        .order_by("-date", "-pk")
    )
    return render(
        request,
        "clients/contact_detail.html",
        {
            "contact": contact,
            "dogs": dogs,
            "appointments": appointments,
            "service_history": service_history,
        },
    )
