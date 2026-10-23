# Expanded evaluation and human review

The frozen `evaluation/dataset-v2.json` contains 200 unique fictional professional profiles, 40 jobs, 60 freelancers and 20 freelance projects. Profiles cover ten professional fields and ten evidence patterns. Sixty professional profiles also have freelance service settings, rates, availability and fictional review histories.

No live candidate accounts or jobs are added. The runner creates a disposable SQLite database, imports the existing local ESCO reference, evaluates the production employment scoring function and freelance search selector, then removes the database and temporary files. It blocks network connections, disables M-Pesa and sends no external email. Your development PostgreSQL records and v1 evaluation evidence are preserved.

## Run and inspect

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_expanded.py
```

Read `docs/evaluation/v2/report.md` for findings and limitations. The two rankings CSV files contain all 9,200 evaluated pairs, including freelance exclusions. `results.json` records per-query metrics, production source hashes, reference checksums and a deterministic ranking digest. Repeated runs should have the same digest; execution times vary. The runner preserves existing reviewer CSV files and their adjudications.

To keep a second run separately:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_expanded.py --output docs/evaluation/v2-repeat
```

This is a matching and retrieval evaluation. It does not replace end-to-end regression tests, PostgreSQL concurrency checks, browser accessibility checks or human user testing. The production website's candidate recommendation policy is represented by its configured score threshold and top-ten limit; this fixture does not model previously submitted applications or personal job preferences.

## Independent review

The generated suitability grades are **synthetic expectations**. They are not recruiter annotations and must not be described as independently verified ground truth. They are fixed before scoring. Neither the dataset nor the production weights should be edited to improve the reported metrics; meaningful revisions require another named dataset version.

For a stronger evaluation, ask two people with relevant recruitment or professional knowledge to assess the same cases independently:

1. Give each person only `blind-review-packets.json`, their own `reviewer-1.csv` or `reviewer-2.csv`, and the grading rubric below. A JSON-capable editor can search packets by `pair_id`. The packets show job requirements and professional evidence, or project terms and worker details. They hide system scores, scenario variants and designed labels.
2. Each reviewer fills `grade_0_to_3`, `reason` and `reviewer_id` for the 400 pairs. They should not see each other's answers, rankings, full frozen dataset or generated results while grading. The selection includes 300 employment and 100 freelance pairs, sampled across designed relevance levels before scoring. It is intentionally challenging, not a prevalence estimate for real applicants.
3. Preserve completed files separately before discussing disagreements. Use `adjudication.csv` to record the final agreed grade, reason and adjudicator, retaining the original independent answers. Do not replace blank answers with generated grades.
4. Measure reviewer agreement after answers are actually available. Pair-level results can be evaluated on this reviewed sample. Full-ranking human Recall@5 or NDCG@10 requires complete judgements for chosen query pools, or a separately justified method for incomplete judgements; the 400-pair sample alone does not support those full-corpus claims.

| Grade | Meaning |
| --- | --- |
| 0 | Unrelated professional evidence or a clear project eligibility conflict |
| 1 | Weak or transferable evidence; substantial gaps |
| 2 | Plausible match with explicit gaps needing review |
| 3 | Strong supporting evidence for this particular opportunity |

For freelance cases, consider availability, work arrangement, price basis and supporting service evidence. An hourly rate alone cannot establish total affordability without an agreed number of hours. No reviews means unknown history, not proof of poor performance. Do not assume certifications or experience claims were independently verified.

## Development and holdout

The fixture declares 10 job identities and 60 profile identities as held out before scoring. Their intersection contains 600 pairs. No tuning is performed by the runner. These records still share synthetic professional templates with development cases, so they are not an independent real-world test set.

The exact-label keyword comparator is deliberately simple and transparent. It helps compare production scoring to one basic approach; it does not represent every keyword-based recruitment product. Employment and freelance outputs are reported separately because freelance production search currently uses standardised skill overlap, eligibility filters and review-based tie ordering rather than employment TF-IDF scoring.

Synthetic profiles can expand the breadth and repeatability of engineering tests. Only actual participant sessions can supply usability observations, satisfaction scores and user acceptance evidence.
