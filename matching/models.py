"""Versioned local reference data, independent of candidate identity."""

import uuid
from django.conf import settings
from django.db import models


class SkillCatalogue(models.Model):
    version = models.CharField(max_length=40)
    language = models.CharField(max_length=8, default="en")
    source_url = models.URLField(max_length=1000)
    checksum = models.CharField(max_length=64)
    skill_count = models.PositiveIntegerField()
    active = models.BooleanField(default=False)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "skill_catalogues"
        constraints = [
            models.UniqueConstraint(
                fields=["version", "language"], name="skill_catalogue_version_unique"
            ),
            models.UniqueConstraint(
                fields=["active"],
                condition=models.Q(active=True),
                name="one_active_skill_catalogue",
            ),
        ]

    def __str__(self):
        return f"ESCO {self.version} ({self.language})"

    def provenance(self):
        return {
            "version": self.version,
            "language": self.language,
            "checksum": self.checksum,
            "source_url": self.source_url,
        }


class CatalogueSkill(models.Model):
    catalogue = models.ForeignKey(
        SkillCatalogue, on_delete=models.CASCADE, related_name="skills"
    )
    uri = models.URLField(max_length=200)
    preferred_label = models.CharField(max_length=500)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "catalogue_skills"
        ordering = ["preferred_label", "uri"]
        constraints = [
            models.UniqueConstraint(
                fields=["catalogue", "uri"], name="catalogue_skill_uri_unique"
            )
        ]

    def __str__(self):
        return self.preferred_label


class SkillLabel(models.Model):
    skill = models.ForeignKey(
        CatalogueSkill, on_delete=models.CASCADE, related_name="labels"
    )
    label = models.CharField(max_length=500)
    normalized = models.CharField(max_length=500, db_index=True)
    preferred = models.BooleanField(default=False)

    class Meta:
        db_table = "skill_labels"
        constraints = [
            models.UniqueConstraint(
                fields=["skill", "normalized"], name="skill_label_normalized_unique"
            )
        ]

    def __str__(self):
        return self.label


class MatchingCorpus(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    catalogue = models.ForeignKey(
        SkillCatalogue, on_delete=models.PROTECT, related_name="matching_corpora"
    )
    tokenizer_version = models.CharField(max_length=40)
    source_checksum = models.CharField(max_length=64)
    checksum = models.CharField(max_length=64, unique=True)
    document_count = models.PositiveIntegerField()
    document_frequencies = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "matching_corpora"
        constraints = [
            models.UniqueConstraint(
                fields=["catalogue", "tokenizer_version", "source_checksum"],
                name="matching_corpus_source_unique",
            )
        ]


class MatchRun(models.Model):
    class Kind(models.TextChoices):
        JOBS = "jobs", "Candidate job matches"
        APPLICANTS = "applicants", "Recruiter applicant rankings"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="match_runs"
    )
    kind = models.CharField(max_length=12, choices=Kind.choices)
    job = models.ForeignKey(
        "jobs.JobPosting",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="match_runs",
    )
    corpus = models.ForeignKey(
        MatchingCorpus, on_delete=models.PROTECT, related_name="runs"
    )
    configuration = models.JSONField()
    input_checksum = models.CharField(max_length=64)
    as_of = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "match_runs"
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind="jobs", job__isnull=True)
                | models.Q(kind="applicants", job__isnull=False),
                name="match_run_kind_job_valid",
            )
        ]


class MatchResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(MatchRun, on_delete=models.CASCADE, related_name="results")
    job = models.ForeignKey(
        "jobs.JobPosting", on_delete=models.CASCADE, related_name="match_results"
    )
    candidate = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="match_results"
    )
    application = models.ForeignKey(
        "applications.Application",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="match_results",
    )
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rank = models.PositiveIntegerField(null=True, blank=True)
    input_snapshot = models.JSONField()
    input_checksum = models.CharField(max_length=64)
    components = models.JSONField(default=list)
    explanation = models.JSONField(default=dict)

    class Meta:
        db_table = "match_results"
        ordering = ["rank", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "candidate", "job"], name="match_result_pair_unique"
            ),
            models.UniqueConstraint(
                fields=["run", "rank"], name="match_result_rank_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(score__isnull=True, rank__isnull=True)
                | models.Q(
                    score__isnull=False,
                    rank__isnull=False,
                    score__gte=0,
                    score__lte=100,
                    rank__gt=0,
                ),
                name="match_result_score_rank_valid",
            ),
        ]
