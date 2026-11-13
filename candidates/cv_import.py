"""Private, expiring CV review drafts and bounded document extraction."""

import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path

from django.conf import settings
from django.core.cache import cache

from .cv_parser import parse_cv
from .cv_text import CVReadError
from .forms import ProfileForm
from .selectors import profile_for

DRAFT_SECONDS = 30 * 60
RELATIONS = {
    "skills": "skills",
    "education": "education",
    "certifications": "certifications",
    "experience": "experience",
    "portfolio": "portfolio_links",
}


def profile_version(user):
    profile = profile_for(user)
    if not profile:
        return "no-profile"
    value = {
        "profile": {
            field: getattr(profile, field) for field in ProfileForm._meta.fields
        }
    }
    for prefix, relation in RELATIONS.items():
        value[prefix] = list(getattr(profile, relation).order_by("pk").values())
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


def extract_text(document):
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "candidates.cv_text",
                document.file.path,
                Path(document.original_name).suffix.lower(),
            ],
            cwd=settings.BASE_DIR,
            capture_output=True,
            timeout=15,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if len(completed.stdout) > 1_000_000:
            raise CVReadError(
                "This CV contains too much text to import. Choose a shorter copy."
            )
        result = json.loads(completed.stdout)
    except subprocess.TimeoutExpired as error:
        raise CVReadError(
            "Reading this CV took too long. Try a simpler Word or PDF copy, or fill in your profile manually."
        ) from error
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        raise CVReadError(
            "We could not read this CV. Try a fresh PDF or Word copy. Your saved profile has not changed."
        ) from error
    if result.get("error"):
        raise CVReadError(result["error"])
    return result


def draft_key(user, token):
    return f"cv-review:{user.pk}:{token}"


def new_draft(user, document):
    # Capture the original state before extracting; stale previews must not
    # silently replace edits made in another tab while the worker is running.
    version = profile_version(user)
    result = extract_text(document)
    suggestions = parse_cv(result["text"])
    token = uuid.uuid4().hex
    draft = {
        "document_id": str(document.pk),
        "filename": document.original_name,
        "source": result["text"],
        "suggestions": suggestions,
        "warnings": result["warnings"],
        "version": version,
    }
    cache.set(draft_key(user, token), draft, DRAFT_SECONDS)
    return token


def entry_identity(prefix, entry):
    fields = {
        "skills": ("name",),
        "education": ("qualification", "institution"),
        "experience": ("job_title", "company", "start_date"),
        "certifications": ("name", "issuer"),
        "portfolio": ("url",),
    }[prefix]
    return tuple(
        " ".join(str(entry.get(field) or "").split()).casefold() for field in fields
    )


def existing_identities(profile, prefix):
    if not profile or not profile.pk:
        return set()
    return {
        entry_identity(prefix, value)
        for value in getattr(profile, RELATIONS[prefix]).values()
    }
