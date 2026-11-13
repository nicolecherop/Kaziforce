# Expanded local accounts and listings

The frozen `synthetic-v2` scenarios can be explored through the local KaziForce website as well as the offline evaluation. Run from the project directory:

```powershell
.\.venv\Scripts\python.exe scripts/import_evaluation_data.py
```

This development-only command first creates a PostgreSQL backup under `.backups/expanded-import-<timestamp>/before-import.dump`. It adds 200 fictional candidates, ten nonprivileged recruiters, 60 freelance profiles, 40 permanent jobs, 20 projects and 400 submitted applications between the new accounts. Existing accounts, roles, passwords, listings and uploaded documents are preserved.

## Sign in and explore

Open `.backups/expanded-accounts-v2-signin.md` for all names, emails, roles, source scenario IDs and the generated shared password. This private local file and its JSON import manifest are ignored by Git. The accounts use the reserved `people.kaziforce.test` domain and do not receive mail.

- Candidate example: `amina.kiptoo.001@people.kaziforce.test`.
- Backend recruiter: `recruiter.backend@people.kaziforce.test`.
- Each professional field has one recruiter who owns four jobs and two freelance projects.
- Candidates have two submitted applications each. New recruiters can review their own applicants and saved rankings immediately.
- Initial recommendations are prepared for one candidate in each field; other candidates can choose **Update my matches**. Normal eligibility rules and the current 60% threshold apply, so some profiles legitimately have no recommendations.
- All 60 freelance profiles are present in admin. Search shows only profiles allowed by active status, sharing, availability and other current filters. Ten profiles start with booking availability switched off, and ten have a later availability date.

Use the dedicated recruiter account to explore its workspace. Existing recruiters do not automatically own the imported jobs or gain access to someone else's applications. Administrators can inspect imported records in the admin panel.

These accounts are prepared directly through the local data import rather than public registration. They use the existing preprovisioned-account sign-in flow. To test first-time email verification or delivery, register a separate account with a real inbox; do not use reserved `.test` addresses. No changes are made to public registration, email-code enforcement for real signups, or admin verification.

## Data adaptations

The professional skills, summaries, education and experience come from the frozen v2 scenarios. Display names, employer names and training institutions are fictional but use ordinary website wording. Project dates and freelance availability are shifted relative to the import date so scheduling remains usable. No supporting documents are invented or uploaded.

The offline evaluation's fictional review histories, historical bookings, ratings and payment records are **not imported**. Actual user interactions should create those records through the normal site workflow. Consequently live freelance ordering can differ from the offline report. Existing human-review materials and historical evaluation reports are not rewritten by this command.

## Safe repeat runs

The import records exact account and listing identities in `.backups/expanded-accounts-v2.json`. Rerunning verifies the recorded cohort and preserves edits and passwords; it does not create duplicates or reset profiles. If a reserved identity already exists without its manifest, or recorded ownership changes, the command stops for manual review. There is no automatic destructive cleanup operation.

Credentials for these local accounts must stay in the ignored `.backups` directory. The importer is intended for the local development database and refuses a configuration with `DEBUG=False`.
