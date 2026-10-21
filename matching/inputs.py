"""Whitelist professional evidence; identities and attachments never enter scoring."""

from applications.services import snapshot_from_profile
from jobs.models import JobPosting
from .scoring import MatchingError
from .normalization import NORMALIZATION_VERSION
from .skills import standardize_skills
from .vectorization import digest

PROFILE_FIELDS = {
    "skills": ("name",),
    "education": ("qualification", "field_of_study"),
    "certifications": ("name",),
    "experience": (
        "job_title",
        "description",
        "start_date",
        "end_date",
        "currently_working",
    ),
}


def professional_profile(snapshot):
    profile = {
        "profile": {
            key: snapshot.get("profile", {}).get(key, "")
            for key in ("headline", "summary")
        }
    }
    for section, fields in PROFILE_FIELDS.items():
        profile[section] = [
            {key: row.get(key) for key in fields} for row in snapshot.get(section, [])
        ]
    return profile


def capture_job(job):
    return {
        **{
            key: getattr(job, key)
            for key in (
                "title",
                "company",
                "description",
                "requirements",
                "education_level",
                "education_field",
                "education_priority",
                "experience_details",
                "experience_priority",
            )
        },
        "education_level_label": job.get_education_level_display(),
        "minimum_experience_years": (
            str(job.minimum_experience_years)
            if job.minimum_experience_years is not None
            else None
        ),
        "skills": [
            {
                "name": skill.name,
                "requirement": skill.requirement,
                "priority": skill.priority,
            }
            for skill in job.skills.all()
        ],
    }


def collect_inputs(user, job=None):
    """Return a complete bounded set; never quietly rank a truncated subset."""
    if job is None:
        profile = professional_profile(snapshot_from_profile(user))
        submitted_jobs = user.applications.exclude(status="draft").values("job_id")
        jobs = list(
            JobPosting.objects.filter(status="open")
            .exclude(pk__in=submitted_jobs)
            .prefetch_related("skills")
            .order_by("pk")[:501]
        )
        if len(jobs) > 500:
            raise MatchingError(
                "There are too many open jobs for one matching request. Please contact the KaziForce administrator."
            )
        pairs = [
            {
                "job_id": str(item.pk),
                "candidate_id": user.pk,
                "application_id": None,
                "profile": profile,
                "job": capture_job(item),
            }
            for item in jobs
        ]
        source = {"profile": profile, "pairs": pairs}
    else:
        applications = list(
            job.applications.exclude(status="draft").order_by("pk")[:1001]
        )
        if len(applications) > 1000:
            raise MatchingError(
                "There are too many applications for one matching request. Please contact the KaziForce administrator."
            )
        captured = capture_job(job)
        pairs = [
            {
                "job_id": str(job.pk),
                "candidate_id": app.candidate_id,
                "application_id": str(app.pk),
                "profile": professional_profile(app.profile_snapshot),
                "job": captured,
            }
            for app in applications
        ]
        source = {"job": captured, "pairs": pairs}
    return pairs, digest(source), source


def standardize_pairs(pairs, catalogue):
    names = [
        entry["name"]
        for pair in pairs
        for side in ("profile", "job")
        for entry in pair[side]["skills"]
    ]
    mappings = []
    for offset in range(0, len(names), 500):
        mappings.extend(
            standardize_skills(names[offset : offset + 500], catalogue)["skills"]
        )
    offset = 0
    for pair in pairs:
        for side in ("profile", "job"):
            # Profiles and jobs are copied because recommendation pairs can
            # share the same source profile object.
            pair[side] = dict(pair[side])
            length = len(pair[side]["skills"])
            pair[side]["skill_standardization"] = {
                "catalogue": catalogue.provenance(),
                "normalization_version": NORMALIZATION_VERSION,
                "skills": mappings[offset : offset + length],
            }
            offset += length
