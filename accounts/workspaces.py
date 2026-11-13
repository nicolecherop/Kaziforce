"""Session-selected product workspace, independent of identity and staff access."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction

SESSION_KEY = "kaziforce_workspace"
WORKSPACES = {"candidate", "recruiter"}


def select_workspace(request, workspace, enable=False):
    if workspace not in WORKSPACES or not request.user.is_active:
        raise PermissionDenied("Choose a candidate or recruiter workspace.")
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
        if not user.has_workspace(workspace):
            if not enable:
                raise PermissionDenied("Enable this workspace before opening it.")
            field = f"{workspace}_workspace_enabled"
            setattr(user, field, True)
            user.save(update_fields=[field])
            setattr(request.user, field, True)
    request.session[SESSION_KEY] = workspace
    request.user._active_workspace = workspace


class WorkspaceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            selected = request.session.get(SESSION_KEY)
            if request.user.has_workspace(selected):
                request.user._active_workspace = selected
            elif selected:
                request.session.pop(SESSION_KEY, None)
        return self.get_response(request)
