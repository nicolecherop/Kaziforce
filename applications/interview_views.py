"""Recruiter controls for private application interview invitations."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST
from jobs.access import recruiter_required
from pages.presentation import public_text, contact_email
from .interview_forms import InterviewForm, InterviewCancellationForm
from .interview_services import (
    owned_application,
    save_interview,
    cancel_interview,
    attempt_delivery,
)
from .models import Application, Interview


@recruiter_required
@never_cache
@require_http_methods(["GET", "POST"])
def interview_edit(request, application_id):
    application = owned_application(request.user, application_id)
    if application.status != Application.Status.SHORTLISTED:
        messages.error(
            request, "Shortlist this application before scheduling an interview."
        )
        return redirect("applications:detail", application_id=application.pk)
    interview = Interview.objects.filter(application=application).first()
    form = InterviewForm(
        request.POST if request.method == "POST" else None,
        instance=interview,
        initial=(
            {}
            if interview
            else {
                "recruiter_name": public_text(request.user.get_full_name()),
                "recruiter_email": contact_email(request.user.email),
            }
        ),
    )
    if request.method == "POST" and form.is_valid():
        try:
            _, changed = save_interview(request.user, application.pk, form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        except (IntegrityError, OperationalError):
            form.add_error(
                None,
                "The invitation could not be saved. Reload the page and try again.",
            )
        else:
            messages.success(
                request,
                (
                    "Interview invitation saved. The candidate can view the details in My applications."
                    if changed
                    else "The interview details are already up to date."
                ),
            )
            return redirect("applications:detail", application_id=application.pk)
    return render(
        request,
        "applications/interview_form.html",
        {"application": application, "interview": interview, "form": form},
    )


@recruiter_required
@never_cache
@require_POST
def interview_cancel(request, application_id):
    application = owned_application(request.user, application_id)
    form = InterviewCancellationForm(request.POST)
    if form.is_valid():
        try:
            cancel_interview(request.user, application.pk, form.cleaned_data["reason"])
        except (ValidationError, IntegrityError, OperationalError):
            messages.error(
                request,
                "The interview could not be cancelled. Reload the page and try again.",
            )
        else:
            messages.success(
                request,
                "Interview cancelled. The candidate can see your update in My applications.",
            )
            return redirect("applications:detail", application_id=application.pk)
    interview = get_object_or_404(Interview, application=application)
    return render(
        request,
        "applications/interview_cancel.html",
        {"application": application, "interview": interview, "form": form},
    )


@recruiter_required
@never_cache
@require_POST
def interview_email_retry(request, application_id):
    application = owned_application(request.user, application_id)
    interview = get_object_or_404(Interview, application=application)
    notification = interview.emails.first()
    if notification:
        attempt_delivery(notification.pk)
    messages.info(
        request,
        "Check the interview's email delivery status below. The invitation remains available to the candidate in My applications.",
    )
    return redirect("applications:detail", application_id=application.pk)
