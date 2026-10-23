# Expanded KaziForce evaluation (synthetic-v2)

This is synthetic engineering evidence. Independent human review and user acceptance remain pending. No hiring accuracy, payment delivery or participant satisfaction is claimed.

## Dataset and isolation

200 fictional candidate profiles, 40 permanent jobs, 60 freelancers drawn from those candidates and 20 freelance projects. Employment: 8,000 labelled pairs. Freelance: 1,200 labelled pairs. Ten professional fields; deterministic seed 20261023; fixed scoring date 23 October 2026.

Labels were generated from a declared scenario rubric before scoring. They are internally designed expectations, not independent ground truth. Multiple variants share domain templates. A larger synthetic set does not establish real-world validity or fairness.

A temporary SQLite database and temporary files are removed after the run. Email uses an in-memory backend; M-Pesa and network connections are disabled. Development PostgreSQL, accounts and uploaded documents are untouched. Timing does not represent production PostgreSQL or concurrent load.

## Ranking results

Precision@5 divides relevant returned top-five results by the number returned (up to five); empty lists are undefined. Recall@5 divides those relevant hits by all relevant labelled items, including items not returned. NDCG@10 uses exponential graded gains and an ideal ranking across the full labelled pool. Undefined values are excluded from macro averages; each query has equal weight. Coverage is reported separately so empty recommendation lists are visible.

| Direction / method | Queries | Coverage | Precision@5 | Recall@5 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recruiter_offline | 40 | 100.00% | 69.50% | 34.06% | 84.01% |
| recruiter_keyword_baseline | 40 | 100.00% | 64.50% | 31.74% | 81.48% |
| candidate_offline | 200 | 100.00% | 42.30% | 94.64% | 92.66% |
| candidate_keyword_baseline | 200 | 100.00% | 42.30% | 94.29% | 94.29% |
| candidate_threshold_policy | 200 | 34.00% | 70.59% | 28.75% | 25.30% |
| freelance production selector | 20 | 100.00% | 65.50% | 94.17% | 97.43% |

Employment offline rankings use all 40 open fixture jobs and all 200 profiles. Recruiter ranking is a counterfactual comparison of all profiles, not a claim that every person applied. Candidate threshold policy applies the current configured minimum and top-ten limit; it does not simulate submitted-job exclusions. Candidate relevance shares recruiter suitability labels and does not measure personal preferences.

The keyword baseline counts exact case-folded skill labels only, with scenario IDs breaking ties. It is a transparent weak comparator, not a reproduction of every keyword recruitment system. The production engine and its weights were not modified or tuned. Employment score ties use scenario IDs; stored production rankings use UUIDs. Freelance ties use stable fixture UUIDs.

Freelance results use the actual production selector, database eligibility filters and public-review ordering. Unreturned workers do not receive retrieval credit. Hourly total affordability cannot be established without an agreed number of hours. Ratings and history are fictional scenarios, not independent measurements of service quality.

## Interpretation

The larger set is harder than v1, and its percentages are not directly comparable because the roles, relevance prevalence and cutoffs differ. Compare methods within this frozen v2 set instead.

The candidate threshold policy returns jobs for only a subset of profiles. This is a precision/coverage trade-off, not evidence that profiles without recommendations are unsuitable for employment. Review the coverage and recall alongside precision before considering any threshold change.

Production scoring does not necessarily outperform the exact-label baseline in both ranking directions. Candidate NDCG can favour the baseline on these designed labels. Retain those results; do not alter the labels or formula to manufacture superiority. Human judgements are needed before choosing improvements.

Query timings also expose optimisation work: repeated skill standardisation and database access should be profiled before scaling the freelance search. These are single-process measurements on temporary SQLite, not production load-test results or a speed guarantee.

## Timing and checks

Employment scoring and ranking: 72.100 seconds for 8,000 pairs (including standardisation).
Freelance query median: 4.409 seconds; nearest-rank p95: 6.678 seconds across 20 queries.
Freelance eligibility/review checks passed: 40/40.

The held-out subset contains 10 job identities and 60 profile identities (600 pairs), with no weight tuning. Role templates are shared with development cases; this is not an external test set. Results are recorded in results.json.

## Human review: not yet completed

Two independent reviewers should each grade the same 400 blind pairs: 300 employment and 100 freelance. Use reviewer-1.csv and reviewer-2.csv with blind-review-packets.json. Each pair gets grade 0–3 and a written reason. Do not show reviewers dataset-v2.json, rankings, generated grades or results.json until their files are frozen. Resolve disagreements in adjudication.csv; never silently substitute generated labels. The sample is stratified and enriched for different relevance levels, not representative of prevalence in a live applicant pool.

Grade 0: unrelated or ineligible. Grade 1: weak/transferable evidence. Grade 2: plausible with gaps. Grade 3: strong supporting evidence. Grade 2 or 3 counts as relevant. Reviewers should use job-specific professional evidence; names and contact details are absent. Review agreements and adjudicated metrics require actual completed reviewer files and are not fabricated by this command.

The blind sample supports pair-level agreement and labelled-pair assessment. It is not a fully judged ranking pool, so full-corpus human Recall@5 or NDCG@10 must not be claimed from these 400 cases alone. Obtain complete judgements for chosen query pools, or use explicitly documented partial-judgement metrics, before reporting human ranking quality.

## Reproduce

Run `.\.venv\Scripts\python.exe scripts/evaluate_expanded.py`. The saved frozen dataset must match the deterministic generator. The original v1 dataset and reports are preserved. Use `--output <directory>` for another result directory. Compare ranking digests across runs; timings will vary.

Dataset SHA-256: `384976267a8fe5f66c069e62a6bf4aeb3fdd3bcc6f0021e9f7778a5cbbfedce4`
Ranking digest: `c8b573f575d8d78db0efe64f6acd8e16c2295350d6c89fec29bb796125394305`

Files: employment-rankings.csv, freelance-rankings.csv, results.json, report.md, reviewer-1.csv, reviewer-2.csv, adjudication.csv and blind-review-packets.json. Review templates are created once and never overwritten on repeat runs.
