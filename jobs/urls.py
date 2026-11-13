from django.urls import path
from . import saved_views, views

app_name = "jobs"
urlpatterns = [
    path("saved/", saved_views.saved_jobs, name="saved"),
    path("<uuid:job_id>/save/", saved_views.save_job, name="save"),
    path("", views.opportunities, name="opportunities"),
    path("manage/", views.manage_jobs, name="manage"),
    path("create/", views.job_edit, name="create"),
    path("<uuid:job_id>/", views.job_detail, name="detail"),
    path("<uuid:job_id>/edit/", views.job_edit, name="edit"),
    path("<uuid:job_id>/close/", views.job_close, name="close"),
]
