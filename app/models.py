from django.db import models


class Incident(models.Model):
    datetime = models.DateTimeField()
    location = models.CharField(max_length=100)
    number_affected = models.IntegerField()
    narcan_doses_administered = models.IntegerField(null=True, blank=True)
    report_text = models.TextField(max_length=500)
    fatal_incident = models.BooleanField()
    coordinates = models.CharField(
        max_length=50,  # plenty of room for "lat, lon"
        blank=True,
        null=True,
        help_text='Latitude, Longitude (e.g. "47.6567, -117.4234")',
    )

    def __str__(self):
        return f"{self.location}"
