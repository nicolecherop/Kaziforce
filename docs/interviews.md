# Contact information and interview invitations

Candidates add optional email and phone contacts under **My profile → Contact information**. Applications copy these contacts and allow separate details for each job. A blank contact email falls back to the account email saved at submission. Contact changes never change sign-in details, submitted applications, matching scores or matching staleness. Old applications without contact fields remain readable; they are not backfilled from today's profile.

## Recruiter flow

1. Open an application, select **Shortlisted**, and save the status.
2. Select **Set up interview** and enter the schedule, format, joining details, instructions and recruiter contacts.
3. Save the invitation. The candidate sees it in their application; both participants see upcoming interviews on their dashboard.
4. Use **Edit interview** to change details, or **Cancel interview** with a message. Each change creates an email record. Repeated identical saves do not duplicate messages. Cancelled interviews can be scheduled again while the application remains shortlisted.

There is one current interview per application. New invitations default to **In person**, with the interview address shown before the optional video link. Editing an existing invitation keeps its saved format. Times use **East Africa Time (Africa/Nairobi, UTC+3)** and are stored as timezone-aware datetimes. Duration must be 15–480 minutes. Video calls require an HTTP(S) meeting link, in-person interviews an address, and phone interviews a recruiter phone number. A contact-person name and recruiter email are always required. Candidates contact the recruiter directly for a different time, further arrangements or to agree who makes a phone call. The site does not create a video meeting or calendar booking, place calls or provide chat.

An upcoming interview must be cancelled before changing the application away from Shortlisted. Interviews that have ended do not block later status updates. Scheduling does not change submitted evidence, application status, scores or rankings. An invitation is not a job offer.

## Communication and delivery

The invitation and a durable email record are saved in one transaction. Delivery runs after commit; delivery failure leaves the invitation available in the candidate's application. Recruiters see whether the latest email was sent, failed, remains pending or has no connected delivery. **Retry email** retries only the latest message. Sent and superseded messages are not resent. Sending confirms acceptance by the backend rather than receipt or reading by the candidate.

Email uses existing Django settings. Console, dummy and file backends do not count as delivery. SMTP requires a configured host, account and password; credentials are never stored in interview records. The sender is `DEFAULT_FROM_EMAIL`, replies go to the recruiter contact email, and the recipient is the email frozen in the application. Reserved example/test addresses are not sent through a real service. Interview emails do not attach uploaded documents.

Gmail configuration and real-inbox delivery remain separate verification steps. Tests use an in-memory email backend and send no real messages. Role, session, application-ownership and CSRF checks protect all actions; mutations are POST-only. Only the candidate and the recruiter who owns the job can read the invitation through the application.

## Tables and source

- `candidate_profiles`: optional `contact_email` and `phone_number` columns.
- `interviews`: one invitation per application, including schedule, format, recruiter contacts, cancellation message and timestamps.
- `interview_emails`: recipient/subject/body/reply-to snapshots for each change, plus delivery status, attempts and sent timestamp. Old messages preserve correspondence history when interview details change.

Migrations are additive. `applications/interview_forms.py`, `interview_services.py` and `interview_views.py` separate validation, workflow/delivery and HTTP routing. `templates/applications/interview_form.html` and `interview_cancel.html` are named pages. Shared invitation and upcoming-interview components keep both workspaces consistent.

Run `python scripts/check_postgres.py test tests --keepdb --noinput`. Tests cover contacts, snapshots, old applications, matching exclusion, schedule changes, timezone conversion, permissions, CSRF, escaping, email retries/failures, duplicate saves and rollback. Human acceptance and real-inbox delivery are not inferred from automated results.
