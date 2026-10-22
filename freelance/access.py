"""Shared access checks for the optional freelance workspace."""

from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from .models import Conversation, Booking


def workspace_required(view):
    @login_required
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if request.user.role not in {"candidate", "recruiter"}:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return guarded


def conversations_for(user):
    return Conversation.objects.filter(
        Q(recruiter=user) | Q(freelancer__user=user)
    ).select_related("recruiter", "freelancer__user", "project")


def bookings_for(user):
    return Booking.objects.filter(
        Q(conversation__recruiter=user) | Q(conversation__freelancer__user=user)
    ).select_related(
        "conversation__recruiter",
        "conversation__freelancer__user",
        "conversation__project",
    )
