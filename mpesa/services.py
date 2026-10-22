"""Idempotent sandbox collection; never settles the worker's payment ledger."""

from decimal import Decimal
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from freelance.models import Booking
from freelance.services import payment_totals
from .client import (
    DarajaSandboxClient,
    ProviderError,
    ProviderRejected,
    normalize_phone,
    sandbox_ready,
)
from .models import MpesaTransaction


def payment_summary(booking):
    collected = (
        booking.mpesa_transactions.filter(status="success").aggregate(
            total=Sum("amount")
        )["total"]
        or 0
    )
    receipts = payment_totals(booking)
    other = receipts["net"]
    received = Decimal(collected) + other
    remaining = max(Decimal("0"), booking.total_price - received)
    paid = remaining == 0
    pending = booking.mpesa_transactions.filter(
        status__in=["initiating", "pending", "unknown"]
    ).exists()
    label = (
        "Payment complete"
        if paid
        else (
            "Partially paid"
            if received > 0
            else "Payment pending" if pending else "Awaiting payment"
        )
    )
    return {
        "mpesa_received": Decimal(collected),
        "other_received": other,
        "received": received,
        "remaining": remaining,
        "is_paid": paid,
        "label": label,
        "other_pending": receipts["reserved_received"] - receipts["received"],
    }


def sandbox_remaining(booking):
    summary = payment_summary(booking)
    return max(Decimal("0"), summary["remaining"] - summary["other_pending"])


def initiate_payment(booking_id, actor, fields):
    if not sandbox_ready():
        raise ValidationError(
            "M-Pesa is currently unavailable. Please try again later."
        )
    with transaction.atomic():
        booking = (
            Booking.objects.select_for_update()
            .select_related("conversation")
            .get(pk=booking_id)
        )
        if actor.pk != booking.conversation.recruiter_id or actor.role != "recruiter":
            raise PermissionDenied
        phone = normalize_phone(fields["phone_number"])
        amount = Decimal(str(fields["amount"]))
        if (
            not amount.is_finite()
            or amount != amount.to_integral_value()
            or not 1 <= amount <= 100000
        ):
            raise ValidationError(
                "Use a whole-shilling amount from KES 1 to KES 100,000."
            )
        previous = MpesaTransaction.objects.filter(
            request_key=fields["request_key"]
        ).first()
        if previous:
            if (
                previous.booking_id != booking.pk
                or previous.initiated_by_id != actor.pk
                or previous.amount != amount
                or previous.phone_number != phone
            ):
                raise ValidationError(
                    "This request was already used for different payment details. Reload the page."
                )
            return previous
        if booking.status != "completed" or not booking.accepted_at:
            raise ValidationError(
                "M-Pesa payments are available after the recruiter confirms completion."
            )
        if booking.mpesa_transactions.filter(
            status__in=["initiating", "pending", "unknown"]
        ).exists():
            raise ValidationError(
                "A payment request is already pending. Check its status before creating another."
            )
        if amount > sandbox_remaining(booking):
            raise ValidationError("The amount exceeds the remaining balance.")
        attempt = MpesaTransaction.objects.create(
            booking=booking,
            initiated_by=actor,
            request_key=fields["request_key"],
            amount=int(amount),
            phone_number=phone,
            shortcode=settings.MPESA_SANDBOX["shortcode"],
        )
    # Keep slow provider calls outside the booking lock. A pending-row constraint
    # protects against simultaneous submissions while this request is in flight.
    try:
        result = DarajaSandboxClient().initiate(attempt)
    except ProviderRejected:
        MpesaTransaction.objects.filter(pk=attempt.pk).update(status="failed")
    except ProviderError:
        # A timeout is not evidence of failure. Never automatically send again.
        MpesaTransaction.objects.filter(pk=attempt.pk).update(status="unknown")
    else:
        MpesaTransaction.objects.filter(pk=attempt.pk).update(
            status="pending",
            checkout_request_id=result["CheckoutRequestID"],
            merchant_request_id=result["MerchantRequestID"],
        )
    attempt.refresh_from_db()
    return attempt


def reconcile_payment(attempt_id, actor):
    with transaction.atomic():
        attempt = (
            MpesaTransaction.objects.select_for_update()
            .select_related("booking__conversation")
            .get(pk=attempt_id)
        )
        if (
            actor.pk != attempt.booking.conversation.recruiter_id
            or actor.role != "recruiter"
        ):
            raise PermissionDenied
        if attempt.status in {"success", "failed"}:
            return attempt
        if not attempt.checkout_request_id:
            raise ValidationError(
                "Submission could not be confirmed. Contact support before making another request to avoid a duplicate charge."
            )
        now = timezone.now()
        if attempt.checked_at and (now - attempt.checked_at).total_seconds() < 15:
            raise ValidationError("Wait 15 seconds before checking again.")
        attempt.checked_at = now
        attempt.save(update_fields=["checked_at", "updated_at"])
    try:
        result = DarajaSandboxClient().query(attempt)
    except ProviderError:
        raise ValidationError(
            "Payment status is unavailable. The request remains pending; check again later."
        ) from None
    # An unauthenticated callback or a browser assertion never confirms collection.
    if (
        result.get("CheckoutRequestID") != attempt.checkout_request_id
        or result.get("MerchantRequestID") != attempt.merchant_request_id
    ):
        raise ValidationError(
            "The payment result could not be verified. The request remains pending."
        )
    code = str(result.get("ResultCode", ""))
    if code.isdigit() and len(code) <= 16:
        new_status = "success" if code == "0" else "failed"
        MpesaTransaction.objects.filter(
            pk=attempt.pk, status__in=["initiating", "pending", "unknown"]
        ).update(status=new_status, result_code=code)
    attempt.refresh_from_db()
    return attempt
