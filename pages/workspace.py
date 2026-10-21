"""Read-only dashboard summaries; visiting a dashboard never calculates matches."""

from django.db.models import Count, Q
from django.utils import timezone
from applications.models import Application, Interview
from candidates.selectors import profile_for, section_status
from matching.models import MatchRun
from matching.recommendations import candidate_recommendations
from matching.services import run_is_current


def candidate_dashboard(user):
    profile = profile_for(user)
    sections = section_status(profile)
    core = sections[:5]
    completed = sum(item["complete"] for item in core)
    next_section = next((item for item in core if not item["complete"]), None)
    run = user.match_runs.filter(kind=MatchRun.Kind.JOBS).first()
    results = candidate_recommendations(user, run)
    hour = timezone.localtime().hour
    return {
        "profile": profile,
        "profile_sections": sections,
        "core_sections": core,
        "completed_sections": completed,
        "completion": round(completed / len(core) * 100),
        "next_section": next_section,
        "greeting": (
            "Good morning"
            if hour < 12
            else "Good afternoon" if hour < 18 else "Good evening"
        ),
        "match_run": run,
        "recommended_jobs": results[:3],
        "recommended_count": results.count(),
        "matches_stale": bool(run and not run_is_current(run, user)),
        "active_application_count": user.applications.filter(
            status__in=["submitted", "reviewing", "shortlisted"]
        ).count(),
        "draft_count": user.applications.filter(status="draft").count(),
        "upcoming_interviews": upcoming_interviews(user),
    }


def recruiter_dashboard(user):
    jobs = user.job_postings.annotate(
        applicant_count=Count("applications", filter=~Q(applications__status="draft"))
    )
    applications = Application.objects.filter(job__recruiter=user).exclude(
        status="draft"
    )
    return {
        "recent_jobs": jobs[:4],
        "open_job_count": jobs.filter(status="open").count(),
        "application_count": applications.count(),
        "shortlisted_count": applications.filter(status="shortlisted").count(),
        "upcoming_interviews": upcoming_interviews(user),
    }


def upcoming_interviews(user):
    interviews = Interview.objects.filter(
        status="scheduled", starts_at__gte=timezone.now()
    ).select_related("application__job")
    interviews = (
        interviews.filter(application__candidate=user)
        if user.role == "candidate"
        else interviews.filter(application__job__recruiter=user)
    )
    return interviews.order_by("starts_at", "pk")[:5]
