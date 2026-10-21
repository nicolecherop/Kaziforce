"""Private contacts, interview scheduling and honest notification delivery."""

from datetime import timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from applications.interview_forms import InterviewForm
from applications.interview_services import deliver_email
from applications.models import Application, Interview, InterviewEmail
from applications.services import snapshot_from_profile
from candidates.forms import ProfileForm
from candidates.models import CandidateProfile
from jobs.models import JobPosting


class InterviewFixtures:
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.candidate = User.objects.create_user(
            username="interview-candidate",
            email="candidate@example.test",
            first_name="Alex",
        )
        cls.other = User.objects.create_user(
            username="interview-other", email="other@example.test"
        )
        cls.recruiter = User.objects.create_user(
            username="interview-recruiter",
            email="recruiter@example.test",
            role="recruiter",
            first_name="Sarah",
            last_name="Mwangi",
        )
        cls.outsider = User.objects.create_user(
            username="interview-outsider",
            email="outsider@example.test",
            role="recruiter",
        )
        cls.profile = CandidateProfile.objects.create(
            user=cls.candidate,
            summary="Software developer",
            contact_email="alex.contact@kaziforce.co.ke",
            phone_number="+254 712 345 678",
        )
        cls.job = JobPosting.objects.create(
            recruiter=cls.recruiter,
            title="Software developer",
            company="Acacia Digital",
            location="Nairobi",
            description="Build web applications",
        )
        cls.application = Application.objects.create(
            candidate=cls.candidate,
            job=cls.job,
            status="shortlisted",
            candidate_name="Alex",
            candidate_email=cls.candidate.email,
            profile_snapshot=snapshot_from_profile(cls.candidate),
            submitted_at=timezone.now(),
        )

    def invitation_data(self, **changes):
        return {
            "starts_at": timezone.localtime(timezone.now() + timedelta(days=3))
            .replace(second=0, microsecond=0)
            .strftime("%Y-%m-%dT%H:%M"),
            "duration_minutes": "45",
            "format": "video",
            "meeting_url": "https://meeting.example.test/private-room",
            "location": "",
            "instructions": "Please prepare a short description of your work.",
            "recruiter_name": "Sarah Mwangi",
            "recruiter_email": "sarah@kaziforce.co.ke",
            "recruiter_phone": "+254 722 333 444",
        } | changes

    def schedule(self, **changes):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("applications:interview_edit", args=[self.application.pk]),
                self.invitation_data(**changes),
            )
        return response


class CandidateContactTests(InterviewFixtures, TestCase):
    def test_optional_contacts_validate_and_do_not_change_account_email(self):
        for values in (
            {},
            {
                "contact_email": "work@kaziforce.co.ke",
                "phone_number": "+254 (712) 345-678",
            },
        ):
            form = ProfileForm(values, instance=self.profile)
            self.assertTrue(form.is_valid(), form.errors)
            form.save()
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.email, "candidate@example.test")
        for values in (
            {"contact_email": "invalid"},
            {"phone_number": "javascript:alert(1)"},
            {"phone_number": "123"},
            {"phone_number": "1" * 16},
        ):
            self.assertFalse(ProfileForm(values, instance=self.profile).is_valid())

    def test_profile_and_application_show_contacts_only_to_authorized_users(self):
        self.client.force_login(self.candidate)
        response = self.client.get(reverse("candidates:profile"))
        self.assertContains(response, "alex.contact@kaziforce.co.ke")
        self.assertContains(response, "+254 712 345 678")
        self.assertContains(
            self.client.get(reverse("candidates:profile_edit")), 'name="phone_number"'
        )
        self.client.force_login(self.recruiter)
        response = self.client.get(
            reverse("applications:detail", args=[self.application.pk])
        )
        self.assertContains(response, "alex.contact@kaziforce.co.ke")
        self.assertContains(response, 'href="tel:+254 712 345 678"')
        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.get(
                reverse("applications:detail", args=[self.application.pk])
            ).status_code,
            404,
        )

    def test_contacts_can_be_tailored_and_submitted_copy_is_immutable(self):
        self.application.delete()
        self.client.force_login(self.candidate)
        page = reverse("applications:edit", args=[self.job.pk])
        response = self.client.get(page)
        self.assertEqual(
            response.context["form"]["contact_email"].value(),
            self.profile.contact_email,
        )
        data = {
            "summary": "Tailored profile",
            "contact_email": "application@kaziforce.co.ke",
            "phone_number": "+254 700 222 333",
            "action": "submit",
        }
        for section in (
            "skills",
            "education",
            "certifications",
            "experience",
            "portfolio",
        ):
            data.update(
                {f"{section}-TOTAL_FORMS": "0", f"{section}-INITIAL_FORMS": "0"}
            )
        response = self.client.post(page, data)
        self.assertEqual(response.status_code, 302)
        application = Application.objects.get(candidate=self.candidate, job=self.job)
        self.assertEqual(
            application.profile_snapshot["profile"]["contact_email"],
            data["contact_email"],
        )
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.contact_email, "alex.contact@kaziforce.co.ke")
        self.profile.phone_number = "+254 799 888 777"
        self.profile.save()
        self.client.post(page, data | {"phone_number": "+254 722 000 000"})
        application.refresh_from_db()
        self.assertEqual(
            application.profile_snapshot["profile"]["phone_number"], "+254 700 222 333"
        )

    def test_old_applications_without_contact_fields_remain_readable(self):
        self.application.profile_snapshot = {"profile": {"summary": "Original profile"}}
        self.application.candidate_email = "original@kaziforce.co.ke"
        self.application.save()
        self.client.force_login(self.recruiter)
        self.assertContains(
            self.client.get(reverse("applications:detail", args=[self.application.pk])),
            "original@kaziforce.co.ke",
        )


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="KaziForce <noreply@kaziforce.co.ke>",
)
class InterviewTests(InterviewFixtures, TestCase):
    def setUp(self):
        self.client.force_login(self.recruiter)

    def test_schedule_communicates_details_and_contacts_to_candidate(self):
        self.assertEqual(self.schedule().status_code, 302)
        interview = Interview.objects.get(application=self.application)
        self.assertEqual(interview.status, "scheduled")
        self.assertEqual(interview.duration_minutes, 45)
        notification = interview.emails.get()
        self.assertEqual(notification.status, "sent")
        self.assertEqual(mail.outbox[0].to, ["alex.contact@kaziforce.co.ke"])
        self.assertEqual(mail.outbox[0].reply_to, ["sarah@kaziforce.co.ke"])
        for detail in (
            "East Africa Time, UTC+3",
            "Sarah Mwangi",
            "+254 722 333 444",
            interview.meeting_url,
        ):
            self.assertIn(detail, mail.outbox[0].body)
        self.client.force_login(self.candidate)
        response = self.client.get(
            reverse("applications:detail", args=[self.application.pk])
        )
        self.assertContains(response, "Interview invitation")
        self.assertContains(response, "Your recruiter contact")
        self.assertContains(response, "sarah@kaziforce.co.ke")
        self.assertContains(response, interview.meeting_url)
        self.assertNotContains(response, "Edit interview")
        self.assertNotContains(response, "Retry email")
        self.assertContains(
            self.client.get(reverse("accounts:dashboard")), "Upcoming interviews"
        )
        self.assertContains(
            self.client.get(reverse("applications:mine")), "Interview scheduled"
        )
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "shortlisted")

    def test_updates_notify_and_repeated_identical_posts_do_not_duplicate_email(self):
        self.schedule()
        self.schedule(duration_minutes="60")
        interview = Interview.objects.get(application=self.application)
        self.assertEqual(interview.duration_minutes, 60)
        self.assertEqual(interview.emails.count(), 2)
        self.assertIn("Interview updated", mail.outbox[1].subject)
        self.schedule(duration_minutes="60")
        self.assertEqual(interview.emails.count(), 2)
        self.assertEqual(len(mail.outbox), 2)

    def test_cancel_is_shared_notified_and_can_be_rescheduled(self):
        self.schedule()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("applications:interview_cancel", args=[self.application.pk]),
                {"reason": "We will arrange a new time by email."},
            )
        self.assertEqual(response.status_code, 302)
        interview = Interview.objects.get(application=self.application)
        self.assertEqual(interview.status, "cancelled")
        self.assertIn("Interview cancelled", mail.outbox[-1].subject)
        self.client.force_login(self.candidate)
        response = self.client.get(
            reverse("applications:detail", args=[self.application.pk])
        )
        self.assertContains(response, "We will arrange a new time by email.")
        self.assertContains(response, "sarah@kaziforce.co.ke")
        self.assertNotContains(response, "Open video meeting")
        self.assertNotContains(
            self.client.get(reverse("accounts:dashboard")), "Upcoming interviews"
        )
        self.client.force_login(self.recruiter)
        self.schedule()
        interview.refresh_from_db()
        self.assertEqual(interview.status, "scheduled")
        self.assertEqual(interview.cancellation_reason, "")

    def test_failed_email_does_not_lose_invitation_and_can_be_retried(self):
        with patch(
            "applications.interview_services.EmailMessage.send",
            side_effect=OSError("unavailable"),
        ):
            self.schedule()
        notification = InterviewEmail.objects.get()
        self.assertEqual(notification.status, "failed")
        self.assertEqual(Interview.objects.count(), 1)
        response = self.client.get(
            reverse("applications:detail", args=[self.application.pk])
        )
        self.assertContains(response, "because delivery failed")
        self.client.post(
            reverse("applications:interview_email_retry", args=[self.application.pk])
        )
        notification.refresh_from_db()
        self.assertEqual(notification.status, "sent")
        self.assertEqual(notification.attempts, 2)
        self.client.post(
            reverse("applications:interview_email_retry", args=[self.application.pk])
        )
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_unconnected_email_is_not_reported_as_sent(self):
        self.schedule()
        self.assertEqual(InterviewEmail.objects.get().status, "not_configured")
        response = self.client.get(
            reverse("applications:detail", args=[self.application.pk])
        )
        self.assertContains(response, "email has not been sent")
        self.assertNotContains(response, "Interview email sent.")

    def test_reserved_email_accounts_are_not_sent_to(self):
        self.application.profile_snapshot["profile"][
            "contact_email"
        ] = "candidate@example.test"
        self.application.save()
        self.schedule()
        self.assertEqual(InterviewEmail.objects.get().status, "not_configured")
        self.assertEqual(len(mail.outbox), 0)

    def test_outdated_email_cannot_be_retried_after_newer_invitation(self):
        with patch(
            "applications.interview_services.EmailMessage.send",
            side_effect=OSError("unavailable"),
        ):
            self.schedule()
        old = InterviewEmail.objects.get()
        self.schedule(duration_minutes="60")
        deliver_email(old.pk)
        old.refresh_from_db()
        self.assertEqual(old.status, "failed")
        self.assertEqual(len(mail.outbox), 1)

    def test_contact_email_falls_back_to_submitted_account_email_not_current_account(
        self,
    ):
        self.application.profile_snapshot["profile"]["contact_email"] = ""
        self.application.candidate_email = "submitted@kaziforce.co.ke"
        self.application.save()
        self.candidate.email = "changed@kaziforce.co.ke"
        self.candidate.save()
        self.schedule()
        self.assertEqual(mail.outbox[0].to, ["submitted@kaziforce.co.ke"])

    def test_timezone_duration_format_and_contact_validation(self):
        changes = [
            {"starts_at": "2020-01-01T09:00"},
            {"duration_minutes": "0"},
            {"duration_minutes": "481"},
            {"meeting_url": ""},
            {"meeting_url": "javascript:alert(1)"},
            {"format": "in_person", "location": ""},
            {"format": "phone", "recruiter_phone": ""},
            {"recruiter_email": "invalid"},
            {"recruiter_phone": "not a number"},
        ]
        for change in changes:
            with self.subTest(change=change):
                self.assertFalse(
                    InterviewForm(self.invitation_data(**change)).is_valid()
                )
        day = (timezone.localdate() + timedelta(days=5)).isoformat()
        form = InterviewForm(
            self.invitation_data(
                starts_at=day + "T09:00",
                format="in_person",
                location="Acacia House, reception",
            )
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["starts_at"].astimezone(datetime_timezone.utc).hour, 6
        )
        self.assertEqual(form.cleaned_data["meeting_url"], "")
        self.schedule(format="phone")
        self.assertEqual(Interview.objects.get().meeting_url, "")

    def test_only_shortlisted_applications_can_be_scheduled(self):
        self.application.status = "reviewing"
        self.application.save()
        self.assertEqual(self.schedule().status_code, 302)
        self.assertFalse(Interview.objects.exists())
        self.application.status = "draft"
        self.application.save()
        self.assertEqual(self.schedule().status_code, 404)

    def test_scope_csrf_and_post_only_mutations(self):
        page = reverse("applications:interview_edit", args=[self.application.pk])
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.recruiter)
        self.assertEqual(strict.post(page, self.invitation_data()).status_code, 403)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(page).status_code, 404)
        self.assertEqual(self.schedule().status_code, 404)
        self.client.force_login(self.candidate)
        self.assertEqual(self.client.get(page).status_code, 403)
        self.assertEqual(self.schedule().status_code, 403)
        self.client.force_login(self.recruiter)
        self.schedule()
        for action in ("interview_cancel", "interview_email_retry"):
            url = reverse("applications:" + action, args=[self.application.pk])
            self.assertEqual(self.client.get(url).status_code, 405)
            self.client.force_login(self.outsider)
            self.assertEqual(
                self.client.post(url, {"reason": "Private"}).status_code, 404
            )
            self.client.force_login(self.candidate)
            self.assertEqual(
                self.client.post(url, {"reason": "Private"}).status_code, 403
            )
            self.client.force_login(self.recruiter)
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.get(
                reverse("applications:detail", args=[self.application.pk])
            ).status_code,
            404,
        )
        self.assertNotContains(
            self.client.get(reverse("accounts:dashboard")), "Upcoming interviews"
        )

    def test_upcoming_interview_must_be_cancelled_before_changing_application_status(
        self,
    ):
        self.schedule()
        status_url = reverse("applications:status", args=[self.application.pk])
        self.client.post(status_url, {"status": "unsuccessful"})
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "shortlisted")
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("applications:interview_cancel", args=[self.application.pk]),
                {"reason": "We are not progressing with this application."},
            )
        self.client.post(status_url, {"status": "unsuccessful"})
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "unsuccessful")

    def test_empty_cancellation_does_not_change_or_notify(self):
        self.schedule()
        response = self.client.post(
            reverse("applications:interview_cancel", args=[self.application.pk]),
            {"reason": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")
        self.assertEqual(Interview.objects.get().status, "scheduled")
        self.assertEqual(InterviewEmail.objects.count(), 1)

    def test_notification_storage_failure_rolls_back_interview(self):
        with patch(
            "applications.interview_services.InterviewEmail.objects.create",
            side_effect=IntegrityError("unavailable"),
        ):
            response = self.schedule()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Interview.objects.exists())
        self.assertFalse(InterviewEmail.objects.exists())

    def test_email_bookkeeping_failure_after_commit_keeps_saved_invitation_retryable(
        self,
    ):
        with patch(
            "applications.interview_services.deliver_email",
            side_effect=OperationalError("unavailable"),
        ):
            self.assertEqual(self.schedule().status_code, 302)
        self.assertEqual(Interview.objects.count(), 1)
        notification = InterviewEmail.objects.get()
        self.assertEqual(notification.status, "pending")
        self.client.post(
            reverse("applications:interview_email_retry", args=[self.application.pk])
        )
        notification.refresh_from_db()
        self.assertEqual(notification.status, "sent")

    def test_candidate_instructions_are_escaped_and_recruiter_dashboard_is_scoped(self):
        self.schedule(instructions="<script>alert(1)</script>")
        self.client.force_login(self.candidate)
        response = self.client.get(
            reverse("applications:detail", args=[self.application.pk])
        )
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert(1)")
        self.client.force_login(self.recruiter)
        self.assertContains(
            self.client.get(reverse("accounts:dashboard")), "Upcoming interviews"
        )
        self.client.force_login(self.outsider)
        self.assertNotContains(
            self.client.get(reverse("accounts:dashboard")), "Upcoming interviews"
        )
