"""Application cutoff boundaries, ownership, persistence and saved recommendations."""

from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from applications.models import Application
from applications.services import save_application, snapshot_from_profile
from candidates.models import CandidateProfile, CandidateSkill
from jobs.forms import JobPostingForm
from jobs.models import JobPosting, JobSkill
from matching.corpus import build_corpus
from matching.inputs import collect_inputs
from matching.models import SkillCatalogue, CatalogueSkill, SkillLabel, MatchResult
from matching.recommendations import candidate_recommendations
from matching.services import generate_matches
from pages.workspace import recruiter_dashboard


@override_settings(TIME_ZONE="Africa/Nairobi")
class JobDeadlineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(
            username="deadline-owner", email="owner@example.test", role="recruiter"
        )
        cls.other = User.objects.create_user(
            username="deadline-other", email="other@example.test", role="recruiter"
        )
        cls.candidate = User.objects.create_user(
            username="deadline-candidate",
            email="candidate@example.test",
            role="candidate",
        )
        profile = CandidateProfile.objects.create(
            user=cls.candidate, headline="Python developer", summary="Python software"
        )
        CandidateSkill.objects.create(profile=profile, name="Python")
        cls.today = timezone.localdate()
        cls.job = JobPosting.objects.create(
            recruiter=cls.owner,
            title="Deadline developer",
            company="Example Studio",
            location="Nairobi",
            description="Python software",
            application_deadline=cls.today + timedelta(days=7),
        )
        JobSkill.objects.create(job=cls.job, name="Python", requirement="required")
        catalogue = SkillCatalogue.objects.create(
            version="deadline-fixture", checksum="d" * 64, skill_count=1, active=True
        )
        skill = CatalogueSkill.objects.create(
            catalogue=catalogue,
            uri="https://example.test/skills/python",
            preferred_label="Python",
            description="Python software",
        )
        SkillLabel.objects.create(
            skill=skill, label="Python", normalized="python", preferred=True
        )
        build_corpus()

    def setUp(self):
        self.client.force_login(self.candidate)

    def payload(self, **changes):
        return {
            "title": "Deadline developer",
            "company": "Example Studio",
            "location": "Nairobi",
            "description": "Python software",
            "requirements": "",
            "education_level": "any",
            "education_field": "",
            "education_priority": "1",
            "minimum_experience_years": "",
            "experience_details": "",
            "experience_priority": "1",
            "application_deadline": (self.today + timedelta(days=7)).isoformat(),
            "skills-TOTAL_FORMS": "0",
            "skills-INITIAL_FORMS": "0",
        } | changes

    def expire(self, status="open"):
        JobPosting.objects.filter(pk=self.job.pk).update(
            application_deadline=self.today - timedelta(days=1), status=status
        )
        self.job.refresh_from_db()

    def test_optional_deadline_and_inclusive_day_are_consistent_between_properties_and_queries(
        self,
    ):
        for deadline, status, expected in [
            (None, "open", True),
            (self.today, "open", True),
            (self.today + timedelta(days=1), "open", True),
            (self.today - timedelta(days=1), "open", False),
            (self.today, "closed", False),
        ]:
            with self.subTest(deadline=deadline, status=status):
                JobPosting.objects.filter(pk=self.job.pk).update(
                    application_deadline=deadline, status=status
                )
                self.job.refresh_from_db()
                self.assertEqual(self.job.accepts_applications, expected)
                self.assertEqual(
                    JobPosting.objects.accepting_applications()
                    .filter(pk=self.job.pk)
                    .exists(),
                    expected,
                )

    def test_deadline_expires_at_midnight_in_east_africa_time(self):
        self.job.application_deadline = datetime(2026, 11, 12).date()
        with timezone.override("Africa/Nairobi"):
            with patch(
                "django.utils.timezone.now",
                return_value=datetime(2026, 11, 12, 20, 59, 59, tzinfo=dt_timezone.utc),
            ):
                self.assertTrue(self.job.accepts_applications)
            with patch(
                "django.utils.timezone.now",
                return_value=datetime(2026, 11, 12, 21, 0, 0, tzinfo=dt_timezone.utc),
            ):
                self.assertFalse(self.job.accepts_applications)

    def test_recruiter_form_rejects_new_and_changed_past_deadlines(self):
        form = JobPostingForm(
            self.payload(
                application_deadline=(self.today - timedelta(days=1)).isoformat()
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn("application_deadline", form.errors)
        form = JobPostingForm(
            self.payload(
                application_deadline=(self.today - timedelta(days=1)).isoformat()
            ),
            instance=self.job,
        )
        self.assertFalse(form.is_valid())

    def test_date_input_has_today_minimum_and_blank_is_allowed(self):
        form = JobPostingForm(self.payload(application_deadline=""))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.fields["application_deadline"].widget.attrs["min"],
            self.today.isoformat(),
        )

    def test_owner_can_publish_with_deadline(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("jobs:create"), self.payload(title="Published deadline role")
        )
        self.assertRedirects(response, reverse("jobs:manage"))
        self.assertEqual(
            JobPosting.objects.get(
                title="Published deadline role"
            ).application_deadline,
            self.today + timedelta(days=7),
        )

    def test_owner_can_extend_an_expired_deadline_or_clear_it(self):
        self.expire()
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("jobs:edit", args=[self.job.pk]), self.payload()
        )
        self.assertRedirects(response, reverse("jobs:manage"))
        self.job.refresh_from_db()
        self.assertTrue(self.job.accepts_applications)
        self.client.post(
            reverse("jobs:edit", args=[self.job.pk]),
            self.payload(application_deadline=""),
        )
        self.job.refresh_from_db()
        self.assertIsNone(self.job.application_deadline)

    def test_manual_closure_is_not_undone_by_extending_deadline(self):
        self.expire(status="closed")
        self.client.force_login(self.owner)
        self.client.post(reverse("jobs:edit", args=[self.job.pk]), self.payload())
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "closed")
        self.assertFalse(self.job.accepts_applications)

    def test_reopening_requires_explicit_choice_and_valid_deadline(self):
        self.expire(status="closed")
        self.client.force_login(self.owner)
        bad = self.payload(
            application_deadline=(self.today - timedelta(days=1)).isoformat(),
            reopen_applications="on",
        )
        response = self.client.post(reverse("jobs:edit", args=[self.job.pk]), bad)
        self.assertEqual(response.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "closed")
        good = self.payload(
            application_deadline=self.today.isoformat(), reopen_applications="on"
        )
        self.assertRedirects(
            self.client.post(reverse("jobs:edit", args=[self.job.pk]), good),
            reverse("jobs:manage"),
        )
        self.job.refresh_from_db()
        self.assertTrue(self.job.accepts_applications)

    def test_expired_unchanged_deadline_does_not_block_other_edits(self):
        self.expire()
        form = JobPostingForm(
            self.payload(
                title="Updated description role",
                application_deadline=self.job.application_deadline.isoformat(),
            ),
            instance=self.job,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_admin_model_validation_cannot_reopen_with_an_expired_deadline(self):
        self.expire(status="closed")
        self.job.status = "open"
        with self.assertRaises(ValidationError):
            self.job.full_clean()

    def test_expired_jobs_leave_browsing_and_new_matching_inputs(self):
        self.expire()
        page = self.client.get(reverse("jobs:opportunities"))
        self.assertNotContains(page, "Deadline developer")
        pairs, _, _ = collect_inputs(self.candidate)
        self.assertFalse(any(p["job_id"] == str(self.job.pk) for p in pairs))

    def test_saved_recommendations_disappear_after_deadline_without_recalculation(self):
        run = generate_matches(self.candidate)
        MatchResult.objects.filter(run=run).update(score=95)
        self.assertTrue(candidate_recommendations(self.candidate, run).exists())
        results_before = list(run.results.values())
        self.expire()
        self.assertFalse(candidate_recommendations(self.candidate, run).exists())
        dashboard = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(dashboard.context["recommended_count"], 0)
        self.assertEqual(list(run.results.values()), results_before)
        JobPosting.objects.filter(pk=self.job.pk).update(
            application_deadline=self.today
        )
        self.assertTrue(candidate_recommendations(self.candidate, run).exists())

    def test_expired_job_detail_remains_available_without_apply_button(self):
        self.expire()
        response = self.client.get(reverse("jobs:detail", args=[self.job.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The application deadline has passed.")
        self.assertNotContains(response, "Start application")
        self.assertContains(response, "11:59 p.m. EAT")

    def test_direct_application_get_and_post_do_not_create_drafts_after_deadline(self):
        self.expire()
        url = reverse("applications:edit", args=[self.job.pk])
        self.assertRedirects(
            self.client.get(url), reverse("jobs:detail", args=[self.job.pk])
        )
        self.assertEqual(self.client.post(url, {"action": "submit"}).status_code, 302)
        self.assertFalse(Application.objects.exists())

    def test_submission_service_rechecks_current_job_deadline(self):
        self.expire()
        for submit in (False, True):
            with self.assertRaises(ValidationError):
                save_application(
                    self.candidate,
                    self.job.pk,
                    snapshot_from_profile(self.candidate),
                    {"cover_letter": "", "documents": []},
                    submit=submit,
                )
        self.assertFalse(Application.objects.exists())

    def test_existing_draft_is_preserved_but_cannot_be_submitted_after_deadline(self):
        draft = save_application(
            self.candidate,
            self.job.pk,
            snapshot_from_profile(self.candidate),
            {"cover_letter": "My private draft", "documents": []},
            submit=False,
        )
        self.expire()
        self.client.post(
            reverse("applications:edit", args=[self.job.pk]), {"action": "submit"}
        )
        draft.refresh_from_db()
        self.assertEqual(draft.status, "draft")
        self.assertEqual(draft.cover_letter, "My private draft")

    def test_submitted_application_remains_visible_to_owner_and_candidate(self):
        application = save_application(
            self.candidate,
            self.job.pk,
            snapshot_from_profile(self.candidate),
            {"cover_letter": "Saved message", "documents": []},
            submit=True,
        )
        original = dict(application.job_snapshot)
        self.assertEqual(
            original["application_deadline"],
            (self.today + timedelta(days=7)).isoformat(),
        )
        self.expire()
        detail = reverse("applications:detail", args=[application.pk])
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertRedirects(
            self.client.get(reverse("applications:edit", args=[self.job.pk])), detail
        )
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertEqual(
            self.client.get(
                reverse("applications:applicants", args=[self.job.pk])
            ).status_code,
            200,
        )
        application.refresh_from_db()
        self.assertEqual(application.job_snapshot, original)

    def test_only_owning_recruiter_can_extend_reopen_or_close(self):
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.post(
                reverse("jobs:edit", args=[self.job.pk]),
                self.payload(reopen_applications="on"),
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse("jobs:close", args=[self.job.pk])).status_code, 404
        )

    def test_recruiter_counts_and_labels_reflect_expiry(self):
        self.expire()
        self.assertEqual(recruiter_dashboard(self.owner)["open_job_count"], 0)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("jobs:manage"))
        self.assertContains(response, "Deadline passed")
        self.assertContains(response, "Application deadline")

    def test_manual_close_takes_effect_before_deadline(self):
        self.client.force_login(self.owner)
        self.assertRedirects(
            self.client.post(reverse("jobs:close", args=[self.job.pk])),
            reverse("jobs:manage"),
        )
        self.job.refresh_from_db()
        self.assertFalse(self.job.accepts_applications)

    def test_recruiter_can_rank_existing_applications_after_expiry(self):
        save_application(
            self.candidate,
            self.job.pk,
            snapshot_from_profile(self.candidate),
            {"cover_letter": "Saved message", "documents": []},
            submit=True,
        )
        self.expire()
        run = generate_matches(self.owner, self.job)
        self.assertEqual(run.results.count(), 1)

    def test_admin_availability_filter_excludes_expired_jobs_from_open(self):
        from django.contrib import admin
        from django.test import RequestFactory
        from jobs.admin import ApplicationAvailabilityFilter

        self.expire()
        model_admin = admin.site._registry[JobPosting]
        request = RequestFactory().get("/admin/jobs/jobposting/")
        request.user = self.owner
        for value, expected in [("open", False), ("expired", True), ("closed", False)]:
            filter_instance = ApplicationAvailabilityFilter(
                request, {"application_window": [value]}, JobPosting, model_admin
            )
            self.assertEqual(
                filter_instance.queryset(request, JobPosting.objects.all())
                .filter(pk=self.job.pk)
                .exists(),
                expected,
            )

    def test_admin_open_count_excludes_expired_jobs(self):
        from accounts.admin_overview import overview_context

        user = get_user_model().objects.create_superuser(
            username="deadline-admin", email="admin@example.test", role="administrator"
        )
        self.expire()
        card = next(c for c in overview_context(user)["overview_cards"] if c["label"] == "Jobs")
        self.assertEqual(card["detail"], "0 open for applications")
