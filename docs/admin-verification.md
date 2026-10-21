# Administration verification

On 21 October 2026 the full PostgreSQL suite passed **186 tests**, including 12 administration tests. They cover permission-aware counts, staff and inactive-user boundaries, email sign-in, draft privacy, searchable/filtered lists, immutable recruitment records, escaped submitted text, protected attachment downloads and unchanged saved evidence. Existing candidate, recruiter, interview, contact and matching tests also passed. The migration check reported no model changes.

An isolated SQLite preview with fictional records was verified over HTTP: the branded overview, linked stylesheet and read-only application/interview/email pages returned successfully. Temporary verification sessions were removed. Browser visual verification was unavailable because the browser connection could not be opened in this session. No visual or human-acceptance pass is claimed.

The development database had no active staff or superuser account at inspection. No staff privileges, passwords or existing account roles were changed. An administrator must create their own local account before using the panel. See [administration setup](administration.md#local-account-setup).
