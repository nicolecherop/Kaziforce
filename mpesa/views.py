import json
from uuid import uuid4
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from allauth.core import ratelimit
from freelance.access import workspace_required, bookings_for
from freelance.pricing import commission_breakdown
from .client import sandbox_ready
from .forms import SandboxPaymentForm
from .models import MpesaTransaction
from .services import (
    initiate_payment,
    reconcile_payment,
    sandbox_remaining,
    payment_summary,
)
from django.conf import settings


@workspace_required
@require_http_methods(["GET", "POST"])
def booking_payments(request, booking_id):
    booking = get_object_or_404(bookings_for(request.user), pk=booking_id)
    is_recruiter = request.user.pk == booking.conversation.recruiter_id
    form = SandboxPaymentForm(
        request.POST if request.method == "POST" else None,
        initial={"request_key": uuid4(), "amount": int(sandbox_remaining(booking))},
    )
    if request.method == "POST":
        if not is_recruiter:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        blocked = ratelimit.consume_or_429(
            request, action="mpesa_sandbox", key=str(request.user.pk)
        )
        if blocked:
            return blocked
        if form.is_valid():
            try:
                attempt = initiate_payment(booking.pk, request.user, form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.info(
                    request,
                    "Payment request sent. We will update your balance after M-Pesa confirms the payment.",
                )
                return redirect("mpesa:booking", booking_id=booking.pk)
    return render(
        request,
        "mpesa/booking_payments.html",
        {
            "booking": booking,
            "commission": commission_breakdown(booking.total_price),
            "form": form,
            "is_recruiter": is_recruiter,
            "sandbox_ready": sandbox_ready(),
            "payment_summary": payment_summary(booking),
            "recipient_shortcode": settings.MPESA_SANDBOX["shortcode"],
            "attempts": booking.mpesa_transactions.all(),
            "has_pending": booking.mpesa_transactions.filter(
                status__in=["initiating", "pending", "unknown"]
            ).exists(),
        },
    )


@workspace_required
@require_POST
def check_status(request, booking_id, pk):
    booking = get_object_or_404(bookings_for(request.user), pk=booking_id)
    attempt = get_object_or_404(booking.mpesa_transactions.all(), pk=pk)
    blocked = ratelimit.consume_or_429(
        request, action="mpesa_sandbox", key=str(request.user.pk)
    )
    if blocked:
        return blocked
    try:
        attempt = reconcile_payment(attempt.pk, request.user)
    except ValidationError as error:
        if request.headers.get("Accept") == "application/json":
            return JsonResponse({"message": " ".join(error.messages)}, status=400)
        messages.error(request, " ".join(error.messages))
    else:
        if request.headers.get("Accept") == "application/json":
            summary = payment_summary(booking)
            return JsonResponse(
                {
                    "status": attempt.status,
                    "message": attempt.payment_status_label,
                    "received": str(summary["received"]),
                    "remaining": str(summary["remaining"]),
                    "is_paid": summary["is_paid"],
                }
            )
        messages.info(request, attempt.payment_status_label)
    return redirect("mpesa:booking", booking_id=booking.pk)


@csrf_exempt
@require_POST
def callback(request):
    # Callbacks are hints only. Confirmed status comes from authenticated Daraja
    # queries; never persist raw payloads, claimed receipts or phone numbers here.
    if len(request.body) > 16384:
        return JsonResponse({"error": "Payload too large"}, status=413)
    try:
        payload = json.loads(request.body)
        body = payload["Body"]["stkCallback"]
        checkout, merchant = body["CheckoutRequestID"], body["MerchantRequestID"]
        if (
            not isinstance(checkout, str)
            or not isinstance(merchant, str)
            or max(len(checkout), len(merchant)) > 128
        ):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"error": "Invalid callback"}, status=400)
    MpesaTransaction.objects.filter(
        checkout_request_id=checkout,
        merchant_request_id=merchant,
        callback_received_at__isnull=True,
    ).update(callback_received_at=timezone.now())
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})
