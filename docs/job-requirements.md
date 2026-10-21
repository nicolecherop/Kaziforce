# Job requirements

Recruiters enter structured requirements on `templates/jobs/job_edit.html`. Each skill has a name, a Required/Preferred choice and a priority: Standard (1), Important (2) or High (3). Required describes a skill the role needs; Preferred describes a useful extra. Priority expresses relative emphasis independently of that choice. The matching app uses these requirements in its scores and explanations; recruitment decisions remain with the recruiter.

## Data and validation

`jobs` retains the original description and additional requirements text. New columns store the minimum education level, accepted subject/equivalent qualification, education priority, minimum relevant experience in years, experience details and experience priority. Education defaults to no specific qualification; experience can be blank, zero or a number up to 60 with one decimal place. Zero explicitly describes an entry-level role; blank leaves the minimum unspecified.

`job_skills` contains one row per skill and a foreign key to `jobs`. Names are trimmed and repeated whitespace is collapsed. Names must be unique within a job without case differences. Choices, priorities and experience ranges are validated by forms; database constraints additionally enforce skill uniqueness, skill requirement choices, priority ranges and experience bounds. The editor accepts at most 40 skills and caps allocated forms at 80 when submitted management values are forged.

`jobs/forms.py` owns the posting form and skill formset. Foreign skill IDs invalidate a save even if marked for deletion. `jobs/views.py` scopes edits to the signed-in recruiter, validates both forms before saving and uses one transaction for posting/skill changes. Invalid fields or database conflicts leave the previous posting intact. Blank new rows are ignored. All skills can be removed; older free-text postings remain valid.

## Pages and application copies

The named job editor, candidate job detail page and application detail page remain separate files. Skill entry and requirements display markup live in `templates/jobs/components/`. `static/css/jobs.css` styles these components, and the existing `static/js/profile.js` adds repeatable rows with accessible labels and unique form indices. One new skill can be added per save without JavaScript.

`JobPosting.structured_requirements()` creates JSON-safe values and their display labels. On submission, `applications/services.py` adds these to `job_snapshot.structured_requirements` while holding the job row lock. Later job edits do not change submitted copies. Drafts use the requirements current at submission, and older submitted applications without this key remain readable without inventing historical requirements.

## Migration and checks

Apply `manage.py migrate` to add the columns and the `job_skills` table. The migration preserves existing jobs and their free-text requirements; it does not infer skills from descriptions or uploaded documents. Run `manage.py test tests --keepdb` against the separate PostgreSQL test database. Requirement tests cover complete saves, updates/removals, rendered form round-trips, duplicates, invalid values, ownership, row limits, transaction rollback, escaped output and frozen application copies.

Skill names retain the recruiter's terminology. The matching app standardizes recognized labels against ESCO and calculates priority-weighted scores without automatically rejecting candidates. See [matching](matching.md) and the [initial synthetic evaluation](evaluation/report.md).
