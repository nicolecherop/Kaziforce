"""Local cohort provisioning, rollback and existing-account preservation."""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from accounts.auth_support import signup_verification_pending
from applications.models import Application
from candidates.models import CandidateProfile, WorkExperience
from evaluation.expanded_dataset import build_dataset
from freelance.models import FreelancerProfile, FreelanceProject, Booking, Review
from jobs.models import JobPosting
from scripts.import_evaluation_data import account_plan, create_batch, verify_existing


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    MPESA_SANDBOX={"enabled": False},
)
class LiveEvaluationImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.original = get_user_model().objects.create_user(
            username="existing-owner",
            email="owner@example.test",
            password="original-fixture-password",
            is_staff=True,
            is_superuser=True,
        )
        cls.dataset = build_dataset()

    def test_complete_cohort_preserves_existing_users_and_creates_no_communications_or_history(
        self,
    ):
        original = get_user_model().objects.filter(pk=self.original.pk).values().get()
        day = date(2026, 11, 1)
        with patch(
            "socket.socket.connect",
            side_effect=AssertionError("Network calls forbidden"),
        ):
            batch = create_batch(self.dataset, "fixture-cohort-password", day)
        self.assertEqual(
            get_user_model().objects.filter(pk=self.original.pk).values().get(),
            original,
        )
        self.assertEqual(len(batch["accounts"]), 210)
        self.assertEqual(CandidateProfile.objects.count(), 200)
        self.assertEqual(FreelancerProfile.objects.count(), 60)
        self.assertEqual(JobPosting.objects.count(), 40)
        self.assertEqual(FreelanceProject.objects.count(), 20)
        self.assertEqual(Application.objects.filter(status="submitted").count(), 400)
        imported = get_user_model().objects.filter(
            pk__in=[a["id"] for a in batch["accounts"]]
        )
        self.assertFalse(imported.filter(is_staff=True).exists())
        self.assertFalse(imported.filter(is_superuser=True).exists())
        self.assertEqual(Booking.objects.count(), 0)
        self.assertEqual(Review.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)
        first = imported.filter(role="candidate").order_by("pk").first()
        self.assertTrue(first.check_password("fixture-cohort-password"))
        self.assertFalse(signup_verification_pending(first))
        self.assertEqual(Application.objects.filter(candidate=first).count(), 2)
        self.assertEqual(
            FreelanceProject.objects.order_by("start_date").first().start_date,
            day + timedelta(days=10),
        )
        self.assertTrue(WorkExperience.objects.exists())
        self.assertEqual(verify_existing(batch), batch)
        # An idempotent verification never resets later user edits.
        CandidateProfile.objects.filter(user=first).update(
            headline="My updated professional headline"
        )
        verify_existing(batch)
        self.assertEqual(
            first.candidate_profile.headline, "My updated professional headline"
        )
        with self.assertRaisesMessage(ValueError, "already exists"):
            create_batch(self.dataset, "do-not-reset", day)
        self.assertTrue(first.check_password("fixture-cohort-password"))

    def test_conflicting_existing_identity_is_not_reused(self):
        plan = account_plan(self.dataset)
        existing = get_user_model().objects.create_user(
            username=plan[0]["username"], email="unrelated@example.test"
        )
        before = get_user_model().objects.count()
        with self.assertRaisesMessage(ValueError, "already exists"):
            create_batch(self.dataset, "fixture-password", date(2026, 10, 23))
        self.assertEqual(get_user_model().objects.count(), before)
        self.assertFalse(JobPosting.objects.exists())
        existing.refresh_from_db()
        self.assertEqual(existing.email, "unrelated@example.test")

    def test_unexpected_failure_rolls_back_entire_cohort(self):
        with patch(
            "applications.services.save_application",
            side_effect=RuntimeError("deliberate fixture failure"),
        ):
            with self.assertRaisesMessage(RuntimeError, "deliberate fixture failure"):
                create_batch(self.dataset, "fixture-password", date(2026, 10, 23))
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertFalse(CandidateProfile.objects.exists())
        self.assertFalse(JobPosting.objects.exists())
        self.assertFalse(FreelanceProject.objects.exists())

    def test_reserved_names_are_unique_and_nonprivileged(self):
        plan = account_plan(self.dataset)
        self.assertEqual(len({a["email"] for a in plan}), 210)
        self.assertEqual(len({a["username"] for a in plan}), 210)
        self.assertEqual(sum(a["role"] == "recruiter" for a in plan), 10)
        self.assertTrue(all(a["role"] in ("candidate", "recruiter") for a in plan))
        self.assertTrue(all("demo" not in a["last_name"].lower() for a in plan))
