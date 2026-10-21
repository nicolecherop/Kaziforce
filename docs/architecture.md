# Architecture and implementation boundaries

KaziForce uses Django templates for presentation, Django apps for application logic and PostgreSQL for persistence. Each page has a descriptive template filename. Shared navigation, footers and repeated interface elements belong in `templates/components`.

Application database tables have explicit readable names such as `users`, `candidate_profiles`, `jobs` and `applications`. The database is `kaziforce`; tests use `test_kaziforce`. See [PostgreSQL configuration](postgresql.md) for the full table map and transfer/verification procedure.

Views coordinate requests. Forms validate submitted input. Models describe records and database constraints. Services serialize manual profiles and preserve application copies independently of HTTP requests. Introduce modules when they have real responsibilities rather than filling the project with empty files.

The custom user model is established before the first migration. Its role describes the product role. Django staff and superuser permissions separately control admin access; assigning an administrator role alone does not grant admin access.

Chapter 4 of the supplied proposal defines the original requirements; the project owner's later instructions replace CV extraction with manual profile entry and recruiter-readable attachments. The supplied mockups define the visual direction. Future rankings support human decisions. Scores must exclude personal identity attributes and preserve input, ESCO and matching configuration provenance. Documents belong in protected storage and must never be served as public static assets.

The matching-v1 baseline combines weighted skill coverage, TF-IDF text similarity, education wording and declared experience. Recruiter priorities use Standard (1), Important (2) and High (3). See [matching](matching.md) for the formula, frozen reference, saved inputs, top-ten results and replay. Representative hiring-quality evaluation remains outstanding. CVs accept PDF/DOCX up to 5 MB; degrees/certificates accept PDF/JPG/PNG. There is no text extraction or page-count restriction. Do not invent claims of matching accuracy before evaluation.

## Delivery stages

The [initial synthetic evaluation](evaluation/report.md) measures rankings in both directions and checks complete HTTP workflows in an isolated database. Independent relevance review and [human acceptance testing](user-acceptance.md) remain pending; these results do not establish hiring accuracy.

1. Foundation and configuration.
2. Approved public pages, video hero, registration and sign-in.
3. Manual profiles, private documents, jobs and independent applications with ownership checks.
4. Versioned ESCO catalogue, reproducible scoring, explanations and top-ten results.
5. Workflow, access-control, matching evaluation and browser verification.

## Public pages and account implementation

The public page stage implements registration for candidates and recruiters, case-insensitive email sign-in, POST-only sign-out, password reset and protected role-specific entry pages. Those entry pages explicitly identify workflows that are still under development. Django's built-in model authentication, password hashing, password validation, CSRF middleware, session handling and reset-token mechanisms remain the basis of authentication.

`accounts/forms.py` validates identity and credentials. `accounts/views.py` coordinates account creation and role dispatch. `accounts/urls.py` binds named endpoints, including Django's password reset views. Registration creates an internal random username; the public interface asks for email. Database constraints continue to enforce case-insensitive email uniqueness, including concurrent submissions.

Production records are never fabricated. Automated fixtures use isolated databases. The optional [local demo dataset](demo-data.md) explicitly labels fictional accounts and jobs and records its own IDs for removal; it does not overwrite existing records.

## Candidate profiles

`CandidateProfile` has one account owner. `CandidateSkill`, `Education`, `Certification`, `WorkExperience` and `PortfolioLink` hold repeatable records. Skill names retain the candidate's terminology; recognized terms are resolved separately against the active ESCO catalogue. The profile timestamp changes on each saved edit, including changes to related records.

`selectors.py` reads an owner-scoped profile with prefetched related records. `forms.py` validates profile data. `views.py` checks the candidate role, binds every formset to the session user's profile, validates all sections and commits the edit atomically. Posted entry and parent IDs are untrusted; foreign entries invalidate the submission, even if marked for deletion. Formsets have row limits. Candidate text is escaped, and validated links open with `noopener noreferrer`.

## Documents and applications

`CandidateDocument` stores a private original, owner, kind and optional title. Uploading never creates or edits a profile. `Application` stores an independently editable profile copy for one candidate/job pair. On submission, it freezes candidate/job details and saves separate file copies as `ApplicationAttachment` records. Only the candidate and that job's recruiter can read submitted copies; drafts belong to the candidate alone. See [manual profiles and applications](manual-applications.md).

## Job requirements

`JobPosting` stores optional education and relevant experience requirements. `JobSkill` stores one named skill, Required/Preferred status and priority per row in `job_skills`. The job form validates all entries before saving the posting and skills in one transaction. Candidate job details display these requirements; new submissions freeze their values and display labels in the application job snapshot. See [job requirements](job-requirements.md) for boundaries and validation.

## Skill standardization

The `matching` app keeps immutable ESCO catalogue versions, concept URIs, preferred labels and alternative labels in three readable reference tables. A local resolver normalizes case, Unicode compatibility forms and whitespace while preserving technical punctuation. Only a unique exact normalized label maps automatically; ambiguous and unknown names remain intact and flagged. Profile/job pages display recognition separately from entered names. Submitted applications freeze both sides against the same catalogue and normalization version. See [skill standardization](skill-standardization.md). No uploaded documents are processed and no user information is sent to ESCO.

## Matching services

Workspace pages share a top bar and role-aware sidebar. Read-only dashboard selectors live in `pages/workspace.py`; templates and the optional workspace JavaScript manage section navigation, table selection and job preview. All selection endpoints filter by the session owner before retrieving a job, application or score. See [workspace design](workspace-design.md) for the candidate/recruiter routes and progressive enhancement behaviour.

`vectorization.py` implements versioned TF-IDF math. `corpus.py` builds and verifies the frozen public ESCO reference. `inputs.py` whitelists professional evidence and captures candidate or submitted-application copies. `scoring.py` is pure scoring logic. `services.py` saves complete runs atomically and supports checksum-verified replay. `result_views.py` applies role/ownership checks and displays private reviews using separate templates under `templates/matching/`. The existing `/skills/` lookup remains separate from `/matches/` review routes. Matching never changes application statuses or reads private document contents.
