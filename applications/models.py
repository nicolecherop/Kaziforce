"""Applications retain the profile and attachments actually submitted for a job."""

import uuid
from django.conf import settings
from django.db import models
from candidates.storage import PrivateDocumentStorage, application_upload_path


class Application(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        REVIEWING = "reviewing", "Under review"
        SHORTLISTED = "shortlisted", "Shortlisted"
        UNSUCCESSFUL = "unsuccessful", "Unsuccessful"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications"
    )
    job = models.ForeignKey(
        "jobs.JobPosting", on_delete=models.PROTECT, related_name="applications"
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.DRAFT
    )
    profile_snapshot = models.JSONField(default=dict)
    job_snapshot = models.JSONField(default=dict)
    candidate_name = models.CharField(max_length=300, blank=True)
    candidate_email = models.EmailField(blank=True)
    cover_letter = models.TextField(max_length=4000, blank=True)
    documents = models.ManyToManyField(
        "candidates.CandidateDocument",
        blank=True,
        related_name="application_drafts",
        db_table="application_draft_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "applications"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "job"], name="unique_candidate_job_application"
            )
        ]


class ApplicationAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(
        storage=PrivateDocumentStorage(), upload_to=application_upload_path
    )
    original_name = models.CharField(max_length=200)
    title = models.CharField(max_length=160, blank=True)
    kind = models.CharField(max_length=12)

    class Meta:
        db_table = "application_attachments"
        ordering = ["kind", "original_name"]

    def __str__(self):
        return self.title or self.original_name
