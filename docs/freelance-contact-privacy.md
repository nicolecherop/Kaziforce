# Contact sharing in freelance work

## Before an accepted booking

Use in-app messages to agree the scope, dates and price. Obvious phone numbers, email
addresses, web links and labelled social handles are rejected with a clear message.
Web links are included because an external page can disclose contact information even
when its address is not itself a phone number or email address.

The same checks apply to freelance listing titles/about/location, service descriptions,
project text and skills, and public reviews. Booking scope, title, location, name and
cancellation text cannot be used to bypass the dedicated private contact fields.
An ordinary meeting address, dates, prices and technical skill names are allowed.

A recruiter cannot retrieve a freelancer's portfolio URL or link title in the profile
page HTML until an accepted booking exists between that recruiter and worker. The
worker's own professional profile editor and existing employment applications continue
to work normally. Uploaded documents remain private.

## After acceptance

Both parties' agreed booking contacts unlock without a deposit. Private messages can
then include contact details and links. The recruiter can view portfolio links on an
available freelance profile. Unlocking belongs to the specific recruiter/worker pair,
including their project conversations; it does not unlock other workers or recruiters.

A requested, declined or withdrawn booking does not unlock anything. An earlier
accepted booking remains part of the pair's contact-sharing history, including after
cancellation. Cancellation cannot make already-disclosed details unknown again.
Blocking a conversation still prevents new messages, regardless of acceptance.

Public information stays subject to the contact check after acceptance because it can
also be seen by people who have not booked the worker. Share contact details privately.

## Existing records and limitations

Deployment does not rewrite or delete earlier text. Obvious contact details in older
messages, shared professional text, public listings/reviews and pending booking text
are masked at display time before the viewer is entitled to see them. Native admin
oversight retains its existing permission controls and access to original evidence.
Owner editors retain the original text so the owner can correct it explicitly.

Detection handles common phone formats (including Kenyan local/international numbers),
emails, common bracketed email separators, URLs, common bare domains and labelled
social handles. Fullwidth characters and invisible formatting characters are normalized
for detection. Date ranges, ordinary prices, room numbers, software versions and common
technology names such as ASP.NET are covered by false-positive tests.

This is a practical text guard, not proof that people cannot exchange contact details.
Images, QR codes, uncommon domains, verbal arrangements and deliberate disguises can
evade it. No OCR, external inspection or automated identity verification is performed.
There is no new logging of rejected message content. A rejected enquiry/proposal does
not save the message or create an empty new conversation.

## Source and verification

- `freelance/contact_rules.py`: bounded text detection, validation, masking and pair access.
- `freelance/forms.py`: field-specific public/form errors.
- `freelance/services.py`: authoritative message, booking-text and public-review checks.
- `freelance/templatetags/freelance_privacy.py`: display masking with HTML escaping retained.
- Freelance views/selectors: server-derived access flags; browser/query flags cannot
  choose whether contact sharing is unlocked.
- `tests/test_freelance_contact_privacy.py`: twenty tests covering detection, legitimate
  work text, rejected writes, pair isolation, legacy display, portfolio HTML and escaping.

The full PostgreSQL suite passes **245 tests**, including the existing employment,
interview, payment and concurrency checks. Django reports no schema changes. A separate
local browser preview with fictional SQLite records verified the portfolio lock and
rejected phone-number warning, with no browser console errors. Preview accounts,
messages and data are not installed into the working PostgreSQL database. Human/device
acceptance remains separate from these engineering checks.
