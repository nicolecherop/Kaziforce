# Matching and applicant rankings

Candidates open **My matches**, then **Update my matches**. Recruiters open a job's **Applicants**, then **Review applicant rankings**. A CSRF-protected POST calculates a new saved run; opening a page does not create records. Candidates see up to ten recommendations scoring at least 70%; recruiters see up to ten scored applicants without a minimum-score filter. Recruiters can still read every application, including applications without enough evidence to score. No matching operation changes application status.

## Evidence

Recommendations compare the candidate's current manually entered profile with open jobs, excluding jobs already applied to (drafts remain eligible). Recruiter rankings compare submitted application profile copies with the same current job requirements. Later profile edits cannot change submitted evidence. Refreshing rankings uses current job requirements; previous results retain their own saved inputs.

Scoring uses professional headline, summary, skill names, qualification and subject wording, certification names, experience titles/descriptions/dates, job title/description/additional requirements, and structured job requirements. Dedicated identity, contact, location, institution, employer, issuer, portfolio URL, cover letter and attachment fields are excluded. Free text may still contain personal information. Uploaded documents are never parsed. Certificates contribute their names to text similarity, not verified credentials.

## Versioned baseline: matching-v1

This is a deterministic, uncalibrated comparison baseline. It has no validated hiring-accuracy claim. A score is not a probability of success or confirmation of eligibility. Missing candidate evidence contributes zero within active components.

| Component | Base weight | Calculation |
| --- | ---: | --- |
| Skills | 50 | Matched requested skill weight / all requested skill weight. Each skill weight = priority (1–3) × 2 if required, or × 1 if preferred. |
| Overall text | 20 | TF-IDF cosine similarity between professional profile text and job text. |
| Education | 15 × education priority | TF-IDF cosine similarity of qualification/subject wording against requested level label and subject. |
| Experience | 15 × experience priority | Declared duration / minimum, capped at 1; relevant experience text cosine similarity when requested. If both are requested, their equal-weight mean. |

A component is inactive when the job has no corresponding requirement. Overall text is active when the job text contains non-stopword tokens. The total is `100 × sum(component value × effective weight) / sum(effective weight)`. Component shares are displayed to the recruiting owner only. Rankings use full precision; displayed percentages round to two decimals. Equal raw scores break by stable application/job UUID, never identity. Aliases map to one ESCO concept and cannot multiply credit; duplicate requirements use maximum priority and required status if any alias is required. Ambiguous/unrecognized skill names only match identical normalized wording; the interface keeps their original names and uses plain-language acknowledgements.

Education compares words, not qualification hierarchy or equivalence. Differently worded equivalent qualifications can score differently. Experience duration uses the union of valid declared dates, clips at the saved calculation date, and counts overlapping roles once. A year is 365.25 days; incomplete/future/invalid periods do not contribute. Duration includes all declared roles, so recruiters must assess relevance. Job-specific experience text supplies a separate relevance signal when requested. A zero-year minimum is fulfilled without experience.

## Fixed public TF-IDF reference

`python manage.py build_matching_corpus` builds one reference document per active ESCO skill, containing preferred label and description. No applicant or job text trains IDF. The vocabulary and document frequencies remain fixed as applicants/jobs change. Tokens use Unicode normalization/case folding, a small versioned stopword list, and preserve technical terms such as C++, C# and .NET. Out-of-vocabulary terms cannot contribute to cosine; explanations show their count. Unrecognized skills can still receive exact-wording skill-coverage credit.

For a term appearing `c` times, TF is `1 + ln(c)`. IDF is `ln((1 + N) / (1 + df)) + 1`, with N public reference documents and df document frequency. Vectors are L2 normalized; cosine is their dot product, or zero for an empty vector. These are the [standard smoothed IDF and sublinear TF definitions](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfTransformer.html). The project implements this small calculation with Python's standard library and adds no machine-learning runtime dependency.

## Storage, replay and permissions

- `matching_corpora`: frozen public document frequencies, catalogue provenance, tokenizer version and SHA-256 checksum.
- `match_runs`: requesting owner, review kind, optional job, corpus, full scoring configuration, calculation date and input checksum.
- `match_results`: score/rank or an explicit unscorable reason, saved professional inputs with checksum, component values and evidence explanation.

All results are stored. Candidate recommendations filter the latest saved run for strong, still-open, unapplied jobs before taking the first ten; recruiter review lists retain their original top-ten ranking. Review pages are owner-scoped and never cached. Only a job's recruiter can rank its submitted applicants. Candidates cannot view recruiter results; other users cannot retrieve private result UUIDs. Refresh errors roll back the whole run. Deleting an account/application removes related private results; referenced public corpora are protected from deletion.

`matching.services.replay_result(result)` recalculates using only stored inputs, calculation date, configuration and corpus, after checksum verification. Retain old tokenizer/scoring implementations when adding future versions; unsupported versions fail explicitly. Pages mark runs stale after professional inputs, eligible jobs/applications, active corpus, configuration or calculation date change. Existing history is preserved. Skill names are resolved against the same catalogue for each run without rewriting the original application mappings.

Synchronous requests refuse more than 500 eligible jobs or 1,000 submitted applications instead of silently truncating ranking input. Larger deployments should use queued matching and pagination. This baseline also needs representative evaluation and human review before any claim about hiring quality.

## Setup and verification

After the ESCO import described in [skill-standardization.md](skill-standardization.md):

```powershell
python manage.py migrate
python manage.py build_matching_corpus
python manage.py check
python scripts/check_postgres.py test tests --keepdb --noinput
```

The corpus build is idempotent. It refuses a changed reference under the same version. Matching tests cover hand-calculated TF-IDF, skill priorities/aliases, experience overlaps, saved-input replay, checksum corruption, private routes, CSRF, rollback, immutable submitted evidence, stable ties and top-ten presentation.

## Candidate recommendations and guidance

`MATCH_RECOMMENDATION_MIN_SCORE = 70` in `config/settings.py` controls candidate recommendation display. The threshold is inclusive, uses the stored two-decimal score, and is a product display choice rather than a validated eligibility or hiring cutoff. `matching/recommendations.py` supplies both dashboard and My matches, keeps saved rank order and limits the list to ten. The dashboard previews three and reports the same capped count. Closed jobs and jobs with a non-draft application are excluded even from an older saved run; drafts remain eligible. Find jobs continues to show all open roles, regardless of their saved score. No qualifying results produces a clear empty state without low-score filler.

Candidates see the overall percentage, public job requirements and general advice to maintain accurate professional information. Their separate `matching/candidate_match_detail.html` does not render skill-by-skill scoring evidence, component shares, review flags or scoring provenance. Recruiter-owned reviews retain the detailed evidence. Private historical candidate links remain accessible to their owner, including low scores, without claiming they are current recommendations. No GET recalculates a score or changes stored evidence.

The existing evaluation artifacts measure the full ranking baseline, before this display filter. They do not validate the 70% cutoff and have not been rewritten. Unit and integration tests cover the display boundary, limits, live eligibility changes, role separation and evidence preservation.
