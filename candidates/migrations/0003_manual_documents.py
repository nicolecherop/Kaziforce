"""Keep uploaded originals and remove extraction-only data."""

import candidates.storage
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def retain_original_paths(apps, schema_editor):
    Document = apps.get_model("candidates", "CandidateDocument")
    for document in (
        Document.objects.using(schema_editor.connection.alias)
        .only("pk", "file")
        .iterator()
    ):
        if document.file.name:
            Document.objects.using(schema_editor.connection.alias).filter(
                pk=document.pk
            ).update(file="cvs/" + document.file.name)


def restore_original_paths(apps, schema_editor):
    Document = apps.get_model("candidates", "CandidateDocument")
    for document in (
        Document.objects.using(schema_editor.connection.alias)
        .only("pk", "file")
        .iterator()
    ):
        if document.file.name.startswith("cvs/"):
            Document.objects.using(schema_editor.connection.alias).filter(
                pk=document.pk
            ).update(file=document.file.name[4:])


class Migration(migrations.Migration):
    dependencies = [("candidates", "0002_cvdocument")]
    operations = [
        migrations.RenameModel("CVDocument", "CandidateDocument"),
        migrations.RunPython(retain_original_paths, restore_original_paths),
        migrations.AlterField(
            "candidatedocument",
            "user",
            models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="documents",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            "candidatedocument",
            "file",
            models.FileField(
                storage=candidates.storage.PrivateDocumentStorage(),
                upload_to=candidates.storage.document_upload_path,
            ),
        ),
        migrations.AddField(
            "candidatedocument",
            "kind",
            models.CharField(
                max_length=12,
                default="cv",
                choices=[
                    ("cv", "CV"),
                    ("degree", "Degree or qualification"),
                    ("certificate", "Certificate"),
                ],
            ),
        ),
        migrations.AddField(
            "candidatedocument", "title", models.CharField(max_length=160, blank=True)
        ),
        *[
            migrations.RemoveField("candidatedocument", field)
            for field in (
                "status",
                "extracted_text",
                "suggestions",
                "message",
                "reviewed_at",
            )
        ],
    ]
