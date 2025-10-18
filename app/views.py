from datetime import date
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Sum

from .models import Incident
from .forms import IncidentForm, RegistrationForm

# widen table
# number of the month
# add ability to edit posts
# average time between reports
# delete post
# sorting for other columns
# export to csv
# break out logic used in 'home' to separate functions
# set datetimes to unique ids to avoid dupes ???
# add section for follow-ups ???


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
        sort_order = request.GET.get("sort", "desc")
        ordering = "datetime" if sort_order == "asc" else "-datetime"
        earliest_date = Incident.objects.earliest("datetime").datetime.date()
        days_since_earliest_date = (date.today() - earliest_date).days
        OD_count_today = Incident.objects.filter(datetime__date=date.today()).count()
        OD_count_since_earliest = Incident.objects.filter(
            datetime__gte=earliest_date
        ).aggregate(total_ods=Sum("number_affected"))["total_ods"]
        print(OD_count_since_earliest)
        fatal_incidents_since_earliest = (
            Incident.objects.filter(datetime__gte=earliest_date)
            .filter(fatal_incident=True)
            .count()
        )
        incidents = Incident.objects.all().order_by(ordering)
        average_incidents_per_day = OD_count_since_earliest / days_since_earliest_date
        average_fatal_incidents_per_day = (
            fatal_incidents_since_earliest / days_since_earliest_date
        )
        return render(
            request,
            "home.html",
            {
                "incidents": incidents,
                "earliest_date": earliest_date,
                "OD_count_today": OD_count_today,
                "OD_count_since_earliest": OD_count_since_earliest,
                "fatal_incidents_since_earliest": fatal_incidents_since_earliest,
                "average_incidents_per_day": average_incidents_per_day,
                "average_fatal_incidents_per_day": average_fatal_incidents_per_day,
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
