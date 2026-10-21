"""Create or remove one recorded batch of fictional, nonprivileged demo data."""

import argparse
from datetime import date
import json
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from applications.models import Application, ApplicationAttachment
from applications.services import save_application, snapshot_from_profile
from candidates.models import (
    CandidateDocument,
    CandidateProfile,
    CandidateSkill,
    Certification,
    Education,
    WorkExperience,
)
from jobs.models import JobPosting, JobSkill
from matching.corpus import active_corpus
from matching.services import generate_matches

MANIFEST = ROOT / ".backups" / "demo-data-v1.json"
DOMAIN = "demo.kaziforce.test"


def saved_batch():
    batch = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if batch.get("version") != 1 or batch.get("database") != str(
        settings.DATABASES["default"]["NAME"]
    ):
        raise ValueError("The demo manifest belongs to another version or database.")
    accounts = list(
        get_user_model().objects.filter(pk__in=[row["id"] for row in batch["accounts"]])
    )
    identities = {(row.pk, row.username, row.email) for row in accounts}
    expected = {(row["id"], row["username"], row["email"]) for row in batch["accounts"]}
    if identities != expected or any(
        not row.email.endswith("@" + DOMAIN) or row.is_staff or row.is_superuser
        for row in accounts
    ):
        raise ValueError("Demo account identities changed. No records were altered.")
    jobs = list(JobPosting.objects.filter(pk__in=batch["jobs"]))
    if len(jobs) != len(batch["jobs"]) or any(
        item.recruiter_id != batch["recruiter_id"] for item in jobs
    ):
        raise ValueError("Demo job ownership changed. No records were altered.")
    return batch, accounts, jobs


def seed():
    if MANIFEST.exists():
        batch, accounts, jobs = saved_batch()
        print(
            f"Existing demo batch retained: {len(accounts) - 1} candidates and {len(jobs)} jobs. Profiles and passwords were not overwritten."
        )
        print(f"Demo sign-in details: {MANIFEST}")
        return
    active_corpus()  # Fail before adding anything if matching is not prepared.
    data = json.loads((ROOT / "data/demo/scenarios.json").read_text(encoding="utf-8"))
    keys = ["recruiter", *[row["key"] for row in data["candidates"]]]
    emails = [f"{key}@{DOMAIN}" for key in keys]
    usernames = [f"kaziforce-demo-{key}-v1" for key in keys]
    User = get_user_model()
    if (
        User.objects.filter(email__in=emails).exists()
        or User.objects.filter(username__in=usernames).exists()
    ):
        raise ValueError(
            "A demo identity already exists without this manifest. No existing accounts were reused or changed."
        )
    password = "Demo-" + secrets.token_urlsafe(12) + "!"
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    temporary = MANIFEST.with_suffix(".tmp")
    try:
        with transaction.atomic():
            recruiter = User.objects.create_user(
                username=usernames[0],
                email=emails[0],
                password=password,
                first_name="Recruiter",
                last_name="Demo",
                role="recruiter",
            )
            people = {}
            for item in data["candidates"]:
                key = item["key"]
                user = User.objects.create_user(
                    username=f"kaziforce-demo-{key}-v1",
                    email=f"{key}@{DOMAIN}",
                    password=password,
                    first_name=item["first_name"],
                    last_name="Demo",
                    role="candidate",
                )
                people[key] = user
                profile = CandidateProfile.objects.create(
                    user=user,
                    headline=item["headline"],
                    location="Nairobi, Kenya",
                    summary=item["summary"],
                )
                for name in item["skills"]:
                    CandidateSkill.objects.create(profile=profile, name=name)
                Education.objects.create(
                    profile=profile,
                    qualification=item["qualification"],
                    institution="Demo Learning Institute (fictional)",
                    field_of_study=item["field"],
                    start_date=date(2016, 9, 1),
                    end_date=date(2020, 12, 1),
                )
                Certification.objects.create(
                    profile=profile,
                    name=item["certificate"],
                    issuer="Demo Training Centre (fictional)",
                    issue_date=date(2025, 1, 10),
                )
                WorkExperience.objects.create(
                    profile=profile,
                    job_title=item["experience_title"],
                    company="Demo Previous Employer (fictional)",
                    start_date=date.fromisoformat(item["experience_start"]),
                    end_date=(
                        date.fromisoformat(item["experience_end"])
                        if item.get("experience_end")
                        else None
                    ),
                    currently_working=not bool(item.get("experience_end")),
                    description=item["experience_description"],
                )
            jobs = []
            for item in data["jobs"]:
                fields = {
                    key: value
                    for key, value in item.items()
                    if key not in ("key", "skills", "applicants")
                }
                fields["title"] = "[Demo] " + fields["title"]
                job = JobPosting.objects.create(
                    recruiter=recruiter,
                    requirements="Fictional demonstration vacancy for testing KaziForce. No real recruitment is taking place.",
                    **fields,
                )
                jobs.append(job)
                for name, requirement, priority in item["skills"]:
                    JobSkill.objects.create(
                        job=job, name=name, requirement=requirement, priority=priority
                    )
                for key in item["applicants"]:
                    user = people[key]
                    save_application(
                        user,
                        job.pk,
                        snapshot_from_profile(user),
                        {
                            "cover_letter": "Fictional demo application to demonstrate profile review and matching.",
                            "documents": [],
                        },
                        submit=True,
                    )
                generate_matches(recruiter, job)
            for user in people.values():
                generate_matches(user)
            batch = {
                "version": 1,
                "database": str(settings.DATABASES["default"]["NAME"]),
                "password": password,
                "recruiter_id": recruiter.pk,
                "accounts": [
                    {
                        "id": user.pk,
                        "username": user.username,
                        "email": user.email,
                        "role": user.role,
                    }
                    for user in [recruiter, *people.values()]
                ],
                "jobs": [str(job.pk) for job in jobs],
            }
            temporary.write_text(json.dumps(batch, indent=2), encoding="utf-8")
        temporary.replace(MANIFEST)
    except Exception:
        if temporary.exists():
            # Preserve recovery identities if the database committed but publishing failed.
            if User.objects.filter(username=usernames[0]).exists():
                print(f"Recovery manifest retained at {temporary}")
            else:
                temporary.unlink()
        raise
    print(
        f"Created {len(people)} candidates, {len(jobs)} demo jobs and {Application.objects.filter(job__in=jobs).count()} submitted applications. Matching reviews are ready."
    )
    print(f"Demo sign-in details: {MANIFEST}")


def remove():
    batch, accounts, jobs = saved_batch()
    ids = [user.pk for user in accounts]
    # Refuse to erase real interactions or uploaded files added while exploring.
    if (
        Application.objects.filter(job__in=jobs).exclude(candidate_id__in=ids).exists()
        or Application.objects.filter(candidate_id__in=ids)
        .exclude(job__in=jobs)
        .exists()
    ):
        raise ValueError(
            "These demo records have applications involving other accounts/jobs. Review them manually before removing the batch."
        )
    if (
        CandidateDocument.objects.filter(user_id__in=ids).exists()
        or ApplicationAttachment.objects.filter(application__job__in=jobs).exists()
    ):
        raise ValueError(
            "The demo accounts have uploaded files. Review those files manually before removing the batch."
        )
    if (
        JobPosting.objects.filter(recruiter_id=batch["recruiter_id"])
        .exclude(pk__in=batch["jobs"])
        .exists()
    ):
        raise ValueError(
            "The demo recruiter has additional jobs. Review them manually before removing the batch."
        )
    with transaction.atomic():
        Application.objects.filter(job__in=jobs).delete()
        JobPosting.objects.filter(pk__in=batch["jobs"]).delete()
        get_user_model().objects.filter(pk__in=ids).delete()
    MANIFEST.unlink()
    print(
        "Removed the recorded demo accounts, jobs, applications and their matching history."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove only the recorded demo batch; refuse interactions with other accounts/jobs or uploaded files.",
    )
    options = parser.parse_args()
    try:
        remove() if options.remove else seed()
    except (ValueError, OSError) as error:
        raise SystemExit(str(error)) from error
