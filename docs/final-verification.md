# Workflow verification follow-up

Date: 21 October 2026. Result: the checks listed below passed after one booking-page usability fix. This records agent-operated engineering checks, not human acceptance, a security audit or production readiness certification.

## Environment

The installed source was copied into a disposable local preview on port 8007, with its own SQLite database and private storage. The reference contained 13,939 ESCO concepts. Seven fictional recruitment accounts, six freelance profiles, five employment jobs, sixteen submitted applications and five short projects were seeded. A full administrator and a staff account limited to viewing freelance projects existed only in this preview. No administrator was created in the development database.

Browser actions used the actual sign-in pages, navigation and forms. Preview email delivery used an in-memory backend; there was no Gmail connection or external delivery. Booking acceptance and payment records were fictional test actions, with no real agreement or transfer of money. The development site's accounts, applications, bookings, uploads and environment configuration were not used for test writes.

## Browser results

| Scenario | Observed result |
| --- | --- |
| Candidate sign-in and dashboard | Amina's account opened the candidate navigation and a clear empty state when no recommendation met the threshold |
| Candidate freelance profile and inbox | Services, rate, availability and the project-scoped conversation were accessible |
| Contact-bearing message before acceptance | An email address was rejected with an explanation; it was not added to the conversation |
| Ordinary message before acceptance | Scope and date discussion saved and appeared in the history |
| Pending booking contacts | Recruiter contact was absent from the worker's pending agreement |
| Freelancer acceptance | Agreement became Confirmed and both saved contact emails appeared |
| Premature completion attempt | Server refused completion before the start date and retained the Confirmed status |
| Completion-action usability fix | Retest showed the start date guidance instead of an action that could not yet succeed |
| Recruiter discovery | Five accepting workers appeared; the unavailable worker was excluded; completed-work ratings were displayed |
| Project-specific discovery after acceptance | A worker reserved for those dates was excluded from the project results |
| Recruiter booking queue | The booking accepted by the candidate appeared as Confirmed |
| Work completion | Recruiter confirmed the worker's completion request; payment reporting and one review became available |
| Cash payment report | Report remained Awaiting recipient confirmation; confirmed received stayed zero; sender had a withdrawal action and no receipt-confirmation action |
| Worker queries payment | Status changed to Recipient has queried this payment; confirmed received stayed zero |
| Worker confirms receipt | Receipt confirmation was recorded and remaining balance changed from KES 12,000 to zero |
| Review | One five-star review saved after completion; the submission form became the saved review |
| Candidate access to administration | Candidate was redirected to admin sign-in with an authorization explanation |
| Administrator overview | Account, employment, matching and freelance summaries were available |
| Administrator agreement view | Agreement, contact snapshots and dates were readable with Close rather than editing/save controls |
| Limited staff | Only the permitted project section appeared; direct booking-list access returned 403 |
| Recruiter employment review | Submitted professional details and the simplified skill acknowledgements were readable |
| Shortlisting | Status changed to Shortlisted and interview scheduling became available |
| Physical interview setup | In person was the default; a future interview saved with venue, preparation instructions, recruiter email and EAT timezone |
| Email-status honesty | Recruiter saw that the invitation was available in the app and the email had not been sent because the sample application had no usable contact email |
| Candidate interview view | Candidate saw the same shortlist status, interview date, venue, instructions and recruiter email; recruiter status/edit/retry controls were absent |
| Narrow-screen layout | Booking and interview pages checked at 390 × 844; measured document width 375px did not exceed the 390px viewport |
| Browser diagnostics | Final collected warning/error logs for the checked tab were empty |

These targeted follow-up checks supplement the earlier [recruitment browser pass](browser-verification.md). Registration, document uploads, draft-to-submission, interview editing/cancellation, cancellation/refunds and screen-reader use were not all repeated in this browser session. Existing automated coverage and earlier checks remain separate evidence, rather than being relabelled as fresh browser observations.

## Fix and regression checks

An accepted future booking previously offered **Mark work complete**, then rejected the action after clicking. The page now says when completion becomes available. The action appears from the start date, once the worker can request completion. Cancellation remains available and the original server-side date validation still rejects crafted early requests.

The PostgreSQL regression suite passed **254 tests**, including two new tests checking future-date guidance, direct early POST refusal, recruiter visibility and the start-day completion transition. The isolated test database was `test_kaziforce`; the browser preview used SQLite. No model changes or database migrations were needed. This test count is a regression result, not matching accuracy, coverage percentage or user satisfaction.

The [synthetic matching evaluation](evaluation/report.md) remains unchanged because no matching calculation or label changed. Freelance ratings and availability have their own workflow tests; they have not undergone an independent recommendation-quality study.

## Evidence

- [Corrected completion guidance](browser-evidence/completion-date-desktop.png)
- [Confirmed receipt and payment history](browser-evidence/receipt-confirmed.png)
- [Read-only administrator agreement](browser-evidence/admin-readonly.png)
- [Limited staff overview](browser-evidence/limited-staff.png)
- [Candidate interview invitation](browser-evidence/candidate-interview.png)
- [Mobile booking](browser-evidence/booking-mobile.png)
- [Mobile interview](browser-evidence/interview-mobile.png)

## Remaining release work

1. Carry out the [human acceptance checklist](user-acceptance.md) with actual users, recording their observations without inventing sign-off.
2. Run broader device/browser and assistive-technology checks as needed for the intended audience.
3. If online deployment is required, complete production configuration, HTTPS, private-file serving and a tested backup/restore process in the chosen hosting environment.
4. Google sign-in, Gmail delivery, Google Meet and M-Pesa remain deferred. Local password-reset behavior does not establish delivery to a real Gmail inbox. Cash/direct-payment reporting does not transfer money.
