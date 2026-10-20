"""Exercise PostgreSQL row locks using independent concurrent transactions."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase, override_settings
from applications.models import Application
from applications.services import save_application
from candidates.models import CandidateDocument
from jobs.models import JobPosting


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL row locking")
class PostgreSQLConcurrencyTests(TransactionTestCase):
    def test_simultaneous_submissions_save_one_application_and_one_attachment(self):
        User = get_user_model()
        candidate = User.objects.create_user(
            username="concurrent-candidate",
            email="candidate@concurrent.test",
            role="candidate",
        )
        recruiter = User.objects.create_user(
            username="concurrent-recruiter",
            email="recruiter@concurrent.test",
            role="recruiter",
        )
        job = JobPosting.objects.create(
            recruiter=recruiter,
            title="Developer",
            company="Example",
            location="Nairobi",
            description="Build applications",
        )
        barrier = Barrier(2)
        with TemporaryDirectory() as directory, override_settings(
            PRIVATE_DOCUMENT_ROOT=Path(directory)
        ):
            document = CandidateDocument(
                user=candidate, kind="cv", original_name="example.pdf"
            )
            document.file.save(
                "example.pdf",
                SimpleUploadedFile("example.pdf", b"%PDF-1.7\nTest original"),
            )

            def submit(summary):
                close_old_connections()
                try:
                    user = User.objects.get(pk=candidate.pk)
                    chosen = CandidateDocument.objects.get(pk=document.pk)
                    snapshot = {
                        "profile": {
                            "headline": "Developer",
                            "location": "Nairobi",
                            "summary": summary,
                        },
                        "skills": [],
                        "education": [],
                        "certifications": [],
                        "experience": [],
                        "portfolio": [],
                    }
                    barrier.wait(timeout=5)
                    result = save_application(
                        user,
                        job.pk,
                        snapshot,
                        {"cover_letter": "", "documents": [chosen]},
                        submit=True,
                    )
                    return result.pk
                finally:
                    connections["default"].close()

            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(submit, "First simultaneous submission")
                second = pool.submit(submit, "Second simultaneous submission")
                ids = [first.result(timeout=15), second.result(timeout=15)]
            self.assertEqual(ids[0], ids[1])
            self.assertEqual(Application.objects.count(), 1)
            application = Application.objects.get()
            self.assertEqual(application.status, "submitted")
            self.assertEqual(application.attachments.count(), 1)
            self.assertIn(
                application.profile_snapshot["profile"]["summary"],
                {"First simultaneous submission", "Second simultaneous submission"},
            )
