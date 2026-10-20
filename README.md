# KaziForce

A Django candidate–job matching application under development. The matching engine will use ESCO skill standardization, TF-IDF, cosine similarity and recruiter skill priorities.

## Current stage

The foundation includes environment configuration, a custom user model, admin registration, shared templates and three public page shells. Authentication forms, profile workflows, matching and the approved visual designs are not implemented yet. Public pages are scaffolding, not completed mockup implementations.

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

`requirements.txt` defines supported dependency ranges. `requirements.lock.txt` records the exact versions verified for this foundation. The task environment has an ignored `.env` with a generated secret and SQLite selected for local verification.

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

Run database tests against PostgreSQL before release. SQLite checks alone do not establish PostgreSQL compatibility.
