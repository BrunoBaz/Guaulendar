"""
URL configuration for guaulendar project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

from appointments.views import appointments
from clients.views import contact_detail, contacts
from dogs.views import dog_detail, dogs_list
from historial.views import service_history, service_history_detail

urlpatterns = [
    path('admin/', admin.site.urls),
    path('contacts/', contacts, name='contacts'),
    path('contacts/<int:contact_id>/', contact_detail, name='contact_detail'),
    path('dogs/', dogs_list, name='dogs_list'),
    path('dogs/<int:dog_id>/', dog_detail, name='dog_detail'),
    path('service_history/', service_history, name='service_history'),
    path('service_history/<int:history_id>/', service_history_detail, name='service_history_detail'),
    path('', appointments, name='appointments'),

    path('__reload__/', include('django_browser_reload.urls')),
]
