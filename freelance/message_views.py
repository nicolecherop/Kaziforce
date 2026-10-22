"""Participant-only inbox; no public contact directory or message attachments."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .access import workspace_required, conversations_for
from .forms import MessageForm, ReportForm
from .models import Conversation, ConversationReport
from .selectors import inbox_for
from .services import send_message
from .contact_rules import contact_sharing_allowed


@workspace_required
def inbox(request):
    page = Paginator(inbox_for(request.user), 20).get_page(request.GET.get("page"))
    return render(request, "freelance/inbox.html", {"page": page})


@workspace_required
@require_http_methods(["GET", "POST"])
def conversation(request, pk):
    thread = get_object_or_404(conversations_for(request.user), pk=pk)
    is_recruiter = thread.recruiter_id == request.user.pk
    form = MessageForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            send_message(thread.pk, request.user, form.cleaned_data["body"])
        except ValidationError as error:
            form.add_error(None, error)
        else:
            return redirect("freelance:conversation", pk=thread.pk)
    read_at = timezone.now()
    page = Paginator(
        thread.messages.select_related("sender").order_by("-created_at", "-pk"), 40
    ).get_page(request.GET.get("page"))
    # Opening the latest page marks only already-delivered messages as read.
    if page.number == 1:
        field = "recruiter_read_at" if is_recruiter else "freelancer_read_at"
        Conversation.objects.filter(pk=pk).update(**{field: read_at})
    return render(
        request,
        "freelance/conversation.html",
        {
            "thread": thread,
            "contacts_unlocked": contact_sharing_allowed(
                thread.recruiter_id, thread.freelancer_id
            ),
            "is_recruiter": is_recruiter,
            "form": form,
            "page": page,
            "thread_messages": list(reversed(page.object_list)),
            "bookings": thread.bookings.all(),
            "own_block": (
                thread.recruiter_blocked if is_recruiter else thread.freelancer_blocked
            ),
        },
    )


@workspace_required
@require_http_methods(["GET", "POST"])
def conversation_controls(request, pk):
    thread = get_object_or_404(conversations_for(request.user), pk=pk)
    form = ReportForm(
        request.POST
        if request.method == "POST" and request.POST.get("action") == "report"
        else None
    )
    if request.method == "POST":
        action = request.POST.get("action")
        if action in {"block", "unblock"}:
            field = (
                "recruiter_blocked"
                if thread.recruiter_id == request.user.pk
                else "freelancer_blocked"
            )
            with transaction.atomic():
                Conversation.objects.select_for_update().get(pk=thread.pk)
                Conversation.objects.filter(pk=thread.pk).update(
                    **{field: action == "block"}
                )
            messages.success(
                request,
                (
                    "Conversation blocked."
                    if action == "block"
                    else "Your conversation block has been removed."
                ),
            )
            return redirect("freelance:conversation", pk=thread.pk)
        if action == "report" and form.is_valid():
            ConversationReport.objects.create(
                conversation=thread,
                reporter=request.user,
                reason=form.cleaned_data["reason"],
            )
            messages.success(
                request, "Your report has been sent to the administration team."
            )
            return redirect("freelance:conversation", pk=thread.pk)
    return render(
        request,
        "freelance/conversation_controls.html",
        {"thread": thread, "form": form},
    )
