"""Profile persistence, validation, ownership and transaction boundaries."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse

from candidates.forms import ExperienceFormSet
from candidates.models import CandidateProfile, CandidateSkill, Education

User = get_user_model()


class CandidateProfileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.candidate = User.objects.create_user(
            username="candidate",
            email="candidate@example.test",
            first_name="Alex",
            role="candidate",
        )
        cls.other = User.objects.create_user(
            username="other", email="other@example.test", role="candidate"
        )
        cls.recruiter = User.objects.create_user(
            username="recruiter", email="recruiter@example.test", role="recruiter"
        )

    def setUp(self):
        self.client.force_login(self.candidate)
        self.edit_url = reverse("candidates:profile_edit")
        self.profile_url = reverse("candidates:profile")

    def empty_payload(self, **changes):
        payload = {
            "headline": "Junior developer",
            "summary": "I build useful web applications.",
            "location": "Nairobi, Kenya",
        }
        for prefix in [
            "skills",
            "education",
            "certifications",
            "experience",
            "portfolio",
        ]:
            payload.update(
                {f"{prefix}-TOTAL_FORMS": "0", f"{prefix}-INITIAL_FORMS": "0"}
            )
        return payload | changes

    def complete_payload(self):
        payload = self.empty_payload()
        payload |= {
            "skills-TOTAL_FORMS": "1",
            "skills-0-name": "Python",
            "education-TOTAL_FORMS": "1",
            "education-0-qualification": "BSc Computer Science",
            "education-0-institution": "Example University",
            "education-0-field_of_study": "Computing",
            "education-0-start_date": "2020-09-01",
            "education-0-end_date": "2024-07-01",
            "certifications-TOTAL_FORMS": "1",
            "certifications-0-name": "Web Development",
            "certifications-0-issuer": "Example Training",
            "certifications-0-issue_date": "2024-08-01",
            "certifications-0-credential_url": "https://example.com/credential",
            "experience-TOTAL_FORMS": "1",
            "experience-0-job_title": "Developer",
            "experience-0-company": "Example Studio",
            "experience-0-start_date": "2024-09-01",
            "experience-0-currently_working": "on",
            "experience-0-description": "Built a web application.",
            "portfolio-TOTAL_FORMS": "1",
            "portfolio-0-title": "My projects",
            "portfolio-0-url": "https://example.com/projects",
        }
        return payload

    def test_reading_profile_pages_does_not_create_records(self):
        for url in [self.profile_url, self.edit_url, reverse("accounts:dashboard")]:
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertFalse(CandidateProfile.objects.exists())

    def test_save_all_sections_and_render_profile(self):
        response = self.client.post(self.edit_url, self.complete_payload(), follow=True)
        self.assertRedirects(response, self.profile_url)
        self.assertContains(response, "Your profile has been saved.")
        profile = CandidateProfile.objects.get(user=self.candidate)
        self.assertEqual(profile.skills.get().name, "Python")
        self.assertEqual(profile.education.get().qualification, "BSc Computer Science")
        self.assertEqual(profile.certifications.get().issuer, "Example Training")
        self.assertTrue(profile.experience.get().currently_working)
        self.assertEqual(profile.portfolio_links.get().title, "My projects")
        for text in [
            "Junior developer",
            "Python",
            "Example University",
            "Example Studio",
            "My projects",
        ]:
            self.assertContains(response, text)

    def test_save_and_edit_existing_profile(self):
        profile = CandidateProfile.objects.create(
            user=self.candidate, headline="Old headline"
        )
        skill = CandidateSkill.objects.create(profile=profile, name="Python")
        payload = self.empty_payload(headline="Updated headline") | {
            "skills-TOTAL_FORMS": "1",
            "skills-INITIAL_FORMS": "1",
            "skills-0-id": str(skill.pk),
            "skills-0-name": "Django",
        }
        self.assertRedirects(self.client.post(self.edit_url, payload), self.profile_url)
        profile.refresh_from_db()
        skill.refresh_from_db()
        self.assertEqual(profile.headline, "Updated headline")
        self.assertEqual(skill.name, "Django")
        self.assertEqual(CandidateProfile.objects.count(), 1)

    def test_remove_selected_entry_and_preserve_other_entries(self):
        profile = CandidateProfile.objects.create(user=self.candidate)
        first = CandidateSkill.objects.create(profile=profile, name="Python")
        second = CandidateSkill.objects.create(profile=profile, name="SQL")
        payload = self.empty_payload() | {
            "skills-TOTAL_FORMS": "2",
            "skills-INITIAL_FORMS": "2",
            "skills-0-id": str(first.pk),
            "skills-0-name": "Python",
            "skills-0-DELETE": "on",
            "skills-1-id": str(second.pk),
            "skills-1-name": "SQL",
        }
        self.assertRedirects(self.client.post(self.edit_url, payload), self.profile_url)
        self.assertEqual(list(profile.skills.values_list("name", flat=True)), ["SQL"])

    def test_wholly_blank_extra_entries_are_ignored(self):
        payload = self.empty_payload(headline="", summary="", location="")
        for prefix in [
            "skills",
            "education",
            "certifications",
            "experience",
            "portfolio",
        ]:
            payload[f"{prefix}-TOTAL_FORMS"] = "1"
        self.assertRedirects(self.client.post(self.edit_url, payload), self.profile_url)
        profile = CandidateProfile.objects.get(user=self.candidate)
        self.assertFalse(profile.skills.exists())
        self.assertFalse(profile.education.exists())
        self.assertFalse(profile.experience.exists())

    def test_bad_dates_keep_previous_profile_and_submitted_values(self):
        profile = CandidateProfile.objects.create(
            user=self.candidate, headline="Original"
        )
        payload = self.complete_payload() | {"education-0-end_date": "2019-01-01"}
        response = self.client.post(self.edit_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your changes have not been saved")
        self.assertContains(
            response, "The end date must be on or after the start date."
        )
        self.assertEqual(response.context["form"].data["headline"], "Junior developer")
        profile.refresh_from_db()
        self.assertEqual(profile.headline, "Original")
        self.assertFalse(profile.skills.exists())

    def test_current_experience_cannot_have_end_date(self):
        payload = self.complete_payload() | {"experience-0-end_date": "2025-01-01"}
        response = self.client.post(self.edit_url, payload)
        self.assertContains(response, "Leave the end date blank for a current entry.")
        self.assertFalse(CandidateProfile.objects.exists())

    def test_unsafe_portfolio_and_credential_urls_are_rejected(self):
        for field, value in [
            ("portfolio-0-url", "javascript:alert(1)"),
            ("certifications-0-credential_url", "ftp://example.com/file"),
        ]:
            with self.subTest(field=field):
                response = self.client.post(
                    self.edit_url, self.complete_payload() | {field: value}
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Enter a valid URL.")
                self.assertFalse(CandidateProfile.objects.exists())

    def test_duplicate_skills_ignore_case_and_extra_spaces(self):
        payload = self.empty_payload() | {
            "skills-TOTAL_FORMS": "2",
            "skills-0-name": "Machine learning",
            "skills-1-name": "  MACHINE   LEARNING  ",
        }
        response = self.client.post(self.edit_url, payload)
        self.assertContains(response, "Remove duplicate skills before saving.")
        self.assertFalse(CandidateProfile.objects.exists())

    def test_recruiter_cannot_read_or_save_candidate_profiles(self):
        self.client.force_login(self.recruiter)
        self.assertEqual(self.client.get(self.profile_url).status_code, 403)
        self.assertEqual(self.client.get(self.edit_url).status_code, 403)
        self.assertEqual(
            self.client.post(self.edit_url, self.complete_payload()).status_code, 403
        )
        self.assertFalse(CandidateProfile.objects.exists())

    def test_anonymous_user_must_sign_in(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.profile_url).status_code, 302)
        self.assertIn(reverse("accounts:sign_in"), self.client.get(self.edit_url).url)

    def test_another_candidate_profile_is_never_exposed(self):
        other_profile = CandidateProfile.objects.create(
            user=self.other,
            summary="Private information belonging to another candidate",
        )
        response = self.client.get(
            self.profile_url, {"user": self.other.pk, "profile": other_profile.pk}
        )
        self.assertNotContains(
            response, "Private information belonging to another candidate"
        )
        self.assertIsNone(response.context["profile"])
        payload = self.empty_payload(
            user=str(self.other.pk), profile=str(other_profile.pk)
        )
        self.assertRedirects(self.client.post(self.edit_url, payload), self.profile_url)
        other_profile.refresh_from_db()
        self.assertEqual(
            other_profile.summary, "Private information belonging to another candidate"
        )
        self.assertTrue(CandidateProfile.objects.filter(user=self.candidate).exists())

    def test_forged_related_entry_id_cannot_be_updated_or_deleted(self):
        profile = CandidateProfile.objects.create(
            user=self.candidate, headline="Original"
        )
        other_profile = CandidateProfile.objects.create(user=self.other)
        foreign_skill = CandidateSkill.objects.create(
            profile=other_profile, name="Private skill"
        )
        for deleted in ["", "on"]:
            with self.subTest(deleted=deleted):
                payload = self.empty_payload() | {
                    "skills-TOTAL_FORMS": "1",
                    "skills-INITIAL_FORMS": "1",
                    "skills-0-id": str(foreign_skill.pk),
                    "skills-0-name": "Tampered",
                    "skills-0-DELETE": deleted,
                }
                response = self.client.post(self.edit_url, payload)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "does not belong to your profile")
                foreign_skill.refresh_from_db()
                profile.refresh_from_db()
                self.assertEqual(foreign_skill.name, "Private skill")
                self.assertEqual(profile.headline, "Original")

    def test_database_failure_rolls_back_every_section(self):
        with patch.object(
            ExperienceFormSet,
            "save",
            side_effect=IntegrityError("Simulated write failure"),
        ):
            response = self.client.post(self.edit_url, self.complete_payload())
        self.assertContains(response, "These changes conflict with saved information")
        self.assertFalse(CandidateProfile.objects.exists())
        self.assertFalse(CandidateSkill.objects.exists())
        self.assertFalse(Education.objects.exists())

    def test_missing_or_excessive_management_data_is_rejected(self):
        for payload in [
            {"headline": "Missing management data"},
            self.empty_payload() | {"skills-TOTAL_FORMS": "10000"},
        ]:
            with self.subTest(payload=payload):
                self.assertEqual(
                    self.client.post(self.edit_url, payload).status_code, 200
                )
                self.assertFalse(CandidateProfile.objects.exists())

    def test_profile_text_is_escaped_in_display(self):
        CandidateProfile.objects.create(
            user=self.candidate, summary='<script>alert("unsafe")</script>'
        )
        response = self.client.get(self.profile_url)
        self.assertNotContains(response, '<script>alert("unsafe")</script>')
        self.assertContains(response, "&lt;script&gt;")

    def test_existing_dates_render_in_html_date_format(self):
        self.client.post(self.edit_url, self.complete_payload())
        response = self.client.get(self.edit_url)
        self.assertContains(response, 'value="2020-09-01"')
        self.assertContains(response, 'value="2024-07-01"')
        self.assertContains(response, 'value="2024-08-01"')

    def test_profile_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.candidate)
        self.assertEqual(
            client.post(self.edit_url, self.complete_payload()).status_code, 403
        )
        self.assertFalse(CandidateProfile.objects.exists())
