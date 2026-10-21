"""Dashboard facts, scoped selectors and connected application review flows."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from applications.models import Application
from candidates.models import CandidateProfile, CandidateSkill
from jobs.models import JobPosting, JobSkill
from matching.corpus import build_corpus
from matching.models import CatalogueSkill, MatchRun, SkillCatalogue, SkillLabel
from matching.services import generate_matches


class WorkspaceTests(TestCase):
    def test_job_search_finds_displayed_company_names_and_keeps_closed_jobs_private(
        self,
    ):
        self.job.company = "Demo Studio"
        self.job.save(update_fields=["company"])
        self.foreign_job.company = "Demo Studio"
        self.foreign_job.status = "closed"
        self.foreign_job.save(update_fields=["company", "status"])
        self.client.force_login(self.candidate)
        for query in ("savanna", "SAVANNA STUDIO", "Studio"):
            with self.subTest(query=query):
                response = self.client.get(reverse("jobs:opportunities"), {"q": query})
                self.assertContains(response, "Savanna Studio")
                self.assertContains(response, self.job.title)
                self.assertNotContains(response, self.foreign_job.title)
                self.assertNotContains(response, "Demo Studio")
        self.assertContains(
            self.client.get(reverse("jobs:opportunities"), {"q": "Remote"}),
            self.job.title,
        )

    def test_new_job_preview_renders_without_saved_relationships(self):
        self.client.force_login(self.recruiter)
        response = self.client.get(reverse("jobs:create"))
        self.assertContains(response, "Job preview")
        self.assertContains(response, "data-job-preview")
        self.assertFalse(response.context["job"].created_at)

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.candidate = User.objects.create_user(
            username="workspace-candidate",
            email="workspace-candidate@example.test",
            first_name="Alex",
        )
        cls.other = User.objects.create_user(
            username="workspace-other", email="workspace-other@example.test"
        )
        cls.recruiter = User.objects.create_user(
            username="workspace-recruiter",
            email="workspace-recruiter@example.test",
            role="recruiter",
        )
        cls.outsider = User.objects.create_user(
            username="workspace-outsider",
            email="workspace-outsider@example.test",
            role="recruiter",
        )
        profile = CandidateProfile.objects.create(
            user=cls.candidate, headline="Python developer", summary="Python software"
        )
        CandidateSkill.objects.create(profile=profile, name="Python")
        cls.job = JobPosting.objects.create(
            recruiter=cls.recruiter,
            title="Workspace developer",
            company="Example",
            description="Python software",
            location="Remote",
        )
        JobSkill.objects.create(job=cls.job, name="Python", requirement="required")
        cls.foreign_job = JobPosting.objects.create(
            recruiter=cls.outsider,
            title="Foreign role",
            company="Other company",
            description="Python",
            location="Remote",
        )
        catalogue = SkillCatalogue.objects.create(
            version="workspace-fixture",
            source_url="https://ec.europa.eu/esco/api/resource/skill",
            checksum="b" * 64,
            skill_count=1,
            active=True,
        )
        concept = CatalogueSkill.objects.create(
            catalogue=catalogue,
            uri="http://data.europa.eu/esco/skill/workspace-fixture",
            preferred_label="Python",
            description="Python software",
        )
        SkillLabel.objects.create(
            skill=concept, label="Python", normalized="python", preferred=True
        )
        build_corpus()
        cls.submitted = Application.objects.create(
            candidate=cls.candidate,
            job=cls.job,
            status="reviewing",
            candidate_name="Alex Example",
            profile_snapshot={
                "profile": {"summary": "Python software"},
                "skills": [{"name": "Python"}],
            },
        )
        cls.draft = Application.objects.create(
            candidate=cls.other, job=cls.job, status="draft"
        )
        cls.foreign = Application.objects.create(
            candidate=cls.other,
            job=cls.foreign_job,
            status="shortlisted",
            candidate_name="Private candidate",
        )

    def test_candidate_dashboard_uses_real_owner_counts_and_never_creates_matches(self):
        self.client.force_login(self.candidate)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(response.context["active_application_count"], 1)
        self.assertEqual(response.context["completed_sections"], 2)
        self.assertEqual(response.context["completion"], 40)
        self.assertEqual(response.context["recommended_count"], 0)
        self.assertEqual(response.context["next_section"]["anchor"], "education")
        self.assertFalse(MatchRun.objects.exists())

    def test_recruiter_dashboard_counts_only_owned_submissions(self):
        self.client.force_login(self.recruiter)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(response.context["open_job_count"], 1)
        self.assertEqual(response.context["application_count"], 1)
        self.assertEqual(response.context["shortlisted_count"], 0)
        self.assertNotContains(response, "Foreign role")

    def test_inbox_excludes_drafts_and_other_recruiters(self):
        self.client.force_login(self.recruiter)
        page = reverse("applications:inbox")
        response = self.client.get(page)
        self.assertEqual(list(response.context["applications"]), [self.submitted])
        self.assertEqual(response.context["selected"], self.submitted)
        for app in (self.draft, self.foreign):
            self.assertEqual(
                self.client.get(page, {"application": app.pk}).status_code, 404
            )
        self.assertEqual(
            self.client.get(page, {"application": "bad-id"}).status_code, 404
        )
        self.client.force_login(self.candidate)
        self.assertEqual(self.client.get(page).status_code, 403)

    def test_candidate_application_filter_and_selection_remain_private(self):
        self.client.force_login(self.candidate)
        page = reverse("applications:mine")
        response = self.client.get(
            page, {"status": "reviewing", "application": self.submitted.pk}
        )
        self.assertEqual(response.context["selected"], self.submitted)
        response = self.client.get(page, {"status": "shortlisted"})
        self.assertFalse(response.context["applications"].exists())
        self.assertEqual(
            self.client.get(page, {"application": self.foreign.pk}).status_code, 404
        )
        self.assertEqual(
            self.client.get(page, {"application": "invalid"}).status_code, 404
        )

    def test_job_picker_restricts_jobs_and_handles_empty_workspace(self):
        self.client.force_login(self.recruiter)
        page = reverse("matches:workspace")
        self.assertRedirects(
            self.client.get(page), reverse("matches:applicants", args=[self.job.pk])
        )
        self.assertEqual(
            self.client.get(page, {"job": self.foreign_job.pk}).status_code, 404
        )
        self.assertEqual(self.client.get(page, {"job": "invalid"}).status_code, 404)
        user = get_user_model().objects.create_user(
            username="empty-recruiter",
            email="empty-recruiter@example.test",
            role="recruiter",
        )
        self.client.force_login(user)
        self.assertContains(self.client.get(page), "Start with a job.")

    def test_selected_ranking_panel_cannot_load_another_run(self):
        run = generate_matches(self.recruiter, self.job)
        other_run = generate_matches(self.outsider, self.foreign_job)
        result = run.results.get()
        foreign_result = other_run.results.get()
        self.client.force_login(self.recruiter)
        page = reverse("matches:applicants", args=[self.job.pk])
        response = self.client.get(page, {"candidate": result.pk})
        self.assertEqual(response.context["selected"], result)
        self.assertContains(
            response, reverse("applications:detail", args=[self.submitted.pk])
        )
        self.assertEqual(
            self.client.get(page, {"candidate": foreign_result.pk}).status_code, 404
        )
        self.assertEqual(
            self.client.get(page, {"candidate": "invalid"}).status_code, 404
        )

    def test_profile_and_editor_keep_manual_document_flow(self):
        self.client.force_login(self.candidate)
        for name in ("candidates:profile", "candidates:profile_edit"):
            response = self.client.get(reverse(name))
            self.assertContains(response, "data-section-nav")
            self.assertContains(response, "Your CV &amp; supporting documents")
            self.assertNotContains(response, "Import from your CV")

    def test_application_detail_connects_owned_ranking_to_review(self):
        result = generate_matches(self.recruiter, self.job).results.get()
        self.client.force_login(self.recruiter)
        response = self.client.get(
            reverse("applications:detail", args=[self.submitted.pk])
        )
        self.assertContains(response, reverse("matches:detail", args=[result.pk]))
        self.assertContains(response, "Update status")
        self.assertContains(response, "Application progress")
