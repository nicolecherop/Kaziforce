"""Recruiter-owned vacancies used by candidate applications."""

import uuid
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower


class Priority(models.IntegerChoices):
    STANDARD = 1, "Standard"
    IMPORTANT = 2, "Important"
    HIGH = 3, "High"


class JobPosting(models.Model):
    class EducationLevel(models.TextChoices):
        ANY = "any", "No specific qualification required"
        SECONDARY = "secondary", "Secondary school"
        CERTIFICATE = "certificate", "Certificate"
        DIPLOMA = "diploma", "Diploma"
        BACHELORS = "bachelors", "Bachelor's degree"
        MASTERS = "masters", "Master's degree"
        DOCTORATE = "doctorate", "Doctorate"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_postings"
    )
    title = models.CharField(max_length=160)
    company = models.CharField(max_length=160)
    location = models.CharField(max_length=160)
    description = models.TextField(max_length=10000)
    requirements = models.TextField(max_length=6000, blank=True)
    education_level = models.CharField(
        max_length=12, choices=EducationLevel.choices, default=EducationLevel.ANY
    )
    education_field = models.CharField(max_length=160, blank=True)
    education_priority = models.PositiveSmallIntegerField(
        choices=Priority.choices, default=Priority.STANDARD
    )
    minimum_experience_years = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(60)],
    )
    experience_details = models.TextField(max_length=500, blank=True)
    experience_priority = models.PositiveSmallIntegerField(
        choices=Priority.choices, default=Priority.STANDARD
    )
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "jobs"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(education_priority__in=Priority.values),
                name="job_education_priority_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(experience_priority__in=Priority.values),
                name="job_experience_priority_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_experience_years__isnull=True)
                | models.Q(
                    minimum_experience_years__gte=0, minimum_experience_years__lte=60
                ),
                name="job_experience_years_valid",
            ),
        ]

    def __str__(self):
        return self.title

    def structured_requirements(self, standardization=None):
        """JSON-safe job requirements, including labels for submitted copies."""
        from matching.skills import standardize_skills

        skills = list(self.skills.all())
        if standardization is None:
            standardization = standardize_skills([skill.name for skill in skills])
        return {
            "skill_standardization": standardization,
            "education_level": self.education_level,
            "education_level_label": self.get_education_level_display(),
            "education_field": self.education_field,
            "education_priority": self.education_priority,
            "education_priority_label": self.get_education_priority_display(),
            "minimum_experience_years": (
                str(self.minimum_experience_years)
                if self.minimum_experience_years is not None
                else None
            ),
            "experience_details": self.experience_details,
            "experience_priority": self.experience_priority,
            "experience_priority_label": self.get_experience_priority_display(),
            "skills": [
                {
                    "name": skill.name,
                    "requirement": skill.requirement,
                    "requirement_label": skill.get_requirement_display(),
                    "priority": skill.priority,
                    "priority_label": skill.get_priority_display(),
                    "standardization": mapping,
                }
                for skill, mapping in zip(
                    skills, standardization["skills"], strict=True
                )
            ],
        }


class JobSkill(models.Model):
    class Requirement(models.TextChoices):
        REQUIRED = "required", "Required"
        PREFERRED = "preferred", "Preferred"

    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name="skills")
    name = models.CharField(max_length=80)
    requirement = models.CharField(
        max_length=9, choices=Requirement.choices, default=Requirement.REQUIRED
    )
    priority = models.PositiveSmallIntegerField(
        choices=Priority.choices, default=Priority.STANDARD
    )

    class Meta:
        db_table = "job_skills"
        ordering = ["-priority", "name", "pk"]
        constraints = [
            models.UniqueConstraint(Lower("name"), "job", name="job_skill_name_unique"),
            models.CheckConstraint(
                condition=models.Q(priority__in=Priority.values),
                name="job_skill_priority_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(requirement__in=["required", "preferred"]),
                name="job_skill_requirement_valid",
            ),
        ]

    def __str__(self):
        return self.name
