"""Freelance listings and agreements, independent of employment applications."""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q, F

from candidates.validators import validate_phone_number

MONEY = {"max_digits": 12, "decimal_places": 2}


class FreelancerProfile(models.Model):
    class WorkMode(models.TextChoices):
        ON_SITE = "on_site", "On site"
        REMOTE = "remote", "Remote"
        FLEXIBLE = "flexible", "On site or remote"

    class RateUnit(models.TextChoices):
        HOUR = "hour", "Per hour"
        DAY = "day", "Per day"
        PROJECT = "project", "Per project"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="freelancer_profile",
    )
    title = models.CharField(max_length=160)
    about = models.TextField(max_length=3000)
    location = models.CharField(max_length=120)
    work_mode = models.CharField(
        max_length=12, choices=WorkMode.choices, default=WorkMode.ON_SITE
    )
    rate = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("1"))])
    rate_unit = models.CharField(
        max_length=10, choices=RateUnit.choices, default=RateUnit.DAY
    )
    available_from = models.DateField()
    accepting_bookings = models.BooleanField(default=False)
    share_professional_profile = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "freelancer_profiles"
        ordering = ["-updated_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(rate__gte=1), name="freelancer_positive_rate"
            )
        ]

    def __str__(self):
        return self.title


class FreelanceService(models.Model):
    profile = models.ForeignKey(
        FreelancerProfile, on_delete=models.CASCADE, related_name="services"
    )
    title = models.CharField(max_length=120)
    description = models.TextField(max_length=1000, blank=True)

    class Meta:
        db_table = "freelance_services"
        ordering = ["pk"]

    def __str__(self):
        return self.title


class FreelanceProject(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open for enquiries"
        CLOSED = "closed", "Closed to new enquiries"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="freelance_projects",
    )
    title = models.CharField(max_length=160)
    description = models.TextField(max_length=5000)
    skills = models.JSONField(default=list)
    location = models.CharField(max_length=120)
    work_mode = models.CharField(
        max_length=12, choices=FreelancerProfile.WorkMode.choices
    )
    budget = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("1"))])
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.OPEN
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "freelance_projects"
        ordering = ["-created_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")), name="project_valid_dates"
            ),
            models.CheckConstraint(
                condition=Q(budget__gte=1), name="project_positive_budget"
            ),
        ]

    def __str__(self):
        return self.title


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="freelance_conversations",
    )
    freelancer = models.ForeignKey(
        FreelancerProfile, on_delete=models.PROTECT, related_name="conversations"
    )
    project = models.ForeignKey(
        FreelanceProject, on_delete=models.PROTECT, null=True, blank=True
    )
    recruiter_blocked = models.BooleanField(default=False)
    freelancer_blocked = models.BooleanField(default=False)
    recruiter_read_at = models.DateTimeField(null=True, blank=True)
    freelancer_read_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "conversations"
        ordering = ["-updated_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["recruiter", "freelancer"],
                condition=Q(project__isnull=True),
                name="unique_direct_conversation",
            ),
            models.UniqueConstraint(
                fields=["recruiter", "freelancer", "project"],
                condition=Q(project__isnull=False),
                name="unique_project_conversation",
            ),
        ]

    @property
    def blocked(self):
        return self.recruiter_blocked or self.freelancer_blocked


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.PROTECT, related_name="messages"
    )
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField(max_length=3000)
    is_system = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "messages"
        ordering = ["created_at", "pk"]


class Booking(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Awaiting freelancer response"
        ACCEPTED = "accepted", "Confirmed"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETION_REQUESTED = (
            "completion_requested",
            "Awaiting completion confirmation",
        )
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.PROTECT, related_name="bookings"
    )
    title = models.CharField(max_length=160)
    scope = models.TextField(max_length=5000)
    location = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    total_price = models.DecimalField(
        **MONEY, validators=[MinValueValidator(Decimal("1"))]
    )
    # Historical agreements only. New bookings always set this to zero.
    deposit_amount = models.DecimalField(
        **MONEY, default=0, validators=[MinValueValidator(Decimal("0"))]
    )
    cancellation_terms = models.TextField(max_length=1500)
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.REQUESTED
    )
    recruiter_name = models.CharField(max_length=160)
    recruiter_email = models.EmailField()
    recruiter_phone = models.CharField(
        max_length=32, blank=True, validators=[validate_phone_number]
    )
    freelancer_name = models.CharField(max_length=160, blank=True)
    freelancer_email = models.EmailField(blank=True)
    freelancer_phone = models.CharField(
        max_length=32, blank=True, validators=[validate_phone_number]
    )
    cancellation_requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    cancellation_reason = models.TextField(max_length=1500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bookings"
        ordering = ["-created_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")), name="booking_valid_dates"
            ),
            models.CheckConstraint(
                condition=Q(total_price__gte=1), name="booking_positive_price"
            ),
            models.CheckConstraint(
                condition=Q(deposit_amount__gte=0)
                & Q(deposit_amount__lte=F("total_price")),
                name="booking_valid_deposit",
            ),
        ]

    def __str__(self):
        return self.title


class BookingEvent(models.Model):
    booking = models.ForeignKey(
        Booking, on_delete=models.PROTECT, related_name="events"
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    description = models.CharField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "booking_events"
        ordering = ["created_at", "pk"]


class Payment(models.Model):
    class Kind(models.TextChoices):
        DEPOSIT = "deposit", "Deposit"  # Kept for historical receipt records only.
        BALANCE = "balance", "Work payment"
        REFUND = "refund", "Refund to recruiter"

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        DIRECT = "direct", "Direct payment arranged outside KaziForce"

    class Status(models.TextChoices):
        REPORTED = "reported", "Awaiting recipient confirmation"
        CONFIRMED = "confirmed", "Receipt confirmed by recipient"
        DISPUTED = "disputed", "Recipient has queried this payment"
        WITHDRAWN = "withdrawn", "Report withdrawn"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(
        Booking, on_delete=models.PROTECT, related_name="payments"
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reported_freelance_payments",
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="confirmed_freelance_payments",
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    method = models.CharField(max_length=10, choices=Method.choices)
    amount = models.DecimalField(
        **MONEY, validators=[MinValueValidator(Decimal("0.01"))]
    )
    reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.REPORTED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payments"
        ordering = ["created_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="payment_positive_amount"
            )
        ]


class Review(models.Model):
    booking = models.OneToOneField(
        Booking, on_delete=models.PROTECT, related_name="review"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(max_length=1500)
    is_hidden = models.BooleanField(default=False)
    moderation_note = models.TextField(max_length=1500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reviews"
        ordering = ["-created_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(rating__gte=1, rating__lte=5), name="review_rating_range"
            )
        ]


class ConversationReport(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.PROTECT, related_name="reports"
    )
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField(max_length=1500)
    is_resolved = models.BooleanField(default=False)
    moderation_note = models.TextField(max_length=1500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "conversation_reports"
        ordering = ["-created_at"]
