"""Bookmark annotations avoid one database query per job card."""

from django.db.models import Exists, OuterRef
from .models import SavedJob


def with_saved_status(queryset, user, job_field="pk"):
    return queryset.annotate(
        is_saved=Exists(
            SavedJob.objects.filter(candidate=user, job_id=OuterRef(job_field))
        )
    )
