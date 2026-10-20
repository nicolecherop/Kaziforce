"""Switch only database settings after source/target verification and local tests."""

import json
from pathlib import Path
import sys
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from migrate_to_postgres import configure_target, records


def main():
    reports = sorted(
        (ROOT / ".backups").glob("postgresql-transfer-*/verification.json")
    )
    if not reports or not json.loads(reports[-1].read_text(encoding="utf-8")).get(
        "verified"
    ):
        raise RuntimeError(
            "Complete and verify the data transfer before activating PostgreSQL."
        )
    configure_target()
    if records("default") != records("postgres_transfer"):
        raise RuntimeError(
            "SQLite changed after transfer. Activation stopped to preserve those changes."
        )
    values = dotenv_values(ROOT / ".env.postgres")
    environment = ROOT / ".env"
    candidate = ROOT / ".env.activate"
    candidate.write_bytes(environment.read_bytes())
    try:
        for key, value in values.items():
            if key == "DATABASE_ENGINE" or key.startswith("POSTGRES_"):
                set_key(candidate, key, value, quote_mode="always")
        candidate.replace(environment)
    finally:
        candidate.unlink(missing_ok=True)
    print("Activated PostgreSQL: database kaziforce, application login kaziforce_app.")
    print("SQLite and the pre-transfer backups remain available for recovery.")


if __name__ == "__main__":
    main()
