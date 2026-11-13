"""Candidate bookmarks are private, idempotent and independent of applications."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from applications.models import Application
from jobs.models import JobPosting, SavedJob


class SavedJobTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(
            username="saved-owner", email="owner@example.test", role="candidate"
        )
        cls.other = User.objects.create_user(
            username="saved-other", email="other@example.test", role="candidate"
        )
        cls.recruiter = User.objects.create_user(
            username="saved-recruiter", email="recruiter@example.test", role="recruiter"
        )
        cls.job = JobPosting.objects.create(
            recruiter=cls.recruiter,
            title="Software Developer",
            company="Example Company",
            location="Nairobi",
            description="Build web applications.",
        )

    def setUp(self):
        self.client.force_login(self.owner)
        self.url = reverse("jobs:save", args=[self.job.pk])
        self.list_url = reverse("jobs:saved")

    def test_save_remove_and_repeated_requests_are_idempotent(self):
        for _ in range(2):
            self.assertRedirects(
                self.client.post(self.url, {"action": "save"}), self.list_url
            )
        self.assertEqual(SavedJob.objects.filter(candidate=self.owner).count(), 1)
        self.assertFalse(Application.objects.exists())
        response = self.client.get(self.list_url)
        self.assertContains(response, self.job.title)
        self.assertContains(response, "Saved ✓")
        for _ in range(2):
            self.client.post(self.url, {"action": "remove"})
        self.assertFalse(SavedJob.objects.exists())
        self.assertContains(self.client.get(self.list_url), "No saved jobs yet.")

    def test_candidate_cannot_read_or_remove_another_candidates_bookmark(self):
        SavedJob.objects.create(candidate=self.other, job=self.job)
        self.assertNotContains(self.client.get(self.list_url), self.job.title)
        self.client.post(self.url, {"action": "remove", "candidate": self.other.pk})
        self.assertTrue(SavedJob.objects.filter(candidate=self.other).exists())
        self.client.post(self.url, {"action": "save", "candidate": self.other.pk})
        self.assertEqual(SavedJob.objects.count(), 2)

    def test_closed_and_expired_bookmarks_remain_visible(self):
        SavedJob.objects.create(candidate=self.owner, job=self.job)
        self.job.status = "closed"
        self.job.save()
        response = self.client.get(self.list_url)
        self.assertContains(response, "Closed")
        self.assertContains(response, "no longer accepting applications")
        self.job.status = "open"
        self.job.application_deadline = timezone.localdate() - timedelta(days=1)
        self.job.save()
        self.assertContains(self.client.get(self.list_url), "Deadline passed")
        self.assertEqual(
            self.client.post(self.url, {"action": "remove"}).status_code, 302
        )

    def test_save_and_unsave_return_to_local_origin_only(self):
        for destination in (
            "https://example.org/",
            "//example.org/",
            "javascript:alert(1)",
        ):
            response = self.client.post(
                self.url, {"action": "save", "next": destination}
            )
            self.assertRedirects(response, self.list_url)
        destination = reverse("jobs:opportunities") + "?q=Software"
        response = self.client.post(self.url, {"action": "save", "next": destination})
        self.assertRedirects(response, destination)

    def test_get_invalid_actions_and_missing_csrf_do_not_save(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(
            self.client.post(self.url, {"action": "toggle"}).status_code, 400
        )
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        self.assertEqual(strict.post(self.url, {"action": "save"}).status_code, 403)
        self.assertFalse(SavedJob.objects.exists())

    def test_role_and_login_boundaries(self):
        self.client.force_login(self.recruiter)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.assertEqual(
            self.client.post(self.url, {"action": "save"}).status_code, 403
        )
        self.client.logout()
        self.assertEqual(self.client.get(self.list_url).status_code, 302)
        self.assertEqual(
            self.client.post(self.url, {"action": "save"}).status_code, 302
        )

    def test_saved_state_on_browse_and_detail(self):
        for url in (
            reverse("jobs:opportunities"),
            reverse("jobs:detail", args=[self.job.pk]),
        ):
            self.assertContains(self.client.get(url), 'aria-pressed="false"')
        SavedJob.objects.create(candidate=self.owner, job=self.job)
        for url in (
            reverse("jobs:opportunities"),
            reverse("jobs:detail", args=[self.job.pk]),
        ):
            self.assertContains(self.client.get(url), 'aria-pressed="true"')

    def test_saved_page_is_paginated_and_not_cached(self):
        jobs = [
            JobPosting(
                recruiter=self.recruiter,
                title=f"Role {i}",
                company="Example",
                location="Remote",
                description="Work",
            )
            for i in range(21)
        ]
        JobPosting.objects.bulk_create(jobs)
        SavedJob.objects.bulk_create(
            [SavedJob(candidate=self.owner, job=job) for job in jobs]
        )
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.context["page"]), 20)
        self.assertIn("no-store", response.headers["Cache-Control"])
        response = self.client.get(self.list_url + "?page=2")
        self.assertEqual(len(response.context["page"]), 1)

    def test_removing_favourite_keeps_submitted_application(self):
        application = Application.objects.create(
            candidate=self.owner,
            job=self.job,
            status="submitted",
            profile_snapshot={"summary": "Saved evidence"},
        )
        self.client.post(self.url, {"action": "save"})
        self.client.post(self.url, {"action": "remove"})
        application.refresh_from_db()
        self.assertEqual(application.profile_snapshot, {"summary": "Saved evidence"})
        self.assertEqual(application.status, "submitted")
