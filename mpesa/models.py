"""Sandbox collections are separate from participant-confirmed worker payments."""

import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


class MpesaTransaction(models.Model):
    class Status(models.TextChoices):
        INITIATING = "initiating", "Submitting test request"
        PENDING = "pending", "Awaiting sandbox result"
        UNKNOWN = "unknown", "Submission uncertain — check before retrying"
        SUCCESS = "success", "Sandbox collection successful"
        FAILED = "failed", "Sandbox collection unsuccessful"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(
        "freelance.Booking", on_delete=models.PROTECT, related_name="mpesa_transactions"
    )
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    request_key = models.UUIDField(unique=True, editable=False)
    amount = models.PositiveIntegerField()
    phone_number = models.CharField(max_length=12)
    shortcode = models.CharField(max_length=6)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.INITIATING
    )
    checkout_request_id = models.CharField(
        max_length=128, unique=True, null=True, blank=True
    )
    merchant_request_id = models.CharField(max_length=128, blank=True)
    result_code = models.CharField(max_length=16, blank=True)
    callback_received_at = models.DateTimeField(null=True, blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mpesa_transactions"
        ordering = ["-created_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gte=1) & Q(amount__lte=100000),
                name="mpesa_sandbox_amount_range",
            ),
            models.UniqueConstraint(
                fields=["booking"],
                condition=Q(status__in=["initiating", "pending", "unknown"]),
                name="one_pending_mpesa_per_booking",
            ),
        ]

    @property
    def payment_status_label(self):
        return {
            "initiating": "Submitting payment request",
            "pending": "Awaiting payment confirmation",
            "unknown": "Confirmation needed",
            "success": "Payment received",
            "failed": "Payment unsuccessful",
        }[self.status]

    @property
    def commission(self):
        from freelance.pricing import commission_breakdown

        return commission_breakdown(self.amount)

    @property
    def masked_phone(self):
        return self.phone_number[:3] + "*****" + self.phone_number[-4:]

    def __str__(self):
        return f"M-Pesa · KES {self.amount} · {self.payment_status_label}"
