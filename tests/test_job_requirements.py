"""Structured requirements validate together, respect ownership and freeze on submission."""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from applications.models import Application
from applications.services import save_application
from jobs.models import JobPosting, JobSkill

User = get_user_model()


class JobRequirementsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.recruiter = User.objects.create_user(
            username="requirements-owner", email="owner@example.test", role="recruiter"
        )
        cls.other = User.objects.create_user(
            username="requirements-other",
            email="other-owner@example.test",
            role="recruiter",
        )
        cls.candidate = User.objects.create_user(
            username="requirements-candidate",
            email="applicant@example.test",
            role="candidate",
        )
        cls.job = JobPosting.objects.create(
            recruiter=cls.recruiter,
            title="Web developer",
            company="Example Studio",
            location="Nairobi",
            description="Build useful web applications.",
            requirements="Portfolio welcome.",
        )

    def setUp(self):
        self.client.force_login(self.recruiter)

    def payload(self, rows=(), initial=0, **changes):
        data = {
            "title": "Web developer",
            "company": "Example Studio",
            "location": "Nairobi",
            "description": "Build useful web applications.",
            "requirements": "Portfolio welcome.",
            "education_level": "diploma",
            "education_field": "Computing or equivalent practical training",
            "education_priority": "2",
            "minimum_experience_years": "1.5",
            "experience_details": "Web application development, including freelance projects.",
            "experience_priority": "3",
            "skills-TOTAL_FORMS": str(len(rows)),
            "skills-INITIAL_FORMS": str(initial),
        }
        for index, row in enumerate(rows):
            for key, value in row.items():
                data[f"skills-{index}-{key}"] = str(value)
        return data | changes

    def edit(self, data):
        return self.client.post(reverse("jobs:edit", args=[self.job.pk]), data)

    def skill(self, **changes):
        return JobSkill.objects.create(
            job=self.job,
            **({"name": "Python", "requirement": "required", "priority": 3} | changes),
        )

    def test_publish_saves_skills_priorities_and_qualification_requirements(self):
        response = self.client.post(
            reverse("jobs:create"),
            self.payload(
                [
                    {"name": "  Python  ", "requirement": "required", "priority": "3"},
                    {
                        "name": "Communication   skills",
                        "requirement": "preferred",
                        "priority": "2",
                    },
                ],
                recruiter=self.other.pk,
            ),
        )
        self.assertRedirects(response, reverse("jobs:manage"))
        job = JobPosting.objects.exclude(pk=self.job.pk).get()
        self.assertEqual(job.recruiter, self.recruiter)
        self.assertEqual(job.minimum_experience_years, Decimal("1.5"))
        self.assertEqual(job.education_level, "diploma")
        self.assertEqual(job.experience_priority, 3)
        self.assertEqual(
            list(job.skills.values_list("name", "requirement", "priority")),
            [("Python", "required", 3), ("Communication skills", "preferred", 2)],
        )

    def test_edit_updates_adds_and_removes_skills_in_one_save(self):
        first, second = self.skill(), self.skill(name="SQL")
        response = self.edit(
            self.payload(
                [
                    {
                        "id": first.pk,
                        "name": "Python",
                        "requirement": "preferred",
                        "priority": 1,
                    },
                    {
                        "id": second.pk,
                        "name": "SQL",
                        "requirement": "required",
                        "priority": 3,
                        "DELETE": "on",
                    },
                    {"name": "Django", "requirement": "required", "priority": 3},
                ],
                initial=2,
            )
        )
        self.assertRedirects(response, reverse("jobs:manage"))
        self.assertEqual(
            set(self.job.skills.values_list("name", "priority")),
            {("Python", 1), ("Django", 3)},
        )

    def test_duplicate_normalized_skills_block_parent_and_child_writes(self):
        response = self.edit(
            self.payload(
                [
                    {"name": " Team   Work ", "requirement": "required", "priority": 1},
                    {"name": "team work", "requirement": "preferred", "priority": 3},
                ],
                title="Should not save",
            )
        )
        self.assertContains(response, "Remove duplicate skills")
        self.job.refresh_from_db()
        self.assertEqual(self.job.title, "Web developer")
        self.assertFalse(self.job.skills.exists())

    def test_unchanged_rendered_rows_and_blank_extra_entry_can_save(self):
        self.skill()
        response = self.client.get(reverse("jobs:edit", args=[self.job.pk]))
        data = self.payload()
        for name, field in response.context["form"].fields.items():
            data[name] = response.context["form"][name].value() or ""
        skills = response.context["skills"]
        data["skills-TOTAL_FORMS"] = skills.total_form_count()
        data["skills-INITIAL_FORMS"] = skills.initial_form_count()
        for index, entry in enumerate(skills):
            for field in entry:
                value = field.value()
                if value not in (None, False, ""):
                    data[f"skills-{index}-{field.name}"] = value
        self.assertRedirects(self.edit(data), reverse("jobs:manage"))
        self.assertEqual(self.job.skills.count(), 1)

    def test_invalid_choices_experience_and_missing_skill_name_block_writes(self):
        for change in [
            {"minimum_experience_years": "-1"},
            {"minimum_experience_years": "61"},
            {"minimum_experience_years": "1.55"},
            {"education_level": "invented"},
            {"education_priority": "4"},
            {"experience_priority": "0"},
            {"skills-0-priority": "999"},
            {"skills-0-requirement": "other"},
            {"skills-0-name": ""},
        ]:
            with self.subTest(change=change):
                response = self.edit(
                    self.payload(
                        [{"name": "Python", "requirement": "preferred", "priority": 3}],
                        title="Invalid update",
                        **change,
                    )
                )
                self.assertEqual(response.status_code, 200)
                self.job.refresh_from_db()
                self.assertEqual(self.job.title, "Web developer")
                self.assertFalse(self.job.skills.exists())

    def test_forged_skill_id_cannot_be_edited_or_deleted_from_another_job(self):
        other_job = JobPosting.objects.create(
            recruiter=self.other,
            title="Other job",
            company="Other",
            location="Remote",
            description="Other role",
        )
        foreign = JobSkill.objects.create(job=other_job, name="SQL")
        for remove in (False, True):
            response = self.edit(
                self.payload(
                    [
                        {
                            "id": foreign.pk,
                            "name": "Changed",
                            "requirement": "required",
                            "priority": 1,
                            "DELETE": "on" if remove else "",
                        }
                    ],
                    initial=1,
                    title="Not saved",
                )
            )
            self.assertEqual(response.status_code, 200)
            foreign.refresh_from_db()
            self.job.refresh_from_db()
            self.assertEqual(foreign.name, "SQL")
            self.assertEqual(self.job.title, "Web developer")
            self.assertFalse(self.job.skills.exists())

    def test_missing_or_excessive_management_data_does_not_save(self):
        for changes in (
            {"skills-TOTAL_FORMS": "10000"},
            {"skills-TOTAL_FORMS": "invalid"},
            {"skills-TOTAL_FORMS": "41"},
        ):
            response = self.edit(self.payload(title="Not saved", **changes))
            self.assertEqual(response.status_code, 200)
        data = self.payload(title="Not saved")
        del data["skills-TOTAL_FORMS"]
        self.assertEqual(self.edit(data).status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.title, "Web developer")

    def test_database_save_failure_rolls_back_job_and_skills(self):
        with patch("jobs.models.JobSkill.save", side_effect=IntegrityError("conflict")):
            response = self.edit(
                self.payload(
                    [{"name": "Python", "requirement": "required", "priority": 3}],
                    title="Not saved",
                )
            )
        self.assertContains(response, "conflict with saved information")
        self.job.refresh_from_db()
        self.assertEqual(self.job.title, "Web developer")
        self.assertFalse(self.job.skills.exists())

    def test_optional_qualifications_zero_experience_and_legacy_text_preserved(self):
        response = self.edit(
            self.payload(
                education_level="any",
                education_field="",
                minimum_experience_years="0",
                experience_details="",
            )
        )
        self.assertRedirects(response, reverse("jobs:manage"))
        self.job.refresh_from_db()
        self.assertEqual(self.job.minimum_experience_years, 0)
        self.assertEqual(self.job.requirements, "Portfolio welcome.")
        self.assertFalse(self.job.skills.exists())
        self.client.force_login(self.candidate)
        response = self.client.get(reverse("jobs:detail", args=[self.job.pk]))
        self.assertContains(response, "0 years minimum")
        self.assertContains(response, "No specific qualification required")

    def test_candidate_sees_required_preferred_and_priorities_with_escaped_text(self):
        self.skill()
        self.skill(name="<script>bad()</script>", requirement="preferred", priority=1)
        self.client.force_login(self.candidate)
        response = self.client.get(reverse("jobs:detail", args=[self.job.pk]))
        for text in (
            "Python",
            "Required",
            "Preferred",
            "High priority",
            "&lt;script&gt;",
        ):
            self.assertContains(response, text)
        self.assertNotContains(response, "<script>bad()")

    def test_new_draft_submission_freezes_latest_requirements_and_labels(self):
        self.skill()
        self.edit(
            self.payload(
                [
                    {
                        "id": self.job.skills.get().pk,
                        "name": "Python",
                        "requirement": "required",
                        "priority": 3,
                    }
                ],
                initial=1,
            )
        )
        application = save_application(
            self.candidate,
            self.job.pk,
            {"profile": {"summary": "My profile"}},
            {"cover_letter": "", "documents": []},
            submit=False,
        )
        self.assertEqual(application.job_snapshot, {})
        application = save_application(
            self.candidate,
            self.job.pk,
            application.profile_snapshot,
            {"cover_letter": "", "documents": []},
            submit=True,
        )
        frozen = application.job_snapshot["structured_requirements"]
        self.assertEqual(frozen["minimum_experience_years"], "1.5")
        self.assertEqual(frozen["education_level_label"], "Diploma")
        self.assertEqual(frozen["skills"][0]["priority_label"], "High")
        self.job.skills.all().delete()
        JobPosting.objects.filter(pk=self.job.pk).update(
            education_level="masters", minimum_experience_years=5
        )
        application.refresh_from_db()
        self.assertEqual(application.job_snapshot["structured_requirements"], frozen)
        self.client.force_login(self.candidate)
        response = self.client.get(
            reverse("applications:detail", args=[application.pk])
        )
        self.assertContains(response, "Job requirements at submission")
        self.assertContains(response, "Diploma")
        self.assertContains(response, "Python")
        self.assertContains(response, "1.5 years minimum")

    def test_older_submitted_applications_remain_readable_without_new_snapshot(self):
        application = Application.objects.create(
            candidate=self.candidate,
            job=self.job,
            status="submitted",
            job_snapshot={"title": "Earlier role", "company": "Example"},
        )
        self.client.force_login(self.candidate)
        response = self.client.get(
            reverse("applications:detail", args=[application.pk])
        )
        self.assertContains(response, "Earlier role")
        self.assertNotContains(response, "Job requirements at submission")

    def test_only_job_owner_can_edit_structured_requirements(self):
        for user, expected in ((self.other, 404), (self.candidate, 403)):
            self.client.force_login(user)
            self.assertEqual(self.edit(self.payload()).status_code, expected)

    def test_database_constraints_reject_duplicate_skills_and_out_of_range_values(self):
        self.skill()
        for operation in (
            lambda: self.skill(name="PYTHON"),
            lambda: self.skill(name="SQL", priority=4),
            lambda: self.skill(name="SQL", requirement="invalid"),
            lambda: JobPosting.objects.filter(pk=self.job.pk).update(
                minimum_experience_years=-1
            ),
            lambda: JobPosting.objects.filter(pk=self.job.pk).update(
                education_priority=4
            ),
        ):
            with self.assertRaises(IntegrityError), transaction.atomic():
                operation()
