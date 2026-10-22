"""Account workflow checks, including privilege boundaries and reset tokens."""

import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

User = get_user_model()


class AccountWorkflowTests(TestCase):
    def setUp(self):
        cache.clear()

    def registration_data(self, **changes):
        data = {
            "full_name": "Alex Testperson",
            "email": "alex@example.test",
            "role": "candidate",
            "password1": "Q7!river-starlight-927",
            "password2": "Q7!river-starlight-927",
            "accept_terms": "on",
        }
        return data | changes

    @override_settings(
        EMAIL_TWO_STEP_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_candidate_and_recruiter_registration(self):
        for role, template in [
            ("candidate", "candidates/dashboard.html"),
            ("recruiter", "recruiters/dashboard.html"),
        ]:
            with self.subTest(role=role):
                self.client.logout()
                response = self.client.post(
                    reverse("accounts:create_account"),
                    self.registration_data(
                        email=f"{role}@example.test",
                        role=role,
                        is_staff="true",
                        is_superuser="true",
                    ),
                    follow=True,
                )
                self.assertTemplateUsed(response, "account/confirm_login_code.html")
                self.assertNotIn("_auth_user_id", self.client.session)
                code = re.search(r"\b\d{6}\b", mail.outbox[-1].body).group()
                response = self.client.post(
                    reverse("account_confirm_login_code"),
                    {"code": code, "action": "verify"},
                    follow=True,
                )
                self.assertTemplateUsed(response, template)
                user = User.objects.get(email=f"{role}@example.test")
                self.assertEqual(user.get_full_name(), "Alex Testperson")
                self.assertEqual(user.role, role)
                self.assertFalse(user.is_staff)
                self.assertFalse(user.is_superuser)
                self.assertTrue(user.check_password("Q7!river-starlight-927"))

    def test_public_registration_cannot_create_administrator(self):
        response = self.client.post(
            reverse("accounts:create_account"),
            self.registration_data(role="administrator"),
        )
        self.assertFormError(
            response.context["form"],
            "role",
            "Select a valid choice. administrator is not one of the available choices.",
        )
        self.assertFalse(User.objects.exists())

    def test_case_insensitive_duplicate_email_is_rejected(self):
        User.objects.create_user(username="existing", email="alex@example.test")
        response = self.client.post(
            reverse("accounts:create_account"),
            self.registration_data(email="ALEX@example.test"),
        )
        self.assertIn("email", response.context["form"].errors)
        self.assertEqual(User.objects.count(), 1)

    def test_invalid_registration_does_not_save_accounts(self):
        for change, field in [
            ({"password2": "a-different-password"}, "password2"),
            ({"password1": "12345678", "password2": "12345678"}, "password2"),
            ({"email": "not-an-email"}, "email"),
            ({"full_name": "   "}, "full_name"),
            ({"accept_terms": ""}, "accept_terms"),
        ]:
            with self.subTest(change=change):
                response = self.client.post(
                    reverse("accounts:create_account"), self.registration_data(**change)
                )
                self.assertIn(field, response.context["form"].errors)
                self.assertFalse(User.objects.exists())

    def test_email_sign_in_is_case_insensitive(self):
        user = User.objects.create_user(
            username="internal-id",
            email="alex@example.test",
            password="Q7!river-starlight-927",
        )
        response = self.client.post(
            reverse("accounts:sign_in"),
            {"username": "ALEX@EXAMPLE.TEST", "password": "Q7!river-starlight-927"},
        )
        self.assertRedirects(response, reverse("accounts:dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_sign_in_does_not_reveal_unknown_or_inactive_accounts(self):
        User.objects.create_user(
            username="disabled",
            email="disabled@example.test",
            password="Q7!river-starlight-927",
            is_active=False,
        )
        errors = []
        for email in ["unknown@example.test", "disabled@example.test"]:
            response = self.client.post(
                reverse("accounts:sign_in"),
                {"username": email, "password": "Q7!river-starlight-927"},
            )
            errors.append(response.context["form"].non_field_errors())
            self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(errors[0], errors[1])

    def test_external_next_redirect_is_ignored(self):
        User.objects.create_user(
            username="internal",
            email="alex@example.test",
            password="Q7!river-starlight-927",
        )
        response = self.client.post(
            reverse("accounts:sign_in"),
            {
                "username": "alex@example.test",
                "password": "Q7!river-starlight-927",
                "next": "https://untrusted.example/",
            },
        )
        self.assertRedirects(response, reverse("accounts:dashboard"))

    def test_dashboard_requires_sign_in(self):
        self.assertRedirects(
            self.client.get(reverse("accounts:dashboard")),
            reverse("accounts:sign_in") + "?next=/accounts/dashboard/",
        )

    def test_logout_is_post_only_and_requires_csrf(self):
        user = User.objects.create_user(username="internal", email="alex@example.test")
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        self.assertEqual(client.get(reverse("accounts:sign_out")).status_code, 405)
        self.assertEqual(client.post(reverse("accounts:sign_out")).status_code, 403)
        client.get(reverse("accounts:dashboard"))
        token = client.cookies["csrftoken"].value
        self.assertRedirects(
            client.post(reverse("accounts:sign_out"), {"csrfmiddlewaretoken": token}),
            reverse("pages:home"),
        )
        self.assertNotIn("_auth_user_id", client.session)

    def test_registration_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            reverse("accounts:create_account"), self.registration_data()
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.exists())

    def test_recruiter_call_to_action_selects_correct_role(self):
        response = self.client.get(
            reverse("accounts:create_account") + "?role=recruiter"
        )
        self.assertEqual(response.context["form"]["role"].value(), "recruiter")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_reset_token_updates_password_and_cannot_be_reused(self):
        user = User.objects.create_user(
            username="reset", email="reset@example.test", password="original-password"
        )
        response = self.client.post(
            reverse("accounts:password_reset"), {"email": user.email}
        )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        link = re.search(r"http://testserver([^\s]+)", mail.outbox[0].body).group(1)
        response = self.client.get(link, follow=True)
        self.assertTrue(response.context["validlink"])
        reset_path = response.request["PATH_INFO"]
        response = self.client.post(
            reset_path,
            {
                "new_password1": "K9!new-river-password",
                "new_password2": "K9!new-river-password",
            },
        )
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        user.refresh_from_db()
        self.assertTrue(user.check_password("K9!new-river-password"))
        response = self.client.get(link, follow=True)
        self.assertFalse(response.context["validlink"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_unknown_reset_email_has_same_confirmation(self):
        response = self.client.post(
            reverse("accounts:password_reset"), {"email": "unknown@example.test"}
        )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_help_and_prototype_information_pages(self):
        for page in ["help", "privacy", "terms"]:
            with self.subTest(page=page):
                self.assertEqual(
                    self.client.get(reverse(f"pages:{page}")).status_code, 200
                )
