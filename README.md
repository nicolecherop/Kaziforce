# KaziForce

A Django candidate–job matching application. Skill names are standardized against a versioned local ESCO reference catalogue. Matching uses TF-IDF, cosine similarity and recruiter priorities with saved evidence and explanations.

## Current stage

Candidates enter their professional information manually, including skills, education, certifications, work experience and portfolio links. CVs, degree documents and certificates are private attachments for recruiters to read. Candidates can start each job application with their saved profile, tailor an independent copy, save a private draft and choose attachments before submitting. Recruiters can publish, edit and close jobs with required/preferred skills, priorities, education and relevant experience requirements, read submitted applications and update their statuses. Local ESCO labels provide skill suggestions and deterministic standardization; all entered skill names remain visible with plain-language messages where needed. Candidates can request up to ten job recommendations scoring at least 70%, with an overall score and general guidance. Recruiters can review their ten highest applicant scores with detailed explanations and no minimum-score filter. Results preserve submitted evidence and reference versions.

## Local setup on Windows

The [administrator panel](docs/administration.md) at `/admin/` provides permission-aware summaries and read-only recruitment monitoring. Sign in with an active staff account's email and password.

Candidates can add contact details and tailor them for each application. Recruiters can schedule, update and cancel interviews for shortlisted applicants, share recruiter contacts and track email delivery. See [interview invitations and contacts](docs/interviews.md).

Use Python 3.12 or later. Run these commands inside this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
Copy-Item .env.example .env
```

Set a random `DJANGO_SECRET_KEY` in `.env`. PostgreSQL is the default. The local project uses database `kaziforce`, login `kaziforce_app` and test database `test_kaziforce`. See [PostgreSQL setup and table names](docs/postgresql.md) for the connection, transfer tools, backups and test instructions. For a separate SQLite-only prototype, explicitly set `DATABASE_ENGINE=sqlite` in `.env`.

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Open http://127.0.0.1:8000/. Keep `.env`, uploaded CVs and database files out of version control. Production requires a deployment-specific security review, HTTPS and `DJANGO_DEBUG=false`.

`requirements.txt` defines supported dependency ranges. `requirements.lock.txt` records the exact verified versions. Keep your own `.env` settings when updating the code. To preview temporarily with SQLite without editing `.env`, run `$env:DATABASE_ENGINE = 'sqlite'` in the server terminal before `runserver`.

## Accounts and email

Public registration accepts Candidate and Recruiter roles only. It never grants Django staff or superuser permissions. Email addresses are unique regardless of case. Password validation and salted hashing use Django's built-in authentication components. The internal username is generated; users sign in with their email address.

Password reset uses expiring, single-use Django tokens. In debug mode, messages appear in the server console instead of being sent. For delivery, configure `DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` and the `EMAIL_*` settings shown in `.env.example`. No outbound email service is configured by this implementation.

The Terms and Privacy pages describe the current academic prototype. They need review before public use. Before deployment, configure PostgreSQL and HTTPS, email delivery, retention and deletion procedures, and sign-in abuse protection.

## Front-end files

Each page is a named template under `templates/`. `components/` contains navigation, footer, icons and form controls. Shared styling is in `static/css/site.css`; page-specific styles are in `landing.css` and `accounts.css`. `site.js` handles password visibility and error focus. `landing.js` manages video playback, reduced-motion preferences and still-image fallback.

The supplied video is encoded as a roughly 2 MB, silent 1080p MP4 for browser delivery. Its poster is a frame from the video. It autoplays when motion and data preferences allow, without an on-page playback control or scroll prompt. Six distinct photographs supplied by the project owner are used once each across the public and account pages. Their source filenames and placements are recorded in `docs/assets.md`.

## Project layout

Candidate pages are `templates/candidates/dashboard.html`, `profile.html` and `profile_edit.html`, using a shared workspace layout. `forms.css` provides shared field styles; `candidates.css` styles the workspace. `profile.js` adds repeatable entries and maintains formset indices. Without JavaScript, each section supports one new entry per save.

- `config`: project configuration and root routes.
- `accounts`: user identity, authentication and roles.
- `candidates`: manually entered profiles, private CV/degree/certificate documents, forms and ownership checks.
- `jobs`: recruiter-owned vacancies, structured requirements and priorities, candidate job browsing and search. See [job requirements](docs/job-requirements.md).
- `applications`: independent profile copies, private drafts, immutable submitted attachments and status tracking.
- `matching`: ESCO imports and skill lookup, fixed public TF-IDF reference, profile/job scoring, private top-ten reviews and reproducible history. See [skill standardization](docs/skill-standardization.md) and [matching](docs/matching.md).
- `pages`: public page routes.
- `templates`: one named template per page plus shared components.
- `static`: styles, scripts and approved public media assets.
- `tests`: cross-module tests. Feature-specific tests can live in their app.
- `docs`: architecture and implementation decisions.

## Verification

The profile editor uses the signed-in account as its owner and rejects related entries from other profiles. It validates every section before saving everything in one transaction. Blank new entries are ignored. Skill names are unique per profile without case differences. Dates must be consistent, and external links accept HTTP or HTTPS only.

Run `manage.py migrate` after updating. After importing ESCO, run `manage.py build_matching_corpus` to prepare the fixed public scoring reference. Candidates use **My matches**; recruiters open **Applicants → Review applicant rankings**. Scores support manual review and do not change application status. See [matching setup, formula and limitations](docs/matching.md).

CVs accept PDF/DOCX, including scanned documents. Degree and certificate evidence accepts PDF/JPG/PNG. Files are limited to 5 MB, with up to 20 library documents and 10 attachments per application. File validation checks formats and signatures without extracting text. The extraction feature and parser dependencies have been removed. The replacement migration preserves existing CV originals and removes extraction-only database fields.

Documents use the Git-ignored `private_uploads/` directory; never expose it through a public media route. Candidates choose which files to share for a job. The recruiter owning that job can read submitted copies, while candidate drafts remain private. See [manual profiles and applications](docs/manual-applications.md) for source organization, ownership, snapshots, storage and deployment notes.

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test tests
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

If Node.js is available, run `node --test tests/video.test.cjs` to check reduced-motion, save-data, background playback and failure fallbacks. Node is only needed for these front-end checks; the application runs on Django.

For PostgreSQL, run `manage.py test tests --keepdb` using the pre-created `test_kaziforce` database. The dedicated application login does not have database-creation privileges. Tests include PostgreSQL concurrency verification; SQLite skips that test.

## Freelance work

Candidates can opt into freelance services through **Freelance work**. Recruiters can
find available workers, publish short projects, discuss terms, request bookings,
record cash/direct payments and review completed work. The employment flow remains
separate. Read [freelance setup, workflows and payment boundaries](docs/freelance.md).
Run `manage.py migrate` after updating to create the new PostgreSQL tables. M-Pesa
collection/payouts are not connected.

## Matching evaluation and acceptance testing

Run the isolated evaluation from this folder:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_project.py
```

This uses five fictional jobs, twenty profiles and 100 predeclared relevance labels with the full local ESCO reference. It measures rankings in both directions and checks the registration-to-application-to-recruiter workflow through actual HTTP forms with CSRF enforcement. A new temporary SQLite database, private storage and in-memory email keep it separate from development PostgreSQL, live accounts and uploads. No network download or email delivery is needed.

Read the [evaluation report](docs/evaluation/report.md), [complete results](docs/evaluation/results.json) and [ranking spreadsheet](docs/evaluation/rankings.csv). These are initial synthetic engineering results, not validated hiring accuracy or completed participant testing. The [human acceptance checklist](docs/user-acceptance.md) records the user testing still to be done. Keep the original `evaluation/dataset-v1.json` labels unchanged; expand future evaluation in a new dataset version.

## Demonstration data

The candidate and recruiter workspaces follow the supplied dashboard, profile, ranking and application mockups, with shared navigation, review panels and responsive tables. See [workspace structure and page flow](docs/workspace-design.md).

For fictional candidate profiles, jobs, submitted applications and ready-to-view matching results, see [local demo data](docs/demo-data.md). The helper records demo IDs separately, preserves existing accounts and supports removing the recorded batch.
