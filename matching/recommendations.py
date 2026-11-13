"""Select candidate recommendations without changing saved matching evidence."""

from applications.models import Application
from jobs.models import JobPosting
from jobs.saved_selectors import with_saved_status
from .models import MatchResult, MatchRun

RECOMMENDATION_LIMIT = 10


def candidate_recommendations(user, run):
    """Return the top ten scored, currently available jobs in their original saved rank order."""
    if (
        run is None
        or user.active_workspace != "candidate"
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
        with_saved_status(run.results.all(), user, "job_id")
        .filter(
            candidate=user,
            score__isnull=False,
            rank__isnull=False,
            job__in=JobPosting.objects.accepting_applications(),
        )
        .exclude(job_id__in=applied_jobs)
        .exclude(job__recruiter=user)
        .select_related("job")
        .order_by("rank", "pk")[:RECOMMENDATION_LIMIT]
    )
