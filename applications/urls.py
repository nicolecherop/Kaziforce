from django.urls import path
from . import views
from . import interview_views

app_name = "applications"
urlpatterns = [
    path(
        "<uuid:application_id>/interview/",
        interview_views.interview_edit,
        name="interview_edit",
    ),
    path(
        "<uuid:application_id>/interview/cancel/",
        interview_views.interview_cancel,
        name="interview_cancel",
    ),
    path(
        "<uuid:application_id>/interview/email/",
        interview_views.interview_email_retry,
        name="interview_email_retry",
    ),
    path("inbox/", views.inbox, name="inbox"),
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
