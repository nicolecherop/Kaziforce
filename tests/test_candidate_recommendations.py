"""Candidate display rules, private detail pages and plain-language skills."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.urls import reverse

from applications.models import Application
from candidates.models import CandidateProfile, CandidateSkill
from jobs.models import JobPosting, JobSkill
from matching.corpus import build_corpus
from matching.models import (
    CatalogueSkill,
    MatchResult,
    MatchRun,
    SkillCatalogue,
    SkillLabel,
)
from matching.recommendations import candidate_recommendations
from matching.services import generate_matches, replay_result


class CandidateRecommendationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.candidate = User.objects.create_user(
            username="recommendation-candidate",
            email="recommendation-candidate@example.test",
        )
        cls.other = User.objects.create_user(
            username="recommendation-other", email="recommendation-other@example.test"
        )
        cls.recruiter = User.objects.create_user(
            username="recommendation-recruiter",
            email="recommendation-recruiter@example.test",
            role="recruiter",
        )
        profile = CandidateProfile.objects.create(
            user=cls.candidate, summary="Python software"
        )
        CandidateSkill.objects.create(profile=profile, name="Python")
        catalogue = SkillCatalogue.objects.create(
            version="recommendation-fixture",
            checksum="c" * 64,
            skill_count=1,
            active=True,
        )
        concept = CatalogueSkill.objects.create(
            catalogue=catalogue,
            uri="http://data.europa.eu/esco/skill/recommendation",
            preferred_label="Python",
            description="Python software",
        )
        SkillLabel.objects.create(
            skill=concept, label="Python", normalized="python", preferred=True
        )
        build_corpus()
        for number in range(14):
            job = JobPosting.objects.create(
                recruiter=cls.recruiter,
                title=f"Opportunity {number}",
                company="Example",
                description="Python software",
                location="Remote",
            )
            JobSkill.objects.create(job=job, name="Python", requirement="required")
        cls.saved_run = generate_matches(cls.candidate)

    def setUp(self):
        self.client.force_login(self.candidate)
        self.results = list(self.saved_run.results.order_by("rank"))

    def test_inclusive_threshold_counts_and_previews_are_consistent(self):
        MatchResult.objects.filter(pk=self.results[0].pk).update(score=Decimal("69.99"))
        MatchResult.objects.filter(pk=self.results[1].pk).update(score=Decimal("70.00"))
        MatchResult.objects.filter(pk=self.results[2].pk).update(score=Decimal("70.01"))
        MatchResult.objects.filter(pk=self.results[3].pk).update(score=None, rank=None)
        expected = [self.results[1].pk, self.results[2].pk] + [
            result.pk for result in self.results[4:12]
        ]
        response = self.client.get(reverse("matches:jobs"))
        self.assertEqual([row.pk for row in response.context["results"]], expected)
        self.assertEqual(response.context["recommended_count"], 10)
        dashboard = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(dashboard.context["recommended_count"], 10)
        self.assertEqual(
            [row.pk for row in dashboard.context["recommended_jobs"]], expected[:3]
        )
        self.assertNotContains(response, "ESCO")
        self.assertNotContains(response, "Missing evidence lowers a score")

    def test_filter_runs_before_limit_and_respects_current_job_and_application_state(
        self,
    ):
        # The saved ranking predates these changes. Never fill the list with them.
        for result in self.results[:2]:
            JobPosting.objects.filter(pk=result.job_id).update(status="closed")
        for result, status in zip(self.results[2:4], ("submitted", "unsuccessful")):
            Application.objects.create(
                candidate=self.candidate, job=result.job, status=status
            )
        Application.objects.create(
            candidate=self.candidate, job=self.results[4].job, status="draft"
        )
        response = self.client.get(reverse("matches:jobs"))
        self.assertEqual(
            [row.pk for row in response.context["results"]],
            [row.pk for row in self.results[4:]],
        )
        self.assertTrue(response.context["stale"])

    @override_settings(MATCH_RECOMMENDATION_MIN_SCORE=90)
    def test_threshold_is_configurable_and_browsing_is_not_filtered(self):
        MatchResult.objects.filter(run=self.saved_run).update(score=Decimal("89.99"))
        self.assertFalse(candidate_recommendations(self.candidate, self.saved_run).exists())
        response = self.client.get(reverse("jobs:opportunities"))
        self.assertEqual(response.context["jobs"].count(), 14)

    def test_no_strong_matches_has_clear_empty_states_without_filler(self):
        MatchResult.objects.filter(run=self.saved_run).update(score=Decimal("69.99"))
        for name in ("matches:jobs", "accounts:dashboard"):
            response = self.client.get(reverse(name))
            self.assertContains(response, "No strong matches right now.")
            self.assertContains(
                response, "Keep your profile up to date or browse available jobs."
            )
            self.assertEqual(response.context["recommended_count"], 0)
            self.assertNotContains(response, self.results[0].job.title)

    def test_no_run_prompts_for_first_matches_and_other_owners_cannot_supply_results(
        self,
    ):
        self.assertFalse(candidate_recommendations(self.other, self.saved_run).exists())
        self.assertFalse(candidate_recommendations(self.recruiter, self.saved_run).exists())
        self.client.force_login(self.other)
        response = self.client.get(reverse("matches:jobs"))
        self.assertContains(response, "Your matches start here")
        self.assertNotContains(response, "No strong matches right now.")
        # A foreign candidate result cannot be displayed even in an owned run.
        MatchResult.objects.filter(pk=self.results[0].pk).update(candidate=self.other)
        self.assertNotIn(
            self.results[0].pk,
            candidate_recommendations(self.candidate, self.saved_run).values_list(
                "pk", flat=True
            ),
        )

    def test_candidate_html_omits_internal_evidence_and_gets_preserve_saved_results(
        self,
    ):
        result = self.results[0]
        replayed = replay_result(result)
        saved = list(MatchResult.objects.order_by("pk").values())
        runs = list(MatchRun.objects.order_by("pk").values())
        response = self.client.get(reverse("matches:detail", args=[result.pk]))
        self.assertTemplateUsed(response, "matching/candidate_match_detail.html")
        self.assertContains(response, "Match score")
        self.assertContains(response, "Keep your profile accurate")
        self.assertContains(response, "Python")
        self.assertNotIn("candidate_evidence", response.context)
        for text in (
            "Points to review",
            "How the score was calculated",
            "Share of total",
            "Saved evidence",
            "Reference checksum",
            result.run.corpus.checksum,
            "Matched from the profile",
            "Not recorded in the profile",
            "ESCO",
        ):
            self.assertNotContains(response, text)
        self.client.get(reverse("matches:jobs"))
        self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(list(MatchResult.objects.order_by("pk").values()), saved)
        self.assertEqual(list(MatchRun.objects.order_by("pk").values()), runs)
        self.assertEqual(replay_result(result), replayed)
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.get(reverse("matches:detail", args=[result.pk])).status_code,
            404,
        )

    def test_old_low_score_details_are_private_and_do_not_claim_a_strong_match(self):
        result = self.results[0]
        MatchResult.objects.filter(pk=result.pk).update(score=Decimal("30.00"))
        profile = self.candidate.candidate_profile
        profile.summary = "A changed professional summary"
        profile.save()
        response = self.client.get(reverse("matches:detail", args=[result.pk]))
        self.assertContains(response, "30%")
        self.assertContains(response, "since this match was saved")
        self.assertNotContains(response, "This role may be a good fit")
        MatchResult.objects.filter(pk=result.pk).update(score=None, rank=None)
        self.assertContains(
            self.client.get(reverse("matches:detail", args=[result.pk])),
            "Match score unavailable",
        )

    def test_recruiter_low_scores_and_detailed_evidence_are_retained(self):
        application = Application.objects.create(
            candidate=self.candidate,
            job=self.results[0].job,
            status="submitted",
            profile_snapshot={
                "profile": {"summary": "Python software"},
                "skills": [{"name": "Python"}],
            },
        )
        run = generate_matches(self.recruiter, application.job)
        result = run.results.get()
        MatchResult.objects.filter(pk=result.pk).update(score=Decimal("20.00"))
        self.client.force_login(self.recruiter)
        response = self.client.get(
            reverse("matches:applicants", args=[application.job_id])
        )
        self.assertEqual([row.pk for row in response.context["results"]], [result.pk])
        response = self.client.get(reverse("matches:detail", args=[result.pk]))
        self.assertTemplateUsed(response, "matching/match_detail.html")
        for text in (
            "How the score was calculated",
            "Points to review",
            "Saved evidence and scoring reference",
        ):
            self.assertContains(response, text)
        self.assertFalse(candidate_recommendations(self.candidate, run).exists())
        self.client.force_login(self.candidate)
        self.assertEqual(
            self.client.get(reverse("matches:detail", args=[result.pk])).status_code,
            404,
        )


class SkillMessageTests(TestCase):
    def test_skill_names_are_kept_and_messages_do_not_expose_catalogue_details(self):
        for status, message in (
            ("mapped", ""),
            ("unrecognized", "Skill added."),
            ("not_checked", "Skill added."),
            ("ambiguous", "Skill added. A more specific name may improve matching."),
        ):
            with self.subTest(status=status):
                html = render_to_string(
                    "components/skill_review.html",
                    {
                        "standardization": {
                            "skills": [
                                {
                                    "name": "<Custom skill>",
                                    "status": status,
                                    "preferred_label": "Internal catalogue wording",
                                }
                            ]
                        }
                    },
                )
                self.assertIn("&lt;Custom skill&gt;", html)
                self.assertNotIn("Internal catalogue wording", html)
                self.assertNotIn("Not recognized", html)
                self.assertNotIn("Needs review", html)
                if message:
                    self.assertIn(message, html)
                else:
                    self.assertNotIn("skill-status", html)
