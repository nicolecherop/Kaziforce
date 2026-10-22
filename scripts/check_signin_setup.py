"""Inspect sign-in readiness without displaying secrets; optionally send a self-test email."""

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def main():
    import django

    django.setup()
    from django.conf import settings
    from django.core.mail import get_connection, send_mail
    from accounts.auth_support import email_codes_ready

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--test-email",
        action="store_true",
        help="Send one setup message to the configured sender account itself.",
    )
    options = parser.parse_args()
    smtp_ready = bool(
        settings.EMAIL_HOST_USER
        and settings.EMAIL_HOST_PASSWORD
        and settings.EMAIL_HOST == "smtp.gmail.com"
    )
    print(
        "Google credentials: "
        + ("configured" if settings.GOOGLE_SIGNIN_ENABLED else "not configured")
    )
    print(
        "Gmail SMTP credentials: " + ("configured" if smtp_ready else "not configured")
    )
    print(
        "Email two-step verification: "
        + ("available" if email_codes_ready() else "not activated")
    )
    if options.test_email:
        if not smtp_ready:
            raise SystemExit(
                "Complete the local Gmail SMTP settings first. No message was sent."
            )
        try:
            connection = get_connection("django.core.mail.backends.smtp.EmailBackend")
            sent = send_mail(
                "KaziForce email setup check",
                "KaziForce can submit email using this sender account. Once you receive this message, you can activate email two-step verification and test a real sign-in code.",
                settings.DEFAULT_FROM_EMAIL,
                [settings.EMAIL_HOST_USER],
                connection=connection,
            )
        except Exception:
            raise SystemExit(
                "The setup email could not be sent. Check the local credentials, TLS settings and connection; no secrets were printed."
            ) from None
        if sent != 1:
            raise SystemExit("No setup message was sent.")
        print(
            "Setup message accepted by SMTP. Check the sender account's inbox and spam folder before activating verification."
        )


if __name__ == "__main__":
    main()
