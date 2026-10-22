# KaziForce administration

Open `/admin/` and sign in with an active staff account's email address and password. Staff sign-in uses the same case-insensitive email lookup as the public pages, with an additional staff check. A product role of Administrator does not grant access by itself. Staff opening `/accounts/dashboard/` are directed to administration, including superusers whose product role was left at its default.

The branded index shows only summaries allowed by each staff member's model permissions: account totals and candidate/recruiter/inactive counts; total/open jobs; submitted applications and status counts; upcoming interviews; email-delivery history; saved matching runs and results. Cards open the corresponding searchable/filterable lists. Staff with no assigned model permissions see an access explanation without private counts. Existing account/profile/job management remains available according to Django permissions. This update does not create or change credentials, staff grants or account roles.

## Read-only recruitment monitoring

Applications, submitted attachments, interviews, email-delivery records, matching runs/results and scoring-reference metadata are available for inspection. Add, change, delete and bulk-delete controls are disabled for these records, including for superusers; forged change requests are rejected. Recruitment decisions, interview changes and email retries stay in the recruiter's workspace. Viewing administration never sends a message or recalculates a match.

Candidate drafts are excluded from application, attachment, interview and email monitoring, including direct object retrieval. Private candidate document-library originals are not registered in the admin panel. Submitted document downloads use a protected GET-only route requiring an active staff session and both application-view and attachment-view permissions. Draft attachments are rejected. Responses are private/no-store, and storage paths/public media URLs are not rendered.

Give private-record permissions only to staff who need them. Saved evidence and email records may contain personal information. Catalogue content still changes only through versioned import commands. Email credentials remain in environment configuration. Delivery counts include historical messages, including failures superseded by a later successful message. A sent status confirms sending rather than reading.

## Local account setup

If no administrator account exists, run this inside the project directory and enter the password locally:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Use that account's email and password at `/admin/`. Staff access and model permissions are independent of the product role. Public registration cannot grant administration access.

## Verification

`tests/test_admin_panel.py` covers summaries, permission isolation, staff/role/inactive boundaries, email sign-in, draft privacy, search/filters, read-only protections, escaping, protected downloads and unchanged saved records. Run `python scripts/check_postgres.py test tests --keepdb --noinput` against the dedicated PostgreSQL test database. Human acceptance remains a separate step.


### Confirming important decisions

The site asks for confirmation before completing or cancelling freelance work, accepting bookings, recording receipts, requesting M-Pesa payments, submitting applications and reviews, changing application status, sending or cancelling interviews, deleting library documents, closing jobs, blocking conversations, or disabling sign-in protections. Cancelling the prompt leaves the form available for editing and sends no request.

Admin saves ask for confirmation when account activation, staff/superuser access, roles, groups, permissions, ownership, status, review visibility, report resolution, or booking availability changes. Other admin bulk actions ask for confirmation; Django retains its existing individual and bulk deletion review pages. Routine unchanged saves do not prompt. These browser confirmations prevent accidental submissions; existing server-side permissions, payment verification, and transition validation remain authoritative.
