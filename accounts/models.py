"""Identity and roles, kept separate from candidate and recruiter profile data."""

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    class Role(models.TextChoices):
        CANDIDATE = "candidate", "Candidate"
        RECRUITER = "recruiter", "Recruiter"
        ADMINISTRATOR = "administrator", "Administrator"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CANDIDATE)
    email_two_step_enabled = models.BooleanField(default=False)
    candidate_workspace_enabled = models.BooleanField(default=False)
    recruiter_workspace_enabled = models.BooleanField(default=False)
    email_updates = models.BooleanField(default=True)

    def has_workspace(self, workspace):
        return workspace in {"candidate", "recruiter"} and (
            self.role == workspace
            or getattr(self, f"{workspace}_workspace_enabled", False)
        )

    @property
    def active_workspace(self):
        selected = getattr(self, "_active_workspace", None)
        return selected if self.has_workspace(selected) else self.role

    @property
    def active_workspace_label(self):
        return self.active_workspace.capitalize()

    class Meta:
        db_table = "users"
        constraints = [
            models.UniqueConstraint(
                Lower("email"), name="unique_user_email_case_insensitive"
            )
        ]


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    event_key = models.CharField(max_length=200, unique=True)
    workspace = models.CharField(
        max_length=10, choices=[("candidate", "Candidate"), ("recruiter", "Recruiter")]
    )
    title = models.CharField(max_length=200)
    body = models.TextField(max_length=2000)
    path = models.CharField(max_length=500)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    email_status = models.CharField(
        max_length=16,
        default="pending",
        choices=[
            ("pending", "Pending"),
            ("sent", "Sent"),
            ("failed", "Failed"),
            ("skipped", "Skipped"),
            ("not_required", "Separate interview email"),
        ],
    )
    email_attempts = models.PositiveIntegerField(default=0)
    emailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(
                fields=["recipient", "read_at"], name="notification_unread_idx"
            )
        ]
