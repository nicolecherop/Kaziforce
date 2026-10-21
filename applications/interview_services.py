"""Owner-scoped interview changes and durable, retryable email notifications."""

import logging
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage, get_connection
from django.db import DatabaseError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from pages.presentation import public_text
from .models import Application, Interview, InterviewEmail

logger = logging.getLogger(__name__)
INTERVIEW_FIELDS = (
    "starts_at",
    "duration_minutes",
    "format",
    "meeting_url",
    "location",
    "instructions",
    "recruiter_name",
    "recruiter_email",
    "recruiter_phone",
)


def owned_application(user, application_id, lock=False):
    queryset = Application.objects
    if lock:
        queryset = queryset.select_for_update()
    return get_object_or_404(
        queryset.filter(job__recruiter=user).exclude(status="draft"), pk=application_id
    )


def interview_is_upcoming(interview):
    return bool(
        interview
        and interview.status == Interview.Status.SCHEDULED
        and interview.starts_at + timedelta(minutes=interview.duration_minutes)
        > timezone.now()
    )


def save_interview(user, application_id, details):
    with transaction.atomic():
        application = owned_application(user, application_id, lock=True)
        if (
            user.role != "recruiter"
            or application.status != Application.Status.SHORTLISTED
        ):
            raise ValidationError(
                "Shortlist this application before scheduling an interview."
            )
        if details["starts_at"] <= timezone.now():
            raise ValidationError("Choose a future interview date and time.")
        interview = Interview.objects.filter(application=application).first()
        if (
            interview
            and interview.status == "scheduled"
            and all(
                getattr(interview, field) == details[field]
                for field in INTERVIEW_FIELDS
            )
        ):
            return interview, False
        updated = interview is not None
        interview = interview or Interview(application=application)
        for field in INTERVIEW_FIELDS:
            setattr(interview, field, details[field])
        interview.status = Interview.Status.SCHEDULED
        interview.cancellation_reason = ""
        interview.full_clean()
        interview.save()
        queue_email(
            interview, "Interview updated" if updated else "Interview invitation"
        )
        return interview, True


def cancel_interview(user, application_id, reason):
    with transaction.atomic():
        application = owned_application(user, application_id, lock=True)
        interview = get_object_or_404(Interview, application=application)
        if interview.status == Interview.Status.CANCELLED:
            return interview
        interview.status = Interview.Status.CANCELLED
        interview.cancellation_reason = reason
        interview.full_clean()
        interview.save()
        queue_email(interview, "Interview cancelled")
        return interview


def change_application_status(user, application_id, status):
    with transaction.atomic():
        application = owned_application(user, application_id, lock=True)
        interview = Interview.objects.filter(application=application).first()
        if status != Application.Status.SHORTLISTED and interview_is_upcoming(
            interview
        ):
            raise ValidationError(
                "Cancel the upcoming interview before changing this application status."
            )
        application.status = status
        application.save(update_fields=["status", "updated_at"])


def queue_email(interview, action):
    application = interview.application
    contact = (
        application.profile_snapshot.get("profile", {}).get("contact_email")
        or application.candidate_email
    )
    job_name = public_text(
        application.job_snapshot.get("title") or application.job.title
    )
    company = public_text(
        application.job_snapshot.get("company") or application.job.company
    )
    when = timezone.localtime(interview.starts_at).strftime("%A, %d %B %Y at %H:%M")
    body = [
        f"{action}: {job_name}",
        company,
        f"Date and time: {when} (East Africa Time, UTC+3)",
        f"Duration: {interview.duration_minutes} minutes",
        f"Format: {interview.get_format_display()}",
    ]
    if interview.status == Interview.Status.CANCELLED:
        body.extend(
            ["This interview has been cancelled.", interview.cancellation_reason]
        )
    else:
        body.extend(
            filter(
                None,
                [interview.meeting_url, interview.location, interview.instructions],
            )
        )
    body.extend(
        [
            f"Contact person: {interview.recruiter_name}",
            f"Email: {interview.recruiter_email}",
        ]
    )
    if interview.recruiter_phone:
        body.append(f"Phone: {interview.recruiter_phone}")
    body.append(
        "You can also review this invitation in KaziForce under My applications. Please contact the recruiter directly for questions or further arrangements."
    )
    notification = InterviewEmail.objects.create(
        interview=interview,
        recipient_email=contact,
        subject=f"KaziForce — {action}: {job_name}"[:255],
        body="\n\n".join(body),
        reply_to=interview.recruiter_email,
    )
    transaction.on_commit(lambda: attempt_delivery(notification.pk))


def attempt_delivery(email_id):
    """Delivery bookkeeping failures must not invalidate an already-saved invite."""
    try:
        deliver_email(email_id)
    except DatabaseError:
        logger.warning(
            "Interview email delivery remains pending; notification %s can be retried.",
            email_id,
        )


def email_is_connected():
    backend = settings.EMAIL_BACKEND
    if backend in (
        "django.core.mail.backends.console.EmailBackend",
        "django.core.mail.backends.dummy.EmailBackend",
        "django.core.mail.backends.filebased.EmailBackend",
    ):
        return False
    if backend == "django.core.mail.backends.smtp.EmailBackend":
        return bool(
            settings.EMAIL_HOST
            and settings.EMAIL_HOST != "localhost"
            and settings.EMAIL_HOST_USER
            and settings.EMAIL_HOST_PASSWORD
        )
    return True


def deliver_email(email_id):
    """Retry only the latest invitation; sent and superseded notices are not resent."""
    with transaction.atomic():
        notification = (
            InterviewEmail.objects.select_for_update()
            .select_related("interview")
            .get(pk=email_id)
        )
        if (
            notification.status == InterviewEmail.Status.SENT
            or notification.interview.emails.first().pk != notification.pk
        ):
            return
        # Reserved example accounts must never trigger mail to a real service.
        reserved = notification.recipient_email.lower().endswith(
            (".test", ".invalid", "@example.com", "@example.org", "@example.net")
        )
        if not email_is_connected() or not notification.recipient_email or reserved:
            notification.status = InterviewEmail.Status.NOT_CONFIGURED
            notification.save(update_fields=["status"])
            return
        notification.attempts += 1
        try:
            with get_connection(timeout=10) as connection:
                sent = EmailMessage(
                    subject=notification.subject,
                    body=notification.body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[notification.recipient_email],
                    reply_to=[notification.reply_to],
                    connection=connection,
                ).send()
            if sent != 1:
                raise RuntimeError("Email was not accepted for delivery.")
        except Exception:
            # Do not log credentials, candidate addresses or invitation contents.
            logger.warning(
                "Interview email could not be sent; notification %s remains retryable.",
                notification.pk,
            )
            notification.status = InterviewEmail.Status.FAILED
        else:
            notification.status = InterviewEmail.Status.SENT
            notification.sent_at = timezone.now()
        notification.save(update_fields=["status", "attempts", "sent_at"])
