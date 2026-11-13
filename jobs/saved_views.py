"""Private candidate bookmarks; saving never submits an application."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from candidates.access import candidate_required
from .models import JobPosting, SavedJob


@candidate_required
@never_cache
@require_GET
def saved_jobs(request):
    bookmarks = SavedJob.objects.filter(candidate=request.user).select_related("job")
    return render(
        request,
        "jobs/saved_jobs.html",
        {"page": Paginator(bookmarks, 20).get_page(request.GET.get("page"))},
    )


@candidate_required
@never_cache
@require_POST
def save_job(request, job_id):
    job = get_object_or_404(JobPosting, pk=job_id)
    action = request.POST.get("action")
    if action == "save":
        SavedJob.objects.get_or_create(candidate=request.user, job=job)
        messages.success(
            request, "Job saved. Find it in Saved jobs whenever you are ready."
        )
    elif action == "remove":
        SavedJob.objects.filter(candidate=request.user, job=job).delete()
        messages.success(request, "Job removed from your saved list.")
    else:
        return HttpResponseBadRequest("Choose save or remove.")
    destination = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
        destination,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        destination = reverse("jobs:saved")
    return redirect(destination or reverse("jobs:saved"))
