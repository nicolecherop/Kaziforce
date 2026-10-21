"""Readable findings plus complete machine-readable and spreadsheet evidence."""

import csv
import json
from pathlib import Path


def percentage(value):
    return "Undefined" if value is None else f"{value * 100:.2f}%"


def write_report(output, report, dataset):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    fields = [
        "job_id",
        "profile_id",
        "grade",
        "rationale",
        "score",
        "raw_score",
        "recruiter_rank",
        "candidate_rank",
        "skills_score",
        "text_score",
        "education_score",
        "experience_score",
        "unresolved_skills",
    ]
    with (output / "rankings.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in report["ranking"]["pairs"]:
            writer.writerow(
                {
                    **{field: row[field] for field in fields[:8]},
                    **{
                        component["key"] + "_score": component["score"]
                        for component in row["components"]
                    },
                    "unresolved_skills": "; ".join(
                        row["explanation"]["unresolved_skills"]
                    ),
                }
            )
    lines = [
        "# Initial matching and workflow evaluation",
        "",
        f"Generated: {report['generated_at']}. Scoring date: {dataset['as_of']}.",
        "",
        "This is a reproducible **synthetic engineering evaluation**, not evidence of hiring accuracy or completed human user acceptance testing. No real applicant records were used.",
        "",
        "## Method",
        "",
        f"The frozen `{dataset['version']}` fixture contains {len(dataset['jobs'])} roles, {len(dataset['profiles'])} fictional profiles and {len(dataset['labels'])} explicit pair labels. Each role has strong, partial, junior and weak profiles. Labels and their rationales were prepared before the first engine run, using a designed rubric rather than independent recruiter annotations. They have not been changed to improve the results.",
        "",
        "Grades: 3 = strong evidence, 2 = plausible with gaps, 1 = weak/transferable evidence, 0 = insufficient/unrelated evidence. Grade 2 or higher counts as relevant. The strong profile was the predeclared expected first result for each job.",
        "",
        "The unchanged production scoring and ESCO standardization functions scored every pair. Recruiter evaluation ranks 20 profiles per job; candidate evaluation ranks 5 jobs per profile using the same relevance labels. These are complete offline rankings, without live eligibility filters. The HTTP workflow separately checks the production endpoints and filters. No model was trained or weights tuned on this fixture.",
        "",
        "Metrics use full-precision scores, with scenario IDs breaking ties. Production uses stored UUIDs to break ties. Precision@3 divides relevant top-three items by min(3, available items). Recall@3 divides top-three relevant items by all relevant items. NDCG@10 uses `(2^grade - 1) / log2(rank + 1)`. MRR@10 finds the first grade-3 item; queries without a grade-3 item contribute zero. Pairwise concordance excludes equal-grade pairs and uses the deterministic ranking for score ties. Undefined metrics are omitted from their macro average. Each query has equal weight.",
        "",
        "## Ranking results",
        "",
        "| Direction | Queries | Precision@3 | Recall@3 | NDCG@10 | MRR@10 (grade 3) | Pairwise concordance |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for direction, result in report["ranking"]["directions"].items():
        macro = result["macro"]
        values = [
            percentage(macro[key])
            for key in (
                "precision_at_3",
                "recall_at_3",
                "ndcg_at_10",
                "mrr_at_10_ideal",
                "pairwise_concordance",
            )
        ]
        lines.append(
            f"| {direction.title()} | {len(result['queries'])} | "
            + " | ".join(values)
            + " |"
        )
    lines.extend(
        [
            "",
            "Candidate queries have at most one relevant job, and 15 of the 20 profiles have no grade-3 job. Consequently ideal Precision@3 is 25% across all 20 queries, and ideal MRR@10 (grade 3) is also 25%. Five weak-profile queries have no relevant job, so Recall@3 is undefined for those queries. These denominators differ from the recruiter evaluation; the percentages are not classification accuracy.",
            "",
            "| Job | Expected first profile | Actual first profile | Score | Agreement |",
            "| --- | --- | --- | ---: | --- |",
        ]
    )
    for query in report["ranking"]["directions"]["recruiter"]["queries"]:
        first = query["ranking"][0]
        expected = dataset["expected_top_profile_by_job"][query["query_id"]]
        lines.append(
            f"| {query['query_id']} | {expected} | {first['item_id']} | {first['score']}% | {'Yes' if first['item_id'] == expected else 'No'} |"
        )
    lines.extend(["", "### Ordering disagreements", ""])
    if report["disagreements"]:
        lines.append(
            f"There were {len(report['disagreements'])} strict grade inversions across the recruiter rankings. A higher rubric grade did not always receive the higher score. Every such pair is retained in `results.json`; examples:"
        )
        lines.append("")
        for row in report["disagreements"][:10]:
            lines.append(
                f"- {row['job_id']}: {row['higher_grade_profile']} (grade {row['higher_grade']}, {row['higher_grade_score']}%) ranked below {row['lower_grade_profile']} (grade {row['lower_grade']}, {row['lower_grade_score']}%)."
            )
    else:
        lines.append(
            "No strict grade inversion occurred in recruiter rankings on this fixture. Equal-grade ordering was not judged as an error."
        )
    lines.extend(
        [
            "",
            "## Behavioral and workflow checks",
            "",
            "| Check | Result |",
            "| --- | --- |",
        ]
    )
    for row in [*report["behavioral_checks"], *report["workflow_checks"]]:
        lines.append(f"| {row['name']} | {'Pass' if row['passed'] else 'Fail'} |")
    lines.extend(
        [
            "",
            "The workflow uses Django's HTTP test client with CSRF enforcement, real registration/login forms, stored application copies and the full local ESCO reference. It runs in a newly created temporary SQLite database with temporary private files and in-memory email. It is automated functional evidence; it does not validate browser layout, accessibility with assistive technology, real inbox delivery, PostgreSQL concurrency or participant usability. Separate PostgreSQL regression tests cover the actual database backend.",
            "",
            "## Limitations and follow-up",
            "",
            "- The dataset is small and deliberately constructed. Strong profiles echo the job descriptions, which favors text similarity. Cross-role examples are mostly clearly unrelated. Results cannot be generalized to real recruitment, fairness, or hiring outcomes.",
            "- Labels were drafted internally from the fixture design. Independent domain reviewers and real candidate/recruiter participants have not validated them. Candidate preference, location eligibility, salary and availability are not measured by the relevance labels.",
            "- Education is wording similarity, not verification of a qualification level or equivalence. A diploma or unrelated degree can share words with a requested degree. Recruiters must inspect the evidence.",
            "- All declared work intervals contribute to duration, even when a role is unrelated. Relevant work text is a separate signal. Dates and credentials are self-reported; supporting files are for manual review.",
            "- ESCO coverage is incomplete for some common product names. Ambiguous labels such as SQL remain unresolved; unknown labels match by exact wording only. Text outside the fixed public vocabulary adds no cosine evidence.",
            "- A percentage describes profile alignment under this formula. It is not a probability of being hired, a hard eligibility decision or a substitute for recruiter judgement.",
            "",
        ]
    )
    for row in report["limitation_probes"]:
        lines.append(
            f"Observed probe: **{row['name']}** scored {row['observed_component_score']:.2f}% on the experience component when the job requested duration without a relevance description. {row['interpretation']}"
        )
    lines.extend(
        [
            "",
            "Next: complete the [human acceptance checklist](../user-acceptance.md), have independent reviewers label more varied cases before scoring, and retain a new dataset version when expanding the evaluation. Keep this baseline and its labels unchanged.",
            "",
            "## Reproduction and evidence",
            "",
            "From the project folder:",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe scripts/evaluate_project.py",
            "```",
            "",
            "No PostgreSQL connection, outbound email, download or live account mutation is made by this command. It creates and removes its own temporary database and documents. Only the named report files in the output directory are written persistently. The fixed local ESCO CSV is required.",
            "",
            f"Dataset SHA-256: `{report['provenance']['dataset_sha256']}`",
            "",
            f"ESCO source SHA-256: `{report['provenance']['catalogue_checksum']}`",
            "",
            f"Corpus SHA-256: `{report['provenance']['corpus_checksum']}`",
            "",
            f"Deterministic ranking digest: `{report['ranking_digest']}`",
            "",
            "`results.json` records complete pair scores, component weights, mapping warnings, every ranking, metric, disagreement, workflow evidence, dependency versions and production source hashes. `rankings.csv` is a spreadsheet-friendly view of all 100 labelled pairs. `dataset-v1.json` under `evaluation/` contains the original expectations.",
            "",
        ]
    )
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
