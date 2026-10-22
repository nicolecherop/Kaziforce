from django.conf import settings
from .auth_support import email_codes_ready


def auth_options(request):
    return {
        "google_signin_enabled": settings.GOOGLE_SIGNIN_ENABLED,
        "email_codes_ready": email_codes_ready(),
    }
