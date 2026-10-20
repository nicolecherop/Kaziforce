from django.urls import path
from django.views.generic import TemplateView

app_name = "accounts"
urlpatterns = [
    path("sign-in/", TemplateView.as_view(template_name="accounts/sign_in.html"), name="sign_in"),
    path("create-account/", TemplateView.as_view(template_name="accounts/create_account.html"), name="create_account"),
]
