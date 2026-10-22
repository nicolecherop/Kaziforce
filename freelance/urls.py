from django.urls import path
from . import profile_views, project_views, booking_views, message_views

app_name = "freelance"
urlpatterns = [
    path("", profile_views.home, name="home"),
    path("profile/", profile_views.my_profile, name="profile"),
    path("profile/edit/", profile_views.profile_edit, name="profile_edit"),
    path("find/", profile_views.find, name="find"),
    path("workers/<uuid:pk>/", profile_views.profile_detail, name="worker"),
    path("projects/", project_views.projects, name="projects"),
    path("projects/new/", project_views.project_edit, name="project_create"),
    path("projects/<uuid:pk>/", project_views.project_detail, name="project_detail"),
    path("projects/<uuid:pk>/edit/", project_views.project_edit, name="project_edit"),
    path("messages/", message_views.inbox, name="inbox"),
    path("messages/<uuid:pk>/", message_views.conversation, name="conversation"),
    path(
        "messages/<uuid:pk>/controls/",
        message_views.conversation_controls,
        name="conversation_controls",
    ),
    path(
        "messages/<uuid:conversation_id>/book/",
        booking_views.booking_create,
        name="book",
    ),
    path("bookings/", booking_views.bookings, name="bookings"),
    path("bookings/<uuid:pk>/", booking_views.booking_detail, name="booking"),
    path(
        "bookings/<uuid:booking_id>/payments/<uuid:pk>/",
        booking_views.payment_action,
        name="payment_action",
    ),
]
