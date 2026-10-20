"""Run Django checks/tests using draft PostgreSQL credentials, without switching .env."""

import os
from pathlib import Path
import sys
from dotenv import load_dotenv

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
if not (root / ".env.postgres").exists():
    raise SystemExit(
        "Run scripts/setup_postgres.py first to prepare the local connection."
    )
load_dotenv(root / ".env")
load_dotenv(root / ".env.postgres", override=True)
os.environ.setdefault("DJANGO_SECRET_KEY", "local-database-verification-only")
os.environ.setdefault("DJANGO_DEBUG", "true")
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

from django.core.management import execute_from_command_line

execute_from_command_line([str(root / "manage.py"), *sys.argv[1:]])
