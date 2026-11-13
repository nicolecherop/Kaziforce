# Job deadline verification ? 12 November 2026

The full regression suite passed **392 Django tests** against the existing separate PostgreSQL test database. The run set `EMAIL_TWO_STEP_ENABLED=False` only inside its test process for legacy business tests; security-specific tests explicitly enable their required settings. The application configuration was not weakened. All **9 JavaScript confirmation checks** passed separately, including job reopening and admin deadline changes.

Deadline-specific coverage includes the whole cutoff day and EAT midnight, optional deadlines, past-date validation, publication, extension/removal, explicit reopening, retaining manual closure, owner-only changes, stale recommendation filtering, direct request and service-level submission blocking, draft preservation, submitted application access, continued recruiter ranking and admin availability summaries/filters.

Migration `jobs.0004_jobposting_application_deadline` was applied to local PostgreSQL after a private database backup. Schema verification found the new nullable indexed deadline field and no ungenerated migrations. All 45 existing postings retained an empty deadline; none were automatically assigned a date or closed.

Existing historical evaluation reports remain unchanged. This is automated functional evidence, not human user acceptance or browser visual/accessibility certification. External payment-provider calls in the regression suite are mocked.
