"""Transactional booking and payment transitions. No payment collection occurs here."""

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from pages.presentation import public_text
from .contact_rules import (
    contact_sharing_allowed,
    validate_no_contacts,
    PRIVATE_CONTACT_MESSAGE,
    BOOKING_CONTACT_MESSAGE,
)
from .models import (
    FreelancerProfile,
    FreelanceProject,
    Conversation,
    Message,
    Booking,
    BookingEvent,
    Payment,
    Review,
)

RESERVING_STATES = [Booking.Status.ACCEPTED, Booking.Status.COMPLETION_REQUESTED]
ZERO = Decimal("0.00")


def event(booking, actor, description):
    BookingEvent.objects.create(booking=booking, actor=actor, description=description)
    Message.objects.create(
        conversation_id=booking.conversation_id,
        sender=actor,
        body=f"{booking.title}: {description}",
        is_system=True,
    )
    Conversation.objects.filter(pk=booking.conversation_id).update(
        updated_at=timezone.now()
    )


def assert_available(profile, start, end, exclude=None):
    if (
        not profile.user.is_active
        or not profile.accepting_bookings
        or not profile.share_professional_profile
    ):
        raise ValidationError("This freelancer is not accepting new bookings.")
    if start < timezone.localdate() or start < profile.available_from:
        raise ValidationError("Choose dates on or after the freelancer's availability.")
    if end < start:
        raise ValidationError("The end date must be on or after the start date.")
    overlapping = Booking.objects.filter(
        conversation__freelancer=profile,
        status__in=RESERVING_STATES,
        start_date__lte=end,
        end_date__gte=start,
    )
    if exclude:
        overlapping = overlapping.exclude(pk=exclude)
    if overlapping.exists():
        raise ValidationError(
            "The freelancer already has a confirmed booking during these dates. Agree different dates in messages."
        )


@transaction.atomic
def start_conversation(actor, freelancer_id, body, project_id=None):
    profile = (
        FreelancerProfile.objects.select_for_update()
        .select_related("user")
        .get(pk=freelancer_id)
    )
    if (
        not profile.accepting_bookings
        or not profile.share_professional_profile
        or not profile.user.is_active
    ):
        raise ValidationError("This freelancer is not accepting new enquiries.")
    if project_id:
        project = (
            FreelanceProject.objects.select_for_update()
            .select_related("recruiter")
            .get(pk=project_id)
        )
        if (
            project.status != "open"
            or project.end_date < timezone.localdate()
            or not project.recruiter.is_active
        ):
            raise ValidationError("This project is closed to new enquiries.")
        recruiter = project.recruiter
        if actor.pk not in {recruiter.pk, profile.user_id}:
            raise PermissionDenied
    else:
        project = None
        if actor.role != "recruiter":
            raise PermissionDenied
        recruiter = actor
    if recruiter.role != "recruiter" or profile.user.role != "candidate":
        raise PermissionDenied
    conversation, _ = Conversation.objects.get_or_create(
        recruiter=recruiter, freelancer=profile, project=project
    )
    # Lock after get_or_create so concurrent messages/block changes serialize.
    conversation = Conversation.objects.select_for_update().get(pk=conversation.pk)
    send_message_locked(conversation, actor, body)
    return conversation


def send_message_locked(conversation, actor, body):
    if actor.pk not in {conversation.recruiter_id, conversation.freelancer.user_id}:
        raise PermissionDenied
    if conversation.blocked:
        raise ValidationError(
            "Messaging is blocked in this conversation. Existing booking records remain available."
        )
    body = body.strip()
    if not body or len(body) > 3000:
        raise ValidationError("Enter a message of up to 3,000 characters.")
    if not contact_sharing_allowed(
        conversation.recruiter_id, conversation.freelancer_id
    ):
        validate_no_contacts(body, PRIVATE_CONTACT_MESSAGE)
    Message.objects.create(conversation=conversation, sender=actor, body=body)
    conversation.updated_at = timezone.now()
    conversation.save(update_fields=["updated_at"])


@transaction.atomic
def send_message(conversation_id, actor, body):
    conversation = (
        Conversation.objects.select_for_update()
        .select_related("freelancer")
        .get(pk=conversation_id)
    )
    send_message_locked(conversation, actor, body)


@transaction.atomic
def request_booking(conversation_id, actor, fields):
    # Retain old agreements in storage, but never create a new advance-payment requirement.
    if fields.get("deposit_amount", ZERO) != ZERO:
        raise ValidationError("Advance payments are not supported for new bookings.")
    fields = {**fields, "deposit_amount": ZERO}
    info = Conversation.objects.values("freelancer_id").get(pk=conversation_id)
    profile = FreelancerProfile.objects.select_for_update().get(
        pk=info["freelancer_id"]
    )
    conversation = (
        Conversation.objects.select_for_update()
        .select_related("freelancer__user", "recruiter")
        .get(pk=conversation_id)
    )
    if actor.pk != conversation.recruiter_id or actor.role != "recruiter":
        raise PermissionDenied
    for name in ("title", "scope", "location", "cancellation_terms", "recruiter_name"):
        validate_no_contacts(fields.get(name, ""), BOOKING_CONTACT_MESSAGE)
    if conversation.blocked:
        raise ValidationError(
            "New bookings are unavailable while messaging is blocked."
        )
    assert_available(profile, fields["start_date"], fields["end_date"])
    booking = Booking(conversation=conversation, **fields)
    booking.full_clean()
    booking.save()
    event(
        booking, actor, "Booking requested. Dates are reserved only after acceptance."
    )
    return booking


@transaction.atomic
def booking_transition(booking_id, actor, action, data=None):
    booking = (
        Booking.objects.select_for_update()
        .select_related("conversation__freelancer__user", "conversation__recruiter")
        .get(pk=booking_id)
    )
    recruiter = actor.pk == booking.conversation.recruiter_id
    worker = actor.pk == booking.conversation.freelancer.user_id
    if not (recruiter or worker):
        raise PermissionDenied
    data = data or {}
    status = booking.status
    if action == "accept" and worker and status == Booking.Status.REQUESTED:
        if booking.deposit_amount:
            raise ValidationError(
                "Ask the recruiter to withdraw this earlier request and send a new booking without an advance payment."
            )
        if booking.conversation.blocked:
            raise ValidationError(
                "Unblock the conversation before accepting a new booking."
            )
        profile = FreelancerProfile.objects.select_for_update().get(
            pk=booking.conversation.freelancer_id
        )
        assert_available(
            profile, booking.start_date, booking.end_date, exclude=booking.pk
        )
        for name in ("freelancer_name", "freelancer_email", "freelancer_phone"):
            setattr(booking, name, data.get(name, ""))
        if (
            not data.get("agree")
            or not booking.freelancer_email
            or not booking.freelancer_name
        ):
            raise ValidationError(
                "Confirm the agreement and your contact details before accepting."
            )
        booking.status = Booking.Status.ACCEPTED
        booking.accepted_at = timezone.now()
        description = (
            "Freelancer accepted the booking and agreed to share contact details."
        )
    elif action == "decline" and worker and status == Booking.Status.REQUESTED:
        booking.status = Booking.Status.DECLINED
        description = "Freelancer declined the request."
    elif action == "cancel" and recruiter and status == Booking.Status.REQUESTED:
        booking.status = Booking.Status.CANCELLED
        description = "Recruiter withdrew the booking request."
    elif action == "request_cancel" and status in RESERVING_STATES:
        if booking.cancellation_requested_by_id:
            raise ValidationError(
                "A cancellation request is already awaiting a response."
            )
        reason = data.get("reason", "").strip()
        if not reason or len(reason) > 1500:
            raise ValidationError("Provide a reason of up to 1,500 characters.")
        booking.cancellation_requested_by = actor
        booking.cancellation_reason = reason
        description = "Cancellation requested. The booking remains active until both parties agree."
    elif (
        action in {"agree_cancel", "decline_cancel", "withdraw_cancel"}
        and status in RESERVING_STATES
        and booking.cancellation_requested_by_id
    ):
        own_request = booking.cancellation_requested_by_id == actor.pk
        if (action == "withdraw_cancel") != own_request:
            raise PermissionDenied
        if action == "agree_cancel":
            booking.status = Booking.Status.CANCELLED
            description = (
                "Cancellation agreed by both parties. Record any refund separately."
            )
        else:
            description = (
                "Cancellation request withdrawn."
                if own_request
                else "Cancellation request declined. The booking remains active."
            )
        booking.cancellation_requested_by = None
        # Keep the reason in the event history even after another request.
        event(booking, actor, public_text(booking.cancellation_reason)[:250])
        booking.cancellation_reason = ""
    elif (
        action == "request_completion" and worker and status == Booking.Status.ACCEPTED
    ):
        if booking.start_date > timezone.localdate():
            raise ValidationError(
                "Work cannot be marked complete before its start date."
            )
        if booking.cancellation_requested_by_id:
            raise ValidationError("Resolve the cancellation request first.")
        booking.status = Booking.Status.COMPLETION_REQUESTED
        description = (
            "Freelancer marked the work complete; awaiting recruiter confirmation."
        )
    elif (
        action in {"confirm_completion", "request_changes"}
        and recruiter
        and status == Booking.Status.COMPLETION_REQUESTED
    ):
        if booking.cancellation_requested_by_id:
            raise ValidationError("Resolve the cancellation request first.")
        if action == "confirm_completion":
            booking.status = Booking.Status.COMPLETED
            booking.completed_at = timezone.now()
            description = (
                "Recruiter confirmed completion. Payment receipt is tracked separately."
            )
        else:
            booking.status = Booking.Status.ACCEPTED
            description = "Recruiter requested further work. Discuss the remaining deliverables in messages."
    else:
        raise ValidationError(
            "This action is not available for the current booking status."
        )
    booking.full_clean()
    booking.save()
    event(booking, actor, description)
    return booking


def payment_totals(booking):
    received = refunded = reserved_received = reserved_refunded = deposit = ZERO
    for payment in booking.payments.all():
        if payment.status == Payment.Status.WITHDRAWN:
            continue
        refund = payment.kind == Payment.Kind.REFUND
        if refund:
            reserved_refunded += payment.amount
        else:
            reserved_received += payment.amount
        if payment.status == Payment.Status.CONFIRMED:
            if refund:
                refunded += payment.amount
            else:
                received += payment.amount
                if payment.kind == Payment.Kind.DEPOSIT:
                    deposit += payment.amount
    net = received - refunded
    return {
        "received": received,
        "refunded": refunded,
        "net": net,
        "remaining": max(ZERO, booking.total_price - net),
        "deposit_remaining": max(ZERO, booking.deposit_amount - deposit),
        "reserved_received": reserved_received,
        "reserved_refunded": reserved_refunded,
    }


@transaction.atomic
def report_payment(booking_id, actor, fields):
    booking = (
        Booking.objects.select_for_update()
        .select_related("conversation__freelancer")
        .get(pk=booking_id)
    )
    recruiter = actor.pk == booking.conversation.recruiter_id
    worker = actor.pk == booking.conversation.freelancer.user_id
    if not (recruiter or worker):
        raise PermissionDenied
    if fields["kind"] == Payment.Kind.DEPOSIT:
        raise ValidationError("Advance payment reports are not supported.")
    refund = fields["kind"] == Payment.Kind.REFUND
    if refund != worker:
        raise PermissionDenied
    if not booking.accepted_at:
        raise ValidationError(
            "Payments can be reported only after the freelancer accepts the agreement."
        )
    if not refund and booking.status != Booking.Status.COMPLETED:
        raise ValidationError(
            "Record work payments after the recruiter confirms completion."
        )
    totals = payment_totals(booking)
    amount = fields["amount"]
    if refund:
        maximum = totals["received"] - totals["reserved_refunded"]
    else:
        maximum = booking.total_price - totals["reserved_received"] + totals["refunded"]
    if amount > maximum:
        raise ValidationError(
            "This amount exceeds the unreported balance. Resolve existing payment reports first."
        )
    payment = Payment(booking=booking, reported_by=actor, **fields)
    payment.full_clean()
    payment.save()
    event(
        booking,
        actor,
        f"{payment.get_kind_display()} reported: KES {payment.amount}. Awaiting recipient confirmation.",
    )
    return payment


@transaction.atomic
def payment_transition(payment_id, actor, action):
    # Always lock the booking first, matching report_payment's lock order.
    info = Payment.objects.values("booking_id").get(pk=payment_id)
    booking = (
        Booking.objects.select_for_update()
        .select_related("conversation__freelancer")
        .get(pk=info["booking_id"])
    )
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    participants = {
        booking.conversation.recruiter_id,
        booking.conversation.freelancer.user_id,
    }
    if actor.pk not in participants:
        raise PermissionDenied
    reporter = payment.reported_by_id == actor.pk
    if action == "withdraw" and reporter and payment.status in {"reported", "disputed"}:
        payment.status = Payment.Status.WITHDRAWN
        description = "Payment report withdrawn by sender."
    elif (
        action in {"confirm", "dispute"}
        and not reporter
        and payment.status in {"reported", "disputed"}
    ):
        if action == "confirm":
            payment.status = Payment.Status.CONFIRMED
            payment.confirmed_by = actor
            payment.confirmed_at = timezone.now()
            description = "Payment receipt confirmed by recipient."
        else:
            payment.status = Payment.Status.DISPUTED
            description = "Recipient queried a payment report. Discuss it in messages."
    else:
        raise ValidationError("This payment action is not available.")
    payment.save()
    event(booking, actor, f"{description} KES {payment.amount}.")


@transaction.atomic
def leave_review(booking_id, actor, fields):
    booking = (
        Booking.objects.select_for_update()
        .select_related("conversation")
        .get(pk=booking_id)
    )
    if actor.pk != booking.conversation.recruiter_id:
        raise PermissionDenied
    validate_no_contacts(fields.get("comment", ""))
    if booking.status != Booking.Status.COMPLETED:
        raise ValidationError(
            "Reviews are available after both parties confirm completion."
        )
    if Review.objects.filter(booking=booking).exists():
        raise ValidationError("You have already reviewed this booking.")
    review = Review(booking=booking, **fields)
    review.full_clean()
    review.save()
    event(booking, actor, "Recruiter submitted a review for the completed booking.")
    return review
