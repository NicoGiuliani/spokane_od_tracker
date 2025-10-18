import calendar
from datetime import date, datetime
import math
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Sum, Max
from django.db.models.functions import TruncDate

from .models import Incident
from .forms import IncidentForm, RegistrationForm

# break out logic used in 'home' to separate functions
# add field for cardiac arrest reports
# extrapolate other data like days of week with most, hours with most
# add graph showing the month by day
# change logic to include other months; not sure what all needs to change yet

# add ability to edit posts
# delete post
# sorting for other columns
# export to csv


def home(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, "Successfully logged in")
            return redirect("home")
        else:
            messages.warning(request, "Incorrect username or password")
            return redirect("home")
    else:
        now = datetime.now()
        incident_this_month = 1
        incidents = list(Incident.objects.all().order_by("datetime"))

        for incident in incidents:
            number_affected = incident.number_affected
            if number_affected == 1:
                incident.incident_this_month = incident_this_month
            else:
                incident.incident_this_month = " - ".join(
                    [
                        str(incident_this_month),
                        str(incident_this_month + number_affected - 1),
                    ]
                )
            incident_this_month += number_affected

        sort_order = request.GET.get("sort", "desc")
        reverse = True if sort_order == "desc" else False
        incidents.sort(key=lambda x: x.datetime, reverse=reverse)

        incidents_per_day = (
            Incident.objects.annotate(date_only=TruncDate("datetime"))
            .values("date_only")
            .annotate(daily_total=Sum("number_affected"))
            .order_by("date_only")
        )

        most_in_single_day_this_month = 0
        highest_incident_date_this_month = None
        for entry in incidents_per_day:
            if entry["daily_total"] > most_in_single_day_this_month:
                most_in_single_day_this_month = entry["daily_total"]
                highest_incident_date_this_month = entry["date_only"]

        print(most_in_single_day_this_month)
        print(highest_incident_date_this_month)

        earliest_incident_date = Incident.objects.earliest("datetime").datetime.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        days_since_earliest_incident_date = (
            (now - earliest_incident_date).total_seconds() / 60 / 60 / 24
        )
        days_since_first_of_month = (
            (now - first_of_month).total_seconds() / 60 / 60 / 24
        )

        OD_count_today = Incident.objects.filter(datetime__date=date.today()).aggregate(
            total_today=Sum("number_affected")
        )["total_today"]

        OD_count_since_earliest = Incident.objects.filter(
            datetime__gte=earliest_incident_date
        ).aggregate(total_ods=Sum("number_affected"))["total_ods"]

        fatalities_since_earliest_incident_date = (
            Incident.objects.filter(datetime__gte=earliest_incident_date)
            .filter(fatal_incident=True)
            .count()
        )

        average_time_between_ods_in_hours = (
            days_since_earliest_incident_date / OD_count_since_earliest * 24
        )

        average_time_between_ods_in_hours_str = f"{math.floor(average_time_between_ods_in_hours)} hours, {math.floor((average_time_between_ods_in_hours % 1) * 60)} minutes"

        average_incidents_per_day = (
            OD_count_since_earliest / days_since_earliest_incident_date
        )
        average_fatal_incidents_per_day = (
            fatalities_since_earliest_incident_date / days_since_earliest_incident_date
        )

        days_in_current_month = calendar.monthrange(now.year, now.month)[1]
        end_of_current_month = datetime(
            now.year, now.month, days_in_current_month, 23, 59, 59, 999999
        )
        time_remaining_in_month = end_of_current_month - now
        days_remaining_in_month = time_remaining_in_month.total_seconds() / 60 / 60 / 24
        projected_additional_ods_by_month_end = (
            days_remaining_in_month * average_incidents_per_day
        )

        projected_end_of_month_total = math.floor(
            OD_count_since_earliest + projected_additional_ods_by_month_end
        )

        return render(
            request,
            "home.html",
            {
                "incidents": incidents,
                "earliest_date": earliest_incident_date.date,
                "OD_count_today": OD_count_today,
                "OD_count_since_earliest": OD_count_since_earliest,
                "fatalities_since_earliest_incident_date": fatalities_since_earliest_incident_date,
                "average_incidents_per_day": average_incidents_per_day,
                "average_fatal_incidents_per_day": average_fatal_incidents_per_day,
                "average_time_between_ods_in_hours_str": average_time_between_ods_in_hours_str,
                "projected_end_of_month_total": projected_end_of_month_total,
                "incidents_per_day": incidents_per_day,
                "highest_incident_date_this_month": highest_incident_date_this_month,
                "most_in_single_day_this_month": most_in_single_day_this_month,
            },
        )


def add_incident(request):
    if request.method == "POST":
        form = IncidentForm(request.POST)
        if form.is_valid():
            form.save()
            location = form.cleaned_data["location"]
            messages.success(request, f"Successfully added incident: {location}")
            return redirect("home")
        else:
            return render(request, "incident.html", {"form": form})
    else:
        form = IncidentForm()
    return render(request, "incident.html", {"form": form})


def logout_user(request):
    username = request.user.username
    logout(request)
    messages.success(request, f"{username} has been logged out")
    return redirect("home")


def register_user(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password1"]
            user = authenticate(request, username=username, password=password)
            login(request, user)
            messages.success(request, f"Successfully registered user {user.username}")
            return redirect("home")
        return render(request, "register.html", {"form": form})
    else:
        form = RegistrationForm()
    return render(request, "register.html", {"form": form})
