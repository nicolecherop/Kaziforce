# Engineering verification

Date: 21 October 2026.

| Check | Observed result |
| --- | --- |
| `scripts/check_postgres.py test tests --keepdb --noinput` | 143 tests passed on the dedicated PostgreSQL test database; Django reported no system-check issues |
| `scripts/check_postgres.py makemigrations --check --dry-run` | No changes detected |
| `scripts/evaluate_project.py` | 100 labelled pair scores; 8 behavioral checks and 30 HTTP workflow checks passed |
| Repeated evaluation | Identical full-precision ranking digest: `b2276225b72412c467f5df81aa8c434b52fd6d760c97c87d43fa22e9019ebfcf` |

The seven new regression tests check hand-calculated metric values, cutoffs, undefined cases, grade ties, invalid rankings and dataset completeness. The remaining tests cover existing authentication, profile, job, application, private-file, matching and database behavior. No production scoring formula or schema was changed for this evaluation.

See [the generated report](report.md) for relevance results and limitations. This record does not claim independent reviewer agreement, participant testing, browser accessibility conformance or Gmail delivery. Human acceptance remains [pending](../user-acceptance.md).
