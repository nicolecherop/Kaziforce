"""Applications retain the profile and attachments actually submitted for a job."""

import uuid
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator, URLValidator
from django.db import models
from candidates.storage import PrivateDocumentStorage, application_upload_path
from candidates.validators import validate_phone_number


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


class Interview(models.Model):
    class Format(models.TextChoices):
        VIDEO = "video", "Video call"
        PHONE = "phone", "Phone call"
        IN_PERSON = "in_person", "In person"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        Application, on_delete=models.CASCADE, related_name="interview"
    )
    starts_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(
        default=30, validators=[MinValueValidator(15), MaxValueValidator(480)]
    )
    format = models.CharField(max_length=12, choices=Format.choices)
    meeting_url = models.URLField(
        max_length=500, blank=True, validators=[URLValidator(schemes=["http", "https"])]
    )
    location = models.CharField(max_length=300, blank=True)
    instructions = models.TextField(max_length=2000, blank=True)
    recruiter_name = models.CharField(max_length=150)
    recruiter_email = models.EmailField()
    recruiter_phone = models.CharField(
        max_length=32, blank=True, validators=[validate_phone_number]
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.SCHEDULED
    )
    cancellation_reason = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "interviews"
        ordering = ["starts_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(duration_minutes__gte=15, duration_minutes__lte=480),
                name="interview_duration_valid",
            )
        ]


class InterviewEmail(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Could not send"
        NOT_CONFIGURED = "not_configured", "Email delivery not connected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interview = models.ForeignKey(
        Interview, on_delete=models.CASCADE, related_name="emails"
    )
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    reply_to = models.EmailField()
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "interview_emails"
        ordering = ["-created_at", "-pk"]
