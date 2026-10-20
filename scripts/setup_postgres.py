"""Create local KaziForce databases using a privately entered admin password.

This never changes an existing role password or overwrites a populated database.
It writes only a draft .env.postgres; the active .env is switched after verification.
"""

import argparse
import getpass
from pathlib import Path
import secrets
import sys

import psycopg
from psycopg import sql
from dotenv import dotenv_values


def prepare(root, administrator_password, host="127.0.0.1", port="5432"):
    draft = root / ".env.postgres"
    existing = dotenv_values(draft) if draft.exists() else {}
    application_password = existing.get("POSTGRES_PASSWORD") or secrets.token_urlsafe(
        40
    )
    with psycopg.connect(
        dbname="postgres",
        user="postgres",
        password=administrator_password,
        host=host,
        port=port,
        connect_timeout=5,
        autocommit=True,
    ) as admin:
        role_exists = admin.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", ("kaziforce_app",)
        ).fetchone()
        if role_exists and not existing.get("POSTGRES_PASSWORD"):
            raise RuntimeError(
                "kaziforce_app already exists. Supply its existing credentials through .env.postgres; its password has not been changed."
            )
        for database in ("kaziforce", "test_kaziforce"):
            row = admin.execute(
                "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s",
                (database,),
            ).fetchone()
            if row:
                with psycopg.connect(
                    dbname=database,
                    user="postgres",
                    password=administrator_password,
                    host=host,
                    port=port,
                    connect_timeout=5,
                ) as check:
                    tables = check.execute(
                        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'"
                    ).fetchone()[0]
                if tables and row[0] != "kaziforce_app":
                    raise RuntimeError(
                        f"{database} already contains tables under another owner. No changes were made to it."
                    )
        if not role_exists:
            admin.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
                ).format(
                    sql.Identifier("kaziforce_app"), sql.Literal(application_password)
                )
            )
        for database in ("kaziforce", "test_kaziforce"):
            if not admin.execute(
                "SELECT 1 FROM pg_database WHERE datname=%s", (database,)
            ).fetchone():
                admin.execute(
                    sql.SQL(
                        "CREATE DATABASE {} OWNER {} ENCODING 'UTF8' TEMPLATE template0"
                    ).format(sql.Identifier(database), sql.Identifier("kaziforce_app"))
                )
            else:
                admin.execute(
                    sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
                        sql.Identifier(database), sql.Identifier("kaziforce_app")
                    )
                )
    # No administrator credentials are saved.
    draft.write_text(
        "\n".join(
            [
                "DATABASE_ENGINE=postgresql",
                "POSTGRES_DB=kaziforce",
                "POSTGRES_USER=kaziforce_app",
                f"POSTGRES_PASSWORD={application_password}",
                f"POSTGRES_HOST={host}",
                f"POSTGRES_PORT={port}",
                "POSTGRES_TEST_DB=test_kaziforce",
                "",
            ]
        ),
        encoding="utf-8",
    )
    with psycopg.connect(
        dbname="kaziforce",
        user="kaziforce_app",
        password=application_password,
        host=host,
        port=port,
        connect_timeout=5,
    ) as application:
        assert (
            application.execute("SELECT current_user").fetchone()[0] == "kaziforce_app"
        )
    print(
        "PostgreSQL connection verified. Role: kaziforce_app. Databases: kaziforce, test_kaziforce."
    )
    print(
        "Connection settings saved privately in .env.postgres. The active .env is unchanged."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent.parent
    )
    parser.add_argument("--password-stdin", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    password = (
        sys.stdin.readline().rstrip("\r\n")
        if args.password_stdin
        else getpass.getpass("PostgreSQL administrator password: ")
    )
    try:
        prepare(args.root.resolve(), password)
    except psycopg.OperationalError:
        print(
            "Could not authenticate or connect to PostgreSQL. No credentials were printed.",
            file=sys.stderr,
        )
        return 1
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
