"""Create fictional listings for the hosted school demo."""

import json
import os
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone

from freelance.models import FreelanceProject
from jobs.models import JobPosting, JobSkill


PROJECTS = [
    ("Build an inventory dashboard", "Clean inventory data and build a dashboard for weekly stock reviews.", "Nairobi", 16000, ["SQL", "Microsoft Excel", "Power BI"]),
    ("Improve a community website", "Update the layout and improve keyboard navigation on a community website.", "Remote", 22000, ["HTML", "CSS", "JavaScript", "web accessibility"]),
    ("Coordinate a training workshop", "Prepare a schedule, track costs and coordinate workshop logistics.", "Kisumu", 18000, ["project management", "communication", "budget management"]),
    ("Automate a reporting API", "Build a small API that delivers a weekly summary of sales activity.", "Remote", 26000, ["Python", "Django", "REST", "SQL"]),
    ("Write a customer support guide", "Turn recurring customer questions into a short internal knowledge base.", "Mombasa", 12000, ["customer service", "technical writing", "communication"]),
]


@transaction.atomic
def seed_demo_listings():
    User = get_user_model()
    publisher, created = User.objects.get_or_create(
        email="listings@render-demo.invalid",
        defaults={"username": "render-demo-listings", "role": User.Role.RECRUITER,
                  "first_name": "Demo", "last_name": "Listings", "email_updates": False},
    )
    if not created:
        return
    publisher.set_unusable_password()
    publisher.save(update_fields=["password"])
    source = settings.BASE_DIR / "data/demo/scenarios.json"
    for item in json.loads(source.read_text(encoding="utf-8"))["jobs"]:
        fields = {key: value for key, value in item.items() if key not in {"key", "skills", "applicants"}}
        job = JobPosting.objects.create(recruiter=publisher, **fields)
        JobSkill.objects.bulk_create(
            JobSkill(job=job, name=name, requirement=requirement, priority=priority)
            for name, requirement, priority in item["skills"]
        )
    today = timezone.localdate()
    for title, description, location, budget, skills in PROJECTS:
        FreelanceProject.objects.create(
            recruiter=publisher, title=title, description=description, location=location,
            budget=budget, skills=skills, work_mode="remote" if location == "Remote" else "on_site",
            start_date=today + timedelta(days=7), end_date=today + timedelta(days=60),
        )


@transaction.atomic
def seed_demo_profiles():
    """Import a small representative cohort from the fictional evaluation data."""
    from scripts.import_evaluation_data import account_plan, create_batch

    source = settings.BASE_DIR / "evaluation/dataset-v2.json"
    dataset = json.loads(source.read_text(encoding="utf-8"))
    freelancer_ids = {row["profile_id"] for row in dataset["freelancers"]}
    selected = []
    by_domain = {}
    for profile in sorted(
        dataset["profiles"], key=lambda row: row["id"] not in freelancer_ids
    ):
        domain = profile["domain"]
        count = by_domain.get(domain, 0)
        if count < 3:
            selected.append(profile)
            by_domain[domain] = count + 1
    selected_ids = {row["id"] for row in selected}
    dataset["profiles"] = selected
    dataset["freelancers"] = [
        row for row in dataset["freelancers"] if row["profile_id"] in selected_ids
    ]
    password = os.getenv("DEMO_ACCOUNT_PASSWORD") or None
    if password:
        validate_password(password)
    User = get_user_model()
    usernames = [row["username"] for row in account_plan(dataset)]
    # The original publisher is provisioned first and serializes concurrent starts.
    User.objects.select_for_update().get(username="render-demo-listings")
    if not User.objects.filter(username__in=usernames).exists():
        create_batch(dataset, password, timezone.localdate())
    elif password:
        # Allow first-time login setup on a later deploy without resetting accounts.
        for user in User.objects.filter(
            username__in=usernames, email__endswith="@people.kaziforce.test",
            is_active=True, is_staff=False, is_superuser=False,
        ):
            if not user.has_usable_password():
                user.set_password(password)
                user.save(update_fields=["password"])
