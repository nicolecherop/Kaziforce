"""Catalogue imports, deterministic mappings, privacy and immutable application provenance."""

import csv
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from applications.services import save_application
from candidates.models import CandidateProfile, CandidateSkill
from jobs.models import JobPosting, JobSkill
from matching.catalogue import import_catalogue
from matching.models import CatalogueSkill, SkillCatalogue, SkillLabel
from matching.normalization import normalize_skill
from matching.skills import skill_suggestions, standardize_skills

SOURCE = "https://ec.europa.eu/esco/api/resource/skill"


def csv_content(rows):
    stream = StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=[
            "conceptUri",
            "preferredLabel",
            "altLabels",
            "description",
            "status",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def skill_row(number, label, aliases="", **changes):
    return {
        "conceptUri": f"http://data.europa.eu/esco/skill/00000000-0000-0000-0000-{number:012d}",
        "preferredLabel": label,
        "altLabels": aliases,
        "description": "Synthetic test fixture, not an ESCO export.",
        "status": "released",
    } | changes


class SkillCatalogueTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "skills.csv"
        self.rows = [
            skill_row(1, "Python", "Python programming\nPYTHON"),
            skill_row(2, "SQL", "Structured Query Language"),
            skill_row(3, "C++", "C plus plus"),
            skill_row(4, "C#", "C sharp"),
        ]
        self.write(self.rows)

    def write(self, rows):
        self.path.write_text(csv_content(rows), encoding="utf-8")

    def load(self, version="v1.2.0", activate=True):
        return import_catalogue(self.path, version, SOURCE, activate)[0]

    def test_imports_uris_preferred_and_alternative_labels_with_checksum_and_source(
        self,
    ):
        catalogue = self.load()
        self.assertEqual(catalogue.skill_count, 4)
        self.assertTrue(catalogue.active)
        self.assertEqual(len(catalogue.checksum), 64)
        self.assertEqual(catalogue.source_url, SOURCE)
        self.assertEqual(catalogue.skills.count(), 4)
        self.assertEqual(
            SkillLabel.objects.filter(skill__preferred_label="Python").count(), 2
        )

    def test_reimport_is_idempotent_but_same_version_with_changed_content_is_rejected(
        self,
    ):
        original = self.load()
        self.assertEqual(self.load(version="1.2.0").pk, original.pk)
        self.assertEqual(SkillCatalogue.objects.count(), 1)
        self.write([skill_row(1, "Changed label")])
        with self.assertRaisesMessage(ValueError, "different content"):
            self.load()
        original.refresh_from_db()
        self.assertTrue(original.active)
        self.assertEqual(original.skills.count(), 4)

    def test_importing_new_version_does_not_activate_until_requested(self):
        original = self.load()
        newer, created = import_catalogue(self.path, "v1.2.1", SOURCE)
        self.assertTrue(created)
        self.assertFalse(newer.active)
        self.assertEqual(SkillCatalogue.objects.get(active=True), original)
        self.load(version="v1.2.1")
        self.assertEqual(SkillCatalogue.objects.get(active=True), newer)
        self.assertEqual(original.skills.count(), 4)

    def test_malformed_duplicate_or_incomplete_import_leaves_active_version_unchanged(
        self,
    ):
        original = self.load()
        for rows in (
            [],
            [skill_row(1, "")],
            [skill_row(1, "A"), skill_row(1, "B")],
            [skill_row(1, "A", conceptUri="https://example.test/skill")],
            [skill_row(1, "A" * 501)],
        ):
            self.write(rows)
            with self.assertRaises(ValueError):
                self.load(version="v1.2.1")
            self.assertEqual(SkillCatalogue.objects.get(active=True), original)
            self.assertEqual(SkillCatalogue.objects.count(), 1)
        self.path.write_text(
            "conceptUri,preferredLabel\nbroken,missing columns", encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            self.load(version="v1.2.1")

    def test_obsolete_skills_are_excluded_and_utf8_bom_is_accepted(self):
        self.write(self.rows + [skill_row(5, "Obsolete skill", status="obsolete")])
        self.path.write_bytes(b"\xef\xbb\xbf" + self.path.read_bytes())
        self.assertEqual(self.load().skill_count, 4)

    def test_write_failure_rolls_back_all_reference_rows_and_activation(self):
        original = self.load()
        with patch(
            "matching.catalogue.SkillLabel.objects.bulk_create",
            side_effect=IntegrityError("write failure"),
        ):
            with self.assertRaises(IntegrityError):
                self.load(version="v1.2.1")
        self.assertEqual(SkillCatalogue.objects.get(active=True), original)
        self.assertEqual(CatalogueSkill.objects.count(), 4)

    def test_cli_reports_invalid_input_and_explicit_version_source_validation(self):
        for version, source in (
            ("latest", SOURCE),
            ("v1.2.0", "https://example.test/data"),
        ):
            with self.assertRaises(CommandError):
                call_command(
                    "import_esco",
                    str(self.path),
                    catalogue_version=version,
                    source_url=source,
                    stdout=StringIO(),
                )
        with self.assertRaises(CommandError):
            call_command(
                "import_esco",
                str(self.path.with_name("absent.csv")),
                catalogue_version="v1.2.0",
                stdout=StringIO(),
            )

    def test_case_whitespace_and_unicode_variants_map_without_losing_original_names(
        self,
    ):
        catalogue = self.load()
        names = ["  PYTHON   programming  ", "ＳＱＬ", "C plus plus", "C sharp"]
        result = standardize_skills(names)
        self.assertEqual([row["name"] for row in result["skills"]], names)
        self.assertTrue(all(row["status"] == "mapped" for row in result["skills"]))
        self.assertEqual(result["catalogue"], catalogue.provenance())
        self.assertEqual(result["normalization_version"], "labels-v1")
        self.assertEqual(
            [row["preferred_label"] for row in result["skills"]],
            ["Python", "SQL", "C++", "C#"],
        )

    def test_technical_punctuation_is_preserved_and_unknown_terms_are_not_guessed(self):
        self.load()
        result = standardize_skills(
            ["C", "C++", "C#", "Pythno", "My own specialist skill"]
        )
        self.assertNotEqual(normalize_skill("C++"), normalize_skill("C#"))
        self.assertEqual(
            [row["status"] for row in result["skills"]],
            ["unrecognized", "mapped", "mapped", "unrecognized", "unrecognized"],
        )
        self.assertIsNone(result["skills"][-1]["uri"])

    def test_shared_alias_requires_review_instead_of_arbitrary_selection(self):
        self.write(self.rows + [skill_row(5, "Database programming", "SQL")])
        self.load()
        result = standardize_skills(["SQL", "Structured Query Language"])
        self.assertEqual(result["skills"][0]["status"], "ambiguous")
        self.assertIsNone(result["skills"][0]["uri"])
        self.assertEqual(result["skills"][1]["preferred_label"], "SQL")

    def test_unavailable_catalogue_is_not_misreported_as_success_or_missing_skills(
        self,
    ):
        result = standardize_skills(["Python"])
        self.assertIsNone(result["catalogue"])
        self.assertEqual(result["skills"][0]["status"], "not_checked")
        self.assertEqual(skill_suggestions("Py"), [])

    def test_resolution_is_deterministic_and_queries_are_bounded_for_many_terms(self):
        self.load()
        with self.assertNumQueries(2):
            first = standardize_skills(["Python", "SQL", "Missing"] * 20)
        self.assertEqual(first, standardize_skills(["Python", "SQL", "Missing"] * 20))

    def test_suggestions_use_reference_labels_only_and_respect_length_and_result_limits(
        self,
    ):
        self.write(
            [
                skill_row(number, f"Skill {number}", "Specialist label")
                for number in range(1, 21)
            ]
            + [skill_row(30, "A" * 90, "Skill too long")]
        )
        self.load()
        self.assertEqual(len(skill_suggestions("skill")), 10)
        self.assertEqual(skill_suggestions("x"), [])
        self.assertEqual(skill_suggestions("x" * 81), [])
        self.assertTrue(
            all(len(row["label"]) <= 80 for row in skill_suggestions("skill"))
        )

    def test_search_is_authenticated_read_only_and_does_not_expose_profile_skill_text(
        self,
    ):
        self.load()
        url = reverse("matching:skill_search")
        self.assertEqual(self.client.get(url, {"q": "Py"}).status_code, 302)
        user = get_user_model().objects.create_user(
            username="skill-user", email="skill-user@example.test", role="candidate"
        )
        profile = CandidateProfile.objects.create(user=user)
        CandidateSkill.objects.create(profile=profile, name="Private specialist term")
        self.client.force_login(user)
        response = self.client.get(url, {"q": "Py"})
        self.assertEqual(response.json()["suggestions"][0]["label"], "Python")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(
            self.client.get(url, {"q": "Private"}).json(), {"suggestions": []}
        )
        self.assertEqual(self.client.post(url, {}).status_code, 405)

    def test_original_profile_skills_remain_visible_with_plain_language_messages(
        self,
    ):
        self.load()
        user = get_user_model().objects.create_user(
            username="skill-profile",
            email="skill-profile@example.test",
            role="candidate",
        )
        profile = CandidateProfile.objects.create(user=user)
        for name in ("Python programming", "<script>unknown()</script>"):
            CandidateSkill.objects.create(profile=profile, name=name)
        self.client.force_login(user)
        response = self.client.get(reverse("candidates:profile"))
        self.assertContains(response, "Python programming")
        self.assertNotContains(response, "Recognized as Python")
        self.assertNotContains(response, "Not recognized yet")
        self.assertContains(response, "Skill added.")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>unknown()")
        self.assertEqual(profile.skills.count(), 2)

    def test_submission_freezes_same_catalogue_and_mappings_for_both_sides(self):
        original = self.load()
        User = get_user_model()
        candidate = User.objects.create_user(
            username="mapped-candidate",
            email="mapped-candidate@example.test",
            role="candidate",
        )
        recruiter = User.objects.create_user(
            username="mapped-recruiter",
            email="mapped-recruiter@example.test",
            role="recruiter",
        )
        job = JobPosting.objects.create(
            recruiter=recruiter,
            title="Developer",
            company="Example",
            location="Remote",
            description="Build applications",
        )
        JobSkill.objects.create(job=job, name="Python")
        application = save_application(
            candidate,
            job.pk,
            {
                "profile": {"summary": "Developer"},
                "skills": [{"name": "Python programming"}, {"name": "Kept unknown"}],
            },
            {"cover_letter": "", "documents": []},
            submit=True,
        )
        saved = application.profile_snapshot["skill_standardization"]
        job_saved = application.job_snapshot["structured_requirements"][
            "skill_standardization"
        ]
        self.assertEqual(saved["catalogue"], original.provenance())
        self.assertEqual(saved["catalogue"], job_saved["catalogue"])
        self.assertEqual(saved["skills"][0]["uri"], job_saved["skills"][0]["uri"])
        self.assertEqual(saved["skills"][1]["status"], "unrecognized")
        self.write([skill_row(1, "A different preferred label", "Python")])
        self.load(version="v1.2.1")
        application.refresh_from_db()
        self.assertEqual(application.profile_snapshot["skill_standardization"], saved)
        self.assertEqual(
            application.job_snapshot["structured_requirements"][
                "skill_standardization"
            ],
            job_saved,
        )
        self.client.force_login(candidate)
        response = self.client.get(
            reverse("applications:detail", args=[application.pk])
        )
        self.assertContains(response, "Python programming")
        self.assertContains(
            response, "included with this application when it was submitted"
        )
        self.assertNotContains(response, "Recognized as Python")
        self.assertNotContains(response, "A different preferred label")

    def test_database_prevents_two_active_versions(self):
        self.load()
        with self.assertRaises(IntegrityError), transaction.atomic():
            SkillCatalogue.objects.create(
                version="v1.2.1",
                language="en",
                source_url=SOURCE,
                checksum="a" * 64,
                skill_count=1,
                active=True,
            )
