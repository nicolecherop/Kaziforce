# Workspace structure and page flow

The three supplied workspace mockups guide page structure: a shared top bar and side navigation, compact overview cards, section-based profile editing, results tables and adjacent review panels. Existing typography, brand colours, public pages and account pages remain the visual foundation. Every full page stays in its own named template.

## Candidate flow

**Overview → My profile → My matches → Match details → Job details → Application editor → My applications**

Dashboard and My matches share a selector for up to ten available roles scoring at least 70%; the dashboard previews three and shows the same capped count. Candidate match details use a separate named template with an overall score, public requirements and general guidance. Recruiter calculation details stay in the recruiting owner's review page. See [matching rules](matching.md#candidate-recommendations-and-guidance).

The dashboard reads real saved profile-section, matching and application counts. The completion ring measures five professional sections, not eligibility for a job; the portfolio is optional. Visiting the dashboard never generates scores. Saved recommendations show a notice when outdated.

Profile view/edit pages have section navigation and a CV/document side panel. JavaScript displays one section at a time while keeping every form field submitted. Invalid sections are shown when server validation returns errors. Without JavaScript, all sections remain visible with working anchor links. Formsets retain their ownership checks and entry limits. The document library opens separately from an editor so unsaved form entries remain in the original tab. Profile information is manually entered; the mockup's extraction/import actions are intentionally not part of this workflow.

Applications use a status-filtered table and a selected application's progress panel. The full submitted copy and document links remain on the application detail page. Progress uses the current recorded status, submission date and most recent update date; it does not invent intermediate dates or claim to provide a complete status-change history.

## Recruiter flow

**Overview → My jobs → Create/edit job → Candidate matches → Match explanation → Submitted application → Update status**

Candidate matches has a job selector and a table showing the ten highest saved scores. Selecting a row uses a scoped GET parameter to display that result's skill evidence in the adjacent panel. The application and explanation links preserve the job/candidate context. The separate Applications page collects submitted applications across owned jobs, with status filters; private candidate drafts remain excluded.

Job creation/editing places role fields, skill priorities and qualifications alongside a live preview. Preview updates use text nodes only, never candidate-supplied HTML. Saving still uses the original validated transaction. There are no invented employment-type, job-draft, notification or bookmark controls.

## Source organisation

- `templates/workspace/base.html`: shared workspace frame and role-aware navigation.
- `templates/workspace/`: small icon and document-panel components.
- `templates/candidates/`, `jobs/`, `matching/`, `applications/`, `recruiters/`: named pages and their reusable components.
- `static/css/workspace.css`: workspace structure, panels, tables and responsive overrides using existing brand tokens.
- `static/js/workspace.js`: optional section navigation, job-picker submission, live preview and account-menu keyboard dismissal.
- `pages/workspace.py`: read-only dashboard summaries.
- `pages/templatetags/workspace_ui.py`: small presentation helpers.

The desktop layout retains its sidebar. On narrow screens, navigation becomes a horizontal strip, side panels stack below content and wide tables scroll inside their own container. No database schema or scoring formula changes are required for this design update.
