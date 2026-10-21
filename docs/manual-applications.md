# Manual profiles, original documents and job applications

The project owner replaced CV extraction with manual professional profiles and original documents for recruiters to read. Skills, education, certifications, experience and portfolio details come from candidate input. No document text is extracted or imported into profiles. ESCO standardization and matching use explicitly entered professional data; see [matching](matching.md) and the [initial synthetic evaluation](evaluation/report.md).

## Candidate workflow

1. Enter professional information in My profile.
2. Upload optional CVs (PDF/DOCX) and degree/certificate evidence (PDF/JPG/PNG) in CV & documents. Scans are accepted. Format/signature checks do not perform document parsing or extraction. The DOCX check examines ZIP entry names only.
3. Browse open jobs. Start application pre-fills an independent copy of the saved profile.
4. Keep the information unchanged or tailor it for the job. Save a private draft to return later, or select attachments and submit.
5. Follow the status in My applications. Submitted content is read-only; editing the main profile only affects future applications.

Each library file is limited to 5 MB, each candidate can keep 20 files, and an application can include up to 10. Candidates can add degree/certificate records manually in their profile and upload evidence separately under the corresponding document type. Documents are not automatically verified qualifications.

## Recruiter workflow

Recruiters publish, edit and close their own job postings. Jobs include title, company, location, description and written requirements. Their applicant list includes submitted applications only. Recruiters can read the candidate's submitted profile, open/download independent copies of the chosen documents and set Submitted, Under review, Shortlisted or Unsuccessful status. Matching scores support manual review and do not make automatic hiring or rejection decisions.

## Application copies

`applications/services.py` serializes a strict set of profile form fields into a JSON snapshot. Submitted rows are never saved into the main profile models. Profile validation is reused for dates, required fields, links and duplicate skills. An application is unique per candidate/job pair.

Drafts retain their own editable snapshot and references to selected library documents. At submission, candidate identity, job details and submission time are recorded, and files are copied into an application-specific private directory. Candidates explicitly submit this copy. The job's recruiter can read it even if the candidate later deletes the original library file. Profile changes, job edits and duplicate submissions cannot rewrite the submitted snapshot or add duplicate attachments.

Application records and attachment metadata save atomically. If copying fails, the transaction rolls back and newly copied files are removed. The service locks the candidate/job/application on databases supporting row locks. SQLite verification does not establish PostgreSQL concurrency guarantees.

## Storage and access

`PRIVATE_DOCUMENT_ROOT` is `private_uploads/`, excluded from Git and public media routes. File storage does not provide public URLs. Authenticated endpoints check document ownership or submitted-application access, serve attachments/inline PDF or image responses with `nosniff`, and disable caching. Word files download for viewing in an external reader. File signature checks are not malware scanning; before public deployment, add upload/request limits, scanning, account abuse controls, backups and retention/deletion procedures.

Deleting a library original leaves submitted copies in place. Deleting a candidate account removes its applications and schedules original/copy file cleanup after commit. Submitted application self-service deletion is not yet implemented. Job records referenced by applications are protected from deletion; closing a job preserves those records. Administrative deletion requires a deliberate retention process.

Migration `candidates.0003_manual_documents` renames the old CV table, preserves original file locations under `cvs/`, adds document categories and removes extraction-only columns. Historical migration `0002` and its storage callable remain solely for database migration compatibility. Existing saved manual profile data is unchanged. Back up existing databases before applying the migration.

## Source layout

- `candidates/document_forms.py`, `document_views.py`, `storage.py`: private library and file validation/access.
- `jobs/`: job records, forms, recruiter ownership, browsing and administration.
- `applications/`: snapshot forms/services, drafts, submission, applicant access and statuses.
- `templates/workspace/base.html`: shared candidate/recruiter shell.
- Separate page templates under `templates/candidates`, `templates/jobs` and `templates/applications`.
- `static/css/workflow.css`: document, job and application styles.
- `tests/test_manual_applications.py`: workflows, privacy, validation, immutable copies and failure rollback.

The proposal's extraction requirements are superseded by this documented owner instruction. The synced proposal itself has not been edited.
