"""Email-code sessions, admin boundaries and explicit Google identity linking."""

import re
from smtplib import SMTPException
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount, SocialLogin
from accounts.auth_adapters import GoogleAccountAdapter
from accounts.auth_support import SECURITY_ACTION

User = get_user_model()
PASSWORD = "Q7!river-starlight-927"


@override_settings(
    EMAIL_TWO_STEP_ENABLED=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class EmailSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="secure-user",
            email="alex@example.test",
            password=PASSWORD,
            email_two_step_enabled=True,
        )

    def begin(self, **extra):
        return self.client.post(
            reverse("accounts:sign_in"),
            {"username": self.user.email, "password": PASSWORD, **extra},
        )

    def code(self):
        return re.search(r"\b\d{6}\b", mail.outbox[-1].body).group()

    def verify(self, value=None):
        return self.client.post(
            reverse("account_confirm_login_code"),
            {"code": value or self.code(), "action": "verify"},
        )

    def test_password_does_not_authenticate_until_code_verified(self):
        self.assertRedirects(self.begin(), reverse("account_confirm_login_code"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(
            self.client.get(reverse("accounts:dashboard")).status_code, 302
        )
        page = self.client.get(reverse("account_confirm_login_code"))
        self.assertContains(page, "a***@example.test")
        self.assertNotContains(page, self.code())
        self.assertRedirects(self.verify(), reverse("accounts:dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
        self.assertNotIn("account_login", self.client.session)

    def test_wrong_codes_are_limited_and_cannot_be_reused_after_lockout(self):
        self.begin()
        good = self.code()
        wrong = "000000" if good != "000000" else "111111"
        for _ in range(5):
            self.verify(wrong)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertNotIn("account_login", self.client.session)
        self.verify(good)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_expired_code_requires_starting_again(self):
        self.begin()
        with patch(
            "allauth.account.internal.flows.code_verification.time.time",
            return_value=9999999999,
        ):
            self.verify()
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertNotIn("account_login", self.client.session)

    def test_code_is_bound_to_the_requesting_session(self):
        self.begin()
        other = Client()
        other.post(reverse("account_confirm_login_code"), {"code": self.code()})
        self.assertNotIn("_auth_user_id", other.session)
        self.verify()
        self.client.logout()
        self.verify()
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_resend_has_cooldown_and_replaces_previous_code(self):
        self.begin()
        old = self.code()
        url = reverse("account_confirm_login_code")
        self.client.post(url, {"action": "resend"})
        self.assertEqual(len(mail.outbox), 1)
        import time

        later = time.time() + 61
        with patch("accounts.security_views.time.time", return_value=later):
            self.client.post(url, {"action": "resend"})
        self.assertEqual(len(mail.outbox), 2)
        new = self.code()
        if old != new:
            self.verify(old)
            self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.verify(new), reverse("accounts:dashboard"))

    def test_smtp_failure_never_authenticates(self):
        with patch(
            "django.core.mail.message.EmailMultiAlternatives.send",
            side_effect=SMTPException("private detail"),
        ):
            response = self.begin()
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, "private detail", status_code=503)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_disabling_delivery_does_not_bypass_an_enrolled_account(self):
        with override_settings(EMAIL_TWO_STEP_ENABLED=False):
            self.assertEqual(self.begin().status_code, 503)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_password_change_or_deactivation_invalidates_pending_login(self):
        for change in ("password", "active"):
            with self.subTest(change=change):
                self.client.logout()
                self.user.is_active = True
                self.user.set_password(PASSWORD)
                self.user.save()
                self.begin()
                if change == "password":
                    self.user.set_password("Another-long-password!24")
                else:
                    self.user.is_active = False
                self.user.save()
                self.verify()
                self.assertNotIn("_auth_user_id", self.client.session)

    def test_external_next_is_rejected_through_code_stage(self):
        self.begin(next="https://untrusted.example/")
        self.assertRedirects(self.verify(), reverse("accounts:dashboard"))

    def test_changing_signin_email_invalidates_a_pending_code(self):
        self.begin()
        User.objects.filter(pk=self.user.pk).update(email="replacement@example.test")
        self.verify()
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_existing_authenticated_session_is_removed_during_challenge(self):
        other = User.objects.create_user(username="other", email="other@example.test")
        self.client.force_login(other)
        self.begin()
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_enrollment_and_disable_require_password_and_inbox_confirmation(self):
        self.user.email_two_step_enabled = False
        self.user.save()
        self.client.force_login(self.user)
        url = reverse("accounts:security")
        self.client.post(url, {"action": "enable", "password": "wrong"})
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_two_step_enabled)
        self.client.post(url, {"action": "enable", "password": PASSWORD})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_two_step_enabled)
        self.verify()
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_two_step_enabled)
        self.client.post(url, {"action": "disable", "password": PASSWORD})
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_two_step_enabled)
        self.verify()
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_two_step_enabled)

    def test_admin_login_cannot_bypass_code(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.email_two_step_enabled = False
        self.user.save()
        response = self.client.post(
            reverse("admin:login"),
            {
                "username": self.user.email,
                "password": PASSWORD,
                "next": reverse("admin:index"),
            },
        )
        self.assertRedirects(response, reverse("account_confirm_login_code"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.verify(), reverse("admin:index"))
        self.client.post(
            reverse("accounts:security"), {"action": "disable", "password": PASSWORD}
        )
        self.assertNotIn(SECURITY_ACTION, self.client.session)

    def test_old_password_only_sessions_are_invalidated(self):
        self.client.force_login(self.user)
        self.assertRedirects(
            self.client.get(reverse("accounts:dashboard")), reverse("accounts:sign_in")
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_google_and_passwordless_entry_are_unavailable_without_configuration(self):
        with override_settings(GOOGLE_SIGNIN_ENABLED=False):
            self.assertEqual(self.client.post(reverse("google_login")).status_code, 503)
        self.assertEqual(self.client.get("/accounts/auth/login/code/").status_code, 404)
        self.assertEqual(
            self.client.get("/accounts/auth/password/reset/").status_code, 404
        )

    def test_code_submission_requires_csrf(self):
        self.begin()
        client = Client(enforce_csrf_checks=True)
        client.cookies = self.client.cookies
        self.assertEqual(
            client.post(
                reverse("account_confirm_login_code"), {"code": self.code()}
            ).status_code,
            403,
        )

    def test_repeated_password_attempts_are_rate_limited(self):
        with override_settings(ACCOUNT_RATE_LIMITS={"login": "2/m/key"}):
            self.begin()
            self.begin()
            self.assertEqual(self.begin().status_code, 429)

    def test_security_settings_cannot_be_changed_without_csrf(self):
        self.user.email_two_step_enabled = False
        self.user.save()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(
            client.post(
                reverse("accounts:security"), {"action": "enable", "password": PASSWORD}
            ).status_code,
            403,
        )

    def test_resending_does_not_extend_original_expiry(self):
        self.begin()
        session = self.client.session
        process = session["account_login"]["state"]["stages"]["login_by_code"]["data"]
        original = process["at"]
        import time

        with patch("accounts.security_views.time.time", return_value=time.time() + 61):
            self.client.post(
                reverse("account_confirm_login_code"), {"action": "resend"}
            )
        process = self.client.session["account_login"]["state"]["stages"][
            "login_by_code"
        ]["data"]
        self.assertEqual(process["at"], original)


@override_settings(GOOGLE_SIGNIN_ENABLED=True)
class GoogleIdentityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="existing", email="alex@example.test", password=PASSWORD
        )

    def social(self, email="new@example.test", verified=True):
        return SocialLogin(
            user=User(email=email, first_name="Alex", is_staff=True, is_superuser=True),
            account=SocialAccount(provider="google", uid="google-subject-123"),
            email_addresses=[
                EmailAddress(email=email, verified=verified, primary=True)
            ],
        )

    def request(self, signed_in=False):
        from django.contrib.auth.models import AnonymousUser
        from django.contrib.messages.storage.fallback import FallbackStorage

        request = RequestFactory().get("/")
        request.user = self.user if signed_in else AnonymousUser()
        request.session = self.client.session
        request._messages = FallbackStorage(request)
        return request

    def test_matching_email_never_links_automatically(self):
        request = self.request()
        with self.assertRaises(ImmediateHttpResponse):
            GoogleAccountAdapter().pre_social_login(
                request, self.social("ALEX@example.test")
            )
        self.assertFalse(SocialAccount.objects.exists())

    def test_unverified_google_email_is_refused(self):
        with self.assertRaises(PermissionDenied):
            GoogleAccountAdapter().pre_social_login(
                self.request(), self.social(verified=False)
            )

    def test_connection_requires_explicit_recent_security_action(self):
        request = self.request(signed_in=True)
        social = self.social()
        social.state["process"] = "connect"
        with self.assertRaises(PermissionDenied):
            GoogleAccountAdapter().pre_social_login(request, social)
        import time

        request.session["google_connection"] = {"user": self.user.pk, "at": time.time()}
        GoogleAccountAdapter().pre_social_login(request, social)

    def test_signup_form_cannot_choose_privileged_role_or_edit_verified_email(self):
        from accounts.social_forms import GoogleSignupForm

        request = self.request()
        social = self.social()
        with patch("allauth.core.context.request", request):
            form = GoogleSignupForm(
                {
                    "email": "attacker@example.test",
                    "role": "administrator",
                    "accept_terms": "on",
                },
                sociallogin=social,
            )
            self.assertFalse(form.is_valid())
            form = GoogleSignupForm(
                {
                    "email": "attacker@example.test",
                    "role": "recruiter",
                    "accept_terms": "on",
                },
                sociallogin=social,
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["email"], "new@example.test")

    def test_new_google_account_keeps_selected_public_role_without_privileges(self):
        from accounts.social_forms import GoogleSignupForm

        request = self.request()
        social = self.social()
        with patch("allauth.core.context.request", request):
            form = GoogleSignupForm(
                {"role": "recruiter", "accept_terms": "on"}, sociallogin=social
            )
            self.assertTrue(form.is_valid(), form.errors)
            user = GoogleAccountAdapter().save_user(request, social, form)
        self.assertEqual(user.role, "recruiter")
        self.assertFalse(
            user.is_staff or user.is_superuser or user.has_usable_password()
        )
        self.assertEqual(user.email, "new@example.test")
        self.assertTrue(SocialAccount.objects.filter(user=user).exists())


@override_settings(
    GOOGLE_SIGNIN_ENABLED=True,
    SOCIALACCOUNT_PROVIDERS={
        "google": {
            "APPS": [{"client_id": "test-client", "secret": "test-secret", "key": ""}],
            "SCOPE": ["profile", "email"],
            "OAUTH_PKCE_ENABLED": True,
        }
    },
)
class GoogleCallbackTests(TestCase):
    def setUp(self):
        cache.clear()

    def begin_google(self, process="login"):
        from urllib.parse import parse_qs, urlparse

        response = self.client.post(reverse("google_login") + f"?process={process}")
        self.assertEqual(response.status_code, 302)
        location = urlparse(response["Location"])
        self.assertEqual(location.hostname, "accounts.google.com")
        query = parse_qs(location.query)
        self.assertIn("code_challenge", query)
        return query["state"][0]

    def callback(self, state, email="new@example.test", uid="new-google-id"):
        def identity(request, app, token, **kwargs):
            from allauth.socialaccount.adapter import get_adapter

            provider = get_adapter(request).get_provider(request, "google")
            return provider.sociallogin_from_response(
                request,
                {
                    "sub": uid,
                    "email": email,
                    "email_verified": True,
                    "given_name": "Alex",
                    "family_name": "Kamau",
                    "name": "Alex Kamau",
                },
            )

        with patch(
            "allauth.socialaccount.providers.oauth2.client.OAuth2Client.get_access_token",
            return_value={
                "access_token": "fictional-provider-token",
                "token_type": "Bearer",
            },
        ), patch(
            "allauth.socialaccount.providers.google.views.GoogleOAuth2Adapter.complete_login",
            side_effect=identity,
        ):
            return self.client.get(
                reverse("google_callback"), {"state": state, "code": "fictional-code"}
            )

    @override_settings(
        EMAIL_TWO_STEP_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_google_signup_completes_with_role_and_terms_through_actual_routes(self):
        response = self.callback(self.begin_google())
        self.assertRedirects(response, reverse("socialaccount_signup"))
        response = self.client.post(
            reverse("socialaccount_signup"),
            {"role": "candidate", "accept_terms": "on"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email="new@example.test")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(EmailAddress.objects.get(user=user).verified)
        code = re.search(r"\b\d{6}\b", mail.outbox[-1].body).group()
        response = self.client.post(
            reverse("account_confirm_login_code"), {"action": "verify", "code": code}
        )
        self.assertRedirects(response, reverse("accounts:dashboard"))
        self.assertTrue(EmailAddress.objects.get(user=user).verified)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertEqual(user.get_full_name(), "Alex Kamau")
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertFalse(user.has_usable_password())

    def test_google_existing_login_keeps_the_original_profile(self):
        user = User.objects.create_user(
            username="linked",
            email="linked@example.test",
            first_name="Existing",
            role="recruiter",
        )
        SocialAccount.objects.create(
            user=user, provider="google", uid="existing-google-id"
        )
        response = self.callback(
            self.begin_google(), email=user.email, uid="existing-google-id"
        )
        self.assertRedirects(response, reverse("accounts:dashboard"))
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Existing")
        self.assertEqual(user.role, "recruiter")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_same_email_callback_returns_to_existing_signin_without_linking(self):
        User.objects.create_user(
            username="local", email="new@example.test", password=PASSWORD
        )
        self.assertRedirects(
            self.callback(self.begin_google()), reverse("accounts:sign_in")
        )
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(SocialAccount.objects.exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_bad_callback_state_cannot_sign_in_or_create_an_account(self):
        self.begin_google()
        self.callback("invalid-state")
        self.assertFalse(User.objects.exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_connect_then_google_login_reuses_the_same_account(self):
        user = User.objects.create_user(
            username="local", email="new@example.test", password=PASSWORD
        )
        self.client.force_login(user)
        self.client.post(
            reverse("accounts:security"),
            {"password": PASSWORD, "action": "connect_google"},
        )
        response = self.callback(self.begin_google("connect"))
        self.assertRedirects(response, reverse("accounts:security"))
        self.assertEqual(User.objects.count(), 1)
        self.assertTrue(SocialAccount.objects.filter(user=user).exists())
        self.assertTrue(user.check_password(PASSWORD))
        self.client.logout()
        self.callback(self.begin_google())
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    @override_settings(
        EMAIL_TWO_STEP_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_google_does_not_bypass_staff_email_verification(self):
        user = User.objects.create_user(
            username="staff-google", email="staff@example.test", is_staff=True
        )
        SocialAccount.objects.create(
            user=user, provider="google", uid="staff-google-id"
        )
        EmailAddress.objects.create(
            user=user, email=user.email, verified=True, primary=True
        )
        response = self.callback(
            self.begin_google(), email=user.email, uid="staff-google-id"
        )
        self.assertRedirects(response, reverse("account_confirm_login_code"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(EMAIL_TWO_STEP_ENABLED=True)
    def test_google_identity_is_not_asked_for_a_duplicate_mailbox_code(self):
        user = User.objects.create_user(
            username="candidate-google",
            email="candidate@example.test",
            email_two_step_enabled=True,
        )
        SocialAccount.objects.create(
            user=user, provider="google", uid="candidate-google-id"
        )
        response = self.callback(
            self.begin_google(), email=user.email, uid="candidate-google-id"
        )
        self.assertRedirects(response, reverse("accounts:dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
