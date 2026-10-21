"""Reproduce synthetic matching/workflow evidence without touching live data."""

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent


def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/evaluation",
        help="Directory for report.md, results.json and rankings.csv.",
    )
    args = parser.parse_args()
    # The canonical fixture is hashed before Django or the scoring engine runs.
    path = ROOT / "evaluation/dataset-v1.json"
    dataset = json.loads(path.read_text(encoding="utf-8"))
    dataset_checksum = file_hash(path)
    sys.path.insert(0, str(ROOT))
    with TemporaryDirectory(
        prefix="kaziforce-evaluation-"
    ) as temporary, ExitStack() as cleanup:
        temporary = Path(temporary)
        (temporary / ".isolated-evaluation").touch()
        os.environ.update(
            DJANGO_SETTINGS_MODULE="config.evaluation_settings",
            DJANGO_SECRET_KEY="isolated-evaluation-only-not-a-deployment-secret",
            KAZIFORCE_EVALUATION_ROOT=str(temporary),
        )
        import django

        django.setup()
        from django.conf import settings
        from django.core.management import call_command
        from django.db import connections
        from django.test.utils import setup_test_environment, teardown_test_environment
        from matching.corpus import build_corpus, reference_for
        from matching.models import SkillCatalogue
        from matching.scoring import configuration
        from matching.vectorization import digest
        from evaluation.matching import (
            behavioral_checks,
            evaluate_rankings,
            validate_dataset,
        )
        from evaluation.report import write_report
        from evaluation.workflows import run_workflows

        cleanup.callback(connections.close_all)
        # Refuse any settings drift that could redirect this command to live data.
        if (
            settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3"
            or Path(settings.DATABASES["default"]["NAME"]).resolve().parent != temporary
        ):
            raise RuntimeError("Evaluation database is not isolated.")
        if (
            Path(settings.PRIVATE_DOCUMENT_ROOT).resolve().parent != temporary
            or settings.EMAIL_BACKEND != "django.core.mail.backends.locmem.EmailBackend"
        ):
            raise RuntimeError("Evaluation storage or email is not isolated.")
        validate_dataset(dataset)
        print("Preparing temporary database and the local ESCO reference...")
        call_command("migrate", verbosity=0, interactive=False)
        call_command(
            "import_esco",
            str(ROOT / "data/esco/esco-v1.2.0-en.csv"),
            "--release",
            "v1.2.0",
            "--activate",
            verbosity=0,
        )
        corpus, _ = build_corpus()
        catalogue = SkillCatalogue.objects.get(active=True)
        reference = reference_for(corpus)
        ranking = evaluate_rankings(dataset, catalogue, reference)
        checks, probes = behavioral_checks(dataset, catalogue, reference)
        disagreements = []
        for left in ranking["pairs"]:
            for right in ranking["pairs"]:
                if (
                    left["job_id"] == right["job_id"]
                    and left["grade"] > right["grade"]
                    and left["recruiter_rank"] > right["recruiter_rank"]
                ):
                    disagreements.append(
                        {
                            "job_id": left["job_id"],
                            "higher_grade_profile": left["profile_id"],
                            "higher_grade": left["grade"],
                            "higher_grade_score": left["score"],
                            "lower_grade_profile": right["profile_id"],
                            "lower_grade": right["grade"],
                            "lower_grade_score": right["score"],
                        }
                    )
        workflow_checks = []
        setup_test_environment()
        try:
            run_workflows(dataset, workflow_checks)
        except Exception as error:
            # Preserve partial evidence and fail the command; never claim completion.
            workflow_checks.append(
                {
                    "name": "Workflow completed without an unexpected error",
                    "passed": False,
                    "evidence": f"{type(error).__name__}: {error}",
                }
            )
        finally:
            teardown_test_environment()
        sources = sorted(
            {
                path
                for folder in (
                    "accounts",
                    "applications",
                    "candidates",
                    "config",
                    "jobs",
                    "matching",
                    "pages",
                    "evaluation",
                    "scripts",
                )
                for path in (ROOT / folder).rglob("*.py")
            }
        )
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dataset_version": dataset["version"],
            "human_acceptance_status": "Pending; no participant sessions have been claimed.",
            "provenance": {
                "dataset_sha256": dataset_checksum,
                "catalogue_checksum": catalogue.checksum,
                "corpus_checksum": corpus.checksum,
                "catalogue_version": catalogue.version,
                "public_reference_documents": corpus.document_count,
                "configuration": configuration(),
                "python": platform.python_version(),
                "django": django.get_version(),
                "psycopg": version("psycopg"),
                "production_source_hashes": {
                    str(path.relative_to(ROOT)).replace("\\", "/"): file_hash(path)
                    for path in sources
                },
            },
            "ranking_digest": digest(ranking),
            "ranking": ranking,
            "disagreements": disagreements,
            "behavioral_checks": checks,
            "workflow_checks": workflow_checks,
            "limitation_probes": probes,
        }
        write_report(args.output, report, dataset)
    failed = [row["name"] for row in [*checks, *workflow_checks] if not row["passed"]]
    print(
        f"Evaluated {len(ranking['pairs'])} labelled pairs; {len(checks)} behavioral checks; {len(workflow_checks)} workflow checks."
    )
    print(f"Ranking digest: {report['ranking_digest']}")
    print(f"Report: {(args.output / 'report.md').resolve()}")
    if failed:
        print("Failed checks: " + "; ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
