"""Invalidate older password-only sessions when email verification is required."""

from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from .auth_support import last_signin_method, signup_verification_pending


class VerifiedSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated:
            if signup_verification_pending(user):
                logout(request)
                return redirect("accounts:sign_in")
            required = user.email_two_step_enabled or (
                user.is_staff and settings.EMAIL_TWO_STEP_ENABLED
            )
            method = last_signin_method(request)
            passed = method == "code" or (
                method == "socialaccount" and not user.is_staff
            )
            if required and not passed:
                logout(request)
                return redirect("accounts:sign_in")
        return self.get_response(request)
