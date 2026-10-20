from django.urls import path
from django.views.generic import TemplateView

app_name = "pages"
urlpatterns = [
    path(
        "",
        TemplateView.as_view(
            template_name="pages/landing.html", extra_context={"is_landing": True}
        ),
        name="home",
    ),
    path(
        "privacy/",
        TemplateView.as_view(template_name="pages/privacy.html"),
        name="privacy",
    ),
    path(
        "terms/", TemplateView.as_view(template_name="pages/terms.html"), name="terms"
    ),
    path("help/", TemplateView.as_view(template_name="pages/help.html"), name="help"),
]
