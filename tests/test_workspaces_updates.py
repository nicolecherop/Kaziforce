"""Dual-workspace ownership, self-dealing prevention and durable update alerts."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Notification
from accounts.update_alerts import notify, deliver_update
from applications.interview_services import change_application_status
from applications.models import Application
from applications.services import save_application
from candidates.models import CandidateProfile, CandidateSkill
from freelance.access import conversations_for, bookings_for
from freelance.models import FreelancerProfile, Conversation
from freelance.selectors import visible_profiles, visible_projects
from freelance.services import (
    start_conversation,
    request_booking,
    booking_transition,
    send_message,
)
from jobs.models import JobPosting


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_TWO_STEP_ENABLED=False,
    SITE_URL="https://kaziforce.example",
)
class WorkspaceUpdateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.dual = User.objects.create_user(
            username="dual",
            email="dual@kaziforce.co.ke",
            role="candidate",
            recruiter_workspace_enabled=True,
        )
        cls.employer = User.objects.create_user(
            username="employer", email="employer@kaziforce.co.ke", role="recruiter"
        )
        cls.worker = User.objects.create_user(
            username="worker", email="worker@kaziforce.co.ke", role="candidate"
        )
        cls.single = User.objects.create_user(
            username="single", email="single@example.test", role="candidate"
        )
        cls.professional = CandidateProfile.objects.create(
            user=cls.dual,
            headline="Developer",
            contact_email="different@thirdparty.test",
        )
        CandidateSkill.objects.create(profile=cls.professional, name="Python")
        cls.job = JobPosting.objects.create(
            recruiter=cls.employer,
            title="Developer",
            company="Example Company",
            location="Remote",
            description="Build applications",
        )
        cls.own_job = JobPosting.objects.create(
            recruiter=cls.dual,
            title="Own role",
            company="Own Company",
            location="Remote",
            description="Manage delivery",
        )
        cls.application = Application.objects.create(
            candidate=cls.dual,
            job=cls.job,
            status="submitted",
            profile_snapshot={"summary": "Original submission"},
        )
        cls.profile = FreelancerProfile.objects.create(
            user=cls.dual,
            title="Development",
            about="Web services",
            location="Nairobi",
            rate=1000,
            rate_unit="day",
            work_mode="remote",
            available_from=timezone.localdate(),
            accepting_bookings=True,
            share_professional_profile=True,
        )
        cls.worker_profile = FreelancerProfile.objects.create(
            user=cls.worker,
            title="Writing",
            about="Writing services",
            location="Nairobi",
            rate=1000,
            rate_unit="day",
            work_mode="remote",
            available_from=timezone.localdate(),
            accepting_bookings=True,
            share_professional_profile=True,
        )
        cls.as_worker = Conversation.objects.create(
            recruiter=cls.employer, freelancer=cls.profile
        )
        cls.as_employer = Conversation.objects.create(
            recruiter=cls.dual, freelancer=cls.worker_profile
        )

    def setUp(self):
        self.client.force_login(self.dual)

    def switch(self, workspace):
        return self.client.post(
            reverse("accounts:switch_workspace"), {"workspace": workspace}
        )

    def alert(self, user=None, key="test-event"):
        return notify(
            user or self.dual,
            event_key=key,
            workspace="candidate",
            title="Application update",
            body="Your application has an update.",
            path=reverse("applications:detail", args=[self.application.pk]),
        )

    def booking_fields(self):
        return {
            "title": "Writing assignment",
            "scope": "Prepare content",
            "location": "Remote",
            "start_date": timezone.localdate(),
            "end_date": timezone.localdate() + timedelta(days=2),
            "total_price": Decimal("5000"),
            "deposit_amount": Decimal("0"),
            "cancellation_terms": "By agreement",
            "recruiter_name": "Employer",
            "recruiter_email": "employer@kaziforce.co.ke",
            "recruiter_phone": "",
        }

    def test_switch_preserves_identity_profile_and_applications(self):
        before = (
            self.dual.email,
            self.dual.password,
            self.dual.role,
            self.dual.is_staff,
            self.dual.is_superuser,
        )
        self.assertRedirects(self.switch("recruiter"), reverse("accounts:dashboard"))
        self.assertEqual(self.client.get(reverse("jobs:manage")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("candidates:profile_edit")).status_code, 403
        )
        self.switch("candidate")
        self.assertEqual(
            self.client.get(reverse("candidates:profile_edit")).status_code, 200
        )
        self.assertEqual(self.client.get(reverse("jobs:create")).status_code, 403)
        self.dual.refresh_from_db()
        self.assertEqual(
            before,
            (
                self.dual.email,
                self.dual.password,
                self.dual.role,
                self.dual.is_staff,
                self.dual.is_superuser,
            ),
        )
        self.application.refresh_from_db()
        self.assertEqual(
            self.application.profile_snapshot, {"summary": "Original submission"}
        )
        self.assertEqual(self.professional.skills.get().name, "Python")

    def test_first_switch_enables_other_workspace_not_admin_permissions(self):
        self.client.force_login(self.single)
        self.assertEqual(self.switch("recruiter").status_code, 302)
        self.single.refresh_from_db()
        self.assertTrue(self.single.has_workspace("candidate"))
        self.assertTrue(self.single.has_workspace("recruiter"))
        self.assertEqual(self.single.role, "candidate")
        self.assertFalse(self.single.is_staff)
        self.assertFalse(self.single.is_superuser)

    def test_recruiter_can_enable_candidate_profile_without_changing_primary_role(self):
        self.client.force_login(self.employer)
        self.switch("candidate")
        self.employer.refresh_from_db()
        profile = CandidateProfile(user=self.employer, headline="Consultant")
        profile.full_clean()
        profile.save()
        self.assertEqual(self.employer.role, "recruiter")
        self.assertEqual(
            self.client.get(reverse("candidates:profile")).status_code, 200
        )

    def test_session_selection_is_not_shared_between_devices(self):
        other_browser = Client()
        other_browser.force_login(self.dual)
        self.switch("recruiter")
        self.assertEqual(
            other_browser.get(reverse("candidates:profile")).status_code, 200
        )
        self.assertEqual(other_browser.get(reverse("jobs:create")).status_code, 403)

    def test_switch_is_post_only_csrf_protected_and_rejects_administrator(self):
        url = reverse("accounts:switch_workspace")
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.switch("administrator").status_code, 403)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.dual)
        self.assertEqual(strict.post(url, {"workspace": "recruiter"}).status_code, 403)

    def test_staff_permissions_are_preserved_and_explicit_switch_opens_workspace(self):
        self.dual.is_staff = True
        self.dual.is_superuser = True
        self.dual.save()
        self.assertRedirects(
            self.client.get(reverse("accounts:dashboard")), reverse("admin:index")
        )
        self.switch("recruiter")
        self.assertTemplateUsed(
            self.client.get(reverse("accounts:dashboard")), "recruiters/dashboard.html"
        )
        self.dual.refresh_from_db()
        self.assertTrue(self.dual.is_staff and self.dual.is_superuser)

    def test_application_views_cannot_cross_workspace_or_owner(self):
        url = reverse("applications:detail", args=[self.application.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.switch("recruiter")
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.employer)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_self_applications_are_blocked_in_view_and_service(self):
        self.assertRedirects(
            self.client.get(reverse("applications:edit", args=[self.own_job.pk])),
            reverse("jobs:detail", args=[self.own_job.pk]),
        )
        with self.assertRaises(ValidationError):
            save_application(
                self.dual,
                self.own_job.pk,
                {},
                {"cover_letter": "", "documents": []},
                True,
            )
        self.assertFalse(
            Application.objects.filter(candidate=self.dual, job=self.own_job).exists()
        )
        self.assertNotContains(
            self.client.get(reverse("jobs:opportunities")), "Own role"
        )

    def test_freelance_listing_and_profile_validation_survive_switching(self):
        self.dual._active_workspace = "recruiter"
        self.assertIn(self.profile, visible_profiles())
        self.professional.user = self.dual
        self.professional.full_clean()
        self.assertEqual(
            set(conversations_for(self.dual).values_list("pk", flat=True)),
            {self.as_employer.pk},
        )
        self.dual._active_workspace = "candidate"
        self.assertEqual(
            set(conversations_for(self.dual).values_list("pk", flat=True)),
            {self.as_worker.pk},
        )

    def test_self_booking_and_wrong_workspace_messages_are_blocked(self):
        self.dual._active_workspace = "recruiter"
        with self.assertRaises(ValidationError):
            start_conversation(self.dual, self.profile.pk, "Can I book myself?")
        with self.assertRaises(PermissionDenied):
            send_message(self.as_worker.pk, self.dual, "Wrong workspace")

    def test_new_submission_notifies_both_parties_once(self):
        application = self.application
        application.status = "draft"
        application.save()
        with self.captureOnCommitCallbacks(execute=True):
            save_application(
                self.dual,
                self.job.pk,
                {"profile": {}, "skills": []},
                {"cover_letter": "", "documents": []},
                True,
            )
        self.assertEqual(Notification.objects.count(), 2)
        self.assertEqual(len(mail.outbox), 2)
        save_application(
            self.dual, self.job.pk, {}, {"cover_letter": "", "documents": []}, True
        )
        self.assertEqual(Notification.objects.count(), 2)

    def test_decision_email_uses_account_inbox_and_duplicate_decision_is_silent(self):
        with self.captureOnCommitCallbacks(execute=True):
            change_application_status(self.employer, self.application.pk, "shortlisted")
            change_application_status(self.employer, self.application.pk, "shortlisted")
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.dual.email])
        self.assertIn(
            "https://kaziforce.example/accounts/notifications/", mail.outbox[0].body
        )

    def test_booking_updates_reach_the_other_party(self):
        self.dual._active_workspace = "recruiter"
        with self.captureOnCommitCallbacks(execute=True):
            booking = request_booking(
                self.as_employer.pk, self.dual, self.booking_fields()
            )
        item = Notification.objects.get()
        self.assertEqual(item.recipient, self.worker)
        self.assertEqual(item.workspace, "candidate")
        with self.captureOnCommitCallbacks(execute=True):
            booking_transition(booking.pk, self.worker, "decline")
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.dual, workspace="recruiter"
            ).count(),
            1,
        )
        self.assertEqual(len(mail.outbox), 2)

    def test_preferences_stop_update_email_but_keep_in_app_notification(self):
        response = self.client.post(reverse("accounts:notification_settings"), {})
        self.assertEqual(response.status_code, 302)
        self.dual.refresh_from_db()
        self.assertFalse(self.dual.email_updates)
        with self.captureOnCommitCallbacks(execute=True):
            item = self.alert()
        item.refresh_from_db()
        self.assertEqual(item.email_status, "skipped")
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Notification.objects.count(), 1)

    def test_reserved_unverified_and_inactive_accounts_do_not_receive_updates(self):
        from allauth.account.models import EmailAddress

        EmailAddress.objects.create(
            user=self.worker, email=self.worker.email, verified=False
        )
        self.employer.is_active = False
        self.employer.save()
        with self.captureOnCommitCallbacks(execute=True):
            for user in (self.single, self.worker, self.employer):
                self.alert(user, key=f"skip:{user.pk}")
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Notification.objects.filter(email_status="skipped").count(), 3)

    def test_failed_email_can_be_retried_and_sent_email_is_not_resent(self):
        with patch(
            "accounts.update_alerts.EmailMessage.send",
            side_effect=RuntimeError("provider failure"),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                item = self.alert()
        item.refresh_from_db()
        self.assertEqual(item.email_status, "failed")
        deliver_update(item.pk)
        deliver_update(item.pk)
        item.refresh_from_db()
        self.assertEqual(item.email_status, "sent")
        self.assertEqual(item.email_attempts, 2)
        self.assertEqual(len(mail.outbox), 1)

    def test_rollback_discards_notification_and_mail(self):
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    self.alert()
                    raise ValueError("Rollback")
            except ValueError:
                pass
        self.assertFalse(Notification.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_notification_access_is_private_and_open_switches_workspace(self):
        item = self.alert()
        other = self.alert(self.worker, key="other-event")
        self.switch("recruiter")
        self.assertEqual(
            self.client.post(
                reverse("accounts:open_notification", args=[other.pk])
            ).status_code,
            404,
        )
        response = self.client.post(
            reverse("accounts:open_notification", args=[item.pk])
        )
        self.assertRedirects(
            response, reverse("applications:detail", args=[self.application.pk])
        )
        item.refresh_from_db()
        self.assertIsNotNone(item.read_at)
        self.assertEqual(self.client.session["kaziforce_workspace"], "candidate")

    def test_no_external_notification_redirect_and_no_get_mutation(self):
        item = self.alert()
        item.path = "https://example.org"
        item.save()
        url = reverse("accounts:open_notification", args=[item.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), reverse("accounts:notifications"))

    def test_notifications_show_only_owner_updates_and_escape_content(self):
        item = self.alert()
        item.title = "<script>private</script>"
        item.save()
        other = self.alert(self.worker, key="other-event")
        other.title = "Private worker update"
        other.save()
        response = self.client.get(reverse("accounts:notifications"))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "Private worker update")
        self.assertIn("no-store", response.headers["Cache-Control"])
