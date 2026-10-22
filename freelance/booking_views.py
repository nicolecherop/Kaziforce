"""Agreements, receipt acknowledgements and completed-booking reviews."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from jobs.access import recruiter_required
from pages.presentation import public_text, contact_email
from .access import workspace_required, bookings_for, conversations_for
from .forms import (
    BookingForm,
    AcceptBookingForm,
    CancellationForm,
    PaymentForm,
    ReviewForm,
)
from .models import Booking
from .pricing import commission_breakdown
from mpesa.services import payment_summary
from .services import (
    request_booking,
    booking_transition,
    report_payment,
    payment_transition,
    payment_totals,
    leave_review,
)


@workspace_required
def bookings(request):
    qs = bookings_for(request.user)
    status = request.GET.get("status", "")
    if status in Booking.Status.values:
        qs = qs.filter(status=status)
    return render(
        request,
        "freelance/bookings.html",
        {
            "page": Paginator(qs, 20).get_page(request.GET.get("page")),
            "status": status,
            "statuses": Booking.Status.choices,
        },
    )


@recruiter_required
@require_http_methods(["GET", "POST"])
def booking_create(request, conversation_id):
    thread = get_object_or_404(
        conversations_for(request.user), pk=conversation_id, recruiter=request.user
    )
    initial = {
        "recruiter_name": public_text(request.user.get_full_name()),
        "recruiter_email": contact_email(request.user.email),
    }
    if thread.project:
        project = thread.project
        initial.update(
            title=project.title,
            scope=project.description,
            location=project.location,
            start_date=project.start_date,
            end_date=project.end_date,
            total_price=project.budget,
        )
    form = BookingForm(
        request.POST if request.method == "POST" else None, initial=initial
    )
    if request.method == "POST" and form.is_valid():
        fields = {name: form.cleaned_data[name] for name in BookingForm._meta.fields}
        try:
            booking = request_booking(thread.pk, request.user, fields)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(
                request,
                "Booking request sent. The freelancer must accept before dates are reserved.",
            )
            return redirect("freelance:booking", pk=booking.pk)
    return render(
        request, "freelance/booking_form.html", {"form": form, "thread": thread}
    )


def booking_context(request, booking):
    is_recruiter = booking.conversation.recruiter_id == request.user.pk
    profile = getattr(request.user, "candidate_profile", None)
    actions = []
    completion_available_from = None
    if booking.status == "requested":
        actions = (
            [("cancel", "Withdraw request")]
            if is_recruiter
            else [("decline", "Decline request")]
        )
    if (
        booking.status == "accepted"
        and not is_recruiter
        and not booking.cancellation_requested_by_id
    ):
        if booking.start_date <= timezone.localdate():
            actions = [("request_completion", "Mark work complete")]
        else:
            completion_available_from = booking.start_date
    if is_recruiter and booking.status in {"accepted", "completion_requested"}:
        actions = [("confirm_completion", "Confirm completion")]
        if (
            booking.status == "completion_requested"
            and not booking.cancellation_requested_by_id
        ):
            actions.append(("request_changes", "Request further work"))
    if booking.cancellation_requested_by_id:
        if booking.cancellation_requested_by_id == request.user.pk:
            actions.append(("withdraw_cancel", "Withdraw cancellation request"))
        else:
            actions.extend(
                [
                    ("agree_cancel", "Agree to cancellation"),
                    ("decline_cancel", "Keep booking active"),
                ]
            )
    return {
        "booking": booking,
        "commission": commission_breakdown(booking.total_price),
        "payment_summary": payment_summary(booking),
        "is_recruiter": is_recruiter,
        "actions": actions,
        "completion_available_from": completion_available_from,
        "completion_blocked": booking.start_date > timezone.localdate()
        or bool(booking.cancellation_requested_by_id),
        "recruiter_completion_date": (
            booking.start_date
            if is_recruiter and booking.start_date > timezone.localdate()
            else None
        ),
        "can_accept": booking.status == "requested"
        and not is_recruiter
        and not booking.deposit_amount,
        "can_cancel": booking.status in {"accepted", "completion_requested"}
        and not booking.cancellation_requested_by_id,
        "can_review": booking.status == "completed"
        and is_recruiter
        and not hasattr(booking, "review"),
        "can_pay": (
            booking.status == "completed"
            if is_recruiter
            else bool(booking.accepted_at) and payment_totals(booking)["net"] > 0
        ),
        "accept_form": AcceptBookingForm(
            initial={
                "freelancer_name": public_text(request.user.get_full_name()),
                "freelancer_email": contact_email(
                    getattr(profile, "contact_email", "") or request.user.email
                ),
                "freelancer_phone": getattr(profile, "phone_number", ""),
            }
        ),
        "cancel_form": CancellationForm(),
        "payment_form": PaymentForm(is_recruiter=is_recruiter),
        "review_form": ReviewForm(),
        "totals": payment_totals(booking),
        "payments": booking.payments.select_related("reported_by"),
        "events": booking.events.select_related("actor"),
    }


@workspace_required
@require_http_methods(["GET", "POST"])
def booking_detail(request, pk):
    booking = get_object_or_404(bookings_for(request.user), pk=pk)
    context = booking_context(request, booking)
    if request.method == "POST":
        action = request.POST.get("action", "")
        form_name = {
            "accept": "accept_form",
            "request_cancel": "cancel_form",
            "report_payment": "payment_form",
            "review": "review_form",
        }.get(action)
        form = None
        if form_name:
            kwargs = (
                {"is_recruiter": context["is_recruiter"]}
                if form_name == "payment_form"
                else {}
            )
            form = type(context[form_name])(request.POST, **kwargs)
            context[form_name] = form
        if form is None or form.is_valid():
            try:
                if action == "report_payment":
                    report_payment(booking.pk, request.user, form.cleaned_data)
                elif action == "review":
                    leave_review(booking.pk, request.user, form.cleaned_data)
                else:
                    booking_transition(
                        booking.pk,
                        request.user,
                        action,
                        form.cleaned_data if form else {},
                    )
            except ValidationError as error:
                if form is not None:
                    form.add_error(None, error)
                else:
                    context["action_errors"] = error.messages
            else:
                if action == "confirm_completion":
                    messages.success(
                        request, "Work completion confirmed. Continue to payment."
                    )
                    return redirect("mpesa:booking", booking_id=booking.pk)
                messages.success(request, "Booking updated.")
                return redirect("freelance:booking", pk=booking.pk)
        return render(request, "freelance/booking_detail.html", context, status=400)
    return render(request, "freelance/booking_detail.html", context)


@workspace_required
@require_POST
def payment_action(request, booking_id, pk):
    booking = get_object_or_404(bookings_for(request.user), pk=booking_id)
    payment = get_object_or_404(booking.payments.all(), pk=pk)
    try:
        payment_transition(payment.pk, request.user, request.POST.get("action"))
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(request, "Payment record updated.")
    return redirect("freelance:booking", pk=booking.pk)
