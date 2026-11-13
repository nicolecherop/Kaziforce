# Saved jobs

Candidates can save or unsave roles from job browsing, recommendations and the job detail page. **Saved jobs** appears in the candidate sidebar and discovery tabs at `/jobs/saved/`.

Bookmarks belong to the signed-in candidate and are stored in `saved_jobs`, with one row per candidate/job pair. Saving is not an application and does not change matching scores. Closed and expired roles remain in the saved list with their current status; application eligibility still uses the normal deadline and closure checks. Lists show 20 bookmarks per page.

Mutations use CSRF-protected POST requests, explicit idempotent save/remove actions and owner-scoped queries. Return URLs are restricted to the current host. Recruiters cannot access this candidate feature. Saved state is annotated in queries rather than queried separately for every card.

Verification on 13 November 2026: all 42 focused saved-job, candidate-recommendation and job-deadline tests passed. Migration `jobs.0005_saved_jobs` was applied locally. No existing application, account role, email preference or matching score was changed. Visual participant testing remains pending.
