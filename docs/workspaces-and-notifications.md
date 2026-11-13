# Workspaces and notifications

## Using both workspaces

Open the account menu and choose **Switch to Recruiter** or **Switch to Candidate**. The first switch enables that workspace. One email, password and Google connection serve both workspaces. Existing profiles, applications, jobs and bookings are retained. Staff permissions are unchanged; the switch cannot grant administration access.

The selected workspace is saved in the current session. Other devices can use a different workspace. Signing out clears the selection; the original account role remains the default. Candidate profiles and freelancer listings remain valid while their owner uses the recruiter workspace. Accounts cannot apply to their own jobs or book themselves.

## Updates and decisions

**Notifications** in the account menu lists private updates from both workspaces. Opening an update marks it read and selects its workspace before showing the relevant record.

- Application submission: acknowledgment to the candidate and notice to the recruiter.
- Application decisions: status update to the candidate. Saving an unchanged status creates no alert.
- Interviews: an in-app update accompanies the existing invitation/update/cancellation email service; no second email is sent by this feature.
- Booking requests, decisions, completion, cancellation, payment reports and reviews: update to the other participant.
- Verified M-Pesa collection success: update to both participants. An unsuccessful payment update goes to the recruiter. Collection is not evidence of a worker payout.

Chat messages do not trigger email alerts. Historical activity is not backfilled or emailed.

## Preferences and delivery

**Notification settings** controls application and booking update emails for the entire account. In-app notifications remain available. Security codes, password resets and existing interview invitations are separate from this preference. Updates go to the account email, not an address typed into a CV or profile contact field.

Inactive accounts, unverified public registrations and reserved example/test email domains are skipped. Email sending occurs synchronously after the business transaction commits. A transport failure does not undo a decision; its notification remains available. Event keys and locked delivery records prevent ordinary duplicate sends. SMTP cannot guarantee exactly-once delivery after an uncertain connection failure.

Set `DJANGO_SITE_URL` to the site's trusted public origin for email links. The local default is `http://127.0.0.1:8001`, which only works on the machine running the app. Gmail/SMTP settings remain in the private environment file.

Administrators can explicitly retry pending or failed update emails:

```powershell
python manage.py retry_update_emails --limit 50
```

This command sends real email when SMTP is configured. It does not resend records marked sent or skipped. It is not a scheduled background worker; configure scheduling separately if required. Interview emails retain their existing retry mechanism.

## Data and verification

The `users` table gains candidate/recruiter workspace flags and the email preference. The `notifications` table stores the recipient, event key, destination workspace/path, message, read state and delivery state. Existing original roles are retained, with access checks using the selected workspace and model validation using workspace membership.

Automated tests cover switching, CSRF, session isolation, private records, self-application/booking prevention, preferences, delivery failures/retries, rollback and duplicate events. They use an in-memory email backend, not real inboxes.

Manual acceptance: switch in both directions; create and review records in their appropriate workspace; submit an application and change its status; open the resulting notification; disable update email and repeat with an authorized test account. Check booking acceptance/completion similarly. Confirm profile and existing hiring records are retained.
