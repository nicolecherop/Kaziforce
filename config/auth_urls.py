"""Expose only the sign-in routes used by KaziForce, with no alternate passwordless entry."""

from django.contrib.auth.views import LogoutView
from django.urls import path
from django.views.generic import RedirectView, TemplateView
from allauth.socialaccount import views as social_views
from accounts.security_views import EmailCodeView
from accounts.google_views import google_login, google_callback

urlpatterns = [
    path(
        "login/",
        RedirectView.as_view(pattern_name="accounts:sign_in", query_string=True),
        name="account_login",
    ),
    path(
        "signup/",
        RedirectView.as_view(pattern_name="accounts:create_account"),
        name="account_signup",
    ),
    path("logout/", LogoutView.as_view(), name="account_logout"),
    path(
        "inactive/",
        TemplateView.as_view(template_name="accounts/signin_unavailable.html"),
        name="account_inactive",
    ),
    path("code/", EmailCodeView.as_view(), name="account_confirm_login_code"),
    path("google/complete/", social_views.signup, name="socialaccount_signup"),
    path(
        "connections/",
        RedirectView.as_view(pattern_name="accounts:security"),
        name="socialaccount_connections",
    ),
    path(
        "cancelled/", social_views.login_cancelled, name="socialaccount_login_cancelled"
    ),
    path("error/", social_views.login_error, name="socialaccount_login_error"),
    path("google/login/", google_login, name="google_login"),
    path("google/login/callback/", google_callback, name="google_callback"),
]
