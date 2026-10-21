from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("candidate/", include("candidates.urls")),
    path("jobs/", include("jobs.urls")),
    path("applications/", include("applications.urls")),
    path("skills/", include("matching.urls")),
    path("matches/", include("matching.results_urls")),
    path("", include("pages.urls")),
]
