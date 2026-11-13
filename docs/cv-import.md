# Filling a profile from a CV

Candidates can upload a CV from **My profile → Manage your documents**, select
**Fill profile from this CV**, and review suggestions before choosing **Save
selected details**. An existing CV also has a **Fill profile from CV** button.
Manual profile entry remains available.

## Behaviour

- Accepts text-based PDF and Word (.docx), up to 5 MB. PDF import has a 20-page
  limit; ordinary document storage still accepts scanned attachments.
- Reads contact details and section headings to suggest a headline, summary,
  skills, education, employment, certifications and professional links.
- English headings and common date/layout conventions are supported. This is
  a local, conservative parser, not an AI service or credential verification.
- Existing non-empty profile fields are unchecked initially. Only selected
  fields are replaced; selected repeatable entries are appended. Duplicates
  are skipped. Existing qualifications, files and applications are not deleted.
- Does not change account identity, login email, verification state or roles.
- Review is editable and supports excluding any entry. Unselected invalid
  suggestions cannot block saving valid selected information.
- Month/year dates use the first day of the stated month and disclose that in
  review. Year-only dates remain blank rather than guessing a month. Required
  employment dates must be corrected or that entry excluded before saving.
- Text that could not be structured is available in an escaped source-text
  panel alongside a link to the original CV. Missing items can be added manually.
- Empty/scanned, encrypted, malformed and over-complex documents give an
  actionable error. Uploading or reading a CV never updates a profile by itself.

## Privacy and boundaries

All processing stays on the application host. No CV is sent to an external AI,
email or parsing service. Candidate-only POST endpoints require normal login,
ownership and CSRF checks. Review responses use `never_cache`. Random review
tokens are bound to the user, expire after 30 minutes, and are consumed on save
or discard. The database cache temporarily holds extracted personal information;
expired rows follow Django's cache eviction lifecycle. It must remain private.

The document worker has a 15-second timeout, file/page/text/XML/ZIP-size limits,
and never follows Word external relationships or executes document content.
XML uses defusedxml. No raw CV content, parser traceback or private path is
logged. These application limits do not replace OS/container memory isolation
when deploying with untrusted public uploads. Import requests are limited to
one every 30 seconds per candidate. Save is transactional, checks the current
profile against the review's starting state, and refuses a stale import.

## Known limits and verification

Image-only scans need OCR or a selectable-text copy; OCR is not implemented.
Unusual column layouts, abbreviated headings, ambiguous organisations and
unlabelled details may need correction. A successful extraction is not proof
that every field is correct. Validate with representative, consented real CVs
before claiming extraction accuracy. Automated fixtures test supported formats,
rejection cases, ownership, no-write preview, validation and merge behaviour.

Readers: [pypdf extraction documentation](https://pypdf.readthedocs.io/en/7.0.0/user/extract-text.html).
