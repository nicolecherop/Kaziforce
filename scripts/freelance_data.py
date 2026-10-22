"""Add one recorded freelance sample batch to the existing sample accounts.

Run from the project root with the project virtual environment. No accounts,
credentials, employment records, external messages or real payments are changed.
"""

import argparse
from datetime import timedelta
from decimal import Decimal
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / ".backups" / "freelance-data-v1.json"
ACCOUNTS = ROOT / ".backups" / "demo-data-v1.json"
KEYS = ("amina", "brian", "chloe", "david", "esther", "felix")


def verified_accounts(batch, *, lock=False):
    from django.conf import settings
    from django.contrib.auth import get_user_model

    if batch.get("version") != 1 or batch.get("database") != str(
        settings.DATABASES["default"]["NAME"]
    ):
        raise ValueError("The account record belongs to another database or version.")
    expected = {row["username"]: row for row in batch["accounts"]}
    names = [f"kaziforce-demo-{key}-v1" for key in ("recruiter", *KEYS)]
    if set(expected) != set(names):
        raise ValueError("The original seven sample accounts are required.")
    query = get_user_model().objects.filter(username__in=names).order_by("pk")
    if lock:
        query = query.select_for_update()
    users = list(query)
    if len(users) != len(names):
        raise ValueError("A recorded sample account is missing.")
    result = {}
    for user in users:
        record = expected[user.username]
        key = user.username.removeprefix("kaziforce-demo-").removesuffix("-v1")
        role = "recruiter" if key == "recruiter" else "candidate"
        if (
            user.pk != record["id"]
            or user.email != record["email"]
            or user.email != f"{key}@demo.kaziforce.test"
            or user.role != role
            or record["role"] != role
            or not user.is_active
            or user.is_staff
            or user.is_superuser
        ):
            raise ValueError("A recorded account identity or access level changed.")
        result[key] = user
    return result


def check_batch(record, accounts):
    """Verify ownership, without resetting statuses or edits made while trying the site."""
    from django.apps import apps
    from django.conf import settings
    from freelance.models import FreelancerProfile, FreelanceProject, Conversation

    users = verified_accounts(accounts)
    if record.get("version") != 1 or record.get("database") != str(
        settings.DATABASES["default"]["NAME"]
    ):
        raise ValueError("The freelance batch belongs to another database or version.")
    if record.get("accounts") != {key: user.pk for key, user in users.items()}:
        raise ValueError("The batch account identities changed.")
    for label, ids in record["records"].items():
        model = apps.get_model(label)
        if model.objects.filter(pk__in=ids).count() != len(ids):
            raise ValueError(
                f"Recorded rows are missing: {label}. No data was recreated."
            )
    ids = record["records"]
    profiles = FreelancerProfile.objects.filter(
        pk__in=ids["freelance.FreelancerProfile"]
    )
    if set(profiles.values_list("user_id", flat=True)) != {users[k].pk for k in KEYS}:
        raise ValueError("Freelancer ownership changed.")
    for model, label in (
        (FreelanceProject, "freelance.FreelanceProject"),
        (Conversation, "freelance.Conversation"),
    ):
        if (
            model.objects.filter(pk__in=ids[label])
            .exclude(recruiter=users["recruiter"])
            .exists()
        ):
            raise ValueError("Project or conversation ownership changed.")
    return record


def create_batch(accounts):
    """Create the batch atomically through the same services used by the pages."""
    from django.conf import settings
    from django.db import transaction
    from django.utils import timezone
    from pages.presentation import public_text
    from freelance.models import (
        FreelancerProfile,
        FreelanceService,
        FreelanceProject,
        Conversation,
        Message,
        Booking,
        BookingEvent,
        Payment,
        Review,
    )
    from freelance.services import (
        start_conversation,
        send_message,
        request_booking,
        booking_transition,
        report_payment,
        payment_transition,
        leave_review,
    )

    with transaction.atomic():
        users = verified_accounts(accounts, lock=True)
        if FreelancerProfile.objects.filter(user__in=users.values()).exists():
            raise ValueError(
                "A sample account already has a freelance profile. Nothing was overwritten."
            )
        today = timezone.localdate()
        recruiter = users["recruiter"]
        profiles = {}
        offerings = [
            (
                "amina",
                "Python backend developer",
                "Build and maintain Python services, database queries and reliable web APIs.",
                "Backend API development",
                6000,
            ),
            (
                "brian",
                "Data analyst and reporting consultant",
                "Turn spreadsheet and SQL data into clear reports and practical business insights.",
                "Sales reporting and data analysis",
                4500,
            ),
            (
                "chloe",
                "Frontend web developer",
                "Create accessible web pages using HTML, CSS and JavaScript, with responsive layouts.",
                "Responsive website improvements",
                4000,
            ),
            (
                "david",
                "Project coordination consultant",
                "Coordinate tasks, budgets and project updates so teams deliver their agreed milestones.",
                "Project planning and coordination",
                5000,
            ),
            (
                "esther",
                "Customer support specialist",
                "Help customers resolve questions and keep clear records of service requests.",
                "Short-term customer support",
                2500,
            ),
            (
                "felix",
                "Junior web development assistant",
                "Support website content changes, simple page styling and database tasks.",
                "Website maintenance support",
                2000,
            ),
        ]
        for key, title, about, service, rate in offerings:
            profile = FreelancerProfile(
                user=users[key],
                title=title,
                about=about,
                location="Nairobi",
                work_mode="flexible",
                rate=rate,
                rate_unit="day",
                available_from=today,
                accepting_bookings=key != "felix",
                share_professional_profile=True,
            )
            profile.full_clean()
            profile.save()
            item = FreelanceService(profile=profile, title=service, description=about)
            item.full_clean()
            item.save()
            profiles[key] = profile

        projects = {}
        specifications = [
            (
                "amina",
                "Inventory API improvements",
                ["Python", "Django", "SQL"],
                18000,
                2,
                4,
            ),
            (
                "brian",
                "Sales reporting dashboard",
                ["SQL", "Microsoft Excel", "data analysis"],
                13500,
                0,
                2,
            ),
            (
                "chloe",
                "Accessible website refresh",
                ["HTML", "CSS", "JavaScript"],
                12000,
                0,
                2,
            ),
            (
                "david",
                "Project handover planning",
                ["project management", "communication"],
                5000,
                0,
                0,
            ),
            (
                "esther",
                "Customer support cover",
                ["customer service", "communication"],
                12500,
                5,
                9,
            ),
        ]
        for key, title, skills, price, first, last in specifications:
            project = FreelanceProject(
                recruiter=recruiter,
                title=title,
                description=f"{profiles[key].services.get().description} Agree the deliverables, provide progress updates and prepare a clear handover.",
                skills=skills,
                location="Nairobi",
                work_mode="flexible",
                budget=price,
                start_date=today + timedelta(days=first),
                end_date=today + timedelta(days=last),
            )
            project.full_clean()
            project.save()
            projects[key] = project
            conversation = start_conversation(
                recruiter,
                profiles[key].pk,
                "Your experience looks relevant to this assignment. Are you available to discuss the scope?",
                project.pk,
            )
            send_message(
                conversation.pk,
                users[key],
                "Yes, I can help. Please confirm the deliverables and proposed dates here.",
            )
            if key == "esther":
                continue
            booking = request_booking(
                conversation.pk,
                recruiter,
                {
                    "title": title,
                    "scope": project.description,
                    "location": "Nairobi",
                    "start_date": project.start_date,
                    "end_date": project.end_date,
                    "total_price": Decimal(price),
                    "cancellation_terms": "Discuss any date changes here before work begins. Cancellation requires both parties to agree.",
                    "recruiter_name": public_text(recruiter.get_full_name()),
                    "recruiter_email": "sarah@kaziforce.example",
                    "recruiter_phone": "",
                },
            )
            if key == "amina":
                continue
            booking_transition(
                booking.pk,
                users[key],
                "accept",
                {
                    "freelancer_name": public_text(users[key].get_full_name()),
                    "freelancer_email": f"{key}@kaziforce.example",
                    "agree": True,
                },
            )
            if key == "brian":
                continue
            booking_transition(booking.pk, users[key], "request_completion")
            if key == "chloe":
                continue
            booking_transition(booking.pk, recruiter, "confirm_completion")
            payment = report_payment(
                booking.pk,
                recruiter,
                {
                    "kind": "balance",
                    "method": "cash",
                    "amount": Decimal(price),
                    "reference": "",
                },
            )
            payment_transition(payment.pk, users[key], "confirm")
            leave_review(
                booking.pk,
                recruiter,
                {
                    "rating": 5,
                    "comment": "Clear updates, well-organised handover notes and all agreed tasks completed.",
                },
            )
            project.status = "closed"
            project.save(update_fields=["status", "updated_at"])

        profile_ids = [p.pk for p in profiles.values()]
        conversations = Conversation.objects.filter(freelancer_id__in=profile_ids)
        bookings = Booking.objects.filter(conversation__in=conversations)
        selections = {
            FreelancerProfile: FreelancerProfile.objects.filter(pk__in=profile_ids),
            FreelanceService: FreelanceService.objects.filter(
                profile_id__in=profile_ids
            ),
            FreelanceProject: FreelanceProject.objects.filter(
                pk__in=[p.pk for p in projects.values()]
            ),
            Conversation: conversations,
            Message: Message.objects.filter(conversation__in=conversations),
            Booking: bookings,
            BookingEvent: BookingEvent.objects.filter(booking__in=bookings),
            Payment: Payment.objects.filter(booking__in=bookings),
            Review: Review.objects.filter(booking__in=bookings),
        }
        return {
            "version": 1,
            "database": str(settings.DATABASES["default"]["NAME"]),
            "created_at": timezone.now().isoformat(),
            "accounts": {key: user.pk for key, user in users.items()},
            "records": {
                model._meta.label: [str(pk) for pk in rows.values_list("pk", flat=True)]
                for model, rows in selections.items()
            },
        }


def seed(account_path=ACCOUNTS, manifest_path=MANIFEST, *, check_only=False):
    from django.db import transaction

    accounts = json.loads(account_path.read_text(encoding="utf-8"))
    verified_accounts(accounts)
    if manifest_path.exists():
        record = check_batch(
            json.loads(manifest_path.read_text(encoding="utf-8")), accounts
        )
        print(
            "Existing freelance batch verified. Your edits and account details were retained."
        )
        return record
    if check_only:
        raise ValueError("No recorded freelance batch exists yet.")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents two runs from adding the same batch. If creation
    # fails, the database transaction rolls back and this run removes its own file.
    with manifest_path.open("x", encoding="utf-8") as handle:
        try:
            with transaction.atomic():
                record = create_batch(accounts)
                json.dump(record, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            handle.close()
            manifest_path.unlink()
            raise
    print(
        "Added 6 freelance profiles, 5 projects, 5 conversations and 4 bookings. No money was transferred."
    )
    return record


def main():
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the recorded batch without adding or resetting records.",
    )
    args = parser.parse_args()
    try:
        seed(check_only=args.check)
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
