from django.conf import settings
from django.shortcuts import render
from allauth.socialaccount.providers.google.views import oauth2_login, oauth2_callback


def google_login(request):
    if not settings.GOOGLE_SIGNIN_ENABLED:
        return render(request, "accounts/signin_unavailable.html", status=503)
    return oauth2_login(request)


def google_callback(request):
    if not settings.GOOGLE_SIGNIN_ENABLED:
        return render(request, "accounts/signin_unavailable.html", status=503)
    return oauth2_callback(request)
