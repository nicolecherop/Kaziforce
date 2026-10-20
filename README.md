# KaziForce

A Django candidate–job matching application under development. The matching engine will use ESCO skill standardization, TF-IDF, cosine similarity and recruiter skill priorities.

## Current stage

The public landing page follows the approved video-hero layout, with responsive lower sections. Sign-in and registration use the approved photo-and-form layouts. Candidate and recruiter registration, email sign-in, CSRF-protected sign-out and password reset are connected. Signed-in users reach role-specific start pages; profiles, jobs, applications and matching are the next stages.

## Local setup on Windows

Use Python 3.12 or later. Run these commands inside this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
Copy-Item .env.example .env
```

Set a random `DJANGO_SECRET_KEY` in `.env`. For PostgreSQL, create a database and user matching the `POSTGRES_*` settings and supply the password. PostgreSQL is the default. For a local prototype without PostgreSQL, explicitly set `DATABASE_ENGINE=sqlite` in `.env`.

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

- `config`: project configuration and root routes.
- `accounts`: user identity, authentication and roles.
- `candidates`: candidate profiles and CV processing, to be implemented.
- `jobs`: recruiter information, postings and skill requirements, to be implemented.
- `applications`: submissions and status tracking, to be implemented.
- `matching`: independent preprocessing, ESCO mapping and scoring services, to be implemented.
- `pages`: public page routes.
- `templates`: one named template per page plus shared components.
- `static`: styles, scripts and approved public media assets.
- `tests`: cross-module tests. Feature-specific tests can live in their app.
- `docs`: architecture and implementation decisions.

## Verification

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test tests
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

If Node.js is available, run `node --test tests/video.test.cjs` to check reduced-motion, save-data, background playback and failure fallbacks. Node is only needed for these front-end checks; the application runs on Django.

Run database tests against PostgreSQL before release. SQLite checks alone do not establish PostgreSQL compatibility.
