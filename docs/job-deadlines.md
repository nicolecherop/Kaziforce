# Job application deadlines

Recruiters can optionally choose an **Application deadline** when publishing or editing a permanent job. Blank means the job stays available until manually closed. The selected date includes the full day: applications stop at midnight immediately after it, in the project's configured Africa/Nairobi timezone (EAT).

Expiration is checked on each request, so no scheduler is needed. Expired jobs are excluded from job browsing, fresh matching inputs, saved candidate recommendations and open-job dashboard counts. Deadline details are visible on job pages and recommendation rows. The recruiter list shows **Deadline passed**, while admin offers application-availability and deadline filters.

Both the application page and the locked submission service enforce availability. Direct links, stale pages and old drafts cannot bypass the cutoff. Existing submitted applications, interviews, attachments and recruiter rankings remain available. Drafts are retained but cannot be edited or submitted while the job is unavailable.

To extend an expired job, choose today or a future date, or clear its deadline. This makes an otherwise-open job available again. A manually closed job remains closed until the recruiter explicitly selects **Reopen applications for this job** and saves with a valid deadline or no deadline. Reopening asks for browser confirmation. **Close job** continues to close a posting immediately, even before its deadline.

New or changed deadlines cannot be in the past. An unchanged historical deadline does not prevent the recruiter editing other job information. Model validation applies the same rule in admin and prevents reopening with an expired deadline. Dates are also constrained in date-picker inputs.

The nullable, indexed `jobs.application_deadline` field is added by migration `jobs.0004_jobposting_application_deadline`. Existing postings are left without a deadline. No existing job is closed or assigned an invented date during migration. Saved matching evidence and previously submitted application copies are not rewritten. New applications record the deadline as it was at submission.

The stored `status` remains the recruiter's explicit open/closed choice; effective availability also accounts for the deadline. This preserves the distinction between expiry and a recruiter deliberately closing a job.

Validation covers cutoff-day inclusion, EAT midnight boundaries, deadline extension and removal, manual closure and explicit reopening, ownership, stale saved recommendations, direct draft/submission attempts, existing application access, admin summaries and availability filters. Run `manage.py test tests.test_job_deadlines --keepdb` and `node --test tests/confirmations.test.cjs` from the project environment.
