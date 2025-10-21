import calendar
from datetime import date, datetime, timedelta
import math
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Sum, Max
from django.db.models.functions import TruncDate
import matplotlib.pyplot as plt
import io, base64

from .models import Incident
from .forms import IncidentForm, RegistrationForm


# add date of most recent fatal incident
# have separate page for fatal incidents across all time
# verify that data is correct for each type of filtering
# reverse the order shown in "totals per day" to most recent first
# extrapolate other data like days of week with most, hours with most
# look at chart.js to see if it can render a better looking chart
# hide graph at a certain width to preserve other windows
# add a "not found" type page when a filter is applied to a month without data
# add field for cardiac arrest reports
# sorting for other columns
# export to csv


def enumerate_incidents(incidents):
    incident_this_month = 1
    month = 0
    for incident in incidents:
        if incident.datetime.month != month:
            if month == 0:
                month = incident.datetime.month
                pass
            else:
                incident_this_month = 1
                month = incident.datetime.month
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
    return incidents


def get_incidents_per_day(time_period, earliest_incident_date, end_of_month):
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    end_of_month_year = end_of_month.year
    end_of_month_month = end_of_month.month
    is_current_month = (
        current_year == end_of_month_year and current_month == end_of_month_month
    )

    start_date = earliest_incident_date.replace(day=1)
    end_date = now if is_current_month else end_of_month

    if time_period == "all_time":
        queryset = Incident.objects.all()
        end_date = now
    else:
        end_date = now if is_current_month else end_of_month
        queryset = Incident.objects.filter(
            datetime__range=(earliest_incident_date.date(), end_of_month.date()),
        )
    data = (
        queryset.annotate(date_only=TruncDate("datetime"))
        .values("date_only")
        .annotate(daily_total=Sum("number_affected"))
        .order_by("date_only")
    )
    by_date = {entry["date_only"]: entry["daily_total"] for entry in data}

    filled_data = []
    current = start_date
    while current <= end_date:
        filled_data.append(
            {"date_only": current.date(), "daily_total": by_date.get(current.date(), 0)}
        )
        current += timedelta(days=1)
    return filled_data


def sort_incidents(incidents, sort_order):
    reverse = True if sort_order == "desc" else False
    incidents.sort(key=lambda x: x.datetime, reverse=reverse)


def get_highest_incident_day(incidents_per_day):
    most_in_single_day_this_month = 0
    highest_incident_date_this_month = None
    for entry in incidents_per_day:
        if entry["daily_total"] > most_in_single_day_this_month:
            most_in_single_day_this_month = entry["daily_total"]
            highest_incident_date_this_month = entry["date_only"]
    return highest_incident_date_this_month, most_in_single_day_this_month


def get_od_count_today():
    return Incident.objects.filter(datetime__date=date.today()).aggregate(
        total_today=Sum("number_affected")
    )["total_today"]


def get_ods_since_earliest_incident_date(
    earliest_incident_date, end_of_month, time_period
):
    if time_period == "all_time":
        end_of_month = datetime.now()
    return Incident.objects.filter(
        datetime__range=(earliest_incident_date, end_of_month)
    ).aggregate(total_ods=Sum("number_affected"))["total_ods"]


def get_fatalities_since_earliest_incident_date(
    earliest_incident_date, end_of_month, time_period
):
    if time_period == "all_time":
        end_of_month = datetime.now()
    return (
        Incident.objects.filter(datetime__range=(earliest_incident_date, end_of_month))
        .filter(fatal_incident=True)
        .count()
    )


def get_earliest_incident_date(time_period):
    if time_period == "all_time":
        first_incident_on_record = Incident.objects.earliest(
            "datetime"
        ).datetime.replace(hour=0, minute=0, second=0, microsecond=0)
        return first_incident_on_record
    elif time_period == None:
        start_of_current_month = datetime.now().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        return start_of_current_month
    else:
        year, month = map(lambda x: int(x), time_period.split("-"))
        return datetime(year, month, day=1, hour=0, minute=0, second=0, microsecond=0)


def get_projected_end_of_month_total(
    end_of_month,
    average_incidents_per_day,
    OD_count_since_earliest_incident_date,
):
    if (end_of_month - datetime.now()) < timedelta(0):
        projected_additional_ods_by_month_end = 0
    else:
        time_remaining_in_month = end_of_month - datetime.now()
        days_remaining_in_month = time_remaining_in_month.total_seconds() / 60 / 60 / 24
        projected_additional_ods_by_month_end = (
            days_remaining_in_month * average_incidents_per_day
        )

    return math.floor(
        OD_count_since_earliest_incident_date + projected_additional_ods_by_month_end
    )


def get_time_span_between_fatal_incidents(average_fatal_incidents_per_day):
    if average_fatal_incidents_per_day == 0:
        return "None"
    one_fatal_incident_every_x_days = 1 / average_fatal_incidents_per_day
    return f"{math.floor(one_fatal_incident_every_x_days)} days, {math.floor((one_fatal_incident_every_x_days % 1) * 24)} hours, {math.floor(((one_fatal_incident_every_x_days % 1) * 24) % 1 * 60)} minutes"


def get_average_time_between_ods_in_hours(
    days_since_earliest_incident_date, OD_count_since_earliest_incident_date
):
    average_time_between_ods_in_hours = (
        days_since_earliest_incident_date / OD_count_since_earliest_incident_date * 24
    )

    return f"{math.floor(average_time_between_ods_in_hours)} hours, {math.floor((average_time_between_ods_in_hours % 1) * 60)} minutes"


def get_graphic(time_period, incidents_per_day):
    now = datetime.now()
    title = (
        f"In {calendar.month_name[now.month]}"
        if time_period != "all_time"
        else "Across All Time"
    )
    x = [item["date_only"] for item in incidents_per_day]
    y = [item["daily_total"] for item in incidents_per_day]

    plt.figure(figsize=(8, 3.5))
    plt.bar(x, y, color="teal")
    plt.xlabel("Date")

    plt.xticks(x, [d.strftime("%b %d") for d in x], rotation=45, ha="right")

    if len(x) <= 31:
        plt.xticks(x, [d.strftime("%b %d") for d in x], rotation=45, ha="right")
    else:
        step = 31
        plt.xticks(
            x[::step], [d.strftime("%b %d") for d in x[::step]], rotation=45, ha="right"
        )

    plt.ylabel("Total Incidents")
    plt.title(f"Incidents Per Day { title }")
    plt.tight_layout()

    # Save to a bytes buffer
    buffer = io.BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()

    # Encode to base64 to embed directly in HTML
    graphic = base64.b64encode(image_png).decode("utf-8")
    return graphic


def get_time_range():
    earliest_incident_on_record = Incident.objects.earliest(
        "datetime"
    ).datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    years = reversed(range(earliest_incident_on_record.year, datetime.now().year + 1))
    months = [
        (1, "January"),
        (2, "February"),
        (3, "March"),
        (4, "April"),
        (5, "May"),
        (6, "June"),
        (7, "July"),
        (8, "August"),
        (9, "September"),
        (10, "October"),
        (11, "November"),
        (12, "December"),
    ]
    return months, years


def home(request, time_period=None):
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
        current_month = now.strftime("%Y-%m")
        time_period = request.GET.get("time_period", current_month)

        # if time_period is not provided, will return the 1st of the current month
        earliest_incident_date = get_earliest_incident_date(time_period)
        last_day = calendar.monthrange(
            earliest_incident_date.year, earliest_incident_date.month
        )[1]
        end_of_month = datetime(
            earliest_incident_date.year,
            earliest_incident_date.month,
            last_day,
            23,
            59,
            59,
            999999,
        )

        time_span = earliest_incident_date.date()

        if time_period == "all_time":
            incidents = Incident.objects.all()
        elif time_period == current_month:
            incidents = Incident.objects.filter(
                datetime__year=earliest_incident_date.year,
                datetime__month=earliest_incident_date.month,
            )
        else:
            incidents = Incident.objects.filter(
                datetime__range=(earliest_incident_date, end_of_month)
            )

        incidents = enumerate_incidents(list(incidents.order_by("datetime")))

        sort_order = request.GET.get("sort", "desc")
        sort_incidents(incidents, sort_order)

        incidents_per_day = get_incidents_per_day(
            time_period, earliest_incident_date, end_of_month
        )

        highest_incident_date_this_month, most_in_single_day_this_month = (
            get_highest_incident_day(incidents_per_day)
        )

        OD_count_today = get_od_count_today()

        if time_period == "all_time" or time_period == current_month:
            days_since_earliest_incident_date = (
                (now - earliest_incident_date).total_seconds() / 60 / 60 / 24
            )
        else:
            days_since_earliest_incident_date = (
                (end_of_month - earliest_incident_date).total_seconds() / 60 / 60 / 24
            )

        OD_count_since_earliest_incident_date = get_ods_since_earliest_incident_date(
            earliest_incident_date, end_of_month, time_period
        )

        fatalities_since_earliest_incident_date = (
            get_fatalities_since_earliest_incident_date(
                earliest_incident_date, end_of_month, time_period
            )
        )

        average_incidents_per_day = (
            OD_count_since_earliest_incident_date / days_since_earliest_incident_date
        )
        average_fatal_incidents_per_day = (
            fatalities_since_earliest_incident_date / days_since_earliest_incident_date
        )

        average_time_between_ods_in_hours_str = get_average_time_between_ods_in_hours(
            days_since_earliest_incident_date, OD_count_since_earliest_incident_date
        )

        one_fatal_incident_every_x_days_str = get_time_span_between_fatal_incidents(
            average_fatal_incidents_per_day
        )

        projected_end_of_month_total = get_projected_end_of_month_total(
            end_of_month,
            average_incidents_per_day,
            OD_count_since_earliest_incident_date,
        )

        graphic = get_graphic(time_period, incidents_per_day)

        months, years = get_time_range()

        return render(
            request,
            "home.html",
            {
                "time_span": time_span,
                "incidents": incidents,
                "earliest_date": earliest_incident_date.date,
                "OD_count_today": OD_count_today,
                "OD_count_since_earliest_incident_date": OD_count_since_earliest_incident_date,
                "fatalities_since_earliest_incident_date": fatalities_since_earliest_incident_date,
                "average_incidents_per_day": round(average_incidents_per_day, 5),
                "average_fatal_incidents_per_day": round(
                    average_fatal_incidents_per_day, 5
                ),
                "one_fatal_incident_every_x_days_str": one_fatal_incident_every_x_days_str,
                "average_time_between_ods_in_hours_str": average_time_between_ods_in_hours_str,
                "projected_end_of_month_total": projected_end_of_month_total,
                "incidents_per_day": incidents_per_day,
                "highest_incident_date_this_month": highest_incident_date_this_month,
                "most_in_single_day_this_month": most_in_single_day_this_month,
                "graph": graphic,
                "months": months,
                "years": years,
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
