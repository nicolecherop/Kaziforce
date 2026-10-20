from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def recruiter_required(view):
    @login_required
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if request.user.role != "recruiter":
            raise PermissionDenied("This page is available to recruiter accounts.")
        return view(request, *args, **kwargs)

    return guarded
