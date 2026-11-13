"""Document-reader fixtures plus authenticated review and merge boundaries."""

import io
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from candidates.cv_import import draft_key, new_draft
from candidates.cv_parser import parse_cv, parse_date
from candidates.cv_text import CVReadError, read_cv
from candidates.models import (
    CandidateDocument,
    CandidateProfile,
    CandidateSkill,
    Education,
    WorkExperience,
)

CV_TEXT = """Alex Wanjiku
Software Developer
Email: alex@example.test
Phone: +254 712 345 678
Location: Nairobi, Kenya
https://example.test/portfolio

PROFESSIONAL SUMMARY
I build and maintain reliable web applications.

TECHNICAL SKILLS
Languages: Python, SQL
Tools: Django; Git; Python

WORK EXPERIENCE
Software Developer | Acacia Labs
January 2022 - Present
Built and maintained web applications.

EDUCATION
BSc Computer Science | Example University
Sep 2018 - Jul 2021

CERTIFICATIONS
Cloud Practitioner | Example Training
Issue date: May 2023

REFERENCES
Another Person
reference@example.test
+254 700 000 001
"""


def docx_bytes(text=CV_TEXT, extra=None, table=False):
    paragraphs = "".join(
        f"<w:p><w:r><w:t>{escape(line)}</w:t></w:r></w:p>" for line in text.splitlines()
    )
    if table:
        paragraphs = f"<w:tbl><w:tr><w:tc>{paragraphs}</w:tc></w:tr></w:tbl>"
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{paragraphs}</w:body></w:document>',
        )
        for name, content in (extra or {}).items():
            archive.writestr(name, content)
    return output.getvalue()


def pdf_bytes(text=CV_TEXT, encrypted=False, pages=1):
    writer = PdfWriter()
    font = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
    )
    for _ in range(pages):
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        commands = ["BT /F1 10 Tf 40 760 Td 14 TL"]
        for line in text.splitlines():
            value = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"({value}) Tj T*")
        commands.append("ET")
        stream = DecodedStreamObject()
        stream.set_data("\n".join(commands).encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("fixture-password")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class CVReaderTests(SimpleTestCase):
    def read(self, content, extension):
        with TemporaryDirectory() as directory:
            path = Path(directory) / ("cv" + extension)
            path.write_bytes(content)
            return read_cv(path, extension)

    def test_pdf_and_word_recover_the_same_core_information(self):
        for extension, content in [(".docx", docx_bytes()), (".pdf", pdf_bytes())]:
            with self.subTest(extension=extension):
                result = parse_cv(self.read(content, extension)["text"])
                self.assertEqual(result["basic"]["contact_email"], "alex@example.test")
                self.assertEqual(result["basic"]["headline"], "Software Developer")
                self.assertEqual(result["basic"]["phone_number"], "+254 712 345 678")
                self.assertEqual(
                    [item["name"] for item in result["skills"]],
                    ["Python", "SQL", "Django", "Git"],
                )
                self.assertEqual(
                    result["education"][0]["institution"], "Example University"
                )
                self.assertEqual(result["experience"][0]["company"], "Acacia Labs")
                self.assertEqual(result["experience"][0]["start_date"], "2022-01-01")
                self.assertTrue(result["experience"][0]["currently_working"])
                self.assertEqual(
                    result["certifications"][0]["issue_date"], "2023-05-01"
                )

    def test_docx_tables_and_headers_are_read(self):
        header = '<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>header@example.test</w:t></w:r></w:p></w:hdr>'
        result = self.read(
            docx_bytes(table=True, extra={"word/header1.xml": header}), ".docx"
        )
        self.assertIn("header@example.test", result["text"])
        self.assertIn("Acacia Labs", result["text"])

    def test_scanned_or_empty_pdf_has_actionable_error(self):
        with self.assertRaisesMessage(CVReadError, "selectable text"):
            self.read(pdf_bytes(text=""), ".pdf")

    def test_encrypted_pdf_is_rejected(self):
        with self.assertRaisesMessage(CVReadError, "password-protected"):
            self.read(pdf_bytes(encrypted=True), ".pdf")

    def test_page_limit(self):
        with self.assertRaisesMessage(CVReadError, "20 pages"):
            self.read(pdf_bytes(pages=21), ".pdf")

    def test_macro_and_expanded_zip_limits(self):
        for extra in (
            {"word/vbaProject.bin": b"macro"},
            {"word/huge.xml": "a" * (26 * 1024 * 1024)},
        ):
            with self.subTest(names=list(extra)), self.assertRaises(CVReadError):
                self.read(docx_bytes(extra=extra), ".docx")

    def test_xml_entities_are_not_resolved(self):
        from defusedxml.common import DefusedXmlException

        output = io.BytesIO()
        with ZipFile(output, "w") as archive:
            archive.writestr(
                "word/document.xml",
                '<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///not-read">]><x>&secret;</x>',
            )
        with self.assertRaises(DefusedXmlException):
            self.read(output.getvalue(), ".docx")

    def test_year_only_dates_are_not_invented(self):
        self.assertEqual(parse_date("2020"), "")
        self.assertEqual(parse_date("Feb 2020"), "2020-02-01")
        self.assertEqual(parse_date("02/2020"), "2020-02-01")
        self.assertEqual(parse_date("2020-02-25"), "2020-02-25")
        self.assertEqual(parse_date("2020-99-99"), "")
        result = parse_cv("Experience\nData Analyst | Example Company\n2019 - 2021")
        self.assertEqual(result["experience"][0]["start_date"], "")
        self.assertFalse(result["experience"][0]["currently_working"])

    def test_unlabelled_details_and_reference_contact_not_guessed(self):
        result = parse_cv(
            "Alex\nUnknown Road\nReferences\nRecruiter\nother@example.test\n+254 712 345 678"
        )
        self.assertEqual(result["basic"], {})

    def test_inline_skills_and_multiword_skills(self):
        result = parse_cv("Skills: Project management, C++, C#, .NET, Customer service")
        self.assertEqual(
            [entry["name"] for entry in result["skills"]],
            ["Project management", "C++", "C#", ".NET", "Customer service"],
        )

    def test_multiple_jobs_do_not_absorb_next_title(self):
        result = parse_cv(
            "Work experience\nData Analyst | Company One\nJan 2020 - Dec 2021\nPrepared monthly reports.\nSoftware Developer | Company Two\nFeb 2022 - Present\nBuilt APIs."
        )
        self.assertEqual(len(result["experience"]), 2)
        self.assertEqual(
            result["experience"][0]["description"], "Prepared monthly reports."
        )
        self.assertEqual(result["experience"][1]["company"], "Company Two")

    def test_non_software_roles_and_date_first_headers(self):
        for header in (
            "Chef | Example Kitchen | Jan 2020 - Dec 2021",
            "Jan 2020 - Dec 2021 | Chef | Example Kitchen",
            "Chef at Example Kitchen\nJan 2020 - Dec 2021",
        ):
            result = parse_cv(
                "Work experience\n"
                + header
                + "\nPrepared meals and managed the kitchen."
            )
            self.assertEqual(result["experience"][0]["job_title"], "Chef")
            self.assertEqual(result["experience"][0]["company"], "Example Kitchen")

    def test_standalone_certificate_date_is_not_a_new_certificate(self):
        result = parse_cv(
            "Certifications\nCloud Practitioner | Example Training\nMay 2023"
        )
        self.assertEqual(len(result["certifications"]), 1)
        self.assertEqual(result["certifications"][0]["issue_date"], "2023-05-01")


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class CVImportFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(
            username="cv-owner",
            email="owner@example.test",
            first_name="Original",
            role="candidate",
        )
        cls.other = User.objects.create_user(
            username="cv-other", email="other@example.test", role="candidate"
        )
        cls.recruiter = User.objects.create_user(
            username="cv-recruiter", email="recruiter@example.test", role="recruiter"
        )

    def setUp(self):
        cache.clear()
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.storage = override_settings(
            PRIVATE_DOCUMENT_ROOT=Path(self.directory.name)
        )
        self.storage.enable()
        self.addCleanup(self.storage.disable)
        self.client.force_login(self.owner)
        self.document = CandidateDocument.objects.create(
            user=self.owner,
            kind="cv",
            original_name="cv.docx",
            file=SimpleUploadedFile("cv.docx", docx_bytes()),
        )
        self.start_url = reverse("candidates:cv_import", args=[self.document.pk])

    def draft(self, actual=False):
        if actual:
            return new_draft(self.owner, self.document)
        with patch(
            "candidates.cv_import.extract_text",
            return_value={"text": CV_TEXT, "warnings": []},
        ):
            return new_draft(self.owner, self.document)

    def payload(self, token):
        response = self.client.get(reverse("candidates:cv_review", args=[token]))
        form = response.context["form"]
        data = {name: form[name].value() or "" for name in form._meta.fields}
        data["selected_fields"] = form["selected_fields"].value() or []
        for section in response.context["sections"]:
            formset = section["formset"]
            prefix = section["prefix"]
            data[f"{prefix}-TOTAL_FORMS"] = str(formset.total_form_count())
            data[f"{prefix}-INITIAL_FORMS"] = str(formset.initial_form_count())
            for entry in formset:
                for name in entry.fields:
                    value = entry[name].value()
                    if value is True:
                        data[entry.add_prefix(name)] = "on"
                    elif value is not False and value is not None:
                        data[entry.add_prefix(name)] = value
        return data

    def save(self, token, data=None):
        return self.client.post(
            reverse("candidates:cv_save", args=[token]),
            self.payload(token) if data is None else data,
        )

    def test_actual_worker_and_preview_do_not_save_profile(self):
        token = self.draft(actual=True)
        response = self.client.get(reverse("candidates:cv_review", args=[token]))
        self.assertContains(response, "Acacia Labs")
        self.assertContains(response, "Save selected details")
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertFalse(CandidateProfile.objects.filter(user=self.owner).exists())

    def test_selected_details_saved_and_account_identity_unchanged(self):
        token = self.draft()
        response = self.save(token)
        self.assertRedirects(response, reverse("candidates:profile"))
        profile = CandidateProfile.objects.get(user=self.owner)
        self.assertEqual(profile.headline, "Software Developer")
        self.assertEqual(profile.contact_email, "alex@example.test")
        self.assertEqual(profile.skills.count(), 4)
        self.assertEqual(profile.experience.get().company, "Acacia Labs")
        self.assertEqual(profile.education.get().institution, "Example University")
        self.assertEqual(profile.certifications.get().issuer, "Example Training")
        self.assertEqual(
            profile.portfolio_links.get().url, "https://example.test/portfolio"
        )
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.email, "owner@example.test")
        self.assertEqual(self.owner.first_name, "Original")
        self.assertFalse(self.owner.is_staff)
        self.assertIsNone(cache.get(draft_key(self.owner, token)))

    def test_existing_fields_and_entries_preserved_and_duplicates_skipped(self):
        profile = CandidateProfile.objects.create(
            user=self.owner, headline="My chosen title", summary="Keep my writing"
        )
        CandidateSkill.objects.create(profile=profile, name="python")
        Education.objects.create(
            profile=profile,
            qualification="Original degree",
            institution="Original College",
        )
        token = self.draft()
        data = self.payload(token)
        self.assertNotIn("headline", data["selected_fields"])
        self.assertEqual(data["skills-TOTAL_FORMS"], "3")
        self.assertEqual(self.save(token, data).status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(profile.headline, "My chosen title")
        self.assertEqual(profile.summary, "Keep my writing")
        self.assertEqual(profile.education.count(), 2)
        self.assertEqual(profile.skills.count(), 4)

    def test_explicit_replacement_is_allowed(self):
        profile = CandidateProfile.objects.create(user=self.owner, headline="Old title")
        token = self.draft()
        data = self.payload(token)
        data["selected_fields"].append("headline")
        data["headline"] = "Corrected title"
        self.assertEqual(self.save(token, data).status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(profile.headline, "Corrected title")

    def test_invalid_unselected_entries_and_contacts_are_ignored(self):
        token = self.draft()
        data = self.payload(token)
        data["selected_fields"].remove("phone_number")
        data["phone_number"] = "invalid phone"
        data.pop("experience-0-include")
        data["experience-0-start_date"] = "invalid date"
        self.assertEqual(self.save(token, data).status_code, 302)
        self.assertFalse(WorkExperience.objects.exists())
        self.assertEqual(CandidateProfile.objects.get(user=self.owner).phone_number, "")

    def test_invalid_selected_entry_prevents_all_saves(self):
        token = self.draft()
        data = self.payload(token)
        data["experience-0-start_date"] = "2099-01-01"
        response = self.save(token, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your changes have not been saved")
        self.assertFalse(CandidateProfile.objects.exists())

    def test_duplicate_values_within_review_are_saved_once(self):
        token = self.draft()
        data = self.payload(token)
        data["skills-1-name"] = "python"
        self.assertEqual(self.save(token, data).status_code, 302)
        self.assertEqual(CandidateSkill.objects.count(), 3)

    def test_discard_and_expiry_do_not_mutate_profile(self):
        token = self.draft()
        self.assertEqual(self.save(token, {"action": "cancel"}).status_code, 302)
        self.assertFalse(CandidateProfile.objects.exists())
        self.assertIsNone(cache.get(draft_key(self.owner, token)))
        token = self.draft()
        data = self.payload(token)
        cache.delete(draft_key(self.owner, token))
        self.assertEqual(self.save(token, data).status_code, 302)
        self.assertFalse(CandidateProfile.objects.exists())

    def test_stale_review_refuses_to_overwrite_new_profile_changes(self):
        profile = CandidateProfile.objects.create(user=self.owner, summary="Before")
        token = self.draft()
        data = self.payload(token)
        profile.summary = "Changed in another tab"
        profile.save()
        response = self.save(token, data)
        self.assertContains(response, "Your profile changed")
        profile.refresh_from_db()
        self.assertEqual(profile.summary, "Changed in another tab")
        self.assertFalse(CandidateSkill.objects.exists())

    def test_replayed_save_cannot_duplicate_entries(self):
        token = self.draft()
        data = self.payload(token)
        self.save(token, data)
        self.save(token, data)
        self.assertEqual(CandidateSkill.objects.count(), 4)
        self.assertEqual(WorkExperience.objects.count(), 1)

    def test_document_and_review_ownership(self):
        token = self.draft()
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.start_url).status_code, 404)
        response = self.client.get(reverse("candidates:cv_review", args=[token]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.save(token, {}).status_code, 302)
        self.client.force_login(self.recruiter)
        self.assertEqual(self.client.post(self.start_url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post(self.start_url).status_code, 302)

    def test_post_only_and_csrf(self):
        self.assertEqual(self.client.get(self.start_url).status_code, 405)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        self.assertEqual(strict.post(self.start_url).status_code, 403)
        token = self.draft()
        self.assertEqual(
            strict.post(reverse("candidates:cv_save", args=[token]), {}).status_code,
            403,
        )

    def test_upload_opt_in_opens_review_but_plain_upload_does_not(self):
        for enabled in (False, True):
            response = self.client.post(
                reverse("candidates:documents"),
                {
                    "kind": "cv",
                    "title": "CV",
                    "file": SimpleUploadedFile("new.docx", docx_bytes()),
                    "fill_profile": "on" if enabled else "",
                },
            )
            self.assertEqual(response.status_code, 302)
            if enabled:
                self.assertIn("/profile/import/", response.url)
            else:
                self.assertEqual(response.url, reverse("candidates:documents"))
        self.assertFalse(CandidateProfile.objects.exists())

    def test_import_failure_keeps_upload_and_profile(self):
        response = self.client.post(
            reverse("candidates:documents"),
            {
                "kind": "cv",
                "file": SimpleUploadedFile("scan.pdf", pdf_bytes(text="")),
                "fill_profile": "on",
            },
            follow=True,
        )
        self.assertContains(response, "selectable text")
        self.assertEqual(CandidateDocument.objects.filter(user=self.owner).count(), 2)
        self.assertFalse(CandidateProfile.objects.exists())

    def test_deleted_document_invalidates_draft(self):
        token = self.draft()
        data = self.payload(token)
        self.document.delete()
        self.assertEqual(self.save(token, data).status_code, 302)
        self.assertFalse(CandidateProfile.objects.exists())

    def test_timeout_does_not_save_and_rate_limit_prevents_repeated_work(self):
        with patch(
            "candidates.cv_import.subprocess.run",
            side_effect=subprocess.TimeoutExpired("reader", 15),
        ) as worker:
            response = self.client.post(self.start_url, follow=True)
            self.assertContains(response, "took too long")
            response = self.client.post(self.start_url, follow=True)
            self.assertContains(response, "wait 30 seconds")
            self.assertEqual(worker.call_count, 1)
        self.assertFalse(CandidateProfile.objects.exists())

    def test_source_text_is_escaped(self):
        with patch(
            "candidates.cv_import.extract_text",
            return_value={
                "text": CV_TEXT + '\n<script>alert("CV")</script>',
                "warnings": [],
            },
        ):
            token = new_draft(self.owner, self.document)
        response = self.client.get(reverse("candidates:cv_review", args=[token]))
        self.assertNotContains(response, '<script>alert("CV")</script>')
        self.assertContains(response, "&lt;script&gt;")

    def test_total_entry_limit_includes_existing_profile(self):
        profile = CandidateProfile.objects.create(user=self.owner)
        CandidateSkill.objects.bulk_create(
            [
                CandidateSkill(profile=profile, name=f"Skill {index}")
                for index in range(60)
            ]
        )
        token = self.draft()
        response = self.save(token)
        self.assertContains(response, "exceed its limit of 60")
        self.assertEqual(CandidateSkill.objects.count(), 60)
        self.assertFalse(WorkExperience.objects.exists())

    def test_malformed_document_worker_returns_safe_error(self):
        self.document.file.save(
            "broken.pdf", SimpleUploadedFile("broken.pdf", b"%PDF-1.7\nnot a real PDF")
        )
        self.document.original_name = "broken.pdf"
        self.document.save()
        response = self.client.post(self.start_url, follow=True)
        self.assertContains(response, "could not read this file")
        self.assertNotContains(response, str(self.directory.name))
        self.assertFalse(CandidateProfile.objects.exists())

    def test_supporting_certificates_cannot_be_imported(self):
        self.document.kind = "certificate"
        self.document.save()
        self.assertEqual(self.client.post(self.start_url).status_code, 404)

    def test_save_is_atomic_on_database_conflict(self):
        from django.db import IntegrityError

        token = self.draft()
        with patch(
            "candidates.models.Education.save",
            side_effect=IntegrityError("fixture conflict"),
        ):
            response = self.save(token)
        self.assertContains(response, "changed while saving")
        self.assertFalse(CandidateProfile.objects.exists())
        self.assertFalse(CandidateSkill.objects.exists())
        self.assertIsNotNone(cache.get(draft_key(self.owner, token)))

    def test_tampered_management_count_rejected_without_partial_save(self):
        token = self.draft()
        data = self.payload(token)
        data["skills-TOTAL_FORMS"] = "10000"
        response = self.save(token, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CandidateProfile.objects.exists())
