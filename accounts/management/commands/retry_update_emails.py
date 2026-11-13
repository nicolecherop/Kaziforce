"""Explicit bounded retry; never resend notices marked sent or skipped."""

from django.core.management.base import BaseCommand, CommandError
from accounts.models import Notification
from accounts.update_alerts import attempt_delivery


class Command(BaseCommand):
    help = "Retry pending/failed application and booking emails (sends real email when SMTP is configured)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        if not 1 <= options["limit"] <= 500:
            raise CommandError("Choose a limit from 1 to 500.")
        ids = list(
            Notification.objects.filter(email_status__in=["pending", "failed"])
            .order_by("created_at")
            .values_list("pk", flat=True)[: options["limit"]]
        )
        for pk in ids:
            attempt_delivery(pk)
        self.stdout.write(f"Processed {len(ids)} update email records.")
