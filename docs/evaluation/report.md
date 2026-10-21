# Initial matching and workflow evaluation

Generated: 2026-10-21T09:07:03.583282+00:00. Scoring date: 2026-10-21.

This is a reproducible **synthetic engineering evaluation**, not evidence of hiring accuracy or completed human user acceptance testing. No real applicant records were used.

## Method

The frozen `synthetic-v1` fixture contains 5 roles, 20 fictional profiles and 100 explicit pair labels. Each role has strong, partial, junior and weak profiles. Labels and their rationales were prepared before the first engine run, using a designed rubric rather than independent recruiter annotations. They have not been changed to improve the results.

Grades: 3 = strong evidence, 2 = plausible with gaps, 1 = weak/transferable evidence, 0 = insufficient/unrelated evidence. Grade 2 or higher counts as relevant. The strong profile was the predeclared expected first result for each job.

The unchanged production scoring and ESCO standardization functions scored every pair. Recruiter evaluation ranks 20 profiles per job; candidate evaluation ranks 5 jobs per profile using the same relevance labels. These are complete offline rankings, without live eligibility filters. The HTTP workflow separately checks the production endpoints and filters. No model was trained or weights tuned on this fixture.

Metrics use full-precision scores, with scenario IDs breaking ties. Production uses stored UUIDs to break ties. Precision@3 divides relevant top-three items by min(3, available items). Recall@3 divides top-three relevant items by all relevant items. NDCG@10 uses `(2^grade - 1) / log2(rank + 1)`. MRR@10 finds the first grade-3 item; queries without a grade-3 item contribute zero. Pairwise concordance excludes equal-grade pairs and uses the deterministic ranking for score ties. Undefined metrics are omitted from their macro average. Each query has equal weight.

## Ranking results

| Direction | Queries | Precision@3 | Recall@3 | NDCG@10 | MRR@10 (grade 3) | Pairwise concordance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Recruiter | 5 | 100.00% | 100.00% | 99.15% | 100.00% | 96.95% |
| Candidate | 20 | 25.00% | 100.00% | 100.00% | 25.00% | 100.00% |

Candidate queries have at most one relevant job, and 15 of the 20 profiles have no grade-3 job. Consequently ideal Precision@3 is 25% across all 20 queries, and ideal MRR@10 (grade 3) is also 25%. Five weak-profile queries have no relevant job, so Recall@3 is undefined for those queries. These denominators differ from the recruiter evaluation; the percentages are not classification accuracy.

| Job | Expected first profile | Actual first profile | Score | Agreement |
| --- | --- | --- | ---: | --- |
| backend | backend-strong | backend-strong | 96.43% | Yes |
| data | data-strong | data-strong | 98.38% | Yes |
| frontend | frontend-strong | frontend-strong | 97.33% | Yes |
| project | project-strong | project-strong | 97.78% | Yes |
| support | support-strong | support-strong | 96.59% | Yes |

### Ordering disagreements

There were 16 strict grade inversions across the recruiter rankings. A higher rubric grade did not always receive the higher score. Every such pair is retained in `results.json`; examples:

- frontend: backend-junior (grade 1, 16.56%) ranked below data-strong (grade 0, 16.90%).
- project: support-partial (grade 1, 13.80%) ranked below backend-strong (grade 0, 15.99%).
- project: support-partial (grade 1, 13.80%) ranked below data-strong (grade 0, 16.07%).
- project: support-partial (grade 1, 13.80%) ranked below frontend-strong (grade 0, 15.99%).
- project: support-junior (grade 1, 8.16%) ranked below backend-strong (grade 0, 15.99%).
- project: support-junior (grade 1, 8.16%) ranked below data-strong (grade 0, 16.07%).
- project: support-junior (grade 1, 8.16%) ranked below frontend-strong (grade 0, 15.99%).
- support: project-partial (grade 1, 7.97%) ranked below backend-strong (grade 0, 15.67%).
- support: project-partial (grade 1, 7.97%) ranked below data-strong (grade 0, 15.51%).
- support: project-partial (grade 1, 7.97%) ranked below frontend-strong (grade 0, 15.43%).

## Behavioral and workflow checks

| Check | Result |
| --- | --- |
| Recruiter priority changes ranking | Pass |
| Python aliases map to the same concept | Pass |
| Duplicate aliases do not inflate score | Pass |
| Ambiguous SQL remains unresolved | Pass |
| Unknown skills require exact wording | Pass |
| Empty profile is explicitly unscorable | Pass |
| Out-of-vocabulary text contributes no cosine evidence | Pass |
| Overlapping roles are not counted twice | Pass |
| Register candidate through public form | Pass |
| Sign in candidate with email | Pass |
| Register recruiter through public form | Pass |
| Sign in recruiter with email | Pass |
| Register other-candidate through public form | Pass |
| Sign in other-candidate with email | Pass |
| Register other-recruiter through public form | Pass |
| Sign in other-recruiter with email | Pass |
| Publish a job with structured priorities | Pass |
| Save all manual professional profile sections | Pass |
| Upload private cv without extraction | Pass |
| Upload private degree without extraction | Pass |
| Upload private certificate without extraction | Pass |
| Original document is private | Pass |
| Candidate requests a saved job recommendation | Pass |
| Save an independent tailored draft | Pass |
| Recruiter cannot read a draft | Pass |
| Submit an application with three independent attachments | Pass |
| Owning recruiter can review; outsiders cannot | Pass |
| Editing main profile preserves submitted application | Pass |
| Profile text is HTML escaped | Pass |
| Submitted application cannot be overwritten | Pass |
| Recruiter ranks submitted evidence | Pass |
| Stored score replays exactly | Pass |
| Recruiter matching explanation is private | Pass |
| Shared attachment is readable only by application parties | Pass |
| Recruiter status update reaches candidate progress | Pass |
| CSRF-less state change is rejected | Pass |
| Closed job stops new applications | Pass |
| Connected workspace pages render successfully | Pass |

The workflow uses Django's HTTP test client with CSRF enforcement, real registration/login forms, stored application copies and the full local ESCO reference. It runs in a newly created temporary SQLite database with temporary private files and in-memory email. It is automated functional evidence; it does not validate browser layout, accessibility with assistive technology, real inbox delivery, PostgreSQL concurrency or participant usability. Separate PostgreSQL regression tests cover the actual database backend.

## Limitations and follow-up

- The dataset is small and deliberately constructed. Strong profiles echo the job descriptions, which favors text similarity. Cross-role examples are mostly clearly unrelated. Results cannot be generalized to real recruitment, fairness, or hiring outcomes.
- Labels were drafted internally from the fixture design. Independent domain reviewers and real candidate/recruiter participants have not validated them. Candidate preference, location eligibility, salary and availability are not measured by the relevance labels.
- Education is wording similarity, not verification of a qualification level or equivalence. A diploma or unrelated degree can share words with a requested degree. Recruiters must inspect the evidence.
- All declared work intervals contribute to duration, even when a role is unrelated. Relevant work text is a separate signal. Dates and credentials are self-reported; supporting files are for manual review.
- ESCO coverage is incomplete for some common product names. Ambiguous labels such as SQL remain unresolved; unknown labels match by exact wording only. Text outside the fixed public vocabulary adds no cosine evidence.
- A percentage describes profile alignment under this formula. It is not a probability of being hired, a hard eligibility decision or a substitute for recruiter judgement.

Observed probe: **Unrelated work still counts towards declared duration** scored 100.00% on the experience component when the job requested duration without a relevance description. Duration includes all declared roles. Recruiters must assess relevance; duration alone is not evidence of relevant experience.

Next: complete the [human acceptance checklist](../user-acceptance.md), have independent reviewers label more varied cases before scoring, and retain a new dataset version when expanding the evaluation. Keep this baseline and its labels unchanged.

## Reproduction and evidence

From the project folder:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_project.py
```

No PostgreSQL connection, outbound email, download or live account mutation is made by this command. It creates and removes its own temporary database and documents. Only the named report files in the output directory are written persistently. The fixed local ESCO CSV is required.

Dataset SHA-256: `00f271d89dbe0241ce03c7b521c3285bab748abb2043a4ddb6bd9fd2049115c9`

ESCO source SHA-256: `7cb3dcaa7a585ceaacba8d522fb414dd2eff400bc53b8ceb8119ba6c352f05cd`

Corpus SHA-256: `97a24c3c4979832c4ca6712858f95fd9648020991d83673da12c6ae00292e26a`

Deterministic ranking digest: `b2276225b72412c467f5df81aa8c434b52fd6d760c97c87d43fa22e9019ebfcf`

`results.json` records complete pair scores, component weights, mapping warnings, every ranking, metric, disagreement, workflow evidence, dependency versions and production source hashes. `rankings.csv` is a spreadsheet-friendly view of all 100 labelled pairs. `dataset-v1.json` under `evaluation/` contains the original expectations.
