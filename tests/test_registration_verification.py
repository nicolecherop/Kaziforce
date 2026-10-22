"""First-time email ownership is required independently of optional two-step login."""

import re
import time
from smtplib import SMTPException
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

User = get_user_model()
PASSWORD = "Q7!river-starlight-927"


@override_settings(
    EMAIL_TWO_STEP_ENABLED=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class RegistrationVerificationTests(TestCase):
    def setUp(self):
        cache.clear()

    def register(self, **changes):
        return self.client.post(
            reverse("accounts:create_account"),
            {
                "full_name": "Alex Kamau",
                "email": "alex@example.test",
                "role": "candidate",
                "password1": PASSWORD,
                "password2": PASSWORD,
                "accept_terms": "on",
                **changes,
            },
        )

    def code(self):
        return re.search(r"\b\d{6}\b", mail.outbox[-1].body).group()

    def verify(self, code=None):
        return self.client.post(
            reverse("account_confirm_login_code"),
            {
                "action": "verify",
                "code": code or self.code(),
            },
        )

    def signin(self, client=None):
        return (client or self.client).post(
            reverse("accounts:sign_in"),
            {
                "username": "alex@example.test",
                "password": PASSWORD,
            },
        )

    def test_registration_requires_code_and_only_verified_email_unlocks_workspace(self):
        self.assertRedirects(self.register(), reverse("account_confirm_login_code"))
        self.assertNotIn("_auth_user_id", self.client.session)
        address = EmailAddress.objects.get(email="alex@example.test")
        self.assertFalse(address.verified)
        self.assertEqual(
            self.client.get(reverse("accounts:dashboard")).status_code, 302
        )
        self.assertContains(
            self.client.get(reverse("account_confirm_login_code")),
            "finish creating your account",
        )
        self.assertRedirects(self.verify(), reverse("accounts:dashboard"))
        address.refresh_from_db()
        self.assertTrue(address.verified)
        self.assertEqual(int(self.client.session["_auth_user_id"]), address.user_id)
        self.assertFalse(address.user.email_two_step_enabled)
        self.client.logout()
        self.assertRedirects(self.signin(), reverse("accounts:dashboard"))

    def test_abandoned_signup_requires_verification_in_a_new_session(self):
        self.register()
        other = Client()
        self.assertRedirects(self.signin(other), reverse("account_confirm_login_code"))
        self.assertNotIn("_auth_user_id", other.session)
        self.assertFalse(EmailAddress.objects.get().verified)

    def test_wrong_code_and_password_reset_do_not_verify_registration(self):
        self.register()
        wrong = "000000" if self.code() != "000000" else "111111"
        self.verify(wrong)
        self.assertFalse(EmailAddress.objects.get().verified)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.client.post(
            reverse("accounts:password_reset"), {"email": "alex@example.test"}
        )
        self.assertFalse(EmailAddress.objects.get().verified)

    def test_expired_signup_code_cannot_verify_account(self):
        self.register()
        with patch(
            "allauth.account.internal.flows.code_verification.time.time",
            return_value=9999999999,
        ):
            self.verify()
        self.assertFalse(EmailAddress.objects.get().verified)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.signin(), reverse("account_confirm_login_code"))

    def test_signup_resend_replaces_code_without_unlocking_account(self):
        self.register()
        old = self.code()
        url = reverse("account_confirm_login_code")
        self.client.post(url, {"action": "resend"})
        self.assertEqual(len(mail.outbox), 1)
        with patch("accounts.security_views.time.time", return_value=time.time() + 61):
            self.client.post(url, {"action": "resend"})
        self.assertEqual(len(mail.outbox), 2)
        new = self.code()
        if old != new:
            self.verify(old)
            self.assertFalse(EmailAddress.objects.get().verified)
        self.assertRedirects(self.verify(new), reverse("accounts:dashboard"))

    def test_delivery_failure_leaves_registration_pending_and_can_be_retried(self):
        with patch(
            "django.core.mail.message.EmailMultiAlternatives.send",
            side_effect=SMTPException("private"),
        ):
            self.assertEqual(self.register().status_code, 503)
        self.assertFalse(EmailAddress.objects.get().verified)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.signin(), reverse("account_confirm_login_code"))
        self.assertRedirects(self.verify(), reverse("accounts:dashboard"))

    def test_disabled_email_delivery_cannot_bypass_registration_verification(self):
        with override_settings(EMAIL_TWO_STEP_ENABLED=False):
            self.assertEqual(self.register().status_code, 503)
            self.assertEqual(self.signin().status_code, 503)
        self.assertFalse(EmailAddress.objects.get().verified)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_manually_authenticated_pending_account_is_blocked(self):
        self.register()
        self.client.force_login(User.objects.get(email="alex@example.test"))
        self.assertRedirects(
            self.client.get(reverse("accounts:dashboard")), reverse("accounts:sign_in")
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(ACCOUNT_RATE_LIMITS={"login": "2/m/key"})
    def test_registration_attempts_are_rate_limited(self):
        self.register(accept_terms="")
        self.register(accept_terms="")
        self.assertEqual(self.register().status_code, 429)
        self.assertFalse(User.objects.exists())
