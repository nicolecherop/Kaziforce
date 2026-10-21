"""Private match pages. Only POST requests create stored matching runs."""

from uuid import UUID

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, OperationalError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from candidates.access import candidate_required
from jobs.access import recruiter_required
from jobs.models import JobPosting
from .models import MatchResult, MatchRun
from .recommendations import candidate_recommendations
from .scoring import MatchingError
from .services import generate_matches, run_is_current


def run_context(user, job=None):
    run = MatchRun.objects.filter(
        owner=user,
        kind=MatchRun.Kind.APPLICANTS if job else MatchRun.Kind.JOBS,
        job=job,
    ).first()
    results = (
        run.results.select_related("job", "application")
        if run
        else MatchResult.objects.none()
    )
    if job is None:
        recommendations = candidate_recommendations(user, run)
        return {
            "run": run,
            "results": recommendations,
            "recommended_count": recommendations.count(),
            "stale": run is not None and not run_is_current(run, user),
        }
    return {
        "run": run,
        "results": results.filter(score__isnull=False).order_by("rank")[:10],
        "unscored": results.filter(score__isnull=True),
        "scored_count": results.filter(score__isnull=False).count(),
        "stale": run is not None and not run_is_current(run, user, job),
        "job": job,
    }


@candidate_required
@never_cache
@require_GET
def job_matches(request):
    return render(request, "matching/job_matches.html", run_context(request.user))


@candidate_required
@never_cache
@require_POST
def refresh_jobs(request):
    refresh(request)
    return redirect("matches:jobs")


@recruiter_required
@never_cache
@require_GET
def applicant_rankings(request, job_id):
    job = get_object_or_404(
        JobPosting.objects.prefetch_related("skills"), pk=job_id, recruiter=request.user
    )
    context = run_context(request.user, job)
    context["jobs"] = request.user.job_postings.all()
    selected = request.GET.get("candidate")
    if selected:
        try:
            selected = UUID(selected)
        except ValueError as error:
            raise Http404 from error
        context["selected"] = get_object_or_404(
            MatchResult.objects.select_related("application", "job"),
            pk=selected,
            run=context["run"],
        )
    else:
        context["selected"] = context["results"].first() if context["run"] else None
    return render(request, "matching/applicant_rankings.html", context)


@recruiter_required
@never_cache
@require_GET
def applicant_workspace(request):
    jobs = request.user.job_postings.all()
    selected = request.GET.get("job")
    if selected:
        try:
            selected = UUID(selected)
        except ValueError as error:
            raise Http404 from error
        job = get_object_or_404(jobs, pk=selected)
    else:
        job = jobs.first()
    if job:
        return redirect("matches:applicants", job_id=job.pk)
    return render(request, "matching/applicant_rankings.html", {"jobs": jobs})


@recruiter_required
@never_cache
@require_POST
def refresh_applicants(request, job_id):
    job = get_object_or_404(
        JobPosting.objects.prefetch_related("skills"), pk=job_id, recruiter=request.user
    )
    refresh(request, job)
    return redirect("matches:applicants", job_id=job.pk)


def refresh(request, job=None):
    try:
        generate_matches(request.user, job)
    except MatchingError as error:
        messages.error(request, str(error))
    except (IntegrityError, OperationalError):
        messages.error(
            request,
            "Matching could not be saved. Please try again; no partial results were saved.",
        )
    else:
        messages.success(request, "Your matching review is ready.")


@login_required
@never_cache
@require_GET
def match_detail(request, result_id):
    queryset = MatchResult.objects.select_related(
        "run__corpus__catalogue", "job", "application"
    )
    if request.user.role == "candidate":
        queryset = queryset.filter(
            run__owner=request.user, run__kind="jobs", candidate=request.user
        )
    elif request.user.role == "recruiter":
        queryset = queryset.filter(
            run__owner=request.user,
            run__kind="applicants",
            job__recruiter=request.user,
            application__isnull=False,
        ).exclude(application__status="draft")
    else:
        queryset = queryset.none()
    result = get_object_or_404(queryset, pk=result_id)
    context = {
        "result": result,
        "job_evidence": result.input_snapshot["job"],
        "historical": not run_is_current(
            result.run,
            request.user,
            result.job if request.user.role == "recruiter" else None,
        ),
    }
    if request.user.role == "candidate":
        context["strong_match"] = (
            result.score is not None
            and result.score >= settings.MATCH_RECOMMENDATION_MIN_SCORE
        )
        template = "matching/candidate_match_detail.html"
    else:
        context["candidate_evidence"] = result.input_snapshot["profile"]
        template = "matching/match_detail.html"
    return render(request, template, context)
