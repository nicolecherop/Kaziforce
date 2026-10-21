"""Offline evaluation configuration, isolated from development PostgreSQL/files."""

import os
from pathlib import Path

from .settings import *  # noqa: F403

EVALUATION_ROOT = Path(os.environ["KAZIFORCE_EVALUATION_ROOT"]).resolve()
if not (EVALUATION_ROOT / ".isolated-evaluation").is_file():
    raise RuntimeError("Start evaluation with scripts/evaluate_project.py.")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": EVALUATION_ROOT / "evaluation.sqlite3",
    }
}
PRIVATE_DOCUMENT_ROOT = EVALUATION_ROOT / "private_uploads"
MEDIA_ROOT = EVALUATION_ROOT / "media"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
ALLOWED_HOSTS = ["testserver"]
DEBUG = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
