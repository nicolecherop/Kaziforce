"""Role checks shared by candidate profile and CV endpoints."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def candidate_required(view):
    @login_required
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if request.user.role != "candidate":
            raise PermissionDenied("This page is available to candidate accounts.")
        return view(request, *args, **kwargs)

    return guarded
