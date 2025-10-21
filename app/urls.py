from django.urls import path
from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("<str:time_period>", views.home, name="home"),
    path("add_incident/", views.add_incident, name="add_incident"),
    path("register/", views.register_user, name="register"),
    path("logout/", views.logout_user, name="logout"),
]
