"""Manual profile applications, private documents, copies and recruiter ownership."""

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from applications.models import Application, ApplicationAttachment
from candidates.models import (
    CandidateDocument,
    CandidateProfile,
    CandidateSkill,
    Education,
)
from jobs.models import JobPosting

User = get_user_model()


def word_file():
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", "<document>Original CV text</document>")
    return buffer.getvalue()


class ManualApplicationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.candidate = User.objects.create_user(
            username="manual-candidate",
            email="candidate@example.test",
            first_name="Alex",
            role="candidate",
        )
        cls.other = User.objects.create_user(
            username="manual-other", email="other@example.test", role="candidate"
        )
        cls.recruiter = User.objects.create_user(
            username="manual-recruiter",
            email="recruiter@example.test",
            role="recruiter",
        )
        cls.other_recruiter = User.objects.create_user(
            username="manual-other-recruiter",
            email="other-recruiter@example.test",
            role="recruiter",
        )
        cls.profile = CandidateProfile.objects.create(
            user=cls.candidate,
            headline="Main headline",
            summary="Main profile summary",
            location="Nairobi",
        )
        CandidateSkill.objects.create(profile=cls.profile, name="Python")
        Education.objects.create(
            profile=cls.profile,
            qualification="BSc Computing",
            institution="Example University",
        )
        cls.job = JobPosting.objects.create(
            recruiter=cls.recruiter,
            title="Developer",
            company="Example Studio",
            location="Nairobi",
            description="Build web applications.",
            requirements="Python and teamwork",
        )

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_override = override_settings(
            PRIVATE_DOCUMENT_ROOT=Path(self.directory.name)
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.client.force_login(self.candidate)

    def document(
        self,
        user=None,
        kind="cv",
        name="example.pdf",
        contents=b"%PDF-1.7\nScanned original document",
    ):
        document = CandidateDocument(
            user=user or self.candidate,
            kind=kind,
            title="My document",
            original_name=name,
        )
        document.file.save(name, SimpleUploadedFile(name, contents), save=False)
        document.save()
        return document

    def edit_url(self, job=None):
        return reverse("applications:edit", args=[(job or self.job).pk])

    def payload(self, **changes):
        values = {
            "headline": "Tailored headline",
            "location": "Nairobi",
            "summary": "Summary tailored for this job",
            "cover_letter": "I would like to join your team.",
            "action": "submit",
        }
        for prefix in (
            "skills",
            "education",
            "certifications",
            "experience",
            "portfolio",
        ):
            values.update(
                {f"{prefix}-TOTAL_FORMS": "0", f"{prefix}-INITIAL_FORMS": "0"}
            )
        return values | changes

    def submit(self, **changes):
        self.client.post(self.edit_url(), self.payload(**changes))
        return Application.objects.get(candidate=self.candidate, job=self.job)

    def test_document_uploads_accept_scans_degrees_certificates_and_word_without_profile_changes(
        self,
    ):
        cases = [
            ("cv", "scanned.pdf", b"%PDF-1.7\nscan"),
            ("cv", "cv.docx", word_file()),
            ("degree", "degree.pdf", b"%PDF-1.7\ndegree"),
            ("certificate", "certificate.png", b"\x89PNG\r\n\x1a\nexample"),
            ("degree", "degree.jpg", b"\xff\xd8\xffexample"),
        ]
        for kind, name, content in cases:
            with self.subTest(kind=kind, name=name):
                response = self.client.post(
                    reverse("candidates:documents"),
                    {
                        "kind": kind,
                        "title": "My qualification",
                        "file": SimpleUploadedFile(name, content),
                    },
                )
                self.assertRedirects(response, reverse("candidates:documents"))
        self.assertEqual(CandidateDocument.objects.count(), 5)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.summary, "Main profile summary")
        self.assertNotIn(
            "extracted_text", [field.name for field in CandidateDocument._meta.fields]
        )
        self.assertNotIn(
            "suggestions", [field.name for field in CandidateDocument._meta.fields]
        )

    def test_invalid_document_formats_signatures_macros_and_size_rejected(self):
        for kind, name, content in [
            ("cv", "cv.exe", b"MZ"),
            ("cv", "cv.pdf", b"fake"),
            ("degree", "degree.docx", word_file()),
            ("cv", "too-big.pdf", b"%PDF-" + b" " * (5 * 1024 * 1024)),
        ]:
            response = self.client.post(
                reverse("candidates:documents"),
                {"kind": kind, "file": SimpleUploadedFile(name, content)},
            )
            self.assertEqual(response.status_code, 200)
        self.assertFalse(CandidateDocument.objects.exists())

    def test_document_library_and_files_are_owner_only(self):
        document = self.document()
        file_url = reverse("candidates:document_file", args=[document.pk])
        response = self.client.get(file_url + "?view=1")
        self.assertEqual(response.status_code, 200)
        self.assertIn("inline", response["Content-Disposition"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertTrue(b"".join(response.streaming_content))
        for user in (self.other, self.recruiter):
            self.client.force_login(user)
            expected = 404 if user.role == "candidate" else 403
            self.assertEqual(self.client.get(file_url).status_code, expected)
        with self.assertRaises(ValueError):
            _ = document.file.url
        self.assertEqual(
            self.client.get(f"/media/{document.file.name}").status_code, 404
        )

    def test_old_cv_review_endpoint_removed(self):
        document = self.document()
        self.assertEqual(
            self.client.get(f"/candidate/cv/{document.pk}/").status_code, 404
        )
        self.assertNotContains(
            self.client.get(reverse("candidates:documents")), "Upload and review"
        )

    def test_get_application_prefills_all_saved_profile_sections_without_creating_draft(
        self,
    ):
        response = self.client.get(self.edit_url())
        self.assertContains(response, "Main profile summary")
        self.assertContains(response, 'value="Python"')
        self.assertContains(response, 'value="BSc Computing"')
        self.assertFalse(Application.objects.exists())

    def test_unedited_prefilled_profile_can_be_submitted(self):
        response = self.client.get(self.edit_url())
        payload = {"action": "submit"}
        for name in ("headline", "location", "summary"):
            payload[name] = response.context["form"][name].value() or ""
        for section in response.context["sections"]:
            formset = section["formset"]
            prefix = section["prefix"]
            payload[f"{prefix}-TOTAL_FORMS"] = str(formset.total_form_count())
            payload[f"{prefix}-INITIAL_FORMS"] = str(formset.initial_form_count())
            for index, form in enumerate(formset):
                for field in form:
                    value = field.value()
                    if value not in (None, False, ""):
                        payload[f"{prefix}-{index}-{field.name}"] = (
                            "on" if value is True else value
                        )
        self.client.post(self.edit_url(), payload)
        application = Application.objects.get()
        self.assertEqual(application.status, "submitted")
        self.assertEqual(application.profile_snapshot["skills"], [{"name": "Python"}])
        self.assertEqual(
            application.profile_snapshot["education"][0]["institution"],
            "Example University",
        )

    def test_tailored_submission_keeps_main_profile_and_other_applications_unchanged(
        self,
    ):
        application = self.submit(
            **{"skills-TOTAL_FORMS": "1", "skills-0-name": "Django"}
        )
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.summary, "Main profile summary")
        self.assertEqual(self.profile.headline, "Main headline")
        self.assertEqual(self.profile.skills.get().name, "Python")
        self.assertEqual(
            application.profile_snapshot["profile"]["summary"],
            "Summary tailored for this job",
        )
        job2 = JobPosting.objects.create(
            recruiter=self.recruiter,
            title="Another role",
            company="Example",
            location="Remote",
            description="Another role",
        )
        response = self.client.get(self.edit_url(job2))
        self.assertContains(response, "Main profile summary")
        self.assertNotContains(response, "Summary tailored for this job")

    def test_draft_is_private_to_candidate_and_can_be_resumed(self):
        self.client.post(self.edit_url(), self.payload(action="draft"))
        application = Application.objects.get()
        self.assertEqual(application.status, "draft")
        response = self.client.get(self.edit_url())
        self.assertContains(response, "Summary tailored for this job")
        self.client.force_login(self.recruiter)
        self.assertEqual(
            self.client.get(
                reverse("applications:detail", args=[application.pk])
            ).status_code,
            404,
        )
        self.assertNotContains(
            self.client.get(reverse("applications:applicants", args=[self.job.pk])),
            "Alex",
        )

    def test_duplicate_submission_does_not_create_duplicate_records_or_files(self):
        document = self.document()
        application = self.submit(documents=[str(document.pk)])
        self.client.post(
            self.edit_url(),
            self.payload(documents=[str(document.pk)], summary="Attempt to overwrite"),
        )
        self.assertEqual(Application.objects.count(), 1)
        self.assertEqual(application.attachments.count(), 1)
        application.refresh_from_db()
        self.assertEqual(
            application.profile_snapshot["profile"]["summary"],
            "Summary tailored for this job",
        )

    def test_job_profile_and_file_copies_survive_changes_to_originals(self):
        document = self.document()
        application = self.submit(documents=[str(document.pk)])
        copy = application.attachments.get()
        original_name = document.file.name
        copy_path = Path(copy.file.path)
        self.assertNotEqual(copy.file.name, original_name)
        self.profile.summary = "Main profile changed later"
        self.profile.save()
        self.job.title = "Changed job title"
        self.job.save()
        self.client.post(reverse("candidates:document_delete", args=[document.pk]))
        self.assertTrue(copy_path.exists())
        application.refresh_from_db()
        self.assertEqual(application.job_snapshot["title"], "Developer")
        self.assertEqual(
            application.profile_snapshot["profile"]["summary"],
            "Summary tailored for this job",
        )
        self.client.force_login(self.recruiter)
        response = self.client.get(
            reverse("applications:attachment_file", args=[copy.pk]) + "?view=1"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"".join(response.streaming_content))

    def test_foreign_documents_and_posted_identity_cannot_be_attached(self):
        document = self.document(user=self.other)
        response = self.client.post(
            self.edit_url(),
            self.payload(
                documents=[str(document.pk)],
                candidate=self.other.pk,
                status="shortlisted",
            ),
        )
        self.assertContains(response, "Select a valid choice")
        self.assertFalse(Application.objects.exists())

    def test_foreign_profile_entry_ids_cannot_modify_saved_records(self):
        education = Education.objects.get(profile=self.profile)
        self.submit(
            **{
                "education-TOTAL_FORMS": "1",
                "education-0-id": education.pk,
                "education-0-qualification": "Tailored qualification",
                "education-0-institution": "Tailored institution",
            }
        )
        education.refresh_from_db()
        self.assertEqual(education.qualification, "BSc Computing")

    def test_incomplete_entries_invalid_dates_links_and_duplicates_block_all_writes(
        self,
    ):
        cases = [
            {
                "education-TOTAL_FORMS": "1",
                "education-0-qualification": "Missing institution",
            },
            {
                "skills-TOTAL_FORMS": "2",
                "skills-0-name": "Python",
                "skills-1-name": "python",
            },
            {
                "portfolio-TOTAL_FORMS": "1",
                "portfolio-0-title": "Bad link",
                "portfolio-0-url": "javascript:alert(1)",
            },
            {
                "experience-TOTAL_FORMS": "1",
                "experience-0-job_title": "Developer",
                "experience-0-company": "Example",
                "experience-0-start_date": "2025-01-01",
                "experience-0-end_date": "2024-01-01",
            },
        ]
        for case in cases:
            response = self.client.post(self.edit_url(), self.payload(**case))
            self.assertEqual(response.status_code, 200, case)
            self.assertFalse(Application.objects.exists(), case)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.summary, "Main profile summary")

    def test_certifications_and_experience_can_be_tailored_without_saving_profile_models(
        self,
    ):
        application = self.submit(
            **{
                "certifications-TOTAL_FORMS": "1",
                "certifications-0-name": "Web Development",
                "certifications-0-issuer": "Example Training",
                "experience-TOTAL_FORMS": "1",
                "experience-0-job_title": "Developer",
                "experience-0-company": "Example Studio",
                "experience-0-start_date": "2024-01-01",
                "experience-0-currently_working": "on",
            }
        )
        self.assertEqual(
            application.profile_snapshot["experience"][0]["start_date"], "2024-01-01"
        )
        self.assertEqual(
            application.profile_snapshot["certifications"][0]["issuer"],
            "Example Training",
        )
        self.assertFalse(self.profile.certifications.exists())
        self.assertFalse(self.profile.experience.exists())

    def test_empty_application_requires_manual_details_to_submit_but_can_save_draft(
        self,
    ):
        response = self.client.post(self.edit_url(), self.payload(summary=""))
        self.assertContains(response, "before submitting")
        self.assertFalse(Application.objects.exists())
        self.client.post(self.edit_url(), self.payload(summary="", action="draft"))
        self.assertEqual(Application.objects.get().status, "draft")

    def test_closed_jobs_reject_applications(self):
        self.job.status = "closed"
        self.job.save()
        self.client.post(self.edit_url(), self.payload())
        self.assertFalse(Application.objects.exists())

    def test_attachment_save_failure_rolls_back_submission_and_deletes_partial_copies(
        self,
    ):
        document = self.document()
        before = set(Path(self.directory.name).rglob("*.pdf"))
        with patch(
            "applications.models.ApplicationAttachment.save",
            side_effect=IntegrityError("failed"),
        ):
            response = self.client.post(
                self.edit_url(), self.payload(documents=[str(document.pk)])
            )
        self.assertContains(response, "changed while saving")
        self.assertFalse(Application.objects.exists())
        self.assertEqual(set(Path(self.directory.name).rglob("*.pdf")), before)

    def test_other_candidates_and_recruiters_cannot_read_applications_or_attachments(
        self,
    ):
        document = self.document()
        application = self.submit(documents=[str(document.pk)])
        copy = application.attachments.get()
        for user in (self.other, self.other_recruiter):
            self.client.force_login(user)
            self.assertEqual(
                self.client.get(
                    reverse("applications:detail", args=[application.pk])
                ).status_code,
                404,
            )
            self.assertEqual(
                self.client.get(
                    reverse("applications:attachment_file", args=[copy.pk])
                ).status_code,
                404,
            )
        self.client.force_login(self.recruiter)
        response = self.client.get(
            reverse("applications:detail", args=[application.pk])
        )
        self.assertContains(response, "Summary tailored for this job")
        self.assertContains(response, "My document")

    def test_only_job_owner_can_change_status_and_candidates_can_track_it(self):
        application = self.submit()
        status_url = reverse("applications:status", args=[application.pk])
        self.assertEqual(
            self.client.post(status_url, {"status": "shortlisted"}).status_code, 403
        )
        self.client.force_login(self.other_recruiter)
        self.assertEqual(
            self.client.post(status_url, {"status": "shortlisted"}).status_code, 404
        )
        self.client.force_login(self.recruiter)
        self.client.post(status_url, {"status": "draft"})
        application.refresh_from_db()
        self.assertEqual(application.status, "submitted")
        self.client.post(status_url, {"status": "reviewing"})
        application.refresh_from_db()
        self.assertEqual(application.status, "reviewing")
        self.client.force_login(self.candidate)
        self.assertContains(
            self.client.get(reverse("applications:mine")), "Under review"
        )

    def test_recruiter_can_publish_edit_close_only_own_jobs(self):
        self.client.force_login(self.recruiter)
        data = {
            "title": "New role",
            "company": "Example",
            "location": "Remote",
            "description": "A new role",
            "recruiter": self.other_recruiter.pk,
        }
        response = self.client.post(reverse("jobs:create"), data)
        self.assertRedirects(response, reverse("jobs:manage"))
        job = JobPosting.objects.get(title="New role")
        self.assertEqual(job.recruiter, self.recruiter)
        self.client.post(
            reverse("jobs:edit", args=[job.pk]), data | {"title": "Updated role"}
        )
        job.refresh_from_db()
        self.assertEqual(job.title, "Updated role")
        self.client.force_login(self.other_recruiter)
        self.assertEqual(
            self.client.post(reverse("jobs:close", args=[job.pk])).status_code, 404
        )
        self.assertEqual(
            self.client.get(
                reverse("applications:applicants", args=[job.pk])
            ).status_code,
            404,
        )
        self.client.force_login(self.recruiter)
        self.client.post(reverse("jobs:close", args=[job.pk]))
        job.refresh_from_db()
        self.assertEqual(job.status, "closed")

    def test_job_search_only_returns_open_matching_roles(self):
        JobPosting.objects.create(
            recruiter=self.recruiter,
            title="Closed role",
            company="Example",
            location="Nairobi",
            description="Old",
            status="closed",
        )
        response = self.client.get(reverse("jobs:opportunities"), {"q": "Developer"})
        self.assertContains(response, "Developer")
        self.assertNotContains(response, "Closed role")

    def test_invalid_management_forms_and_role_boundaries(self):
        for value in ("10000", "bad"):
            self.client.post(
                self.edit_url(), self.payload(**{"skills-TOTAL_FORMS": value})
            )
            self.assertFalse(Application.objects.exists())
        self.assertEqual(self.client.get(reverse("jobs:create")).status_code, 403)
        self.client.force_login(self.recruiter)
        self.assertEqual(self.client.get(self.edit_url()).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("candidates:documents")).status_code, 403
        )
        self.client.logout()
        self.assertEqual(self.client.get(self.edit_url()).status_code, 302)

    def test_csrf_required_for_document_application_job_and_status_mutations(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.candidate)
        self.assertEqual(
            client.post(reverse("candidates:documents"), {}).status_code, 403
        )
        self.assertEqual(client.post(self.edit_url(), self.payload()).status_code, 403)
        client.force_login(self.recruiter)
        self.assertEqual(client.post(reverse("jobs:create"), {}).status_code, 403)

    def test_application_html_is_escaped(self):
        application = self.submit(summary="<script>bad()</script>")
        response = self.client.get(
            reverse("applications:detail", args=[application.pk])
        )
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>bad()")

    def test_account_deletion_removes_original_and_submitted_file_copies(self):
        document = self.document()
        application = self.submit(documents=[str(document.pk)])
        paths = [
            Path(document.file.path),
            Path(application.attachments.get().file.path),
        ]
        with self.captureOnCommitCallbacks(execute=True):
            self.candidate.delete()
        self.assertTrue(all(not path.exists() for path in paths))
