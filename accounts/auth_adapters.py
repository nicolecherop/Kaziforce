"""Keep social identity, role assignment and email verification boundaries explicit."""

from smtplib import SMTPException
from uuid import uuid4
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.internal.stagekit import clear_login
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from .auth_support import (
    SECURITY_ACTION,
    PASSWORD_BINDING,
    email_codes_ready,
    last_signin_method,
    recent_google_connection,
    signin_binding,
    signup_verification_pending,
)
from .models import User


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return (
            False  # Local registration remains the existing validated KaziForce form.
        )

    def is_login_by_code_required(self, login):
        if last_signin_method(self.request) == "code":
            return False
        user = login.user
        if not user:
            return False
        if signup_verification_pending(user):
            return True
        intent = self.request.session.get(SECURITY_ACTION, {})
        if intent.get("user") == user.pk:
            return True
        if user.is_staff and settings.EMAIL_TWO_STEP_ENABLED:
            return True
        return (
            user.email_two_step_enabled
            and last_signin_method(self.request) != "socialaccount"
        )

    def pre_login(self, request, user, **kwargs):
        response = super().pre_login(request, user, **kwargs)
        if response:
            return response
        request.session[PASSWORD_BINDING] = signin_binding(user)
        return None

    def login(self, request, user):
        # Recheck the current account after a challenge: deactivation or a password
        # change while the code is pending must invalidate the pending login.
        user.refresh_from_db()
        if (
            signup_verification_pending(user)
            or not user.is_active
            or request.session.get(PASSWORD_BINDING) != signin_binding(user)
        ):
            clear_login(request)
            logout(request)
            messages.error(request, "Your account changed. Please sign in again.")
            raise ImmediateHttpResponse(redirect("accounts:sign_in"))
        super().login(request, user)

    def post_login(self, request, user, **kwargs):
        intent = request.session.pop(SECURITY_ACTION, {})
        if intent.get("user") == user.pk and last_signin_method(request) == "code":
            enabled = intent.get("action") == "enable"
            User.objects.filter(pk=user.pk).update(email_two_step_enabled=enabled)
            user.email_two_step_enabled = enabled
            messages.success(
                request,
                "Email two-step verification is now "
                + ("enabled." if enabled else "disabled."),
            )
        request.session.pop(PASSWORD_BINDING, None)
        return super().post_login(request, user, **kwargs)

    def send_mail(self, template_prefix, email, context):
        if template_prefix == "account/email/login_code" and not email_codes_ready():
            clear_login(self.request)
            raise ImmediateHttpResponse(
                render(self.request, "accounts/email_unavailable.html", status=503)
            )
        try:
            return super().send_mail(template_prefix, email, context)
        except (SMTPException, OSError):
            clear_login(self.request)
            raise ImmediateHttpResponse(
                render(self.request, "accounts/email_unavailable.html", status=503)
            )

    def get_signup_redirect_url(self, request):
        return self.get_login_redirect_url(request)


class GoogleAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        verified = [item for item in sociallogin.email_addresses if item.verified]
        if (
            not settings.GOOGLE_SIGNIN_ENABLED
            or sociallogin.account.provider != "google"
            or not verified
        ):
            raise PermissionDenied("A verified Google email address is required.")
        if request.user.is_authenticated:
            if sociallogin.state.get(
                "process"
            ) != "connect" or not recent_google_connection(request):
                raise PermissionDenied("Start connecting Google from Account security.")
        elif (
            not sociallogin.is_existing
            and User.objects.filter(email__iexact=verified[0].email).exists()
        ):
            messages.error(
                request,
                "An account with this email already exists. Sign in first, then connect Google from Account security.",
            )
            raise ImmediateHttpResponse(redirect("accounts:sign_in"))
        if not sociallogin.is_existing:
            # Never allow a posted address to replace the Google-verified identity.
            sociallogin.user.email = verified[0].email.strip().lower()

    def is_open_for_signup(self, request, sociallogin):
        return settings.GOOGLE_SIGNIN_ENABLED

    @transaction.atomic
    def save_user(self, request, sociallogin, form=None):
        if (
            form is None
            or form.cleaned_data.get("role") not in {"candidate", "recruiter"}
            or not form.cleaned_data.get("accept_terms")
        ):
            raise PermissionDenied("Choose your account type and accept the terms.")
        user = sociallogin.user
        user.role = form.cleaned_data["role"]
        user.is_staff = user.is_superuser = False
        user.username = uuid4().hex
        user.email = form.cleaned_data["email"].strip().lower()
        user = super().save_user(request, sociallogin, form=form)
        # All new public accounts complete KaziForce's inbox-code confirmation,
        # including identities whose provider has already verified the address.
        from allauth.account.models import EmailAddress

        EmailAddress.objects.filter(user=user, email__iexact=user.email).update(
            verified=False
        )
        return user

    def get_connect_redirect_url(self, request, socialaccount):
        request.session.pop("google_connection", None)
        return "/accounts/security/"
