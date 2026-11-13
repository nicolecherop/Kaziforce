"""Provision the frozen evaluation scenarios in the local development site.

Adds only a recorded cohort. Never reuses existing identities or overwrites
profiles on rerun. Offline evaluation data and reports remain unchanged.
"""

import csv
from datetime import date, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parent.parent
DOMAIN = "people.kaziforce.test"
FIRST_NAMES = [
    "Amina",
    "Brian",
    "Faith",
    "David",
    "Esther",
    "Felix",
    "Grace",
    "Hassan",
    "Irene",
    "James",
    "Mercy",
    "Kevin",
    "Lilian",
    "Martin",
    "Naomi",
    "Peter",
    "Ruth",
    "Samuel",
    "Sharon",
    "Victor",
]
LAST_NAMES = [
    "Kiptoo",
    "Otieno",
    "Wanjiru",
    "Mutua",
    "Hassan",
    "Kamau",
    "Cheruiyot",
    "Omondi",
    "Njeri",
    "Mwangi",
]
COMPANIES = [
    "Mawingu Product Studio",
    "Kijani Interface Works",
    "Imara Analytics",
    "Tawi Technology Services",
    "Nuru Delivery Partners",
    "Pamoja Accounting Services",
    "Soko Creative Media",
    "Rangi Design Studio",
    "Jenga People Partners",
    "Dira Supply Solutions",
]


def record_id(key):
    return uuid5(NAMESPACE_URL, "kaziforce-local-evaluation-v2/" + key)


def account_plan(dataset):
    accounts = []
    for index, domain in enumerate(
        dict.fromkeys(p["domain"] for p in dataset["profiles"])
    ):
        accounts.append(
            {
                "source_id": domain,
                "username": "kz-v2-recruiter-" + domain,
                "email": f"recruiter.{domain}@{DOMAIN}",
                "first_name": FIRST_NAMES[index],
                "last_name": LAST_NAMES[(index + 4) % 10],
                "role": "recruiter",
                "company": COMPANIES[index],
            }
        )
    for index, profile in enumerate(dataset["profiles"]):
        first = FIRST_NAMES[index % 20]
        last = LAST_NAMES[(index // 20 + index % 20) % 10]
        accounts.append(
            {
                "source_id": profile["id"],
                "username": "kz-v2-candidate-" + profile["id"],
                "email": f"{first.lower()}.{last.lower()}.{index + 1:03d}@{DOMAIN}",
                "first_name": first,
                "last_name": last,
                "role": "candidate",
            }
        )
    return accounts


def verify_existing(batch):
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from jobs.models import JobPosting
    from freelance.models import FreelancerProfile, FreelanceProject

    if batch["version"] != "local-evaluation-v2" or batch["database"] != str(
        settings.DATABASES["default"]["NAME"]
    ):
        raise ValueError("The import record belongs to another database or version.")
    expected = {(row["id"], row["username"], row["email"]) for row in batch["accounts"]}
    users = list(get_user_model().objects.filter(pk__in=[row[0] for row in expected]))
    if {(u.pk, u.username, u.email) for u in users} != expected:
        raise ValueError(
            "Imported identities changed or are missing; no existing records were altered."
        )
    if any(
        u.is_staff or u.is_superuser or not u.email.endswith("@" + DOMAIN)
        for u in users
    ):
        raise ValueError(
            "Imported account permissions changed; review the cohort manually."
        )
    recruiter_ids = {u.pk for u in users if u.role == "recruiter"}
    if (
        JobPosting.objects.filter(
            pk__in=batch["jobs"], recruiter_id__in=recruiter_ids
        ).count()
        != 40
        or FreelanceProject.objects.filter(
            pk__in=batch["projects"], recruiter_id__in=recruiter_ids
        ).count()
        != 20
        or FreelancerProfile.objects.filter(
            pk__in=batch["freelancers"], user_id__in=[u.pk for u in users]
        ).count()
        != 60
    ):
        raise ValueError(
            "Imported listings are missing or ownership changed; no records were overwritten."
        )
    return batch


def create_batch(dataset, password, import_date, progress=lambda message: None):
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from allauth.account.models import EmailAddress
    from candidates.models import (
        CandidateProfile,
        CandidateSkill,
        Education,
        Certification,
        WorkExperience,
    )
    from jobs.models import JobPosting, JobSkill
    from freelance.models import FreelancerProfile, FreelanceProject, FreelanceService
    from applications.services import save_application, snapshot_from_profile

    plan = account_plan(dataset)
    User = get_user_model()
    if (
        User.objects.filter(username__in=[a["username"] for a in plan]).exists()
        or User.objects.filter(email__in=[a["email"] for a in plan]).exists()
        or EmailAddress.objects.filter(email__in=[a["email"] for a in plan]).exists()
        or JobPosting.objects.filter(
            pk__in=[record_id(j["id"]) for j in dataset["jobs"]]
        ).exists()
        or FreelanceProject.objects.filter(
            pk__in=[record_id(p["id"]) for p in dataset["projects"]]
        ).exists()
    ):
        raise ValueError(
            "A reserved import identity already exists without this manifest. No records were reused."
        )
    with transaction.atomic():
        users, accounts = {}, []
        for index, row in enumerate(plan):
            fields = {k: v for k, v in row.items() if k not in ("source_id", "company")}
            user = User.objects.create_user(**fields, password=password)
            users[row["source_id"]] = user
            accounts.append({**row, "id": user.pk})
            if (index + 1) % 50 == 0:
                progress(f"Prepared {index + 1}/210 nonprivileged accounts.")
        recruiters = {a["source_id"]: a for a in plan if a["role"] == "recruiter"}
        for index, row in enumerate(dataset["profiles"]):
            user = users[row["id"]]
            snapshot = row["snapshot"]
            profile = CandidateProfile.objects.create(
                user=user,
                **snapshot["profile"],
                location=row["location"],
                contact_email=user.email,
            )
            CandidateSkill.objects.bulk_create(
                [
                    CandidateSkill(profile=profile, name=s["name"])
                    for s in snapshot["skills"]
                ]
            )
            for item in snapshot["education"]:
                Education.objects.create(
                    profile=profile, **item, institution="Eastland Learning Centre"
                )
            for item in snapshot["certifications"]:
                Certification.objects.create(
                    profile=profile, **item, issuer="Professional Development Centre"
                )
            for item in snapshot["experience"]:
                WorkExperience.objects.create(
                    profile=profile, **item, company=COMPANIES[(index + 3) % 10]
                )
        jobs, job_keys = {}, []
        for index, row in enumerate(dataset["jobs"]):
            values = {
                k: v
                for k, v in row["requirements"].items()
                if k not in ("skills", "education_level_label", "company")
            }
            job = JobPosting.objects.create(
                id=record_id(row["id"]),
                recruiter=users[row["domain"]],
                company=recruiters[row["domain"]]["company"],
                location=("Nairobi", "Mombasa", "Kisumu", "Remote")[index % 4],
                **values,
            )
            JobSkill.objects.bulk_create(
                [JobSkill(job=job, **skill) for skill in row["requirements"]["skills"]]
            )
            jobs[row["id"]] = job
            job_keys.append(str(job.pk))
        shift = import_date - date.fromisoformat(dataset["as_of"])
        freelancers = []
        profiles = {p["id"]: p for p in dataset["profiles"]}
        for row in dataset["freelancers"]:
            source = profiles[row["profile_id"]]
            worker = FreelancerProfile.objects.create(
                id=record_id(row["id"]),
                user=users[row["profile_id"]],
                title=row["title"],
                about=source["snapshot"]["profile"]["summary"],
                location=row["location"],
                work_mode=row["work_mode"],
                rate=row["rate"],
                rate_unit=row["rate_unit"],
                available_from=date.fromisoformat(row["available_from"]) + shift,
                accepting_bookings=row["accepting_bookings"],
                share_professional_profile=row["share_professional_profile"],
            )
            FreelanceService.objects.create(
                profile=worker,
                title=row["title"],
                description=source["snapshot"]["profile"]["summary"],
            )
            freelancers.append(str(worker.pk))
        projects = []
        for row in dataset["projects"]:
            values = {
                k: v
                for k, v in row.items()
                if k not in ("id", "domain", "start_date", "end_date")
            }
            project = FreelanceProject.objects.create(
                id=record_id(row["id"]),
                recruiter=users[row["domain"]],
                start_date=date.fromisoformat(row["start_date"]) + shift,
                end_date=date.fromisoformat(row["end_date"]) + shift,
                **values,
            )
            projects.append(str(project.pk))
        applications = []
        for index, row in enumerate(dataset["profiles"]):
            user = users[row["id"]]
            snapshot = snapshot_from_profile(user)
            for offset in (0, 1):
                job = jobs[f'{row["domain"]}-job-{(index % 4 + offset) % 4 + 1}']
                application = save_application(
                    user,
                    job.pk,
                    snapshot,
                    {
                        "cover_letter": "I would welcome the opportunity to discuss how my experience and skills could contribute to your team.",
                        "documents": [],
                    },
                    submit=True,
                )
                applications.append(str(application.pk))
        progress(
            "Prepared profiles, 40 jobs, 60 freelancers, 20 projects and 400 applications."
        )
        return {
            "version": "local-evaluation-v2",
            "database": str(settings.DATABASES["default"]["NAME"]),
            "import_date": import_date.isoformat(),
            "source_version": dataset["version"],
            "password": password,
            "accounts": accounts,
            "jobs": job_keys,
            "freelancers": freelancers,
            "projects": projects,
            "applications": applications,
            "adaptations": "Realistic display names; dates shifted relative to import. No documents, ratings, booking history, financial records or email sends. Preprovisioned local accounts use the existing non-public-signup login flow; use real public registration to test inbox verification.",
        }


def backup_database(directory):
    from django.conf import settings

    config = settings.DATABASES["default"]
    if config["ENGINE"] != "django.db.backends.postgresql":
        raise ValueError(
            "This command is intended for the local PostgreSQL development database."
        )
    executable = Path(r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe")
    if not executable.is_file():
        raise ValueError("PostgreSQL backup tool not found; no data imported.")
    directory.mkdir(parents=True, exist_ok=False)
    path = directory / "before-import.dump"
    environment = {**os.environ, "PGPASSWORD": str(config.get("PASSWORD", ""))}
    subprocess.run(
        [
            str(executable),
            "--host",
            str(config.get("HOST") or "localhost"),
            "--port",
            str(config.get("PORT") or "5432"),
            "--username",
            str(config["USER"]),
            "--format=custom",
            "--no-password",
            "--file",
            str(path),
            str(config["NAME"]),
        ],
        env=environment,
        check=True,
        capture_output=True,
    )
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError("Database backup is empty; import stopped.")
    return path


def main():
    from datetime import datetime

    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from accounts.auth_support import signup_verification_pending
    from matching.corpus import active_corpus
    from matching.services import generate_matches

    manifest = ROOT / ".backups/expanded-accounts-v2.json"
    if manifest.exists():
        batch = verify_existing(json.loads(manifest.read_text(encoding="utf-8")))
        print(
            f"Existing cohort retained: {len(batch['accounts'])} accounts, 40 jobs and 20 projects. Edits and passwords preserved."
        )
        print(
            "Sign-in details: " + str(ROOT / ".backups/expanded-accounts-v2-signin.md")
        )
        return
    if not settings.DEBUG:
        raise ValueError(
            "Enable the local development configuration; this import is not for a public deployment."
        )
    active_corpus()
    dataset_path = ROOT / "evaluation/dataset-v2.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    from evaluation.expanded_dataset import build_dataset

    if dataset != build_dataset():
        raise ValueError("Dataset differs from the frozen generator; import stopped.")
    backup = backup_database(
        ROOT
        / ".backups"
        / ("expanded-import-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    )
    print("Database backup verified: " + str(backup), flush=True)
    User = get_user_model()
    existing = list(User.objects.order_by("pk").values())
    password = "KaziForce-" + secrets.token_urlsafe(16) + "!"
    temporary = manifest.with_suffix(".pending.json")
    with transaction.atomic():
        batch = create_batch(
            dataset,
            password,
            timezone.localdate(),
            progress=lambda message: print(message, flush=True),
        )
        batch["source_sha256"] = sha256(dataset_path.read_bytes()).hexdigest()
        batch["database_backup"] = str(backup)
        if (
            list(
                User.objects.filter(pk__in=[r["id"] for r in existing])
                .order_by("pk")
                .values()
            )
            != existing
        ):
            raise RuntimeError("Existing accounts changed; rolling back the import.")
        temporary.write_text(json.dumps(batch, indent=2) + "\n", encoding="utf-8")
    temporary.replace(manifest)
    details = [
        "# Local KaziForce sign-in details",
        "",
        "These fictional accounts are for the local website. They have no administrator permissions. Their reserved email addresses do not receive mail.",
        "",
        "Shared account password:",
        "",
        password,
        "",
        "| Name | Role | Email | Scenario |",
        "| --- | --- | --- | --- |",
    ]
    details.extend(
        f'| {a["first_name"]} {a["last_name"]} | {a["role"]} | {a["email"]} | {a["source_id"]} |'
        for a in batch["accounts"]
    )
    credentials = ROOT / ".backups/expanded-accounts-v2-signin.md"
    credentials.write_text("\n".join(details) + "\n", encoding="utf-8")
    # Prepare recruiter pages and a small selection of candidate dashboards.
    from jobs.models import JobPosting

    print(
        "Preparing applicant rankings and initial candidate recommendations...",
        flush=True,
    )
    for job in JobPosting.objects.filter(pk__in=batch["jobs"]).select_related(
        "recruiter"
    ):
        generate_matches(job.recruiter, job)
    sample_candidates = [a for a in batch["accounts"] if a["role"] == "candidate"][::20]
    for row in sample_candidates:
        user = User.objects.get(pk=row["id"])
        generate_matches(user)
        assert user.check_password(password) and not signup_verification_pending(user)
    verify_existing(batch)
    print(
        "Added 200 candidates, 10 recruiters, 60 freelance profiles, 40 jobs, 20 projects and 400 applications."
    )
    print(
        "Existing accounts preserved. No emails, bookings, ratings or payments created."
    )
    print("Private account list and password: " + str(credentials))


if __name__ == "__main__":
    main()
