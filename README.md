# KaziForce

KaziForce is a Django and PostgreSQL application for employment recruitment and short-term freelance work. Candidates maintain professional profiles, find suitable opportunities and track applications. Recruiters publish jobs, review applicants, arrange interviews and book freelancers.

## Features

### Candidates

- Maintain skills, work experience, education, certifications, portfolio links and contact information.
- Upload private CVs, degree documents and certificates. Information is entered manually; uploaded documents are not parsed or used for automatic extraction.
- Start an application from a saved profile, tailor a separate copy for the job, save a draft and select supporting documents before submission.
- View application progress and interview arrangements, including the recruiter's contact details.
- Request up to ten job recommendations with a match score of at least 60%, with general guidance for improving the profile.

### Recruiters

- Create, edit, publish and close jobs with structured skills, priorities, qualification and experience requirements.
- Read submitted applications and documents, review applicant rankings and update application statuses.
- Schedule, update and cancel interviews for shortlisted candidates. Physical meetings are the default; invitations share meeting details and recruiter contacts, with email-delivery tracking.

### Freelance work

- Candidates can create a freelance profile, list services and rates, and switch availability for new bookings on or off.
- Recruiters can find freelancers, publish short projects, discuss terms through private in-app messages and request bookings.
- Contact details unlock after the worker accepts the booking and agrees to share them. No deposit is required.
- Accepted bookings reserve the agreed dates. Completion, cancellation requests, payment reports and refund acknowledgements follow the saved agreement.
- Recruiters can leave one rating and review per completed booking. Completed-work ratings appear in freelancer discovery.
- Cash and direct payments are arranged outside KaziForce. The site records participant reports and confirmations; it does not collect, hold or transfer money.

### Accounts and administration

- Email-and-password sign-in and **Continue with Google**.
- New public accounts, including Google registrations, must confirm their email using a six-digit code before accessing a workspace.
- Codes expire after five minutes. Users can resend after one minute; only the newest code works.
- Optional email two-step verification for ordinary users; required email codes for staff when the feature is activated.
- Email password reset using expiring, single-use links. Google-only accounts manage their Google password through Google.
- Existing users connect Google from **Account security**; matching email addresses never automatically merge accounts.
- A branded Django administrator panel with model permissions, summaries, filtering and protected recruitment monitoring. Public registration cannot grant staff access.

## Technology and matching

- Python 3.12 or later; Django 5.2; PostgreSQL; django-allauth for Google identity and staged email-code sign-in.
- Django templates with shared components, CSS and JavaScript. Each page has a descriptive template file.
- A versioned local ESCO skill catalogue supports suggestions and skill-name standardization.
- Matching combines skill coverage, recruiter priorities, TF-IDF cosine similarity, education and declared experience. Saved runs retain their inputs, reference versions and explanations.

Candidates receive general recommendations; detailed score calculations are available to the recruiting owner. Recruiter rankings show up to ten applicants without the candidate recommendation threshold. All applications remain available for manual review. Scores describe profile alignment, are not hiring probabilities and never automatically change an application's status.

## Run locally on Windows

Run commands from the KaziForce project directory. The existing local checkout is:

```text
C:\Users\Nicole\Desktop\Assignments\IS Project 2\Kaziforce
```

For a new checkout, create a virtual environment and install the application dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create `.env` from the example only if it does not already exist:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Set a random `DJANGO_SECRET_KEY` and configure the PostgreSQL connection locally. Keep existing `.env` values when updating an installed project. The database names are:

| Purpose | Name |
| --- | --- |
| Application database | `kaziforce` |
| Application login | `kaziforce_app` |
| Separate test database | `test_kaziforce` |

The application login is not a PostgreSQL superuser and does not have database-creation privileges. Follow [PostgreSQL setup](docs/postgresql.md) for initial provisioning, connection settings, table names and backups. The existing local database is already configured.

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001
```

Open [KaziForce](http://127.0.0.1:8001/), [sign in](http://127.0.0.1:8001/accounts/sign-in/) or [create an account](http://127.0.0.1:8001/accounts/create-account/).

For a new staff account, run the following command and enter its credentials locally. Use a real email inbox because staff sign-in requires a code when email verification is enabled.

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Administration is available at [the administrator panel](http://127.0.0.1:8001/admin/). A product role alone does not grant Django staff permissions.

PostgreSQL stores application records and uploaded-file metadata. The actual private files remain in `private_uploads/`; they are not stored inside PostgreSQL. SQLite is available only when explicitly selected for a separate isolated environment.

## Configure email and Google sign-in

Credentials belong in the ignored local `.env`, never in the README, screenshots or source control. The existing installation has Gmail delivery and Google sign-in connected; a fresh checkout needs its own configuration.

For Gmail delivery, configure `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` and `DEFAULT_FROM_EMAIL`. Use a Google app password rather than the Gmail account password. After confirming receipt of the setup email, activate:

```dotenv
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_TWO_STEP_ENABLED=true
```

Check configuration without displaying credentials:

```powershell
.\.venv\Scripts\python.exe scripts/check_signin_setup.py
```

To explicitly send one setup message to the configured sender's own inbox:

```powershell
.\.venv\Scripts\python.exe scripts/check_signin_setup.py --test-email
```

New registrations cannot access a workspace if email delivery is unavailable. Existing sample accounts with non-deliverable addresses should not be enrolled in repeated email verification.

For Google, create a **Web application** OAuth client and save `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` locally. Register this exact authorized redirect URI:

```text
http://127.0.0.1:8001/accounts/auth/google/login/callback/
```

Restart Django after changing `.env`. The Google button appears when both credentials are configured. Only email and basic profile access are requested; this does not enable Gmail inbox access, Google Calendar or Google Meet. Use Chrome or Edge for Google sign-in if an embedded browser is rejected.

See [sign-in and email setup](docs/sign-in-setup.md) for the complete configuration, code limits, account linking and recovery boundaries.

## Matching reference setup

The existing installation has an imported ESCO catalogue. For a fresh installation, follow [skill standardization](docs/skill-standardization.md) to import the reference, then build the fixed public TF-IDF corpus:

```powershell
.\.venv\Scripts\python.exe manage.py build_matching_corpus
```

Candidates refresh recommendations from **My matches**. Recruiters open a job's **Applicants** and select **Review applicant rankings**. Refreshing creates a saved run; simply opening a page does not recalculate results. See [matching calculations and limitations](docs/matching.md).

## Project structure

| Directory | Responsibility |
| --- | --- |
| `config/` | Settings, root routes and administrator configuration |
| `accounts/` | Identity, registration, email verification, Google linking and roles |
| `candidates/` | Professional profiles, contact details and private document library |
| `jobs/` | Recruiter vacancies, requirements and candidate job browsing |
| `applications/` | Private drafts, submitted profile copies, attachments and interview workflows |
| `matching/` | ESCO reference import, skill lookup, scoring and saved matching evidence |
| `freelance/` | Services, projects, discovery, messages, bookings, payment reports and reviews |
| `mpesa/` | Sandbox-only Daraja collections, callback hints and authenticated status checks |
| `pages/` | Public pages and workspace presentation |
| `templates/` | Named page templates and reusable components |
| `static/` | CSS, JavaScript, fonts and public media |
| `tests/` | Cross-module regression and security tests |
| `scripts/` | Setup, configuration checks, data management and evaluation tools |
| `docs/` | Setup instructions, workflows, verification records and acceptance checklist |
| `evaluation/` | Versioned synthetic matching dataset and evaluation code |

The supplied photographs, video and official Google sign-in logo are recorded in [asset documentation](docs/assets.md). The homepage video respects reduced-motion and data-saving preferences.

## Security and privacy

- Django password hashing, validation and CSRF protection; case-insensitive unique account emails.
- Rate-limited sign-in, registration and code verification, with session-bound codes and limited attempts and resends.
- Workspace access is withheld until required verification succeeds. An email delivery failure does not bypass verification.
- Ownership checks protect profiles, applications, conversations, bookings and documents. Submitted applications retain their own profile and attachment copies.
- Private uploads are served through authorized routes, not public media URLs. Candidates choose the documents shared with an application.
- Staff access follows Django permissions. Protected monitoring records are read-only in administration; recruitment actions remain in the recruiter workspace.

Keep `.env`, `.env.postgres`, `private_uploads/` and `.backups/` private. Database exports include account and personal information. Back up PostgreSQL and private files together. For public deployment, configure HTTPS, production hosts, secure settings and `DJANGO_DEBUG=false`, and review recovery, retention and operational arrangements.

## Verification and remaining work

Run the regression suite against the separate, pre-created PostgreSQL test database:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test tests --keepdb
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

For focused authentication checks:

```powershell
.\.venv\Scripts\python.exe manage.py test tests.test_accounts tests.test_signin_security tests.test_registration_verification --keepdb
```

The latest full PostgreSQL regression run passed 327 tests, including 20 M-Pesa sandbox tests. It used the separate test database and isolated feature settings; tests that require email verification explicitly enable it. Payment-provider calls were mocked, so this result does not establish external Daraja connectivity or callback delivery. Google sign-in, Gmail delivery and first-time email confirmation have also been exercised with real accounts. Real-inbox password-reset testing, complete participant acceptance testing and final documentation consolidation remain outstanding.

If Node.js is available, `node --test tests/video.test.cjs` checks video playback and fallback behaviour. Node.js is not required to run the Django application.

The [matching evaluation report](docs/evaluation/report.md), [results](docs/evaluation/results.json) and [rankings](docs/evaluation/rankings.csv) describe a synthetic dataset of five jobs, twenty profiles and 100 relevance labels. These historical engineering results are separate from human acceptance testing and are not validated hiring accuracy. The evaluation workflow harness also needs rechecking against mandatory first-time email confirmation before its registration results are regenerated.

The expanded [v2 evaluation report](docs/evaluation/v2/report.md) adds 200 fictional profiles, 40 jobs, 60 freelancers and 20 projects: 8,000 employment pairs and 1,200 freelance pairs. Reproduce it with `.\.venv\Scripts\python.exe scripts/evaluate_expanded.py`. It runs in a disposable database with network access and payments disabled. The [expanded evaluation guide](docs/evaluation/expanded-guide.md) explains the metrics and the 400-pair blind review pack; independent human grades remain pending. Existing v1 evidence is preserved.

A sandbox-only M-Pesa collection flow is available on completed freelance bookings. It records test transactions separately and never settles a worker's actual payment balance. Connect your own Daraja sandbox credentials and HTTPS callback using the [M-Pesa sandbox guide](docs/mpesa-sandbox.md). Live M-Pesa collection, worker payouts, Phone/Apple sign-in, Google Calendar/Meet integration and public hosting are not included.

## Documentation

| Topic | Guide |
| --- | --- |
| Database, table names and backups | [PostgreSQL](docs/postgresql.md) |
| Authentication and email delivery | [Sign-in setup](docs/sign-in-setup.md) |
| Candidate profiles and application copies | [Manual applications](docs/manual-applications.md) |
| Job requirements | [Job requirements](docs/job-requirements.md) |
| Skills and matching | [Skill standardization](docs/skill-standardization.md), [matching](docs/matching.md) |
| Interviews and contacts | [Interviews](docs/interviews.md) |
| Freelance workflows and payment boundaries | [Freelance work](docs/freelance.md), [contact privacy](docs/freelance-contact-privacy.md) |
| Administrator permissions | [Administration](docs/administration.md) |
| Page layout and navigation | [Workspace design](docs/workspace-design.md) |
| Fictional accounts and records | [Recruitment sample data](docs/demo-data.md), [freelance sample data](docs/freelance-sample-data.md) |
| Participant testing | [User acceptance checklist](docs/user-acceptance.md) |
