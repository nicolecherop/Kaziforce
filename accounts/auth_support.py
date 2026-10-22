"""Small shared helpers for sign-in readiness and session evidence."""

import time
from django.conf import settings
from django.utils.crypto import salted_hmac

AUTH_RECORDS = "account_authentication_methods"
SECURITY_ACTION = "kaziforce_security_action"
PASSWORD_BINDING = "kaziforce_signin_binding"


def signup_verification_pending(user):
    """Public signups keep a pending address until an inbox code proves ownership.

    Older accounts without an address record retain their existing sign-in flow.
    """
    from allauth.account.models import EmailAddress

    return EmailAddress.objects.filter(
        user=user, email__iexact=user.email, verified=False
    ).exists()


def signin_binding(user):
    return salted_hmac(
        "accounts.pending_signin",
        f"{user.get_session_auth_hash()}:{user.email.lower()}",
    ).hexdigest()


def email_codes_ready():
    if not settings.EMAIL_TWO_STEP_ENABLED:
        return False
    if settings.EMAIL_BACKEND == "django.core.mail.backends.locmem.EmailBackend":
        return True  # Explicit in-memory delivery for isolated automated tests only.
    return (
        settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
        and bool(settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD)
        and settings.EMAIL_HOST not in {"", "localhost"}
    )


def last_signin_method(request):
    records = request.session.get(AUTH_RECORDS, [])
    return records[-1].get("method") if records else None


def recent_google_connection(request):
    intent = request.session.get("google_connection", {})
    return (
        intent.get("user") == request.user.pk
        and time.time() - intent.get("at", 0) < 300
    )
