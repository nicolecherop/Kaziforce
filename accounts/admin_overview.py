"""Permission-aware counts and operational summaries for the admin index."""

from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from applications.interview_services import email_is_connected
from applications.models import Application, Interview, InterviewEmail
from jobs.models import JobPosting
from matching.models import MatchRun, MatchResult
from freelance.models import Booking, ConversationReport, Payment


def can_view(user, model):
    label = model._meta.app_label
    name = model._meta.model_name
    return user.has_perm(f"{label}.view_{name}") or user.has_perm(
        f"{label}.change_{name}"
    )


def list_url(model):
    return reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")


def overview_context(user):
    cards, application_statuses, email_statuses = [], [], []
    recent_applications, upcoming_interviews = [], []
    User = get_user_model()
    if can_view(user, User):
        counts = User.objects.aggregate(
            total=Count("pk"),
            candidates=Count("pk", filter=Q(role="candidate")),
            recruiters=Count("pk", filter=Q(role="recruiter")),
            inactive=Count("pk", filter=Q(is_active=False)),
        )
        cards.append(
            {
                "label": "Accounts",
                "value": counts["total"],
                "url": list_url(User),
                "detail": f'{counts["candidates"]} candidates · {counts["recruiters"]} recruiters · {counts["inactive"]} inactive',
            }
        )
    if can_view(user, JobPosting):
        counts = JobPosting.objects.aggregate(
            total=Count("pk"), open=Count("pk", filter=Q(status="open"))
        )
        cards.append(
            {
                "label": "Jobs",
                "value": counts["total"],
                "url": list_url(JobPosting),
                "detail": f'{counts["open"]} open for applications',
            }
        )
    if can_view(user, Application):
        applications = Application.objects.exclude(status="draft")
        cards.append(
            {
                "label": "Submitted applications",
                "value": applications.count(),
                "url": list_url(Application),
                "detail": "Submitted copies available for oversight",
            }
        )
        totals = dict(applications.values_list("status").annotate(total=Count("pk")))
        application_statuses = [
            {
                "label": label,
                "count": totals.get(value, 0),
                "url": list_url(Application) + f"?status__exact={value}",
            }
            for value, label in Application.Status.choices
            if value != "draft"
        ]
        recent_applications = applications.select_related("job", "candidate").order_by(
            "-submitted_at", "pk"
        )[:5]
    if can_view(user, Interview):
        interviews = Interview.objects.exclude(application__status="draft")
        now = timezone.now()
        upcoming = interviews.filter(status="scheduled", starts_at__gte=now)
        cards.append(
            {
                "label": "Upcoming interviews",
                "value": upcoming.count(),
                "url": list_url(Interview)
                + "?"
                + urlencode(
                    {"status__exact": "scheduled", "starts_at__gte": now.isoformat()}
                ),
                "detail": "Scheduled from now onward",
            }
        )
        upcoming_interviews = upcoming.select_related("application__job").order_by(
            "starts_at", "pk"
        )[:5]
    if can_view(user, InterviewEmail):
        emails = InterviewEmail.objects.exclude(interview__application__status="draft")
        totals = dict(emails.values_list("status").annotate(total=Count("pk")))
        email_statuses = [
            {
                "label": label,
                "count": totals.get(value, 0),
                "url": list_url(InterviewEmail) + f"?status__exact={value}",
            }
            for value, label in InterviewEmail.Status.choices
        ]
    if can_view(user, MatchRun):
        cards.append(
            {
                "label": "Matching runs",
                "value": MatchRun.objects.count(),
                "url": list_url(MatchRun),
                "detail": "Saved calculation history",
            }
        )
    if can_view(user, MatchResult):
        cards.append(
            {
                "label": "Saved match results",
                "value": MatchResult.objects.count(),
                "url": list_url(MatchResult),
                "detail": "Scores and original matching evidence",
            }
        )
    for model, label, queryset, detail in [
        (
            Booking,
            "Freelance bookings",
            Booking.objects.all(),
            "Agreements, completion and payment history",
        ),
        (
            Payment,
            "Payment queries",
            Payment.objects.filter(status="disputed"),
            "Participant-reported payments awaiting resolution",
        ),
        (
            ConversationReport,
            "Conversation reports",
            ConversationReport.objects.filter(is_resolved=False),
            "Open concerns requiring review",
        ),
    ]:
        if can_view(user, model):
            cards.append(
                {
                    "label": label,
                    "value": queryset.count(),
                    "url": list_url(model)
                    + (
                        "?status__exact=disputed"
                        if model == Payment
                        else (
                            "?is_resolved__exact=0"
                            if model == ConversationReport
                            else ""
                        )
                    ),
                    "detail": detail,
                }
            )
    return {
        "overview_cards": cards,
        "application_statuses": application_statuses,
        "email_statuses": email_statuses,
        "email_connected": email_is_connected() if email_statuses else None,
        "recent_applications": recent_applications,
        "upcoming_interviews": upcoming_interviews,
    }
