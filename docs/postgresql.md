# PostgreSQL configuration and table names

KaziForce uses PostgreSQL for local application development. The database is `kaziforce`, the dedicated login is `kaziforce_app`, and the separate test database is `test_kaziforce`. The application login owns these two databases but does not have superuser, role-creation, database-creation, replication or row-security bypass privileges.

## Application tables

| Table | Data |
| --- | --- |
| `users` | Accounts and product roles |
| `candidate_profiles` | Professional headline, location and summary |
| `candidate_skills` | Manually entered skills |
| `candidate_education` | Degrees and qualifications |
| `candidate_certifications` | Certification details |
| `candidate_experience` | Work experience |
| `candidate_portfolio_links` | Professional and project links |
| `candidate_documents` | Original private CV, degree and certificate metadata |
| `jobs` | Recruiter job postings |
| `job_skills` | Required/preferred skills and their recruiter priorities |
| `applications` | Draft/submitted profile copies, job copies and application statuses |
| `application_draft_documents` | Selected library document references |
| `application_attachments` | Private copies actually submitted with applications |

Names are explicitly configured with Django `Meta.db_table` and the many-to-many field's `db_table`. Django's internal authentication, session, administration and migration tables keep their framework names. Automatic user/group and user/permission join tables use `users_groups` and `users_user_permissions`.

The new table-name migrations rename existing tables; they do not recreate candidate data or change file paths. The user table rename depends on the other table renames so that historical SQLite migration reversal also rebuilds foreign keys consistently. Historical migrations retain their earlier table names for upgrade compatibility.

## Configuration

The active database settings live in the Git-ignored `.env`. The setup script saves draft PostgreSQL values in the also-ignored `.env.postgres`. Administrator credentials are requested privately and are never written to either file. The application password is generated separately.

For the existing local project, the setup has already been performed. Start with:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001
```

Do not set `DATABASE_ENGINE=sqlite` in that terminal when using PostgreSQL. Process environment variables take precedence over `.env`. If a terminal has an old override, remove it with `Remove-Item Env:DATABASE_ENGINE -ErrorAction SilentlyContinue` before starting.

Original uploaded files stay under private storage. PostgreSQL stores their references and metadata. Do not expose `private_uploads/` through public media routes or commit it to Git.

## Verification

The test database is pre-created, allowing tests to run with the restricted application login. Use `--keepdb` to reuse it without requiring `CREATEDB` permission:

```powershell
.\.venv\Scripts\python.exe manage.py test tests --keepdb
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

The test suite covers the table names, source migration preservation, profiles, documents, jobs, applications and authorization. A PostgreSQL-specific transaction test submits the same application from two independent database connections at once and checks that only one application and one attachment are saved. SQLite skips this row-locking test.

## Setup and transfer tools

- `scripts/setup_postgres.py`: prompts for the existing local `postgres` administrator password, creates the dedicated role/databases and writes draft credentials. It refuses to replace an unknown existing role or a populated database belonging to another owner.
- `scripts/check_postgres.py`: runs Django commands with draft PostgreSQL credentials before the active configuration is changed.
- `scripts/migrate_to_postgres.py`: with KaziForce servers stopped, backs up SQLite, the previous `.env` and private files; applies table renames to SQLite; exports records with natural foreign keys; builds an empty PostgreSQL database; imports the records; and verifies their values, IDs, file references and file hashes. Framework content types/permissions are recreated by migrations and resolved through natural keys.
- `scripts/activate_postgres.py`: compares source and target records again, then changes only database variables in `.env` atomically. It preserves the Django secret key and non-database settings.

Transfer tools refuse to overwrite a populated target. Keep all snapshots under the Git-ignored `.backups/` directory private: database exports contain account hashes and personal records. Original SQLite data and snapshots remain available after activation. Once PostgreSQL receives new writes, switching back to an older SQLite snapshot would lose those newer records; recovery must account for both databases.

Official references: [Django table names](https://docs.djangoproject.com/en/5.2/ref/models/options/#db-table), [PostgreSQL role privileges](https://www.postgresql.org/docs/18/sql-createrole.html), [Django data export](https://docs.djangoproject.com/en/5.2/ref/django-admin/#dumpdata).
