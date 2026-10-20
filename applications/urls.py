from django.urls import path
from . import views

app_name = "applications"
urlpatterns = [
    path("", views.my_applications, name="mine"),
    path("job/<uuid:job_id>/apply/", views.application_edit, name="edit"),
    path("job/<uuid:job_id>/applicants/", views.applicants, name="applicants"),
    path("<uuid:application_id>/", views.application_detail, name="detail"),
    path("<uuid:application_id>/status/", views.application_status, name="status"),
    path(
        "attachments/<uuid:attachment_id>/",
        views.attachment_file,
        name="attachment_file",
    ),
]
