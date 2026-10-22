# Candidate and recruiter acceptance testing

Status: **Pending human testing.** The automated evaluation report is engineering evidence, not participant feedback or user sign-off. No test participants, satisfaction scores or completed sessions have been invented.

Agent-operated [browser workflow checks](browser-verification.md) were completed on 21 October 2026 using fictional data in a disposable preview, including desktop and mobile views. These provide additional implementation evidence; the Human result entries below still require actual participants.

The later [workflow verification follow-up](final-verification.md) adds freelance acceptance, contacts, completion, receipt confirmation, ratings, staff restrictions and physical interview checks. The PostgreSQL regression suite passed 254 tests after a completion-date usability fix. Human results remain pending.

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

## Administrator session

| Task | Expected result | Human result |
| --- | --- | --- |
| Sign in to `/admin/` with an active staff email | Branded overview opens with only permitted summaries | Pending |
| Compare account, job and application counts with lists | Counts match; candidate drafts are excluded | Pending |
| Review an application, interview, email record and saved score | Records are readable; decisions and saved evidence cannot be edited here | Pending |
| Open a submitted attachment with appropriate permissions | Protected download works without exposing a public storage URL | Pending |
| Use a limited staff account | Unpermitted counts, records and documents remain inaccessible | Pending |

## Freelance session

| Task | Expected result | Human result |
| --- | --- | --- |
| Enable a candidate's freelance profile | Only agreed professional information appears to recruiters; contact fields and uploads stay private | Pending |
| Stop accepting new bookings | Listing disappears; existing bookings and messages remain accessible | Pending |
| Publish a short project and send a proposal | A scoped conversation opens without a normal employment application | Pending |
| Send and accept a booking request | Scope, dates, total price and cancellation terms are saved; both parties can see agreed contacts | Pending |
| Try overlapping bookings | Only one can be accepted for the same dates | Pending |
| Complete work, then report, query and confirm a cash payment | Reports and confirmed receipts remain distinct; the sender cannot confirm their own payment | Pending |
| Request cancellation and record a refund | Cancellation requires the other party's agreement; refund receipt is confirmed separately | Pending |
| Confirm work completion and rate it | Only the booking recruiter can leave one review after completion | Pending |
| Block or report a conversation | New messaging stops; existing agreements remain manageable; reports are private to authorised staff | Pending |
| Review freelancer administration | Agreement/payment evidence stays read-only; authorised staff can moderate reviews and handle concerns | Pending |
| Try a phone number, email or link in a pre-booking enquiry | A clear warning appears and the message is not sent | Pending |
| View a worker's portfolio before and after acceptance | External URLs are absent before acceptance and available only to the booked recruiter afterwards | Pending |
| Add contact details to public services, projects or reviews | The affected field explains that contact details belong in the private conversation after booking | Pending |

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
