"""Serialize manual profile fields and freeze independent application copies."""

from datetime import date
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import transaction
from django.utils import timezone
from candidates.selectors import profile_for
from jobs.models import JobPosting
from .forms import APPLICATION_SECTIONS
from .models import Application, ApplicationAttachment


def serializable(values):
    return {
        key: value.isoformat() if isinstance(value, date) else value
        for key, value in values.items()
    }


def profile_fields(form):
    return [name for name in form._meta.fields if name != "profile"]


def snapshot_from_profile(user):
    profile = profile_for(user)
    snapshot = {
        "profile": {
            key: getattr(profile, key, "")
            for key in ("headline", "location", "summary")
        }
    }
    for prefix, title, factory, label in APPLICATION_SECTIONS:
        relation = "portfolio_links" if prefix == "portfolio" else prefix
        snapshot[prefix] = (
            [
                serializable(row)
                for row in getattr(profile, relation).values(
                    *profile_fields(factory.form)
                )
            ]
            if profile
            else []
        )
    return snapshot


def snapshot_from_forms(profile_form, sections):
    snapshot = {
        "profile": {
            key: profile_form.cleaned_data[key]
            for key in ("headline", "location", "summary")
        }
    }
    for section in sections:
        snapshot[section["prefix"]] = [
            serializable({key: form.cleaned_data[key] for key in profile_fields(form)})
            for form in section["formset"]
            if form.cleaned_data and not form.cleaned_data.get("DELETE")
        ]
    return snapshot


def save_application(user, job_id, snapshot, application_data, submit):
    new_files = []
    try:
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=user.pk)
            job = JobPosting.objects.select_for_update().get(pk=job_id)
            if job.status != JobPosting.Status.OPEN:
                raise ValidationError(
                    "This job has closed. Your application has not been submitted."
                )
            application, _ = Application.objects.select_for_update().get_or_create(
                candidate=user, job=job
            )
            if application.status != Application.Status.DRAFT:
                return application
            application.profile_snapshot = snapshot
            application.cover_letter = application_data["cover_letter"]
            documents = list(application_data["documents"])
            # Recheck ownership here as well as in the HTTP form boundary.
            if any(document.user_id != user.pk for document in documents):
                raise ValidationError("Choose documents from your own library.")
            if submit:
                application.status = Application.Status.SUBMITTED
                application.submitted_at = timezone.now()
                application.candidate_name = user.get_full_name()
                application.candidate_email = user.email
                application.job_snapshot = {
                    key: getattr(job, key)
                    for key in (
                        "title",
                        "company",
                        "location",
                        "description",
                        "requirements",
                    )
                }
                application.job_snapshot["structured_requirements"] = (
                    job.structured_requirements()
                )
            application.save()
            application.documents.set(documents)
            if submit:
                for document in documents:
                    attachment = ApplicationAttachment(
                        application=application,
                        title=document.title,
                        original_name=document.original_name,
                        kind=document.kind,
                    )
                    with document.file.open("rb") as original:
                        attachment.file.save(
                            document.original_name, File(original), save=False
                        )
                    new_files.append((attachment.file.storage, attachment.file.name))
                    attachment.save()
            return application
    except Exception:
        # Database rollback cannot undo a filesystem write.
        for storage, name in new_files:
            storage.delete(name)
        raise
