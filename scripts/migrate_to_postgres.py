"""Back up SQLite/files and copy verified records into an empty PostgreSQL database.

Run with the KaziForce servers stopped. This deliberately leaves .env unchanged.
"""

from collections import Counter
from copy import deepcopy
from datetime import datetime
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import sqlite3
import sys
from zipfile import ZipFile, ZIP_DEFLATED

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["DATABASE_ENGINE"] = "sqlite"
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

import django

django.setup()
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db import connections


def configure_target():
    values = dotenv_values(ROOT / ".env.postgres")
    if (
        values.get("POSTGRES_DB") != "kaziforce"
        or values.get("POSTGRES_USER") != "kaziforce_app"
    ):
        raise RuntimeError("Prepare the agreed PostgreSQL database and role first.")
    target = deepcopy(connections["default"].settings_dict)
    target.update(
        ENGINE="django.db.backends.postgresql",
        NAME="kaziforce",
        USER="kaziforce_app",
        PASSWORD=values["POSTGRES_PASSWORD"],
        HOST=values["POSTGRES_HOST"],
        PORT=values["POSTGRES_PORT"],
    )
    settings.DATABASES["postgres_transfer"] = target


def records(alias):
    output = StringIO()
    call_command(
        "dumpdata",
        database=alias,
        natural_foreign=True,
        exclude=["contenttypes", "auth.permission"],
        stdout=output,
        verbosity=0,
    )
    result = json.loads(output.getvalue())
    for record in result:
        model = apps.get_model(record["model"])
        for name, value in record["fields"].items():
            if model._meta.get_field(name).many_to_many:
                record["fields"][name] = sorted(
                    value, key=lambda item: json.dumps(item, sort_keys=True)
                )
    return sorted(result, key=lambda record: (record["model"], str(record.get("pk"))))


def file_hashes():
    hashes = {}
    for label in ("candidates.CandidateDocument", "applications.ApplicationAttachment"):
        for item in apps.get_model(label).objects.using("default").all():
            path = Path(item.file.path)
            hashes[item.file.name] = (
                hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
            )
    return hashes


def main():
    if not (ROOT / "db.sqlite3").exists():
        raise RuntimeError("The source SQLite database is missing.")
    configure_target()
    target = connections["postgres_transfer"]
    with target.cursor() as cursor:
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        tables = {row[0] for row in cursor.fetchall()}
    if tables:
        raise RuntimeError(
            "kaziforce already contains tables. This transfer only accepts an empty target and will not overwrite records."
        )
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = ROOT / ".backups" / f"postgresql-transfer-{stamp}"
    backup.mkdir(parents=True)
    with sqlite3.connect(ROOT / "db.sqlite3") as source, sqlite3.connect(
        backup / "source.sqlite3"
    ) as saved:
        source.backup(saved)
    if (ROOT / ".env").exists():
        (backup / "source.env").write_bytes((ROOT / ".env").read_bytes())
    with ZipFile(
        backup / "private-documents.zip", "w", compression=ZIP_DEFLATED
    ) as archive:
        directory = ROOT / "private_uploads"
        if directory.exists():
            for path in directory.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(directory).as_posix())
    call_command("migrate", database="default", verbosity=1)
    original_files = file_hashes()
    source_records = records("default")
    fixture = backup / "records.json"
    fixture.write_text(json.dumps(source_records, ensure_ascii=False), encoding="utf-8")
    call_command("migrate", database="postgres_transfer", verbosity=1)
    call_command("loaddata", str(fixture), database="postgres_transfer", verbosity=1)
    if records("postgres_transfer") != source_records:
        raise RuntimeError(
            "Verification failed: source and target records differ. The active .env has not changed."
        )
    if file_hashes() != original_files:
        raise RuntimeError(
            "An original file changed during transfer. The active .env has not changed."
        )
    with target.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname=current_user"
        )
        if any(cursor.fetchone()):
            raise RuntimeError(
                "The application login has unexpected administrative privileges."
            )
    report = {
        "database": "kaziforce",
        "user": "kaziforce_app",
        "verified": True,
        "records": dict(Counter(record["model"] for record in source_records)),
        "file_references": len(original_files),
        "missing_source_files": sum(value is None for value in original_files.values()),
    }
    (backup / "verification.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(
        f"Verified {len(source_records)} records and {len(original_files)} file references. Backup: {backup.name}"
    )
    print(
        "The active .env is unchanged. Run PostgreSQL checks, then scripts/activate_postgres.py."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            "Database transfer stopped. The active .env was not switched; inspect the backup and run checks before retrying.",
            file=sys.stderr,
        )
        print(
            str(error) if isinstance(error, RuntimeError) else type(error).__name__,
            file=sys.stderr,
        )
        raise SystemExit(1)
