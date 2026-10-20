from django.urls import path
from . import document_views, views

app_name = "candidates"
urlpatterns = [
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
