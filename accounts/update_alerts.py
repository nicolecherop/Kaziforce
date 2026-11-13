"""Durable in-app updates and post-commit email delivery to account inboxes."""

import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from .models import Notification

logger = logging.getLogger(__name__)


def notify(user, *, event_key, workspace, title, body, path, email=True):
    notification, created = Notification.objects.get_or_create(
        event_key=event_key,
        defaults={
            "recipient": user,
            "workspace": workspace,
            "title": title[:200],
            "body": body[:2000],
            "path": path,
            "email_status": "pending" if email else "not_required",
        },
    )
    if created and email:
        transaction.on_commit(lambda: attempt_delivery(notification.pk), robust=True)
    return notification


def attempt_delivery(notification_id):
    try:
        deliver_update(notification_id)
    except Exception:
        # Delivery must not turn an already committed decision into an HTTP
        # failure. No contact details, contents or provider errors are logged.
        logger.warning(
            "Update email remains retryable; notification %s", notification_id
        )


def safe_recipient(user):
    from .auth_support import signup_verification_pending

    domain = user.email.rpartition("@")[2].lower()
    reserved = domain in {
        "example.com",
        "example.net",
        "example.org",
        "localhost",
    } or domain.endswith((".test", ".invalid", ".example", ".localhost"))
    return bool(
        user.is_active
        and user.email
        and not reserved
        and not signup_verification_pending(user)
    )


def deliver_update(notification_id):
    from applications.interview_services import email_is_connected

    with transaction.atomic():
        item = (
            Notification.objects.select_for_update()
            .select_related("recipient")
            .get(pk=notification_id)
        )
        if item.email_status not in {"pending", "failed"}:
            return
        user = item.recipient
        if not user.email_updates or not safe_recipient(user):
            item.email_status = "skipped"
            item.save(update_fields=["email_status"])
            return
        if not email_is_connected():
            return  # Leave pending for an explicitly configured retry.
        item.email_attempts += 1
        try:
            link = settings.SITE_URL.rstrip("/") + "/accounts/notifications/"
            sent = EmailMessage(
                subject=f"KaziForce — {item.title}".replace("\r", " ").replace(
                    "\n", " "
                )[:255],
                body=f"{item.body}\n\nOpen your KaziForce notifications to view this update in your {item.workspace} workspace:\n{link}\n\nManage update emails from Notification settings in your account menu. Security emails and interview invitations are managed separately.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            ).send()
            if sent != 1:
                raise RuntimeError("Message not accepted")
        except Exception:
            item.email_status = "failed"
        else:
            item.email_status = "sent"
            item.emailed_at = timezone.now()
        item.save(update_fields=["email_status", "email_attempts", "emailed_at"])


def workspace_notifications(request):
    if not request.user.is_authenticated:
        return {}
    return {
        "unread_update_count": Notification.objects.filter(
            recipient=request.user, read_at__isnull=True
        ).count()
    }
