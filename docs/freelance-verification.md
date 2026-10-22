# Freelance engineering verification

Date: 21 October 2026. These checks concern the optional freelance module, not a new
study of employment matching accuracy. Earlier evaluation evidence remains unchanged.

## Automated checks

- Full Django suite on PostgreSQL: **221 tests passed** (186 existing and 35 freelance).
- Freelance checks cover the full booking/deposit/balance/completion/review lifecycle,
  participant-only access, private contact exclusion from listings, contact snapshots,
  opt-in, inactive listings, form ownership, service-entry tampering, project editing,
  invalid dates/deposits, cancellation/refunds, unread notices, blocking/reporting,
  HTML escaping, CSRF, POST-only payment actions and read-only admin evidence.
- Three independent-transaction PostgreSQL checks verify that simultaneous overlapping
  acceptances reserve dates only once, simultaneous payment reports cannot exceed the
  balance and simultaneous enquiries reuse one conversation.
- Recommendations exclude inactive/busy workers and unrelated skills for a selected
  project. Hidden reviews do not affect ratings. New workers remain eligible.
- Django system checks: no issues. Migration drift check: no changes detected.

Command, using the pre-created isolated test database:

```powershell
.\.venv\Scripts\python.exe scripts/check_postgres.py test tests --keepdb --noinput
.\.venv\Scripts\python.exe scripts/check_postgres.py makemigrations --check --dry-run
```

## Browser inspection

Inspected the freelancer directory, project selection, booking navigation, agreement
details, confirmed cash receipt, outstanding balance, candidate freelance listing and
profile editor through an isolated local preview with fictional SQLite records.
Verified Add service inserts labelled fields and produces no browser console error.
The preview used separate session cookies and no external email/payment delivery.
It does not populate the working PostgreSQL database or disclose real contacts.

These are desktop browser checks. Mobile/device coverage, screen-reader testing and
human acceptance remain **Pending** in `docs/user-acceptance.md`. No accessibility
conformance, production penetration test or live payment-provider verification is claimed.

## Rollout checks

The rollout creates only the new freelance tables, permissions and source files.
Existing business rows, saved scores, `.env` and private uploads are compared using
before/after fingerprints. A PostgreSQL custom-format backup and source backups are
created before installation. Live checks use temporary sessions without changing
accounts, passwords or submitted records; those sessions are removed afterwards.

M-Pesa collection, callbacks, payouts and escrow are not connected or tested. Payment
receipts are participant confirmations. Google sign-in, Meet and Gmail remain deferred.

## Follow-up: no-deposit workflow

The no-deposit update passed **225 PostgreSQL tests** (186 existing and 39 freelance),
with no migration drift. The additional checks reject new advance requirements and
reports, ignore forged deposit form fields, hide a recruiter's saved contacts before
acceptance, unlock both parties' contacts on acceptance without payment, and require
recruiter-confirmed completion before work-payment reports. Earlier advance-payment
records remain readable, confirmable and refundable. An old pending request requiring
an advance cannot be silently converted or accepted; it must be withdrawn and replaced.

The follow-up rollout fingerprints include all freelance tables as well as the existing
business records, saved scores, environment and private files. No schema or historical
record changes are required. Existing desktop layout is retained; this follow-up uses
automated form/HTTP checks, not a new device/accessibility acceptance session.

## Follow-up: pre-booking contact controls

The contact-privacy update passed **245 PostgreSQL tests** (225 previous and 20 new).
Tests cover emails/phones/links/social handles, ordinary work text, prices and dates,
field validation, rejected-write rollback, per-pair unlocking, portfolio HTML exclusion,
legacy display masking and continued HTML escaping. No migrations are required. Desktop
browser inspection in a separate fictional preview verified the actual portfolio lock
and rejected phone-number warning with no console errors. See
`docs/freelance-contact-privacy.md` for the supported formats and practical limits.
