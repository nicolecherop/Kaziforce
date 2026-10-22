# Freelance work

Freelance work is an optional module alongside employment recruitment. Existing users,
applications, interviews, documents, matching runs and scores are retained. No account
is automatically opted in, no private files are published and no new role is needed.

## Candidate flow

1. Open **Freelance work → Create freelance profile**.
2. Add a service introduction, location, work arrangement, starting rate in KES and
   availability date. Add up to ten services. Skills, education, experience,
   certifications and portfolio links are maintained in **My profile**.
3. Explicitly allow this professional information to be shared with signed-in
   recruiters, then enable **Accepting new bookings**. CVs, uploaded documents and
   private profile contact fields are excluded. Check any portfolio links for personal
   information before sharing.
4. Respond to recruiter enquiries, or open **Find projects** and send a brief proposal.
5. Read the booking agreement. Accept with chosen contact details or decline it.
   Ask for different terms in messages before accepting; the recruiter can withdraw
   the request and send a revised one. Accepted terms cannot be silently edited.
6. Mark work complete. The recruiter confirms completion or requests further work.
7. Confirm actual payment receipt, query a payment report, or report a refund sent.

Turning off new bookings hides the listing and prevents new enquiries or booking
requests. Existing messages, booked work, payment records and agreed contacts remain
available. Accepted bookings reserve **whole calendar dates**, including both ends.
Availability is separate from account activation. There is no external calendar sync.

## Recruiter flow

1. Open **Freelance work → Find freelancers**. Filter by service, location, arrangement,
   starting-rate basis and date range. A price filter requires a rate basis so unlike
   units are not compared.
2. Optionally publish a short project with scope, dates, budget and relevant skills.
   Choose it on the freelancer search to see available people with relevant skills.
3. Send an enquiry and discuss the deliverables, full price and cancellation
   terms. After a project proposal, use its conversation for the same booking flow.
4. Send a booking request. No deposit or advance payment is required. Both parties'
   saved contact details unlock after the worker accepts and agrees to share theirs.
5. Confirm completion or request further work. Then report money actually sent. Reports
   count as received only after the worker confirms.
6. Leave one review (1–5 stars and a comment) per completed
   booking. The worker cannot review themselves or be reviewed without a booking.

Closing a project stops new proposals. Existing conversations and agreements remain.
Cancelling an accepted booking requires a request and the other party's agreement.
The dates remain reserved until cancellation is agreed. Refunds are reported and
confirmed separately according to the saved agreement; cancellation does not fabricate
a refund or erase payment history.

## Messages and notifications

Conversations are private to the recruiter and worker. A direct conversation is reused
for that pair; project conversations are scoped to the project. New messages and booking
events appear as unread items in **Messages**. Pages have an explicit refresh link;
there are no push notifications, automatic email delivery, real-time sockets or attachments.
Either party can block messaging/new bookings and privately report concerns. Blocking
does not remove access to existing agreements or prevent their completion/cancellation.

## Payment boundaries

**No M-Pesa, collection, payout or escrow is enabled.** Methods are Cash and Direct
payment arranged outside KaziForce. The ledger distinguishes reported, queried,
withdrawn and recipient-confirmed reports. Full price, confirmed
receipts, refunds and outstanding balance are separate. Users must not enter PINs or
bank passwords. A receipt confirmation is a participant acknowledgement, not provider
verification. Work may be complete while a balance is outstanding.

Booking locks prevent concurrent reports exceeding the remaining balance and refunds
exceeding confirmed receipts. Confirmed records
cannot be edited or withdrawn. Refunds are separate entries rather than negative edits.

For a later M-Pesa phase, first agree the merchant/payee, fees and refund arrangements.
Use Daraja sandbox before live activation. Merchant collection and worker payout need
separate designs, provider credentials, validated/reconciled results and idempotency.
Do not call normal STK Push collection escrow. Google integrations remain deferred too.

## Freelance recommendations

The freelance list is separate from the employment algorithm and does not write saved
job scores. A selected project filters active listings by available dates and work
arrangement. On-site location comparison uses the entered location (case insensitive);
use a consistent city name. Fixed starting rates and daily estimates are checked against
the budget. Hourly rates require a scope/hour estimate agreed in conversation.

Relevant profile skills are resolved with the existing local skill catalogue, with exact
normalised labels retained where no unique concept exists. If the project specifies
skills, at least one relevant skill is required to appear. Skill relevance orders results
first; ratings are secondary. Ratings use `(rating_sum + 3.5 * 5) / (review_count + 5)`
only for ordering; the card shows the actual average and count. The prior gives new
workers a starting position; it is not displayed as a fabricated review. Hidden reviews
do not contribute to either average or ordering. Without a selected project the page is
a service directory, not a calculated job-match percentage.

## Source organization and database

The `freelance` Django app contains `models.py`, explicit forms, transactional services,
selectors and separate profile/project/booking/message view files. Each page has its own
named template under `templates/freelance/`; styles extend the existing workspace.

New tables in the existing `kaziforce` PostgreSQL database:

| Table | Purpose |
| --- | --- |
| `freelancer_profiles` | Optional listings and availability |
| `freelance_services` | Services offered by a freelancer |
| `freelance_projects` | Recruiter short assignments |
| `conversations` | Scoped recruiter/worker enquiries |
| `messages` | Private messages and booking update notices |
| `bookings` | Saved agreements, contacts and status |
| `booking_events` | Append-only workflow history |
| `payments` | Participant payment/refund reports and confirmations |
| `reviews` | One rating per completed booking and moderation state |
| `conversation_reports` | Private concerns and administration follow-up |

Migrations only add tables; they do not modify existing business records. No new
dependencies, secrets, payment credentials, accounts or example records are installed.

## Administration and access

Normal candidate/recruiter routes use role and object-ownership checks, POST mutations
and CSRF protection. Profiles require opt-in; conversations, agreements, payment actions
and reports are participant scoped. Acceptance serializes on the freelancer row to
prevent overlapping accepted dates. Payments serialize on the booking row.

Native Django admin permissions apply to all new records. Agreements, messages, booking
events, projects and payment evidence are read-only there. Authorised staff can hide a
review with an internal moderation note, resolve a conversation report, or stop a
freelancer accepting bookings. Counts are permission-scoped. Staff must have explicit
permissions; a product account role does not grant staff access.

Human acceptance testing, real payment delivery and production hardening are separate
from the automated engineering checks. There is no automated dispute adjudication,
identity verification, payment assurance or anti-spam rate limiting in this module.

## No-deposit workflow update

New bookings always have a zero advance-payment amount. The booking form and payment
choices no longer offer deposits, and service validation rejects new advance-payment
requirements and reports. Work-payment reports require recruiter-confirmed completion.
Earlier agreements and receipts are retained for accurate history and refunds; an old
pending request requiring an advance payment must be withdrawn and replaced before it
can be accepted. No existing booking, contact snapshot or payment record is rewritten.

Saved contacts unlock on acceptance. Obvious contact details and web links are blocked
in pre-booking messages and public freelance information. Portfolio links are hidden
until that recruiter has an accepted booking with the worker. Older text is masked for
viewers who are not yet entitled to see it, without rewriting stored records. See
[contact-sharing rules and limits](freelance-contact-privacy.md).
