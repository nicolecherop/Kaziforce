from django.urls import path
from . import views

app_name = "mpesa"
urlpatterns = [
    path("bookings/<uuid:booking_id>/", views.booking_payments, name="booking"),
    path(
        "bookings/<uuid:booking_id>/<uuid:pk>/check/", views.check_status, name="check"
    ),
    path("callback/", views.callback, name="callback"),
]
