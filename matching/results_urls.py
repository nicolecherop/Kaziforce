from django.urls import path
from . import result_views as views

app_name = "matches"
urlpatterns = [
    path("applicants/", views.applicant_workspace, name="workspace"),
    path("jobs/", views.job_matches, name="jobs"),
    path("jobs/refresh/", views.refresh_jobs, name="refresh_jobs"),
    path("job/<uuid:job_id>/applicants/", views.applicant_rankings, name="applicants"),
    path(
        "job/<uuid:job_id>/applicants/refresh/",
        views.refresh_applicants,
        name="refresh_applicants",
    ),
    path("result/<uuid:result_id>/", views.match_detail, name="detail"),
]
