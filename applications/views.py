"""Candidate application drafts and recruiter access to submitted copies."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from candidates.access import candidate_required
from candidates.document_views import document_response
from candidates.forms import ProfileForm
from candidates.models import CandidateProfile
from jobs.access import recruiter_required
from jobs.models import JobPosting
from .forms import APPLICATION_SECTIONS, ApplicationForm, ApplicationStatusForm
from .models import Application, ApplicationAttachment
from .services import save_application, snapshot_from_forms, snapshot_from_profile


@candidate_required
@never_cache
@require_GET
def my_applications(request):
    return render(
        request,
        "applications/my_applications.html",
        {"applications": request.user.applications.select_related("job")},
    )


@candidate_required
@never_cache
@require_http_methods(["GET", "POST"])
def application_edit(request, job_id):
    job = get_object_or_404(JobPosting, pk=job_id)
    application = request.user.applications.filter(job=job).first()
    if application and application.status != "draft":
        return redirect("applications:detail", application_id=application.pk)
    if job.status != "open":
        messages.error(request, "This job is closed to applications.")
        return redirect("jobs:detail", job_id=job.pk)
    snapshot = (
        application.profile_snapshot
        if application
        else snapshot_from_profile(request.user)
    )
    data = request.POST if request.method == "POST" else None
    form = ProfileForm(
        data,
        instance=CandidateProfile(user=request.user, **snapshot.get("profile", {})),
    )
    application_form = ApplicationForm(
        data,
        user=request.user,
        initial={
            "cover_letter": application.cover_letter if application else "",
            "documents": (
                application.documents.values_list("pk", flat=True)
                if application
                else []
            ),
        },
    )
    sections = [
        {
            "prefix": prefix,
            "title": title,
            "add_label": label,
            "formset": factory(
                data,
                initial=snapshot.get(prefix, []) if data is None else None,
                prefix=prefix,
            ),
        }
        for prefix, title, factory, label in APPLICATION_SECTIONS
    ]
    if request.method == "POST":
        valid = [
            form.is_valid(),
            application_form.is_valid(),
            *[section["formset"].is_valid() for section in sections],
        ]
        if all(valid):
            snapshot = snapshot_from_forms(form, sections)
            submit = request.POST.get("action") == "submit"
            has_details = snapshot["profile"]["summary"] or any(
                snapshot[key]
                for key in ("skills", "education", "certifications", "experience")
            )
            if submit and not has_details:
                form.add_error(
                    None,
                    "Add a summary, skills, education, certification or experience before submitting.",
                )
            else:
                try:
                    saved = save_application(
                        request.user,
                        job.pk,
                        snapshot,
                        application_form.cleaned_data,
                        submit,
                    )
                except ValidationError as error:
                    form.add_error(None, error)
                except (IntegrityError, OperationalError):
                    form.add_error(
                        None,
                        "The application changed while saving. Reload the page and try again.",
                    )
                except OSError:
                    form.add_error(
                        None,
                        "An attachment is unavailable. Check your documents and try again. No changes were saved.",
                    )
                else:
                    messages.success(
                        request,
                        (
                            "Your application has been submitted."
                            if submit
                            else "Your application draft has been saved."
                        ),
                    )
                    return redirect("applications:detail", application_id=saved.pk)
    has_errors = form.is_bound and (
        form.errors
        or application_form.errors
        or any(section["formset"].total_error_count() for section in sections)
    )
    return render(
        request,
        "applications/application_edit.html",
        {
            "job": job,
            "application": application,
            "form": form,
            "application_form": application_form,
            "sections": sections,
            "has_errors": has_errors,
        },
    )


def accessible_application(user, application_id):
    queryset = Application.objects.select_related("job", "candidate")
    if user.role == "candidate":
        queryset = queryset.filter(candidate=user)
    elif user.role == "recruiter":
        queryset = queryset.filter(job__recruiter=user).exclude(status="draft")
    else:
        queryset = queryset.none()
    return get_object_or_404(queryset, pk=application_id)


@login_required
@never_cache
@require_GET
def application_detail(request, application_id):
    application = accessible_application(request.user, application_id)
    return render(
        request,
        "applications/application_detail.html",
        {
            "application": application,
            "snapshot": application.profile_snapshot,
            "status_form": ApplicationStatusForm(
                initial={"status": application.status}
            ),
        },
    )


@recruiter_required
@never_cache
@require_GET
def applicants(request, job_id):
    job = get_object_or_404(JobPosting, pk=job_id, recruiter=request.user)
    return render(
        request,
        "applications/applicants.html",
        {"job": job, "applications": job.applications.exclude(status="draft")},
    )


@recruiter_required
@never_cache
@require_POST
def application_status(request, application_id):
    application = accessible_application(request.user, application_id)
    form = ApplicationStatusForm(request.POST)
    if form.is_valid():
        application.status = form.cleaned_data["status"]
        application.save(update_fields=["status", "updated_at"])
        messages.success(request, "Application status updated.")
    else:
        messages.error(request, "Choose a valid application status.")
    return redirect("applications:detail", application_id=application.pk)


@login_required
@never_cache
@require_GET
def attachment_file(request, attachment_id):
    attachment = get_object_or_404(ApplicationAttachment, pk=attachment_id)
    accessible_application(request.user, attachment.application_id)
    return document_response(
        attachment.file, attachment.original_name, inline=request.GET.get("view") == "1"
    )
