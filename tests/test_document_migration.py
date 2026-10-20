"""The replacement migration must keep original CV files available."""

from pathlib import Path
from tempfile import TemporaryDirectory
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings


class ManualDocumentMigrationTests(TransactionTestCase):
    def test_original_cv_and_profile_survive_while_extraction_columns_are_removed(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [("accounts", "0001_initial"), ("candidates", "0002_cvdocument")]
        executor.migrate(previous)
        try:
            state = executor.loader.project_state(previous).apps
            user = state.get_model("accounts", "User").objects.create(
                username="migration-owner",
                email="migration@example.test",
                role="candidate",
                password="!",
            )
            profile = state.get_model("candidates", "CandidateProfile").objects.create(
                user_id=user.pk, summary="Keep my manual profile"
            )
            old = state.get_model("candidates", "CVDocument").objects.create(
                user_id=user.pk,
                file="owner/original.pdf",
                original_name="original.pdf",
                status="ready",
                extracted_text="Remove old extracted text",
                suggestions={"skills": []},
            )
            with TemporaryDirectory() as directory, override_settings(
                PRIVATE_DOCUMENT_ROOT=Path(directory)
            ):
                original = Path(directory) / "cvs/owner/original.pdf"
                original.parent.mkdir(parents=True)
                original.write_bytes(b"%PDF-1.7\nOriginal attachment")
                executor = MigrationExecutor(connection)
                executor.migrate(latest)
                new_apps = executor.loader.project_state(latest).apps
                Document = new_apps.get_model("candidates", "CandidateDocument")
                document = Document.objects.get(pk=old.pk)
                self.assertEqual(document.kind, "cv")
                self.assertEqual(document.file.name, "cvs/owner/original.pdf")
                self.assertTrue(Path(document.file.path).exists())
                self.assertEqual(document.original_name, "original.pdf")
                self.assertNotIn(
                    "extracted_text", [field.name for field in Document._meta.fields]
                )
                self.assertEqual(
                    new_apps.get_model("candidates", "CandidateProfile")
                    .objects.get(pk=profile.pk)
                    .summary,
                    "Keep my manual profile",
                )
        finally:
            MigrationExecutor(connection).migrate(latest)
