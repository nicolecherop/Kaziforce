from django.urls import path
from . import cv_views, document_views, views

app_name = "candidates"
urlpatterns = [
    path(
        "documents/<uuid:document_id>/import/", cv_views.start_import, name="cv_import"
    ),
    path("profile/import/<slug:token>/", cv_views.review_import, name="cv_review"),
    path("profile/import/<slug:token>/save/", cv_views.save_import, name="cv_save"),
    path("profile/", views.profile, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("documents/", document_views.documents, name="documents"),
    path(
        "documents/<uuid:document_id>/file/",
        document_views.document_file,
        name="document_file",
    ),
    path(
        "documents/<uuid:document_id>/delete/",
        document_views.document_delete,
        name="document_delete",
    ),
    path("cv/", document_views.documents, name="cv_upload"),
]
