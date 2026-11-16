"""Self-service removal of identity; shared agreements remain auditable."""

import secrets
import uuid
from datetime import timedelta
from smtplib import SMTPException

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .auth_support import signin_binding
from .models import AccountDeletionCode


class DeleteAccountForm(forms.Form):
    code = forms.RegexField(
        r"^[0-9]{6}$",
        label="Email confirmation code",
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "maxlength": 6,
            }
        ),
        error_messages={"invalid": "Enter the six-digit code from your email."},
    )
    confirm = forms.BooleanField(
        label="I understand that this deletes both workspaces and cannot be undone."
    )


def deletion_blockers(user):
    from freelance.models import Booking, Payment
    from freelance.services import payment_totals
    from mpesa.models import MpesaTransaction

    blockers = []
    User = get_user_model()
    if (
        user.is_superuser
        and not User.objects.filter(is_active=True, is_superuser=True)
        .exclude(pk=user.pk)
        .exists()
    ):
        blockers.append(
            "Another active administrator must be appointed before you can delete the last administrator account."
        )
    bookings = Booking.objects.filter(
        Q(conversation__recruiter=user) | Q(conversation__freelancer__user=user)
    )
    if bookings.filter(
        status__in=["requested", "accepted", "completion_requested"]
    ).exists():
        blockers.append(
            "Complete or cancel your outstanding freelance bookings first, including requests awaiting a response."
        )
    if Payment.objects.filter(
        booking__in=bookings, status__in=["reported", "disputed"]
    ).exists():
        blockers.append(
            "Resolve your unconfirmed or disputed payments before deleting your account."
        )
    if MpesaTransaction.objects.filter(
        booking__in=bookings, status__in=["initiating", "pending", "unknown"]
    ).exists():
        blockers.append(
            "Wait for your pending M-Pesa payment to be resolved before deleting your account."
        )
    for booking in bookings.filter(status="completed").prefetch_related("payments"):
        collected = (
            booking.mpesa_transactions.filter(status="success").aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )
        if payment_totals(booking)["remaining"] > collected:
            blockers.append(
                "Settle the remaining payment on your completed freelance work first."
            )
            break
    return blockers


@transaction.atomic
def remove_account(user):
    """Caller must verify a one-use code. Never cascade through shared records."""
    from allauth.account.models import EmailAddress
    from allauth.socialaccount.models import SocialAccount
    from applications.models import Application, Interview, InterviewEmail
    from candidates.models import CandidateDocument, CandidateProfile
    from freelance.models import (
        Conversation,
        FreelancerProfile,
        FreelanceService,
        FreelanceProject,
    )
    from jobs.models import JobPosting, SavedJob
    from matching.models import MatchRun, MatchResult
    from .models import Notification

    User = get_user_model()
    # Serialize administrator removals so two admins cannot remove the last one.
    list(User.objects.select_for_update().filter(is_superuser=True).order_by("pk"))
    user = User.objects.select_for_update().get(pk=user.pk)
    if not user.is_active or user.deleted_at:
        raise ValidationError("This account has already been deleted.")
    blockers = deletion_blockers(user)
    if blockers:
        raise ValidationError(blockers)
    now = timezone.now()
    CandidateDocument.objects.filter(user=user).delete()
    CandidateProfile.objects.filter(user=user).delete()
    SavedJob.objects.filter(candidate=user).delete()
    MatchResult.objects.filter(candidate=user).delete()
    MatchRun.objects.filter(owner=user).delete()
    Application.objects.filter(candidate=user, status="draft").delete()
    # Unsent invitations must not be retried after either participant leaves.
    InterviewEmail.objects.filter(
        Q(interview__application__candidate=user)
        | Q(interview__application__job__recruiter=user)
    ).exclude(status="sent").delete()
    # Submitted copies belong to the recruitment record and are disclosed as retained.
    Interview.objects.filter(
        Q(application__candidate=user) | Q(application__job__recruiter=user),
        status="scheduled",
        starts_at__gte=now,
    ).update(
        status="cancelled",
        cancellation_reason="A participant has deleted their account.",
        updated_at=now,
    )
    JobPosting.objects.filter(recruiter=user).update(status="closed", updated_at=now)
    FreelanceProject.objects.filter(recruiter=user).update(
        status="closed", updated_at=now
    )
    FreelanceService.objects.filter(profile__user=user).delete()
    FreelancerProfile.objects.filter(user=user).update(
        title="Deleted account",
        about="",
        location="",
        accepting_bookings=False,
        share_professional_profile=False,
        updated_at=now,
    )
    Conversation.objects.filter(Q(recruiter=user) | Q(freelancer__user=user)).update(
        recruiter_blocked=True, freelancer_blocked=True
    )
    Notification.objects.filter(recipient=user).delete()
    SocialAccount.objects.filter(user=user).delete()
    EmailAddress.objects.filter(user=user).delete()
    user.groups.clear()
    user.user_permissions.clear()
    identifier = uuid.uuid4().hex
    user.email = f"deleted-{identifier}@accounts.invalid"
    user.username = f"deleted-{identifier}"
    user.first_name = "Deleted"
    user.last_name = "account"
    user.is_active = user.is_staff = user.is_superuser = False
    user.email_updates = user.email_two_step_enabled = False
    user.candidate_workspace_enabled = user.recruiter_workspace_enabled = False
    user.deleted_at = now
    user.set_unusable_password()  # Invalidates existing sessions and password reset links.
    user.save()
    AccountDeletionCode.objects.filter(user=user).delete()


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def delete_account(request):
    form = DeleteAccountForm(
        request.POST
        if request.method == "POST" and request.POST.get("action") == "delete"
        else None
    )
    blockers = deletion_blockers(request.user)
    if request.method == "POST" and not blockers:
        action = request.POST.get("action")
        if action == "send_code":
            try:
                with transaction.atomic():
                    user = (
                        get_user_model()
                        .objects.select_for_update()
                        .get(pk=request.user.pk)
                    )
                    if not user.is_active or user.deleted_at:
                        logout(request)
                        return redirect("accounts:sign_in")
                    challenge = AccountDeletionCode.objects.filter(user=user).first()
                    if challenge and challenge.sent_at > timezone.now() - timedelta(
                        seconds=60
                    ):
                        messages.error(
                            request,
                            "Please wait a minute before requesting another code.",
                        )
                    else:
                        code = f"{secrets.randbelow(1000000):06d}"
                        AccountDeletionCode.objects.update_or_create(
                            user=user,
                            defaults={
                                "code_hash": make_password(code),
                                "binding": signin_binding(user),
                                "expires_at": timezone.now() + timedelta(minutes=10),
                                "sent_at": timezone.now(),
                                "attempts": 0,
                            },
                        )
                        sent = send_mail(
                            "Confirm your KaziForce account deletion",
                            f"Your account deletion code is {code}.\n\nIt expires in 10 minutes. Enter it only if you want to permanently delete your KaziForce account and both workspaces. If you did not request this, do not share or enter the code.",
                            settings.DEFAULT_FROM_EMAIL,
                            [user.email],
                            fail_silently=False,
                        )
                        if not sent:
                            raise OSError("Email was not sent")
                        messages.success(
                            request,
                            "A confirmation code has been sent to your sign-in email. It expires in 10 minutes.",
                        )
            except (SMTPException, OSError):
                messages.error(
                    request,
                    "We could not send your code. Your account is unchanged. Please try again later.",
                )
            return redirect("accounts:delete_account")
        if action == "delete" and form.is_valid():
            removed = False
            with transaction.atomic():
                User = get_user_model()
                list(
                    User.objects.select_for_update()
                    .filter(is_superuser=True)
                    .order_by("pk")
                )
                current_user = User.objects.select_for_update().get(pk=request.user.pk)
                challenge = (
                    AccountDeletionCode.objects.select_for_update()
                    .filter(user=request.user)
                    .first()
                )
                if (
                    not current_user.is_active
                    or not challenge
                    or challenge.expires_at <= timezone.now()
                    or challenge.attempts >= 5
                    or challenge.binding != signin_binding(current_user)
                ):
                    form.add_error(
                        "code", "Request a new confirmation code and try again."
                    )
                elif not check_password(form.cleaned_data["code"], challenge.code_hash):
                    challenge.attempts += 1
                    challenge.save(update_fields=["attempts"])
                    form.add_error(
                        "code",
                        "That code is incorrect. After five attempts you must request a new code.",
                    )
                else:
                    try:
                        remove_account(request.user)
                        removed = True
                    except ValidationError as exc:
                        form.add_error(None, exc)
            if removed:
                logout(request)
                return render(request, "accounts/account_deleted.html")
    return render(
        request,
        "accounts/delete_account.html",
        {
            "form": form,
            "blockers": blockers,
            "code_sent": AccountDeletionCode.objects.filter(
                user=request.user, expires_at__gt=timezone.now(), attempts__lt=5
            ).exists(),
        },
    )
