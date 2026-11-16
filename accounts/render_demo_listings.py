"""Create fictional listings for the hosted school demo."""

import json
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
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
