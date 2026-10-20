"""Candidate-owned professional information, independent of account identity."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


def validate_past_date(value):
    if value > timezone.localdate():
        raise ValidationError("Enter today or an earlier date.")


def validate_period(start, end, current):
    errors = {}
    if start and end and end < start:
        errors["end_date"] = "The end date must be on or after the start date."
    if current and end:
        errors["end_date"] = "Leave the end date blank for a current entry."
    return errors


class CandidateProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
        limit_choices_to={"role": "candidate"},
    )
    headline = models.CharField(max_length=160, blank=True)
    location = models.CharField(max_length=120, blank=True)
    summary = models.TextField(max_length=3000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.user_id and self.user.role != "candidate":
            raise ValidationError(
                {"user": "A professional profile must belong to a candidate."}
            )

    def __str__(self):
        return self.user.get_full_name() or self.user.email


class CandidateSkill(models.Model):
    profile = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="skills"
    )
    name = models.CharField(max_length=80)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"), models.F("profile"), name="unique_candidate_skill_name"
            ),
        ]

    def __str__(self):
        return self.name


class Education(models.Model):
    profile = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="education"
    )
    qualification = models.CharField(max_length=160)
    institution = models.CharField(max_length=160)
    field_of_study = models.CharField(max_length=160, blank=True)
    start_date = models.DateField(
        blank=True, null=True, validators=[validate_past_date]
    )
    end_date = models.DateField(blank=True, null=True, validators=[validate_past_date])
    currently_studying = models.BooleanField(default=False)

    class Meta:
        ordering = ["-pk"]

    def clean(self):
        errors = validate_period(
            self.start_date, self.end_date, self.currently_studying
        )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.qualification} — {self.institution}"


class Certification(models.Model):
    profile = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="certifications"
    )
    name = models.CharField(max_length=160)
    issuer = models.CharField(max_length=160)
    issue_date = models.DateField(
        blank=True, null=True, validators=[validate_past_date]
    )
    expiry_date = models.DateField(blank=True, null=True)
    credential_id = models.CharField(max_length=120, blank=True)
    credential_url = models.URLField(
        max_length=500, blank=True, validators=[URLValidator(schemes=["http", "https"])]
    )

    class Meta:
        ordering = ["-pk"]

    def clean(self):
        if self.issue_date and self.expiry_date and self.expiry_date < self.issue_date:
            raise ValidationError(
                {"expiry_date": "Expiry must be on or after the issue date."}
            )

    def __str__(self):
        return self.name


class WorkExperience(models.Model):
    profile = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="experience"
    )
    job_title = models.CharField(max_length=160)
    company = models.CharField(max_length=160)
    start_date = models.DateField(validators=[validate_past_date])
    end_date = models.DateField(blank=True, null=True, validators=[validate_past_date])
    currently_working = models.BooleanField(default=False)
    description = models.TextField(max_length=2000, blank=True)

    class Meta:
        ordering = ["-start_date", "-pk"]

    def clean(self):
        errors = validate_period(self.start_date, self.end_date, self.currently_working)
        if not self.currently_working and not self.end_date:
            errors["end_date"] = (
                "Enter an end date or select that you currently work here."
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.job_title} — {self.company}"


class PortfolioLink(models.Model):
    profile = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="portfolio_links"
    )
    title = models.CharField(max_length=120)
    url = models.URLField(
        max_length=500, validators=[URLValidator(schemes=["http", "https"])]
    )

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.title
