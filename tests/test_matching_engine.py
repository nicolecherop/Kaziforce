"""Deterministic math, submitted evidence, persistence and workspace boundaries."""

from datetime import date
from decimal import Decimal
from math import log, sqrt
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase, Client
from django.urls import reverse

from applications.models import Application
from candidates.models import CandidateProfile, CandidateSkill
from jobs.models import JobPosting, JobSkill
from matching.corpus import build_corpus, reference_for
from matching.inputs import capture_job, professional_profile, standardize_pairs
from matching.models import (
    CatalogueSkill,
    SkillCatalogue,
    SkillLabel,
    MatchRun,
    MatchResult,
)
from matching.normalization import normalize_skill
from matching.scoring import MatchingError, experience_years, score_pair
from matching.services import generate_matches, replay_result, run_is_current
from matching.vectorization import cosine, document_frequencies, tokens, vector


def profile(*skills, summary="Python software"):
    return {
        "profile": {"summary": summary},
        "skills": [{"name": name} for name in skills],
        "education": [],
        "certifications": [],
        "experience": [],
    }


class VectorTests(SimpleTestCase):
    def test_smoothed_idf_sublinear_tf_and_l2_match_hand_calculation(self):
        count, frequencies = document_frequencies(["python python sql", "python"])
        result = vector("python python sql", frequencies, count)
        python = 1 + log(2)
        sql = 1 + log(3 / 2)
        length = sqrt(python**2 + sql**2)
        self.assertAlmostEqual(result["python"], python / length)
        self.assertAlmostEqual(result["sql"], sql / length)
        self.assertEqual(frequencies, {"python": 2, "sql": 1})

    def test_cosine_identity_disjoint_empty_and_unknown_vocabulary(self):
        frequencies = {"python": 1, "sql": 1}
        self.assertAlmostEqual(cosine("python sql", "sql python", frequencies, 2), 1)
        for other in ("sql", "", "unknown"):
            self.assertEqual(cosine("python", other, frequencies, 2), 0)

    def test_technical_tokens_preserve_distinctions(self):
        self.assertEqual(
            tokens("C++ C# .NET Python SQL the 123"),
            ["c++", "c#", ".net", "python", "sql"],
        )

    def test_overlapping_current_and_future_experience(self):
        rows = [
            {"start_date": "2020-01-01", "end_date": "2022-01-01"},
            {"start_date": "2021-01-01", "currently_working": True},
            {"start_date": "2026-01-01", "currently_working": True},
            {"start_date": None, "end_date": None},
        ]
        years, incomplete = experience_years(rows, date(2023, 1, 1))
        self.assertAlmostEqual(
            years, (date(2023, 1, 1) - date(2020, 1, 1)).days / 365.25
        )
        self.assertTrue(incomplete)

    def test_professional_whitelist_excludes_identity_and_documents(self):
        snapshot = profile("Python") | {
            "identity": {"name": "Private"},
            "documents": ["private.pdf"],
        }
        snapshot["profile"]["location"] = "Private location"
        snapshot["education"] = [
            {
                "qualification": "Degree",
                "institution": "Private college",
                "field_of_study": "Software",
            }
        ]
        snapshot["experience"] = [
            {"job_title": "Developer", "company": "Private employer"}
        ]
        result = str(professional_profile(snapshot))
        self.assertNotIn("Private", result)
        self.assertNotIn("private.pdf", result)


class MatchingEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.candidate = User.objects.create_user(
            username="match-candidate", email="match-candidate@example.test"
        )
        cls.other = User.objects.create_user(
            username="match-other", email="match-other@example.test"
        )
        cls.recruiter = User.objects.create_user(
            username="match-recruiter",
            email="match-recruiter@example.test",
            role="recruiter",
        )
        cls.outsider = User.objects.create_user(
            username="match-outsider",
            email="match-outsider@example.test",
            role="recruiter",
        )
        CandidateProfile.objects.create(user=cls.candidate, summary="Python software")
        CandidateSkill.objects.create(
            profile=cls.candidate.candidate_profile, name="Python programming"
        )
        cls.job = JobPosting.objects.create(
            recruiter=cls.recruiter,
            title="Python developer",
            company="Example",
            location="Remote",
            description="Python software",
            status="open",
        )
        JobSkill.objects.create(
            job=cls.job, name="Python", requirement="required", priority=3
        )
        JobSkill.objects.create(
            job=cls.job, name="SQL", requirement="preferred", priority=1
        )
        cls.catalogue = SkillCatalogue.objects.create(
            version="synthetic-v1",
            language="en",
            source_url="https://ec.europa.eu/esco/api/resource/skill",
            checksum="a" * 64,
            skill_count=3,
            active=True,
        )
        for number, (label, aliases, description) in enumerate(
            [
                (
                    "Python",
                    ["Python programming"],
                    "Python software developer programming",
                ),
                ("SQL", [], "SQL data database"),
                ("Education", [], "bachelors software diploma education experience"),
            ]
        ):
            skill = CatalogueSkill.objects.create(
                catalogue=cls.catalogue,
                uri=f"http://data.europa.eu/esco/skill/{number}",
                preferred_label=label,
                description=description,
            )
            for word in [label, *aliases]:
                SkillLabel.objects.create(
                    skill=skill,
                    label=word,
                    normalized=normalize_skill(word),
                    preferred=word == label,
                )
        cls.corpus = build_corpus()[0]

    def calculate(self, candidate_profile, job=None):
        pair = {"profile": candidate_profile, "job": capture_job(job or self.job)}
        standardize_pairs([pair], self.catalogue)
        return score_pair(
            pair["profile"], pair["job"], reference_for(self.corpus), date(2026, 1, 1)
        )

    def application(self, user=None, snapshot=None, status="submitted"):
        return Application.objects.create(
            candidate=user or self.candidate,
            job=self.job,
            profile_snapshot=profile("Python") if snapshot is None else snapshot,
            status=status,
            candidate_name="Submitted Person",
            candidate_email="submitted@example.test",
        )

    def test_priority_weighted_coverage_recognizes_alias_and_missing_preferred(self):
        result = self.calculate(profile("Python programming"))
        coverage = next(row for row in result["components"] if row["key"] == "skills")
        self.assertAlmostEqual(coverage["raw_value"], 6 / 7)
        self.assertEqual(result["explanation"]["matched_skills"][0]["label"], "Python")
        self.assertEqual(
            result["explanation"]["missing_preferred_skills"][0]["name"], "SQL"
        )

    def test_alias_duplicates_do_not_inflate_coverage(self):
        self.assertEqual(
            self.calculate(profile("Python"))["score"],
            self.calculate(profile("Python", "Python programming"))["score"],
        )

    def test_priority_changes_total_in_expected_direction(self):
        before = self.calculate(profile("Python"))["score"]
        self.job.skills.filter(name="SQL").update(priority=3, requirement="required")
        after = self.calculate(profile("Python"))["score"]
        self.assertLess(after, before)

    def test_unrecognized_skills_use_exact_normalized_wording_only(self):
        self.job.skills.all().delete()
        JobSkill.objects.create(
            job=self.job, name="Internal toolkit", requirement="required", priority=1
        )
        result = self.calculate(profile("INTERNAL  toolkit"))
        self.assertTrue(
            result["explanation"]["matched_skills"][0]["exact_wording_only"]
        )
        self.assertEqual(
            self.calculate(profile("Internal tool"))["explanation"]["matched_skills"],
            [],
        )

    def test_ambiguous_alias_is_never_assigned_to_a_concept(self):
        for skill in self.catalogue.skills.all()[:2]:
            SkillLabel.objects.create(
                skill=skill, label="Shared alias", normalized="shared alias"
            )
        self.job.skills.all().delete()
        JobSkill.objects.create(
            job=self.job, name="Shared alias", requirement="required"
        )
        result = self.calculate(profile("Python"))
        self.assertEqual(result["explanation"]["matched_skills"], [])
        self.assertIn("Shared alias", result["explanation"]["unresolved_skills"])

    def test_missing_candidate_evidence_scores_zero_and_inactive_components_do_not_contribute(
        self,
    ):
        result = self.calculate(profile(summary="unknownvocabulary"))
        self.assertEqual(result["score"], Decimal("0.00"))
        self.assertEqual(sum(row["weight"] for row in result["components"]), 70)
        self.assertAlmostEqual(
            sum(row["share"] for row in result["components"]), 100, places=3
        )

    def test_empty_profile_is_unscorable(self):
        with self.assertRaises(MatchingError):
            self.calculate(profile(summary=""))

    def test_headline_is_professional_scoring_evidence(self):
        candidate = profile(summary="")
        candidate["profile"]["headline"] = "Python software developer"
        self.assertGreater(self.calculate(candidate)["score"], 0)

    def test_daily_date_change_marks_saved_review_stale(self):
        run = generate_matches(self.candidate)
        with patch(
            "matching.services.timezone.localdate", return_value=date(2040, 1, 1)
        ):
            self.assertFalse(run_is_current(run, self.candidate))

    def test_missing_reference_creates_no_partial_history(self):
        SkillCatalogue.objects.update(active=False)
        with self.assertRaises(MatchingError):
            generate_matches(self.candidate)
        self.assertFalse(MatchRun.objects.exists())

    def test_ranking_ignores_later_profile_edits_and_detects_job_edits(self):
        self.application()
        run = generate_matches(self.recruiter, self.job)
        self.candidate.candidate_profile.skills.all().delete()
        self.assertTrue(run_is_current(run, self.recruiter, self.job))
        self.job.description = "Changed role"
        self.job.save()
        self.assertFalse(run_is_current(run, self.recruiter, self.job))

    def test_database_rejects_partial_score_rank_and_out_of_range(self):
        result = generate_matches(self.candidate).results.get()
        for changes in ({"score": None}, {"rank": None}, {"score": Decimal("100.01")}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                MatchResult.objects.filter(pk=result.pk).update(**changes)

    def test_candidate_run_refuses_truncated_input(self):
        JobPosting.objects.bulk_create(
            [
                JobPosting(
                    recruiter=self.recruiter,
                    title=f"Role {number}",
                    company="Example",
                    description="Python",
                    status="open",
                )
                for number in range(500)
            ]
        )
        with self.assertRaisesMessage(MatchingError, "too many open jobs"):
            generate_matches(self.candidate)
        self.assertFalse(MatchRun.objects.exists())

    def test_education_priority_and_experience_duration_are_explicit(self):
        self.job.education_level = "bachelors"
        self.job.education_field = "Software"
        self.job.education_priority = 3
        self.job.minimum_experience_years = Decimal("4.0")
        candidate = profile("Python")
        candidate["education"] = [
            {
                "qualification": self.job.get_education_level_display(),
                "field_of_study": "Software",
            }
        ]
        candidate["experience"] = [
            {
                "job_title": "Developer",
                "description": "Python",
                "start_date": "2024-01-01",
                "end_date": "2026-01-01",
            }
        ]
        result = self.calculate(candidate)
        education = next(
            row for row in result["components"] if row["key"] == "education"
        )
        experience = next(
            row for row in result["components"] if row["key"] == "experience"
        )
        self.assertEqual(education["weight"], 45)
        self.assertAlmostEqual(education["raw_value"], 1)
        self.assertAlmostEqual(experience["raw_value"], 731 / 365.25 / 4)

    def test_recommendations_exclude_closed_and_submitted_but_include_drafts(self):
        draft = self.application(status="draft")
        run = generate_matches(self.candidate)
        self.assertEqual(run.results.count(), 1)
        draft.status = "submitted"
        draft.save()
        with self.assertRaisesMessage(MatchingError, "No new open jobs"):
            generate_matches(self.candidate)
        draft.delete()
        self.job.status = "closed"
        self.job.save()
        with self.assertRaisesMessage(MatchingError, "No new open jobs"):
            generate_matches(self.candidate)

    def test_rankings_use_submitted_snapshot_and_do_not_change_application_status(self):
        app = self.application(snapshot=profile("SQL", summary="SQL data"))
        self.application(self.other, status="draft")
        run = generate_matches(self.recruiter, self.job)
        result = run.results.get()
        self.assertEqual(result.input_snapshot["profile"]["skills"], [{"name": "SQL"}])
        self.assertEqual(result.application_id, app.pk)
        app.refresh_from_db()
        self.assertEqual(app.status, "submitted")

    def test_unscorable_application_is_retained_separately(self):
        self.application(snapshot={})
        result = generate_matches(self.recruiter, self.job).results.get()
        self.assertIsNone(result.score)
        self.assertIsNone(result.rank)
        self.assertIn("unavailable", result.explanation)

    def test_saved_result_replays_after_profile_job_and_catalogue_changes(self):
        result = generate_matches(self.candidate).results.get()
        before = replay_result(result)
        self.candidate.candidate_profile.skills.all().delete()
        self.job.description = "SQL"
        self.job.save()
        SkillCatalogue.objects.update(active=False)
        self.assertEqual(replay_result(result), before)
        self.assertEqual(before["score"], result.score)
        self.assertFalse(run_is_current(result.run, self.candidate))

    def test_corpus_is_idempotent_and_input_or_reference_tampering_is_rejected(self):
        self.assertEqual(build_corpus()[0].pk, self.corpus.pk)
        self.assertFalse(build_corpus()[1])
        result = generate_matches(self.candidate).results.get()
        result.input_snapshot["profile"]["profile"]["summary"] = "tampered"
        with self.assertRaisesMessage(MatchingError, "inputs failed"):
            replay_result(result)
        result.refresh_from_db()
        result.run.corpus.document_frequencies["python"] = 99
        with self.assertRaisesMessage(MatchingError, "reference failed"):
            replay_result(result)

    def test_staleness_detects_professional_edits_but_not_identity_edits(self):
        run = generate_matches(self.candidate)
        self.assertTrue(run_is_current(run, self.candidate))
        self.candidate.first_name = "Changed identity"
        self.candidate.save()
        self.assertTrue(run_is_current(run, self.candidate))
        self.candidate.candidate_profile.summary = "SQL"
        self.candidate.candidate_profile.save()
        self.assertFalse(run_is_current(run, self.candidate))

    def test_contact_changes_do_not_affect_matching_evidence_or_score(self):
        run = generate_matches(self.candidate)
        original = replay_result(run.results.get())
        profile = self.candidate.candidate_profile
        profile.contact_email = "private-contact@kaziforce.co.ke"
        profile.phone_number = "+254 712 345 678"
        profile.save()
        self.assertTrue(run_is_current(run, self.candidate))
        fresh = generate_matches(self.candidate).results.get()
        self.assertEqual(fresh.score, original["score"])
        self.assertNotIn("contact_email", fresh.input_snapshot["profile"]["profile"])
        self.assertNotIn("phone_number", fresh.input_snapshot["profile"]["profile"])

    def test_unrelated_applicants_cannot_change_existing_score(self):
        self.application()
        first = generate_matches(self.recruiter, self.job).results.get()
        self.application(self.other, profile("SQL"))
        second = generate_matches(self.recruiter, self.job).results.get(
            candidate=self.candidate
        )
        self.assertEqual(first.score, second.score)
        self.assertEqual(first.run.corpus_id, second.run.corpus_id)

    def test_failed_result_write_rolls_back_run(self):
        with patch.object(
            MatchResult.objects, "bulk_create", side_effect=IntegrityError("test")
        ):
            with self.assertRaises(IntegrityError):
                generate_matches(self.candidate)
        self.assertEqual(MatchRun.objects.count(), 0)

    def test_service_rejects_other_recruiter_and_wrong_role(self):
        for user, job in [
            (self.outsider, self.job),
            (self.candidate, self.job),
            (self.recruiter, None),
        ]:
            with self.assertRaises(MatchingError):
                generate_matches(user, job)

    def test_private_pages_post_only_refresh_and_csrf(self):
        self.client.force_login(self.candidate)
        self.assertEqual(self.client.get(reverse("matches:jobs")).status_code, 200)
        self.assertEqual(MatchRun.objects.count(), 0)
        self.assertEqual(
            self.client.get(reverse("matches:refresh_jobs")).status_code, 405
        )
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.candidate)
        self.assertEqual(strict.post(reverse("matches:refresh_jobs")).status_code, 403)
        response = self.client.post(reverse("matches:refresh_jobs"), follow=True)
        self.assertContains(response, "View match")
        self.assertIn("no-store", response.headers["Cache-Control"])
        result = MatchResult.objects.get()
        detail = reverse("matches:detail", args=[result.pk])
        self.assertContains(self.client.get(detail), "Considering this opportunity?")
        self.assertNotContains(self.client.get(detail), "How the score was calculated")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(
            self.client.get(
                reverse("matches:applicants", args=[self.job.pk])
            ).status_code,
            403,
        )

    def test_ranking_page_top_ten_stable_ties_and_ownership(self):
        for number in range(12):
            user = get_user_model().objects.create_user(
                username=f"rank{number}", email=f"rank{number}@example.test"
            )
            self.application(user)
        self.client.force_login(self.recruiter)
        page = reverse("matches:applicants", args=[self.job.pk])
        response = self.client.post(
            reverse("matches:refresh_applicants", args=[self.job.pk]), follow=True
        )
        self.assertEqual(len(response.context["results"]), 10)
        self.assertContains(response, 'aria-label="View match for', count=10)
        self.assertContains(response, "Read submitted profile and documents", count=1)
        self.assertContains(response, "12 scored results")
        first = list(
            MatchResult.objects.order_by("rank").values_list(
                "application_id", flat=True
            )
        )
        second = list(
            generate_matches(self.recruiter, self.job)
            .results.order_by("rank")
            .values_list("application_id", flat=True)
        )
        self.assertEqual(first, second)
        detail = reverse("matches:detail", args=[MatchResult.objects.first().pk])
        self.assertContains(self.client.get(detail), "Skill evidence")
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(page).status_code, 404)
        self.assertEqual(
            self.client.post(
                reverse("matches:refresh_applicants", args=[self.job.pk])
            ).status_code,
            404,
        )
        self.assertEqual(self.client.get(detail).status_code, 404)
