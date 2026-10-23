"""Isolated production-selector evaluation and blind review exports."""

import csv
from datetime import date, timedelta
from decimal import Decimal
import json
from pathlib import Path
from random import Random
from statistics import mean, median
from time import perf_counter
from uuid import NAMESPACE_URL, uuid5

from .expanded_dataset import SEED


def stable_id(value):
    return uuid5(NAMESPACE_URL, "kaziforce-evaluation-v2/" + value)


def write_json(path, value):
    Path(path).write_text(
        json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


def write_csv(path, rows, fields=None):
    rows = list(rows)
    with Path(path).open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def quality(grades, all_grades):
    from evaluation.metrics import ranking_metrics

    # Filtered-out items are omitted from returned rankings, never treated as
    # retrieved matches. Recall's denominator still includes every relevant case.
    missing = list(all_grades)
    for grade in grades:
        missing.remove(grade)
    full = grades + missing
    metrics = ranking_metrics(full, full)
    hits = sum(grade >= 2 for grade in grades[:5])
    relevant = sum(grade >= 2 for grade in all_grades)
    metrics["precision_at_5"] = hits / min(5, len(grades)) if grades else None
    metrics["recall_at_5"] = hits / relevant if relevant else None
    # Ranking metrics must not credit an item that production did not return.
    from math import log2

    def dcg(items):
        return sum(
            (2**grade - 1) / log2(rank + 2) for rank, grade in enumerate(items[:10])
        )

    ideal = dcg(sorted(all_grades, reverse=True))
    metrics["ndcg_at_10"] = dcg(grades) / ideal if ideal else None
    metrics.pop("pairwise_concordance")
    metrics.pop("precision_at_3")
    metrics.pop("recall_at_3")
    metrics.pop("mrr_at_10_ideal")
    return metrics


def summarize_queries(queries):
    from evaluation.metrics import macro_average

    return {
        "query_count": len(queries),
        "queries_with_results": sum(q["returned"] > 0 for q in queries),
        "coverage": mean(q["returned"] > 0 for q in queries) if queries else None,
        "macro": macro_average([q["metrics"] for q in queries]),
        "queries": queries,
    }


def employment_summary(dataset, ranking, threshold):
    pairs = ranking["pairs"]
    result = {}
    for direction, query_key, item_key in (
        ("recruiter", "job_id", "profile_id"),
        ("candidate", "profile_id", "job_id"),
    ):
        queries, baseline = [], []
        for query in sorted({row[query_key] for row in pairs}):
            rows = sorted(
                (r for r in pairs if r[query_key] == query),
                key=lambda r: (-r["raw_score"], r[item_key]),
            )
            grades = [row["grade"] for row in rows]
            queries.append(
                {"id": query, "returned": len(rows), "metrics": quality(grades, grades)}
            )
            keyword = sorted(
                rows, key=lambda row: (-row["keyword_overlap"], row[item_key])
            )
            baseline.append(
                {
                    "id": query,
                    "returned": len(keyword),
                    "metrics": quality([r["grade"] for r in keyword], grades),
                }
            )
        result[direction + "_offline"] = summarize_queries(queries)
        result[direction + "_keyword_baseline"] = summarize_queries(baseline)
    candidates = []
    for profile in dataset["profiles"]:
        all_rows = sorted(
            (r for r in pairs if r["profile_id"] == profile["id"]),
            key=lambda r: (-r["raw_score"], r["job_id"]),
        )
        returned = [r for r in all_rows if Decimal(r["score"]) >= threshold][:10]
        candidates.append(
            {
                "id": profile["id"],
                "returned": len(returned),
                "metrics": quality(
                    [r["grade"] for r in returned], [r["grade"] for r in all_rows]
                ),
            }
        )
    result["candidate_threshold_policy"] = summarize_queries(candidates)
    result["threshold"] = str(threshold)
    # Held-out profile/job identities were declared before scoring. No tuning.
    hold_jobs = {r["id"] for r in dataset["jobs"] if r["split"] == "holdout"}
    hold_profiles = {r["id"] for r in dataset["profiles"] if r["split"] == "holdout"}
    result["holdout"] = {
        "pairs": sum(
            r["job_id"] in hold_jobs and r["profile_id"] in hold_profiles for r in pairs
        ),
        "note": "Identity-held-out subset, same synthetic role templates; not independent external validation.",
    }
    result["holdout"]["recruiter"] = summarize_queries(
        [
            {
                "id": job,
                "returned": len(
                    rows := sorted(
                        [
                            r
                            for r in pairs
                            if r["job_id"] == job and r["profile_id"] in hold_profiles
                        ],
                        key=lambda r: (-r["raw_score"], r["profile_id"]),
                    )
                ),
                "metrics": quality(
                    [r["grade"] for r in rows], [r["grade"] for r in rows]
                ),
            }
            for job in sorted(hold_jobs)
        ]
    )
    return result


def evaluate_freelance(dataset):
    from django.contrib.auth import get_user_model
    from candidates.models import CandidateProfile, CandidateSkill
    from freelance.models import (
        FreelancerProfile,
        FreelanceProject,
        Booking,
        Conversation,
        Review,
        FreelanceService,
    )
    from freelance.selectors import freelance_search

    User = get_user_model()
    recruiter = User.objects.create_user(
        username="evaluation-recruiter",
        email="recruiter@example.test",
        role="recruiter",
        password=None,
    )
    source_profiles = {row["id"]: row for row in dataset["profiles"]}
    workers = {}
    as_of = date.fromisoformat(dataset["as_of"])
    for row in dataset["freelancers"]:
        source = source_profiles[row["profile_id"]]
        user = User.objects.create_user(
            username=row["id"],
            email=row["id"] + "@example.test",
            role="candidate",
            password=None,
        )
        professional = CandidateProfile.objects.create(
            user=user, **source["snapshot"]["profile"], location=row["location"]
        )
        CandidateSkill.objects.bulk_create(
            [
                CandidateSkill(profile=professional, name=s["name"])
                for s in source["snapshot"]["skills"]
            ]
        )
        worker = FreelancerProfile.objects.create(
            id=stable_id(row["id"]),
            user=user,
            title=row["title"],
            about=source["snapshot"]["profile"]["summary"],
            location=row["location"],
            work_mode=row["work_mode"],
            rate=row["rate"],
            rate_unit=row["rate_unit"],
            available_from=row["available_from"],
            accepting_bookings=row["accepting_bookings"],
            share_professional_profile=row["share_professional_profile"],
        )
        workers[row["id"]] = worker
        FreelanceService.objects.create(
            profile=worker,
            title=row["title"],
            description=source["snapshot"]["profile"]["summary"],
        )
        thread = Conversation.objects.create(
            id=stable_id(row["id"] + "/thread"), recruiter=recruiter, freelancer=worker
        )
        for index, rating in enumerate(
            row["ratings"] + ([row["hidden_rating"]] if row["hidden_rating"] else [])
        ):
            booking = Booking.objects.create(
                id=stable_id(f'{row["id"]}/history/{index}'),
                conversation=thread,
                title="Previous assignment",
                scope="Fictional completed assignment",
                location=row["location"],
                start_date=as_of - timedelta(days=60 + index * 2),
                end_date=as_of - timedelta(days=60 + index * 2),
                total_price=1000,
                cancellation_terms="By agreement",
                status="completed",
                recruiter_name="Evaluation recruiter",
                recruiter_email="recruiter@example.test",
            )
            Review.objects.create(
                booking=booking,
                rating=rating,
                comment="Fictional evaluation feedback",
                is_hidden=index >= len(row["ratings"]),
            )
        if row["busy"]:
            Booking.objects.create(
                id=stable_id(row["id"] + "/busy"),
                conversation=thread,
                title="Reserved dates",
                scope="Existing assignment",
                location=row["location"],
                start_date="2026-11-01",
                end_date="2026-11-07",
                total_price=1000,
                cancellation_terms="By agreement",
                status="accepted",
                recruiter_name="Evaluation recruiter",
                recruiter_email="recruiter@example.test",
            )
    labels = {(r["job_id"], r["profile_id"]): r for r in dataset["freelance_labels"]}
    ids = {worker.pk: key for key, worker in workers.items()}
    pairs, queries, checks, times = [], [], [], []
    for row in dataset["projects"]:
        project = FreelanceProject.objects.create(
            id=stable_id(row["id"]),
            recruiter=recruiter,
            **{k: v for k, v in row.items() if k not in ("id", "domain")},
        )
        project.refresh_from_db()
        started = perf_counter()
        found = freelance_search({}, project=project)
        times.append(perf_counter() - started)
        returned = {ids[p.pk]: (rank, p) for rank, p in enumerate(found, 1)}
        for worker in dataset["freelancers"]:
            key = worker["id"]
            rank, item = returned.get(key, (None, None))
            pairs.append(
                {
                    "job_id": row["id"],
                    "profile_id": key,
                    "grade": labels[row["id"], key]["grade"],
                    "rationale": labels[row["id"], key]["rationale"],
                    "returned": rank is not None,
                    "rank": rank,
                    "matched_skill_count": item.relevant_skills if item else None,
                    "rating_order": item.rating_order if item else None,
                }
            )
        grades = [labels[row["id"], ids[p.pk]]["grade"] for p in found]
        all_grades = [
            labels[row["id"], w["id"]]["grade"] for w in dataset["freelancers"]
        ]
        queries.append(
            {
                "id": row["id"],
                "returned": len(found),
                "metrics": quality(grades, all_grades),
            }
        )
        checks.append(
            {
                "name": row["id"]
                + ": inactive, unavailable and conflicting workers excluded",
                "passed": all(
                    not w["busy"]
                    and w["accepting_bookings"]
                    and w["available_from"] <= row["start_date"]
                    for w in dataset["freelancers"]
                    if w["id"] in returned
                ),
            }
        )
        checks.append(
            {
                "name": row["id"] + ": hidden reviews excluded from displayed count",
                "passed": all(
                    item.review_count
                    == len(
                        next(
                            w for w in dataset["freelancers"] if w["id"] == ids[item.pk]
                        )["ratings"]
                    )
                    for item in found
                ),
            }
        )
    return {
        "summary": summarize_queries(queries),
        "pairs": pairs,
        "checks": checks,
        "latency": timings(times),
        "note": "Actual production freelance_search selector and database filters; skills plus review-based ordering, no TF-IDF. Hourly totals are not compared to project budgets without an hour estimate.",
    }


def timings(values):
    ordered = sorted(values)
    return {
        "count": len(values),
        "total_seconds": sum(values),
        "median_seconds": median(values),
        "p95_seconds": ordered[max(0, (95 * len(values) + 99) // 100 - 1)],
    }


def export_reviews(output, dataset):
    rng = Random(SEED + 1)
    records = []
    # Stratified, pre-score sampling includes weak matches and hard cases.
    for section, labels, total in (
        ("employment", dataset["labels"], 300),
        ("freelance", dataset["freelance_labels"], 100),
    ):
        query_ids = sorted({r["job_id"] for r in labels})
        for index, query in enumerate(query_ids):
            candidates = [r for r in labels if r["job_id"] == query]
            rng.shuffle(candidates)
            groups = [
                [r for r in candidates if r["grade"] == grade] for grade in (3, 2, 1, 0)
            ]
            selected = []
            needed = total // len(query_ids) + (index < total % len(query_ids))
            while len(selected) < needed:
                for group in groups:
                    if group and len(selected) < needed:
                        selected.append(group.pop())
            for row in selected:
                records.append(
                    {
                        "pair_id": f'{section}/{row["job_id"]}/{row["profile_id"]}',
                        "section": section,
                        "opportunity_id": row["job_id"],
                        "profile_id": row["profile_id"],
                        "grade_0_to_3": "",
                        "reason": "",
                        "reviewer_id": "",
                    }
                )
    rng.shuffle(records)
    for reviewer in (1, 2):
        write_csv(output / f"reviewer-{reviewer}.csv", records)
    write_csv(
        output / "adjudication.csv",
        [
            {
                "pair_id": r["pair_id"],
                "final_grade_0_to_3": "",
                "reason": "",
                "adjudicator_id": "",
            }
            for r in records
        ],
    )
    profiles = {p["id"]: p for p in dataset["profiles"]}
    workers = {p["id"]: p for p in dataset["freelancers"]}
    jobs = {j["id"]: j for j in dataset["jobs"]}
    projects = {j["id"]: j for j in dataset["projects"]}
    packets = []
    for row in records:
        if row["section"] == "employment":
            opportunity = jobs[row["opportunity_id"]]["requirements"]
            evidence = profiles[row["profile_id"]]["snapshot"]
        else:
            worker = workers[row["profile_id"]]
            opportunity = {
                k: v
                for k, v in projects[row["opportunity_id"]].items()
                if k != "domain"
            }
            evidence = {
                k: v
                for k, v in worker.items()
                if k not in ("domain", "hidden_rating", "ratings")
            }
            evidence["profile"] = profiles[worker["profile_id"]]["snapshot"]
            evidence["public_ratings"] = worker["ratings"]
            evidence["reserved_dates"] = (
                ["2026-11-01", "2026-11-07"] if worker["busy"] else []
            )
        packets.append(
            {
                "pair_id": row["pair_id"],
                "opportunity": opportunity,
                "evidence": evidence,
            }
        )
    write_json(output / "blind-review-packets.json", packets)
    return {
        "employment": 300,
        "freelance": 100,
        "total": len(records),
        "status": "Pending; reviewer files and adjudications intentionally blank.",
    }


def write_report(output, report):
    def percent(value):
        return "undefined" if value is None else f"{100 * value:.2f}%"

    lines = [
        "# Expanded KaziForce evaluation (synthetic-v2)",
        "",
        "This is synthetic engineering evidence. Independent human review and user acceptance remain pending. No hiring accuracy, payment delivery or participant satisfaction is claimed.",
        "",
        "## Dataset and isolation",
        "",
        "200 fictional candidate profiles, 40 permanent jobs, 60 freelancers drawn from those candidates and 20 freelance projects. Employment: 8,000 labelled pairs. Freelance: 1,200 labelled pairs. Ten professional fields; deterministic seed 20261023; fixed scoring date 23 October 2026.",
        "",
        "Labels were generated from a declared scenario rubric before scoring. They are internally designed expectations, not independent ground truth. Multiple variants share domain templates. A larger synthetic set does not establish real-world validity or fairness.",
        "",
        "A temporary SQLite database and temporary files are removed after the run. Email uses an in-memory backend; M-Pesa and network connections are disabled. Development PostgreSQL, accounts and uploaded documents are untouched. Timing does not represent production PostgreSQL or concurrent load.",
        "",
        "## Ranking results",
        "",
        "Precision@5 divides relevant returned top-five results by the number returned (up to five); empty lists are undefined. Recall@5 divides those relevant hits by all relevant labelled items, including items not returned. NDCG@10 uses exponential graded gains and an ideal ranking across the full labelled pool. Undefined values are excluded from macro averages; each query has equal weight. Coverage is reported separately so empty recommendation lists are visible.",
        "",
        "| Direction / method | Queries | Coverage | Precision@5 | Recall@5 | NDCG@10 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, item in [
        (k, v)
        for k, v in report["employment"].items()
        if isinstance(v, dict) and "macro" in v
    ] + [("freelance production selector", report["freelance"]["summary"])]:
        metrics = item["macro"]
        lines.append(
            f'| {name} | {item["query_count"]} | {percent(item["coverage"])} | {percent(metrics["precision_at_5"])} | {percent(metrics["recall_at_5"])} | {percent(metrics["ndcg_at_10"])} |'
        )
    lines += [
        "",
        "Employment offline rankings use all 40 open fixture jobs and all 200 profiles. Recruiter ranking is a counterfactual comparison of all profiles, not a claim that every person applied. Candidate threshold policy applies the current configured minimum and top-ten limit; it does not simulate submitted-job exclusions. Candidate relevance shares recruiter suitability labels and does not measure personal preferences.",
        "",
        "The keyword baseline counts exact case-folded skill labels only, with scenario IDs breaking ties. It is a transparent weak comparator, not a reproduction of every keyword recruitment system. The production engine and its weights were not modified or tuned. Employment score ties use scenario IDs; stored production rankings use UUIDs. Freelance ties use stable fixture UUIDs.",
        "",
        "Freelance results use the actual production selector, database eligibility filters and public-review ordering. Unreturned workers do not receive retrieval credit. Hourly total affordability cannot be established without an agreed number of hours. Ratings and history are fictional scenarios, not independent measurements of service quality.",
        "",
        "## Interpretation",
        "",
        "The larger set is harder than v1, and its percentages are not directly comparable because the roles, relevance prevalence and cutoffs differ. Compare methods within this frozen v2 set instead.",
        "",
        "The candidate threshold policy returns jobs for only a subset of profiles. This is a precision/coverage trade-off, not evidence that profiles without recommendations are unsuitable for employment. Review the coverage and recall alongside precision before considering any threshold change.",
        "",
        "Production scoring does not necessarily outperform the exact-label baseline in both ranking directions. Candidate NDCG can favour the baseline on these designed labels. Retain those results; do not alter the labels or formula to manufacture superiority. Human judgements are needed before choosing improvements.",
        "",
        "Query timings also expose optimisation work: repeated skill standardisation and database access should be profiled before scaling the freelance search. These are single-process measurements on temporary SQLite, not production load-test results or a speed guarantee.",
        "",
        "## Timing and checks",
        "",
        f'Employment scoring and ranking: {report["employment_seconds"]:.3f} seconds for 8,000 pairs (including standardisation).',
        f'Freelance query median: {report["freelance"]["latency"]["median_seconds"]:.3f} seconds; nearest-rank p95: {report["freelance"]["latency"]["p95_seconds"]:.3f} seconds across 20 queries.',
        f'Freelance eligibility/review checks passed: {sum(c["passed"] for c in report["freelance"]["checks"])}/{len(report["freelance"]["checks"])}.',
        "",
        "The held-out subset contains 10 job identities and 60 profile identities (600 pairs), with no weight tuning. Role templates are shared with development cases; this is not an external test set. Results are recorded in results.json.",
        "",
        "## Human review: not yet completed",
        "",
        "Two independent reviewers should each grade the same 400 blind pairs: 300 employment and 100 freelance. Use reviewer-1.csv and reviewer-2.csv with blind-review-packets.json. Each pair gets grade 0–3 and a written reason. Do not show reviewers dataset-v2.json, rankings, generated grades or results.json until their files are frozen. Resolve disagreements in adjudication.csv; never silently substitute generated labels. The sample is stratified and enriched for different relevance levels, not representative of prevalence in a live applicant pool.",
        "",
        "Grade 0: unrelated or ineligible. Grade 1: weak/transferable evidence. Grade 2: plausible with gaps. Grade 3: strong supporting evidence. Grade 2 or 3 counts as relevant. Reviewers should use job-specific professional evidence; names and contact details are absent. Review agreements and adjudicated metrics require actual completed reviewer files and are not fabricated by this command.",
        "",
        "The blind sample supports pair-level agreement and labelled-pair assessment. It is not a fully judged ranking pool, so full-corpus human Recall@5 or NDCG@10 must not be claimed from these 400 cases alone. Obtain complete judgements for chosen query pools, or use explicitly documented partial-judgement metrics, before reporting human ranking quality.",
        "",
        "## Reproduce",
        "",
        "Run `.\\.venv\\Scripts\\python.exe scripts/evaluate_expanded.py`. The saved frozen dataset must match the deterministic generator. The original v1 dataset and reports are preserved. Use `--output <directory>` for another result directory. Compare ranking digests across runs; timings will vary.",
        "",
        f'Dataset SHA-256: `{report["dataset_sha256"]}`',
        f'Ranking digest: `{report["ranking_digest"]}`',
        "",
        "Files: employment-rankings.csv, freelance-rankings.csv, results.json, report.md, reviewer-1.csv, reviewer-2.csv, adjudication.csv and blind-review-packets.json. Review templates are created once and never overwritten on repeat runs.",
    ]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
