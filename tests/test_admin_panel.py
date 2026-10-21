"""Administration permissions, operational summaries and immutable records."""

from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from applications.models import (
    Application,
    ApplicationAttachment,
    Interview,
    InterviewEmail,
)
from candidates.models import CandidateProfile
from jobs.models import JobPosting
from matching.models import SkillCatalogue, MatchingCorpus, MatchRun, MatchResult


class AdminPanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.administrator = User.objects.create_superuser(
            username="admin-panel-owner",
            email="owner@example.test",
            role="administrator",
        )
        cls.staff = User.objects.create_user(
            username="admin-panel-staff",
            email="staff@example.test",
            role="administrator",
            is_staff=True,
        )
        cls.role_only = User.objects.create_user(
            username="admin-role-only", email="role@example.test", role="administrator"
        )
        cls.candidate = User.objects.create_user(
            username="admin-panel-candidate",
            email="candidate@example.test",
            first_name="Alex",
        )
        cls.other = User.objects.create_user(
            username="admin-panel-other", email="other@example.test"
        )
        cls.recruiter = User.objects.create_user(
            username="admin-panel-recruiter",
            email="recruiter@example.test",
            role="recruiter",
        )
        CandidateProfile.objects.create(user=cls.candidate, summary="Python developer")
        cls.job = JobPosting.objects.create(
            recruiter=cls.recruiter,
            title="Platform developer",
            company="Acacia Digital",
            description="Build web applications",
            location="Nairobi",
        )
        JobPosting.objects.create(
            recruiter=cls.recruiter,
            title="Closed role",
            company="Acacia Digital",
            description="A previous role",
            status="closed",
        )
        cls.submitted = Application.objects.create(
            candidate=cls.candidate,
            job=cls.job,
            status="shortlisted",
            candidate_name="Alex Kamau",
            candidate_email=cls.candidate.email,
            submitted_at=timezone.now(),
            profile_snapshot={"profile": {"summary": "Original submitted profile"}},
            job_snapshot={"title": cls.job.title},
        )
        cls.reviewing = Application.objects.create(
            candidate=cls.other,
            job=cls.job,
            status="reviewing",
            candidate_name="Under review",
            submitted_at=timezone.now(),
        )
        cls.draft = Application.objects.create(
            candidate=cls.role_only,
            job=cls.job,
            status="draft",
            candidate_name="Private draft identity",
            profile_snapshot={"profile": {"summary": "Private draft content"}},
        )
        cls.interview = Interview.objects.create(
            application=cls.submitted,
            starts_at=timezone.now() + timedelta(days=3),
            duration_minutes=30,
            format="in_person",
            location="Acacia House, reception",
            recruiter_name="Sarah Mwangi",
            recruiter_email="sarah@example.test",
        )
        cls.cancelled = Interview.objects.create(
            application=cls.reviewing,
            starts_at=timezone.now() + timedelta(days=4),
            format="in_person",
            status="cancelled",
            recruiter_name="Sarah Mwangi",
            recruiter_email="sarah@example.test",
        )
        cls.notification = InterviewEmail.objects.create(
            interview=cls.interview,
            recipient_email="alex@example.test",
            subject="Interview invitation",
            body="Original invitation text",
            reply_to="sarah@example.test",
            status="failed",
            attempts=1,
        )
        InterviewEmail.objects.create(
            interview=cls.cancelled,
            recipient_email="other@example.test",
            subject="Interview cancelled",
            body="Cancellation text",
            reply_to="sarah@example.test",
            status="sent",
            sent_at=timezone.now(),
        )
        catalogue = SkillCatalogue.objects.create(
            version="admin-fixture", checksum="a" * 64, skill_count=1, active=True
        )
        cls.corpus = MatchingCorpus.objects.create(
            catalogue=catalogue,
            tokenizer_version="admin-fixture",
            source_checksum="b" * 64,
            checksum="c" * 64,
            document_count=1,
            document_frequencies={"python": 1},
        )
        cls.match_run = MatchRun.objects.create(
            owner=cls.recruiter,
            kind="applicants",
            job=cls.job,
            corpus=cls.corpus,
            configuration={"version": "matching-v1"},
            input_checksum="d" * 64,
            as_of=timezone.localdate(),
        )
        cls.match_result = MatchResult.objects.create(
            run=cls.match_run,
            job=cls.job,
            candidate=cls.candidate,
            application=cls.submitted,
            score="72.00",
            rank=1,
            input_snapshot={"profile": {"summary": "Frozen evidence"}},
            input_checksum="e" * 64,
            components=[{"label": "Skills", "score": 72}],
            explanation={"saved": True},
        )

    def setUp(self):
        self.client.force_login(self.administrator)

    def grant(self, *codenames):
        self.staff.user_permissions.add(
            *Permission.objects.filter(codename__in=codenames)
        )
        self.staff = get_user_model().objects.get(pk=self.staff.pk)
        self.client.force_login(self.staff)

    def test_overview_counts_real_records_and_excludes_drafts(self):
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, "KaziForce")
        cards = {row["label"]: row for row in response.context["overview_cards"]}
        self.assertEqual(cards["Accounts"]["value"], 6)
        self.assertEqual(cards["Jobs"]["value"], 2)
        self.assertEqual(cards["Submitted applications"]["value"], 2)
        self.assertEqual(cards["Upcoming interviews"]["value"], 1)
        self.assertEqual(cards["Matching runs"]["value"], 1)
        self.assertEqual(cards["Saved match results"]["value"], 1)
        self.assertNotContains(response, "Private draft")
        self.assertEqual(len(response.context["recent_applications"]), 2)
        self.assertEqual(
            list(response.context["upcoming_interviews"]), [self.interview]
        )
        statuses = {
            row["label"]: row["count"] for row in response.context["email_statuses"]
        }
        self.assertEqual(statuses["Could not send"], 1)
        self.assertEqual(statuses["Sent"], 1)
        self.assertIn("no-store", response.headers["Cache-Control"])
        interview_list = self.client.get(cards["Upcoming interviews"]["url"])
        self.assertEqual(list(interview_list.context["cl"].queryset), [self.interview])

    def test_limited_staff_only_see_permitted_counts_and_records(self):
        self.grant("view_user")
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(
            [row["label"] for row in response.context["overview_cards"]], ["Accounts"]
        )
        self.assertFalse(response.context["recent_applications"])
        self.assertFalse(response.context["email_statuses"])
        self.assertNotContains(response, "Original submitted profile")
        self.assertEqual(
            self.client.get(
                reverse("admin:applications_application_changelist")
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "admin:applications_interviewemail_change",
                    args=[self.notification.pk],
                )
            ).status_code,
            403,
        )

    def test_staff_without_model_permissions_get_no_private_counts(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, "no assigned administration permissions")
        self.assertEqual(response.context["overview_cards"], [])
        self.assertFalse(response.context["recent_applications"])
        self.assertFalse(response.context["upcoming_interviews"])

    def test_product_role_alone_does_not_grant_admin_and_staff_dashboard_opens_admin(
        self,
    ):
        self.assertRedirects(
            self.client.get(reverse("accounts:dashboard")), reverse("admin:index")
        )
        for user in (self.candidate, self.recruiter, self.role_only):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)
        self.client.force_login(self.role_only)
        self.assertEqual(
            self.client.get(reverse("accounts:dashboard")).status_code, 403
        )
        self.staff.is_active = False
        self.staff.save()
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)

    def test_application_lists_are_searchable_filtered_and_hide_drafts(self):
        page = reverse("admin:applications_application_changelist")
        self.assertContains(self.client.get(page), "Alex Kamau")
        self.assertNotContains(self.client.get(page), "Private draft identity")
        self.assertNotContains(
            self.client.get(page, {"q": "Private draft"}), "Private draft content"
        )
        response = self.client.get(page, {"status__exact": "reviewing"})
        self.assertEqual(list(response.context["cl"].queryset), [self.reviewing])
        response = self.client.get(page, {"q": "Alex"})
        self.assertEqual(list(response.context["cl"].queryset), [self.submitted])
        response = self.client.get(
            reverse("admin:applications_application_change", args=[self.draft.pk]),
            follow=True,
        )
        self.assertNotContains(response, "Private draft content")

    def test_monitoring_records_are_read_only_even_for_superusers(self):
        records = [
            self.submitted,
            self.interview,
            self.notification,
            self.match_run,
            self.match_result,
            self.corpus,
        ]
        for record in records:
            with self.subTest(model=record._meta.label):
                url = reverse(
                    f"admin:{record._meta.app_label}_{record._meta.model_name}_change",
                    args=[record.pk],
                )
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'name="_save"')
                before = type(record).objects.filter(pk=record.pk).values().get()
                self.assertEqual(
                    self.client.post(
                        url,
                        {
                            "status": "unsuccessful",
                            "body": "Tampered",
                            "score": "100.00",
                        },
                    ).status_code,
                    403,
                )
                self.assertEqual(
                    type(record).objects.filter(pk=record.pk).values().get(), before
                )
                delete_url = reverse(
                    f"admin:{record._meta.app_label}_{record._meta.model_name}_delete",
                    args=[record.pk],
                )
                self.assertEqual(
                    self.client.post(delete_url, {"post": "yes"}).status_code, 403
                )
                add_url = reverse(
                    f"admin:{record._meta.app_label}_{record._meta.model_name}_add"
                )
                self.assertEqual(self.client.post(add_url, {}).status_code, 403)

    def test_email_monitoring_cannot_send_or_retry_messages(self):
        response = self.client.get(
            reverse(
                "admin:applications_interviewemail_change", args=[self.notification.pk]
            )
        )
        self.assertContains(response, "Original invitation text")
        self.assertNotContains(response, "Retry email")
        self.assertEqual(
            InterviewEmail.objects.get(pk=self.notification.pk).attempts, 1
        )
        self.assertEqual(
            InterviewEmail.objects.get(pk=self.notification.pk).status, "failed"
        )

    def test_record_pages_escape_submitted_text(self):
        self.submitted.cover_letter = "<script>alert('private')</script>"
        self.submitted.save()
        response = self.client.get(
            reverse("admin:applications_application_change", args=[self.submitted.pk])
        )
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert('private')")

    def test_private_attachment_download_requires_both_permissions_and_never_exposes_url(
        self,
    ):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        with override_settings(PRIVATE_DOCUMENT_ROOT=Path(directory.name)):
            attachment = ApplicationAttachment(
                application=self.submitted, original_name="submitted.pdf", kind="cv"
            )
            attachment.file.save(
                "submitted.pdf",
                ContentFile(b"%PDF-1.7\nOriginal submitted CV"),
                save=True,
            )
            url = reverse(
                "admin:applications_applicationattachment_download",
                args=[attachment.pk],
            )
            response = self.client.get(
                reverse(
                    "admin:applications_applicationattachment_change",
                    args=[attachment.pk],
                )
            )
            self.assertContains(response, "Download submitted document")
            self.assertNotContains(response, attachment.file.name)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn(
                b"Original submitted CV", b"".join(response.streaming_content)
            )
            self.assertIn("no-store", response.headers["Cache-Control"])
            self.grant("view_applicationattachment")
            self.assertEqual(self.client.get(url).status_code, 403)
            self.grant("view_application")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Original submitted CV", b"".join(response.streaming_content))
            self.client.force_login(self.candidate)
            self.assertEqual(self.client.get(url).status_code, 302)
            self.client.force_login(self.administrator)
            attachment.application = self.draft
            attachment.save()
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url).status_code, 405)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_email_status_is_honest_without_connected_smtp(self):
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, "Email delivery is not connected")
        self.assertContains(response, "invitations remain available")

    def test_overview_get_does_not_modify_saved_records_or_create_matching_runs(self):
        models = (Application, Interview, InterviewEmail, MatchRun, MatchResult)
        before = {
            model: list(model.objects.order_by("pk").values()) for model in models
        }
        self.client.get(reverse("admin:index"))
        for model in models:
            self.assertEqual(list(model.objects.order_by("pk").values()), before[model])

    def test_admin_sign_in_accepts_staff_email_and_rejects_nonstaff(self):
        password = "Q7!river-starlight-927"
        self.administrator.set_password(password)
        self.administrator.save()
        self.candidate.set_password(password)
        self.candidate.save()
        self.client.logout()
        url = reverse("admin:login")
        self.assertContains(self.client.get(url), "Email address")
        response = self.client.post(
            url,
            {
                "username": self.administrator.email.upper(),
                "password": password,
                "next": reverse("admin:index"),
            },
        )
        self.assertRedirects(response, reverse("admin:index"))
        self.client.logout()
        response = self.client.post(
            url, {"username": self.candidate.email, "password": password}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
