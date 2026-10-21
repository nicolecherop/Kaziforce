# Candidate and recruiter acceptance testing

Status: **Pending human testing.** The automated evaluation report is engineering evidence, not participant feedback or user sign-off. No test participants, satisfaction scores or completed sessions have been invented.

Agent-operated [browser workflow checks](browser-verification.md) were completed on 21 October 2026 using fictional data in a disposable preview, including desktop and mobile views. These provide additional implementation evidence; the Human result entries below still require actual participants.

Use the local demo or a separate disposable database with fictional data. Give each participant the tasks below without explaining each click. Record whether they complete the task, the time taken, errors, assistance needed and their own comments. Do not enter real CVs or personal details into an uncontrolled demonstration.

## Candidate session

| Task | Expected result | Human result |
| --- | --- | --- |
| Create a Candidate account and sign in | Candidate workspace opens; no recruiter controls | Pending |
| Add headline, skills, education, certification, experience and portfolio | Entries save and appear in the professional profile | Pending |
| Upload a CV, degree and certificate | Files remain private; no extraction or automatic profile changes | Pending |
| Request matches and open match details | Up to ten roles scoring at least 70% appear; details show the overall score, public requirements and general guidance without calculation breakdowns | Pending |
| View matches when none qualify | A clear empty state offers profile updates and browsing all open jobs without low-score filler | Pending |
| Add a skill with an unfamiliar or ambiguous name | The entered name remains visible with a plain-language acknowledgement or suggestion to be more specific | Pending |
| Open a job, tailor its application and save a draft | Application starts from the saved profile; tailoring leaves the main profile intact | Pending |
| Choose attachments and submit | Submitted application shows the selected files and cannot be edited | Pending |
| Change the main profile, then revisit the application | Submitted information remains unchanged | Pending |
| Check the application after recruiter review | Updated status and next-step wording are clear | Pending |
| Add contact information and tailor it for a job | Recruiter sees the submitted contacts; later profile edits leave that copy unchanged | Pending |
| Read an interview invitation and later update/cancellation | Date, EAT timezone, joining details and recruiter contacts are clear | Pending |

## Recruiter session

| Task | Expected result | Human result |
| --- | --- | --- |
| Create a Recruiter account and publish a job | Required/preferred skills, priorities, education and experience save correctly | Pending |
| Open applicants for the job | Submitted applications appear; candidate drafts do not | Pending |
| Request applicant rankings and inspect a match | Job selection, ranking table and review panel form a clear flow | Pending |
| Read a submitted profile and its attached evidence | Only shared application copies are available | Pending |
| Change a skill priority and refresh | Requirements are saved, old results are marked stale and new explanations reflect the change | Pending |
| Shortlist an applicant | Recruiter and candidate see the same updated status | Pending |
| Set up, edit and cancel an interview | Candidate sees the current details; recruiter sees accurate email status and can retry a failed message | Pending |
| Close the job | New applications stop; existing submissions remain available | Pending |

## Navigation and accessibility session

Try both workspaces at a desktop width and a narrow mobile width. Use keyboard navigation to reach menus, tabs, form controls, repeatable entries and submission buttons. Check visible focus, error messages, labels, contrast and reading order. Use a screen reader where available. Record problems as observed; automated HTML checks do not establish accessibility conformance.

## Matching relevance review

Ask at least two domain reviewers to independently judge a new, more varied set of fictional or appropriately consented profiles against job requirements **before** viewing the scores. Use the same 0–3 rubric as the baseline. Include paraphrases, alternative qualification wording, career changes, overlapping work periods, incomplete profiles and harder cases from the same professional field. Record disagreements and agree labels before scoring. Preserve `synthetic-v1`; save expanded labels as a new version. Do not report a larger or independent study until it has actually happened.

## Session record

Copy one record per session. Use participant codes rather than names in shared reports.

| Field | Record |
| --- | --- |
| Participant code and role | Pending |
| Date, browser, device/viewport and build/version | Pending |
| Tasks attempted/completed without help | Pending |
| Time and assistance per task | Pending |
| Observed problems and reproduction steps | Pending |
| Participant comments in their own words | Pending |
| Fixes required and retest outcome | Pending |
| Participant/reviewer acceptance | Pending |

Record blocking issues before optional refinements. After fixes, repeat the affected tasks and the automated evaluation. Gmail password-reset delivery remains a separate configuration and real-inbox test; this checklist does not claim it has been configured or delivered.
