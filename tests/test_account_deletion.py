"""Deletion checks run only against test records and the in-memory mail backend."""

import re
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import timedelta
from unittest.mock import patch

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.account_deletion import deletion_blockers, remove_account
from accounts.models import AccountDeletionCode
from applications.models import Application
from candidates.models import CandidateProfile, CandidateDocument
from freelance.models import Booking, Conversation, FreelancerProfile, Payment
from jobs.models import JobPosting, SavedJob


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_TWO_STEP_ENABLED=False,
)
class AccountDeletionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="delete-owner",
            email="delete-owner@example.test",
            password="Temporary-test-pass-292!",
            first_name="Original",
        )
        self.other = User.objects.create_user(
            username="delete-other", email="delete-other@example.test", role="recruiter"
        )
        self.profile = CandidateProfile.objects.create(
            user=self.user, summary="Private biography"
        )
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, verified=True, primary=True
        )
        self.url = reverse("accounts:delete_account")
        self.client.force_login(self.user)

    def code(self):
        response = self.client.post(self.url, {"action": "send_code"})
        self.assertEqual(response.status_code, 302)
        return re.search(r"code is (\d{6})", mail.outbox[-1].body).group(1)

    def confirm(self, code, **extra):
        return self.client.post(
            self.url, {"action": "delete", "code": code, "confirm": "on", **extra}
        )

    def booking(self, status="accepted"):
        freelancer = FreelancerProfile.objects.create(
            user=self.user,
            title="Analyst",
            about="Private services",
            location="Nairobi",
            rate=1000,
            available_from=timezone.localdate(),
            accepting_bookings=True,
        )
        conversation = Conversation.objects.create(
            recruiter=self.other, freelancer=freelancer
        )
        return Booking.objects.create(
            conversation=conversation,
            title="Analysis",
            scope="Data report",
            location="Remote",
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
            total_price=1000,
            status=status,
            recruiter_name="Employer",
            recruiter_email=self.other.email,
            freelancer_name="Original",
            freelancer_email=self.user.email,
        )

    def test_get_and_cancel_do_not_change_account(self):
        self.assertContains(self.client.get(self.url), "Shared records remain")
        self.assertFalse(AccountDeletionCode.objects.exists())
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_password_account_deleted_and_other_sessions_invalidated(self):
        other_session = Client()
        other_session.force_login(self.user)
        original_email = self.user.email
        code = self.code()
        self.assertNotEqual(
            AccountDeletionCode.objects.get(user=self.user).code_hash, code
        )
        self.assertContains(self.confirm(code), "Your account has been deleted")
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertFalse(self.user.has_usable_password())
        self.assertIsNotNone(self.user.deleted_at)
        self.assertNotEqual(self.user.email, original_email)
        self.assertFalse(CandidateProfile.objects.filter(user=self.user).exists())
        self.assertFalse(EmailAddress.objects.filter(user=self.user).exists())
        self.assertFalse(AccountDeletionCode.objects.filter(user=self.user).exists())
        self.assertEqual(
            other_session.get(reverse("accounts:security")).status_code, 302
        )
        self.other.refresh_from_db()
        self.assertTrue(self.other.is_active)

    def test_google_only_account_can_delete(self):
        self.user.set_unusable_password()
        self.user.save()
        SocialAccount.objects.create(
            user=self.user, provider="google", uid="fictional-google-id"
        )
        self.client.force_login(self.user)
        self.assertContains(self.confirm(self.code()), "Your account has been deleted")
        self.assertFalse(SocialAccount.objects.filter(user=self.user).exists())

    def test_wrong_code_five_attempt_limit(self):
        code = self.code()
        wrong = "111111" if code != "111111" else "222222"
        for _ in range(5):
            self.assertContains(self.confirm(wrong), "That code is incorrect")
        self.assertContains(self.confirm(code), "Request a new confirmation code")
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_expired_code(self):
        code = self.code()
        AccountDeletionCode.objects.filter(user=self.user).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertContains(self.confirm(code), "Request a new confirmation code")

    def test_email_change_invalidates_code(self):
        code = self.code()
        self.user.email = "changed@example.test"
        self.user.save()
        self.assertContains(self.confirm(code), "Request a new confirmation code")

    def test_confirmation_checkbox_required(self):
        code = self.code()
        self.confirm(code, confirm="")
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_cooldown_and_resend_invalidates_old_code(self):
        with patch("accounts.account_deletion.secrets.randbelow", return_value=123456):
            first = self.code()
        self.client.post(self.url, {"action": "send_code"})
        self.assertEqual(len(mail.outbox), 1)
        AccountDeletionCode.objects.filter(user=self.user).update(
            sent_at=timezone.now() - timedelta(minutes=2)
        )
        with patch("accounts.account_deletion.secrets.randbelow", return_value=654321):
            second = self.code()
        self.assertContains(self.confirm(first), "That code is incorrect")
        self.assertContains(self.confirm(second), "Your account has been deleted")

    def test_email_failure_preserves_account_and_no_challenge(self):
        with patch(
            "accounts.account_deletion.send_mail", side_effect=OSError("Unavailable")
        ):
            self.client.post(self.url, {"action": "send_code"})
        self.assertFalse(AccountDeletionCode.objects.exists())
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_cannot_target_another_user(self):
        self.confirm(self.code(), user_id=self.other.pk, email=self.other.email)
        self.other.refresh_from_db()
        self.assertTrue(self.other.is_active)

    def test_anonymous_and_csrf_protected(self):
        self.assertEqual(Client().get(self.url).status_code, 302)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(
            strict.post(self.url, {"action": "send_code"}).status_code, 403
        )

    def test_pending_booking_blocks_deletion(self):
        self.booking()
        self.assertContains(self.client.get(self.url), "Complete or cancel")
        with self.assertRaises(ValidationError):
            remove_account(self.user)
        self.assertTrue(CandidateProfile.objects.filter(user=self.user).exists())

    def test_unpaid_completed_booking_and_disputed_payment_block(self):
        booking = self.booking("completed")
        self.assertTrue(
            any("remaining payment" in text for text in deletion_blockers(self.user))
        )
        Payment.objects.create(
            booking=booking,
            reported_by=self.other,
            amount=1000,
            kind="balance",
            method="cash",
            status="disputed",
        )
        self.assertTrue(
            any("disputed" in text for text in deletion_blockers(self.user))
        )

    def test_paid_booking_retained_but_profile_hidden(self):
        booking = self.booking("completed")
        Payment.objects.create(
            booking=booking,
            reported_by=self.other,
            confirmed_by=self.user,
            amount=1000,
            kind="balance",
            method="cash",
            status="confirmed",
        )
        self.confirm(self.code())
        booking.refresh_from_db()
        self.assertEqual(booking.freelancer_email, "delete-owner@example.test")
        self.assertEqual(booking.payments.count(), 1)
        freelancer = FreelancerProfile.objects.get(user=self.user)
        self.assertFalse(freelancer.accepting_bookings)
        self.assertEqual(freelancer.about, "")
        booking.conversation.refresh_from_db()
        self.assertTrue(booking.conversation.blocked)

    def test_last_superuser_blocked(self):
        self.user.is_superuser = self.user.is_staff = True
        self.user.save()
        self.assertTrue(
            any("administrator" in text for text in deletion_blockers(self.user))
        )
        with self.assertRaises(ValidationError):
            remove_account(self.user)

    def test_submitted_application_kept_draft_and_bookmarks_removed(self):
        job = JobPosting.objects.create(
            recruiter=self.other,
            title="Engineer",
            company="Acacia",
            description="Build",
            location="Nairobi",
        )
        second = JobPosting.objects.create(
            recruiter=self.other,
            title="Designer",
            company="Acacia",
            description="Design",
            location="Nairobi",
        )
        submitted = Application.objects.create(
            candidate=self.user,
            job=job,
            status="submitted",
            candidate_name="Original",
            profile_snapshot={"summary": "Submitted copy"},
        )
        Application.objects.create(candidate=self.user, job=second, status="draft")
        SavedJob.objects.create(candidate=self.user, job=job)
        self.confirm(self.code())
        submitted.refresh_from_db()
        self.assertEqual(submitted.candidate_name, "Original")
        self.assertFalse(
            Application.objects.filter(candidate=self.user, status="draft").exists()
        )
        self.assertFalse(SavedJob.objects.filter(candidate=self.user).exists())

    def test_blockers_rechecked_after_code_sent(self):
        code = self.code()
        self.booking()
        self.assertContains(self.confirm(code), "Complete or cancel")
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_admin_cannot_reactivate_deleted_account(self):
        self.confirm(self.code())
        admin = get_user_model().objects.create_superuser(
            username="remaining-admin", email="admin@example.test"
        )
        self.client.force_login(admin)
        response = self.client.post(
            reverse("admin:accounts_user_change", args=[self.user.pk]),
            {"is_active": "on"},
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_dashboard_new_sections_respect_permissions(self):
        admin = get_user_model().objects.create_superuser(
            username="layout-admin", email="layout@example.test"
        )
        self.client.force_login(admin)
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, "Manage KaziForce")
        self.assertContains(response, "Administration overview")
        self.other.is_staff = True
        self.other.save()
        self.client.force_login(self.other)
        response = self.client.get(reverse("admin:index"))
        self.assertNotContains(response, reverse("admin:accounts_user_changelist"))

    def test_original_document_removed_after_commit(self):
        with TemporaryDirectory() as directory, override_settings(
            PRIVATE_DOCUMENT_ROOT=Path(directory)
        ):
            document = CandidateDocument.objects.create(
                user=self.user,
                file=ContentFile(b"Fictional file", name="cv.pdf"),
                original_name="cv.pdf",
            )
            original = Path(document.file.path)
            self.assertTrue(original.exists())
            code = self.code()
            with self.captureOnCommitCallbacks(execute=True):
                self.assertContains(self.confirm(code), "Your account has been deleted")
            self.assertFalse(original.exists())

    def test_recruiter_jobs_close_without_removing_other_applications(self):
        self.user.role = "recruiter"
        self.user.save()
        job = JobPosting.objects.create(
            recruiter=self.user,
            title="Engineer",
            company="Acacia",
            description="Build",
            location="Nairobi",
        )
        application = Application.objects.create(
            candidate=self.other, job=job, status="submitted"
        )
        self.confirm(self.code())
        job.refresh_from_db()
        self.assertEqual(job.status, "closed")
        self.assertTrue(Application.objects.filter(pk=application.pk).exists())
