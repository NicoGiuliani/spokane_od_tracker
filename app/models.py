from django.db import models


class Incident(models.Model):
    datetime = models.DateTimeField(unique=True)
    location = models.CharField(max_length=100)
    number_affected = models.IntegerField()
    narcan_doses_administered = models.IntegerField(null=True, blank=True)
    report_text = models.TextField(max_length=500)
    fatal_incident = models.BooleanField()

    def __str__(self):
        return f"{self.location}"
