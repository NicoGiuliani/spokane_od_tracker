from django.contrib import admin
from .models import Incident

admin.site.register(Incident)


# class IncidentAdmin(admin.ModelAdmin):
#     list_display = ("datetime", "location", "latitude", "longitude", "number_affected")
#     list_editable = ("latitude", "longitude")
