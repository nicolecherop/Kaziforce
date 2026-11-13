"""Account identity prefills stay editable, owner-scoped and non-destructive."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from allauth.socialaccount.models import SocialAccount
from candidates.models import CandidateProfile


class ProfilePrefillTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="google-profile-owner",
            email="alex@example.test",
            first_name="Alex",
            last_name="Kamau",
            role="candidate",
        )
        SocialAccount.objects.create(
            user=cls.user, provider="google", uid="profile-prefill-subject"
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("candidates:profile_edit")

    def payload(self, **changes):
        data = {
            "headline": "Developer",
            "summary": "I build web applications.",
            "contact_email": "",
            "phone_number": "",
            "location": "",
        }
        for name in (
            "skills",
            "education",
            "certifications",
            "experience",
            "portfolio",
        ):
            data[name + "-TOTAL_FORMS"] = "0"
            data[name + "-INITIAL_FORMS"] = "0"
        return data | changes

    def test_google_name_is_displayed_and_email_is_prefilled_without_creating_a_profile(
        self,
    ):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"]["contact_email"].value(), self.user.email
        )
        self.assertContains(response, 'value="Alex Kamau"')
        self.assertContains(response, 'id="profile-account-name"')
        self.assertFalse(CandidateProfile.objects.filter(user=self.user).exists())

    def test_signup_email_is_also_suggested_for_password_accounts(self):
        SocialAccount.objects.filter(user=self.user).delete()
        self.assertEqual(
            self.client.get(self.url).context["form"]["contact_email"].value(),
            self.user.email,
        )

    def test_existing_contact_and_professional_details_are_preserved(self):
        profile = CandidateProfile.objects.create(
            user=self.user,
            contact_email="recruitment@example.test",
            headline="Existing headline",
            summary="My own summary",
            location="Mombasa",
        )
        response = self.client.get(self.url)
        self.assertEqual(
            response.context["form"]["contact_email"].value(),
            "recruitment@example.test",
        )
        self.assertEqual(
            response.context["form"]["headline"].value(), "Existing headline"
        )
        profile.refresh_from_db()
        self.assertEqual(profile.summary, "My own summary")

    def test_user_can_save_a_different_contact_email_without_changing_identity(self):
        response = self.client.post(
            self.url,
            self.payload(
                contact_email="jobs@example.test", full_name="Posted attacker name"
            ),
        )
        self.assertRedirects(response, reverse("candidates:profile"))
        self.assertEqual(
            CandidateProfile.objects.get(user=self.user).contact_email,
            "jobs@example.test",
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "alex@example.test")
        self.assertEqual(self.user.get_full_name(), "Alex Kamau")

    def test_explicit_blank_submission_is_not_replaced_with_the_account_email(self):
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 302)
        self.assertEqual(CandidateProfile.objects.get(user=self.user).contact_email, "")

    def test_validation_failure_keeps_the_entered_value_instead_of_prefilling_again(
        self,
    ):
        response = self.client.post(
            self.url, self.payload(contact_email="not-an-email")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"]["contact_email"].value(), "not-an-email"
        )
        self.assertTrue(response.context["form"]["contact_email"].errors)
        self.assertFalse(CandidateProfile.objects.filter(user=self.user).exists())
