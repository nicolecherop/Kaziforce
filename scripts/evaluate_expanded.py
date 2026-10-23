"""Reproduce expanded synthetic evidence without live accounts or payments."""

import argparse
from contextlib import ExitStack
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evaluation/v2")
    args = parser.parse_args()
    output = args.output.resolve()
    # Refuse to accidentally overwrite the existing baseline or source tree.
    if output in (ROOT, ROOT / "evaluation", ROOT / "docs/evaluation"):
        parser.error("Choose a dedicated expanded-evaluation output directory.")
    sys.path.insert(0, str(ROOT))
    from evaluation.expanded_dataset import build_dataset

    frozen_path = ROOT / "evaluation/dataset-v2.json"
    dataset = json.loads(frozen_path.read_text(encoding="utf-8"))
    if dataset != build_dataset():
        raise RuntimeError(
            "Frozen dataset differs from its generator. Version changes explicitly before scoring."
        )
    checksum = sha256(frozen_path.read_bytes()).hexdigest()
    baseline_paths = [
        ROOT / "evaluation/dataset-v1.json",
        ROOT / "docs/evaluation/report.md",
        ROOT / "docs/evaluation/results.json",
        ROOT / "docs/evaluation/rankings.csv",
    ]
    baseline_before = {
        str(path): sha256(path.read_bytes()).hexdigest() for path in baseline_paths
    }
    with TemporaryDirectory(
        prefix="kaziforce-expanded-evaluation-"
    ) as directory, ExitStack() as cleanup:
        temporary = Path(directory)
        (temporary / ".isolated-evaluation").touch()
        os.environ.update(
            DJANGO_SETTINGS_MODULE="config.evaluation_settings",
            KAZIFORCE_EVALUATION_ROOT=str(temporary),
            DJANGO_SECRET_KEY="isolated-expanded-evaluation-only",
        )
        # Fail closed even if local .env contains working Gmail/Daraja credentials.
        cleanup.enter_context(
            patch(
                "socket.socket.connect",
                side_effect=RuntimeError("Network disabled during offline evaluation."),
            )
        )
        import django

        django.setup()
        from django.conf import settings
        from django.core.management import call_command
        from django.db import connections
        from evaluation.matching import evaluate_rankings, validate_dataset
        from evaluation.expanded import (
            employment_summary,
            evaluate_freelance,
            export_reviews,
            write_csv,
            write_json,
            write_report,
        )
        from matching.corpus import build_corpus, reference_for
        from matching.models import SkillCatalogue
        from matching.scoring import configuration
        from matching.vectorization import digest

        cleanup.callback(connections.close_all)
        settings.MPESA_SANDBOX = {"enabled": False}
        settings.SOCIALACCOUNT_PROVIDERS = {}
        settings.EMAIL_TWO_STEP_ENABLED = False
        if (
            settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3"
            or Path(settings.DATABASES["default"]["NAME"]).resolve().parent != temporary
            or Path(settings.PRIVATE_DOCUMENT_ROOT).resolve().parent != temporary
            or Path(settings.MEDIA_ROOT).resolve().parent != temporary
            or settings.EMAIL_BACKEND != "django.core.mail.backends.locmem.EmailBackend"
        ):
            raise RuntimeError("Database, storage or email isolation failed.")
        cleanup.enter_context(
            patch(
                "django.utils.timezone.localdate",
                return_value=date.fromisoformat(dataset["as_of"]),
            )
        )
        validate_dataset(dataset)
        assert len(dataset["jobs"]) == 40 and len(dataset["profiles"]) == 200
        assert len(dataset["freelancers"]) == 60 and len(dataset["projects"]) == 20
        print(
            "Preparing disposable database; outbound network and payments disabled.",
            flush=True,
        )
        call_command("migrate", interactive=False, verbosity=0)
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
        print(
            "Scoring 8,000 employment pairs with the unchanged production engine...",
            flush=True,
        )
        started = perf_counter()
        ranking = evaluate_rankings(dataset, catalogue, reference_for(corpus))
        elapsed = perf_counter() - started
        jobs = {r["id"]: r for r in dataset["jobs"]}
        profiles = {r["id"]: r for r in dataset["profiles"]}
        for row in ranking["pairs"]:
            job_keys = {
                s["name"].strip().casefold()
                for s in jobs[row["job_id"]]["requirements"]["skills"]
            }
            profile_keys = {
                s["name"].strip().casefold()
                for s in profiles[row["profile_id"]]["snapshot"]["skills"]
            }
            row["keyword_overlap"] = len(job_keys & profile_keys)
        employment = employment_summary(
            dataset, ranking, Decimal(str(settings.MATCH_RECOMMENDATION_MIN_SCORE))
        )
        print(
            "Evaluating 20 freelance projects against 60 workers using production search...",
            flush=True,
        )
        freelance = evaluate_freelance(dataset)
        output.mkdir(parents=True, exist_ok=True)
        review_names = (
            "reviewer-1.csv",
            "reviewer-2.csv",
            "adjudication.csv",
            "blind-review-packets.json",
        )
        existing = [(output / name).exists() for name in review_names]
        if any(existing) and not all(existing):
            raise RuntimeError(
                "Partial review packet exists; preserve it and choose a new output directory."
            )
        if not any(existing):
            review = export_reviews(output, dataset)
        else:
            review = {
                "total": 400,
                "status": "Existing reviewer files preserved; not read or scored by this run.",
            }
        compact = [
            {
                k: row[k]
                for k in (
                    "job_id",
                    "profile_id",
                    "grade",
                    "score",
                    "raw_score",
                    "keyword_overlap",
                    "recruiter_rank",
                    "candidate_rank",
                    "rationale",
                )
            }
            for row in ranking["pairs"]
        ]
        source_hashes = {
            str(path.relative_to(ROOT))
            .replace("\\", "/"): sha256(path.read_bytes())
            .hexdigest()
            for folder in ("matching", "freelance", "evaluation", "config", "scripts")
            for path in sorted((ROOT / folder).rglob("*.py"))
        }
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dataset_version": dataset["version"],
            "dataset_sha256": checksum,
            "ranking_digest": digest(
                {"employment": compact, "freelance": freelance["pairs"]}
            ),
            "isolation": {
                "database": "temporary SQLite",
                "network": "blocked",
                "email": "in-memory",
                "payments": "disabled",
                "live_records_modified": False,
            },
            "provenance": {
                "catalogue_sha256": catalogue.checksum,
                "corpus_sha256": corpus.checksum,
                "configuration": configuration(),
                "django": django.get_version(),
                "source_sha256": source_hashes,
            },
            "employment_seconds": elapsed,
            "employment": employment,
            "freelance": freelance,
            "human_review": review,
        }
        write_csv(output / "employment-rankings.csv", compact)
        write_csv(output / "freelance-rankings.csv", freelance["pairs"])
        write_json(output / "results.json", report)
        write_report(output, report)
        if baseline_before != {
            str(path): sha256(path.read_bytes()).hexdigest() for path in baseline_paths
        }:
            raise RuntimeError("Original evaluation evidence changed unexpectedly.")
        if not all(check["passed"] for check in freelance["checks"]):
            raise RuntimeError(
                "A production freelance eligibility/review check failed; inspect results.json."
            )
    print(
        "Completed 8,000 employment and 1,200 freelance comparisons; baseline unchanged."
    )
    print("Ranking digest: " + report["ranking_digest"])
    print("Report: " + str(output / "report.md"))


if __name__ == "__main__":
    main()
