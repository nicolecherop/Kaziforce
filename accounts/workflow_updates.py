"""Messages for committed recruitment and freelance workflow events."""

from django.urls import reverse
from pages.presentation import public_text
from .update_alerts import notify


def application_submitted(application):
    title = public_text(application.job.title)
    path = reverse("applications:detail", args=[application.pk])
    notify(
        application.candidate,
        event_key=f"application:{application.pk}:submitted:candidate",
        workspace="candidate",
        title="Application submitted",
        body=f"Your application for {title} has been submitted. You can follow its progress in My applications.",
        path=path,
    )
    notify(
        application.job.recruiter,
        event_key=f"application:{application.pk}:submitted:recruiter",
        workspace="recruiter",
        title="New application received",
        body=f"A new application for {title} is ready for your review.",
        path=path,
    )


def application_decision(application):
    notify(
        application.candidate,
        event_key=f"application:{application.pk}:status:{application.updated_at.isoformat()}",
        workspace="candidate",
        title="Application status updated",
        body=f"Your application for {public_text(application.job.title)} is now {application.get_status_display().lower()}. Open the application to review the latest details.",
        path=reverse("applications:detail", args=[application.pk]),
    )


def interview_update(interview, email_record, action):
    # The existing interview delivery service already sends the invitation;
    # add an in-app update without sending a second email for the same event.
    notify(
        interview.application.candidate,
        event_key=f"interview-email:{email_record.pk}",
        workspace="candidate",
        title=action,
        body=f"{action} for {public_text(interview.application.job.title)}. Open your application to check the date, location and recruiter contact details.",
        path=reverse("applications:detail", args=[interview.application_id]),
        email=False,
    )


def booking_update(booking, actor, event_record):
    conversation = booking.conversation
    recipient = (
        conversation.freelancer.user
        if actor.pk == conversation.recruiter_id
        else conversation.recruiter
    )
    workspace = (
        "candidate" if recipient.pk == conversation.freelancer.user_id else "recruiter"
    )
    notify(
        recipient,
        event_key=f"booking-event:{event_record.pk}",
        workspace=workspace,
        title="Booking update",
        body=f"{public_text(booking.title)}: {public_text(event_record.description)}",
        path=reverse("freelance:booking", args=[booking.pk]),
    )


def payment_update(attempt, status):
    booking = attempt.booking
    conversation = booking.conversation
    recipients = [(conversation.recruiter, "recruiter")]
    if status == "success":
        recipients.append((conversation.freelancer.user, "candidate"))
    body = (
        f"An M-Pesa collection of KES {attempt.amount} has been recorded for {public_text(booking.title)}. Worker payout is tracked separately."
        if status == "success"
        else f"The M-Pesa payment for {public_text(booking.title)} was not completed. Open the booking to check its payment status."
    )
    for recipient, workspace in recipients:
        notify(
            recipient,
            event_key=f"mpesa:{attempt.pk}:{status}:{recipient.pk}",
            workspace=workspace,
            title="Payment update",
            body=body,
            path=reverse("mpesa:booking", kwargs={"booking_id": booking.pk}),
        )
