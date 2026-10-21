"""Select candidate recommendations without changing saved matching evidence."""

from django.conf import settings

from applications.models import Application
from jobs.models import JobPosting
from .models import MatchResult, MatchRun

RECOMMENDATION_LIMIT = 10


def candidate_recommendations(user, run):
    """Return strong, currently available jobs in their original saved rank order."""
    if (
        run is None
        or user.role != "candidate"
        or run.kind != MatchRun.Kind.JOBS
        or run.owner_id != user.pk
    ):
        return MatchResult.objects.none()

    applied_jobs = (
        Application.objects.filter(candidate=user)
        .exclude(status="draft")
        .values("job_id")
    )
    return (
        run.results.filter(
            candidate=user,
            score__gte=settings.MATCH_RECOMMENDATION_MIN_SCORE,
            job__status=JobPosting.Status.OPEN,
        )
        .exclude(job_id__in=applied_jobs)
        .select_related("job")
        .order_by("rank", "pk")[:RECOMMENDATION_LIMIT]
    )
