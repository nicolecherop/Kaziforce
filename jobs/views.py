from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from candidates.access import candidate_required
from .access import recruiter_required
from .forms import JobPostingForm
from .models import JobPosting


@candidate_required
@require_GET
def opportunities(request):
    jobs = JobPosting.objects.filter(status="open")
    query = request.GET.get("q", "").strip()[:160]
    if query:
        jobs = jobs.filter(
            Q(title__icontains=query)
            | Q(company__icontains=query)
            | Q(location__icontains=query)
        )
    return render(
        request, "jobs/opportunities.html", {"jobs": jobs[:100], "query": query}
    )


@candidate_required
@require_GET
def job_detail(request, job_id):
    job = get_object_or_404(JobPosting, pk=job_id)
    application = request.user.applications.filter(job=job).first()
    return render(
        request, "jobs/job_detail.html", {"job": job, "application": application}
    )


@recruiter_required
@require_GET
def manage_jobs(request):
    jobs = request.user.job_postings.annotate(
        applicant_count=Count("applications", filter=~Q(applications__status="draft"))
    )
    return render(request, "jobs/manage_jobs.html", {"jobs": jobs})


@recruiter_required
@require_http_methods(["GET", "POST"])
def job_edit(request, job_id=None):
    job = (
        get_object_or_404(JobPosting, pk=job_id, recruiter=request.user)
        if job_id
        else JobPosting(recruiter=request.user)
    )
    form = JobPostingForm(
        request.POST if request.method == "POST" else None, instance=job
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your job posting has been saved.")
        return redirect("jobs:manage")
    return render(request, "jobs/job_edit.html", {"form": form, "job": job})


@recruiter_required
@require_POST
def job_close(request, job_id):
    job = get_object_or_404(JobPosting, pk=job_id, recruiter=request.user)
    job.status = JobPosting.Status.CLOSED
    job.save(update_fields=["status", "updated_at"])
    messages.success(request, "This job is closed to new applications.")
    return redirect("jobs:manage")
