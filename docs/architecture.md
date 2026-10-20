# Architecture and implementation boundaries

KaziForce uses Django templates for presentation, Django apps for application logic and PostgreSQL for persistence. Each page has a descriptive template filename. Shared navigation, footers and repeated interface elements belong in `templates/components`.

Views coordinate requests. Forms validate submitted input. Models describe records and database constraints. Services contain CV processing and matching operations, independent of HTTP requests. Introduce modules when they have real responsibilities rather than filling the project with empty files.

The custom user model is established before the first migration. Its role describes the product role. Django staff and superuser permissions separately control admin access; assigning an administrator role alone does not grant admin access.

Chapter 4 of the supplied proposal defines the detailed feature requirements. The supplied mockups define the visual direction. Rankings support human decisions. Scores must exclude personal identity attributes and preserve input, ESCO and matching configuration provenance. CV data belongs in protected storage and must never be served as public static assets.

The scoring formula, skill priority scale, CV format and size limits, application status transitions and evaluation metrics still need explicit implementation decisions. Do not invent claims of matching accuracy before evaluation.

## Delivery stages

1. Foundation and configuration.
2. Approved public pages, video hero, registration and sign-in.
3. Profiles, reviewed CV extraction, jobs and applications with ownership checks.
4. Versioned ESCO catalogue, reproducible scoring, explanations and top-ten results.
5. Workflow, access-control, matching evaluation and browser verification.

## Public pages and account implementation

The public page stage implements registration for candidates and recruiters, case-insensitive email sign-in, POST-only sign-out, password reset and protected role-specific entry pages. Those entry pages explicitly identify workflows that are still under development. Django's built-in model authentication, password hashing, password validation, CSRF middleware, session handling and reset-token mechanisms remain the basis of authentication.

`accounts/forms.py` validates identity and credentials. `accounts/views.py` coordinates account creation and role dispatch. `accounts/urls.py` binds named endpoints, including Django's password reset views. Registration creates an internal random username; the public interface asks for email. Database constraints continue to enforce case-insensitive email uniqueness, including concurrent submissions.

No profile, job, application or scoring data is fabricated. The matching implementation remains independent of the page and account stage.

## Candidate profiles

`CandidateProfile` has one account owner. `CandidateSkill`, `Education`, `Certification`, `WorkExperience` and `PortfolioLink` hold repeatable records. Skill names retain the candidate's terminology until the ESCO stage. The profile timestamp changes on each saved edit, including changes to related records.

`selectors.py` reads an owner-scoped profile with prefetched related records. `forms.py` validates profile data. `views.py` checks the candidate role, binds every formset to the session user's profile, validates all sections and commits the edit atomically. Posted entry and parent IDs are untrusted; foreign entries invalidate the submission, even if marked for deletion. Formsets have row limits. Candidate text is escaped, and validated links open with `noopener noreferrer`.
