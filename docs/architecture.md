# Architecture and implementation boundaries

KaziForce uses Django templates for presentation, Django apps for application logic and PostgreSQL for persistence. Each page has a descriptive template filename. Shared navigation, footers and repeated interface elements belong in `templates/components`.

Application database tables have explicit readable names such as `users`, `candidate_profiles`, `jobs` and `applications`. The database is `kaziforce`; tests use `test_kaziforce`. See [PostgreSQL configuration](postgresql.md) for the full table map and transfer/verification procedure.

Views coordinate requests. Forms validate submitted input. Models describe records and database constraints. Services serialize manual profiles and preserve application copies independently of HTTP requests. Introduce modules when they have real responsibilities rather than filling the project with empty files.

The custom user model is established before the first migration. Its role describes the product role. Django staff and superuser permissions separately control admin access; assigning an administrator role alone does not grant admin access.

Chapter 4 of the supplied proposal defines the original requirements; the project owner's later instructions replace CV extraction with manual profile entry and recruiter-readable attachments. The supplied mockups define the visual direction. Future rankings support human decisions. Scores must exclude personal identity attributes and preserve input, ESCO and matching configuration provenance. Documents belong in protected storage and must never be served as public static assets.

The scoring formula and evaluation metrics still need implementation decisions. Recruiter priorities use Standard (1), Important (2) and High (3); no matching scores are calculated yet. CVs accept PDF/DOCX up to 5 MB; degrees/certificates accept PDF/JPG/PNG. There is no text extraction or page-count restriction. Do not invent claims of matching accuracy before evaluation.

## Delivery stages

1. Foundation and configuration.
2. Approved public pages, video hero, registration and sign-in.
3. Manual profiles, private documents, jobs and independent applications with ownership checks.
4. Versioned ESCO catalogue, reproducible scoring, explanations and top-ten results.
5. Workflow, access-control, matching evaluation and browser verification.

## Public pages and account implementation

The public page stage implements registration for candidates and recruiters, case-insensitive email sign-in, POST-only sign-out, password reset and protected role-specific entry pages. Those entry pages explicitly identify workflows that are still under development. Django's built-in model authentication, password hashing, password validation, CSRF middleware, session handling and reset-token mechanisms remain the basis of authentication.

`accounts/forms.py` validates identity and credentials. `accounts/views.py` coordinates account creation and role dispatch. `accounts/urls.py` binds named endpoints, including Django's password reset views. Registration creates an internal random username; the public interface asks for email. Database constraints continue to enforce case-insensitive email uniqueness, including concurrent submissions.

No profile, job, application or scoring data is fabricated. The matching implementation remains independent of the page and account stage.

## Candidate profiles

`CandidateProfile` has one account owner. `CandidateSkill`, `Education`, `Certification`, `WorkExperience` and `PortfolioLink` hold repeatable records. Skill names retain the candidate's terminology until the ESCO stage. The profile timestamp changes on each saved edit, including changes to related records.

`selectors.py` reads an owner-scoped profile with prefetched related records. `forms.py` validates profile data. `views.py` checks the candidate role, binds every formset to the session user's profile, validates all sections and commits the edit atomically. Posted entry and parent IDs are untrusted; foreign entries invalidate the submission, even if marked for deletion. Formsets have row limits. Candidate text is escaped, and validated links open with `noopener noreferrer`.

## Documents and applications

`CandidateDocument` stores a private original, owner, kind and optional title. Uploading never creates or edits a profile. `Application` stores an independently editable profile copy for one candidate/job pair. On submission, it freezes candidate/job details and saves separate file copies as `ApplicationAttachment` records. Only the candidate and that job's recruiter can read submitted copies; drafts belong to the candidate alone. See [manual profiles and applications](manual-applications.md).

## Job requirements

`JobPosting` stores optional education and relevant experience requirements. `JobSkill` stores one named skill, Required/Preferred status and priority per row in `job_skills`. The job form validates all entries before saving the posting and skills in one transaction. Candidate job details display these requirements; new submissions freeze their values and display labels in the application job snapshot. See [job requirements](job-requirements.md) for boundaries and validation.
