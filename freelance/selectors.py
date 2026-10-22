"""Freelance-only discovery; employment scores and saved runs are never changed."""

from decimal import Decimal
from django.db.models import Avg, Count, Q, Exists, OuterRef
from django.utils import timezone
from matching.skills import standardize_skills
from matching.normalization import normalize_skill
from .models import FreelancerProfile, FreelanceProject, Booking, Review, Message
from .services import RESERVING_STATES


def visible_profiles():
    reviews = Q(conversations__bookings__review__is_hidden=False)
    return (
        FreelancerProfile.objects.filter(
            accepting_bookings=True,
            share_professional_profile=True,
            user__is_active=True,
            user__role="candidate",
        )
        .select_related("user", "user__candidate_profile")
        .prefetch_related("services", "user__candidate_profile__skills")
        .annotate(
            average_rating=Avg(
                "conversations__bookings__review__rating", filter=reviews
            ),
            review_count=Count(
                "conversations__bookings__review", filter=reviews, distinct=True
            ),
        )
    )


def visible_projects():
    return FreelanceProject.objects.filter(
        status="open",
        end_date__gte=timezone.localdate(),
        recruiter__is_active=True,
        recruiter__role="recruiter",
    ).select_related("recruiter")


def profile_reviews(profile):
    return Review.objects.filter(
        booking__conversation__freelancer=profile, is_hidden=False
    ).select_related("booking")


def skill_keys(names):
    # Only unambiguous catalogue concepts share a key. Unmapped labels retain exact wording matching.
    return {
        s["uri"] or "text:" + normalize_skill(s["name"])
        for s in standardize_skills(names)["skills"]
    }


def freelance_search(data, project=None):
    qs = visible_profiles()
    if data.get("q"):
        q = data["q"]
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(about__icontains=q)
            | Q(services__title__icontains=q)
            | Q(user__candidate_profile__skills__name__icontains=q)
        ).distinct()
    if data.get("location"):
        qs = qs.filter(location__icontains=data["location"])
    if data.get("work_mode"):
        qs = qs.filter(work_mode__in=[data["work_mode"], "flexible"])
    if data.get("rate_unit"):
        qs = qs.filter(rate_unit=data["rate_unit"])
    if data.get("maximum_rate") is not None:
        qs = qs.filter(rate__lte=data["maximum_rate"])
    start, end = data.get("start_date"), data.get("end_date")
    if project:
        start, end = project.start_date, project.end_date
        if project.work_mode != "flexible":
            qs = qs.filter(work_mode__in=[project.work_mode, "flexible"])
        if project.work_mode == "on_site":
            qs = qs.filter(location__iexact=project.location)
        # Compare like units: hourly starting rates require an agreed hour estimate.
        qs = qs.exclude(rate_unit="project", rate__gt=project.budget)
        if start and end:
            qs = qs.exclude(
                rate_unit="day",
                rate__gt=project.budget / Decimal((end - start).days + 1),
            )
    if start and end:
        overlaps = Booking.objects.filter(
            conversation__freelancer=OuterRef("pk"),
            status__in=RESERVING_STATES,
            start_date__lte=end,
            end_date__gte=start,
        )
        qs = (
            qs.filter(available_from__lte=start)
            .annotate(busy=Exists(overlaps))
            .filter(busy=False)
        )
    profiles = list(qs)
    target = skill_keys(project.skills) if project else set()
    for profile in profiles:
        professional = getattr(profile.user, "candidate_profile", None)
        keys = (
            skill_keys([s.name for s in professional.skills.all()])
            if target and professional
            else set()
        )
        profile.relevant_skills = len(keys & target)
        # Ratings are a secondary signal, moderated by review count for new workers.
        count = profile.review_count
        profile.rating_order = (
            float(profile.average_rating or 0) * count + 3.5 * 5
        ) / (count + 5)
    if target:
        profiles = [p for p in profiles if p.relevant_skills]
    profiles.sort(key=lambda p: (-p.relevant_skills, -p.rating_order, str(p.pk)))
    return profiles


def inbox_for(user):
    from .access import conversations_for

    field = "recruiter_read_at" if user.role == "recruiter" else "freelancer_read_at"
    unread = (
        Message.objects.filter(conversation=OuterRef("pk"))
        .exclude(sender=user)
        .filter(
            Q(**{f"conversation__{field}__isnull": True})
            | Q(created_at__gt=OuterRef(field))
        )
    )
    accepted = Booking.objects.filter(
        conversation__recruiter_id=OuterRef("recruiter_id"),
        conversation__freelancer_id=OuterRef("freelancer_id"),
        accepted_at__isnull=False,
    )
    return conversations_for(user).annotate(
        unread=Exists(unread), contacts_unlocked=Exists(accepted)
    )
