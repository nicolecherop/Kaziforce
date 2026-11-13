# Candidate profile workflow check — 6 November 2026

Account: `grace.cheruiyot.007@people.kaziforce.test` (fictional local account).

Method: CSRF-enforced Django HTTP client, normal password sign-in, local development PostgreSQL. Browser automation host was unavailable; browser JavaScript/visual interaction is not certified by this run.

The profile was completed through the actual form endpoints. New example entries remain saved for inspection. Original profile and submitted-application snapshots are backed up privately. Contact email is a reserved `.test` address; the phone uses a fictional 555 number. No files were uploaded and no emails were sent.

| Check | Result |
| --- | --- |
| Candidate signs in using the normal email/password form | Pass |
| Profile edit form opens for candidate | Pass |
| Rejects malformed contact email | Pass |
| Rejects malformed contact email: no partial data saved | Pass |
| Rejects malformed phone number | Pass |
| Rejects malformed phone number: no partial data saved | Pass |
| Rejects education end date before start date | Pass |
| Rejects education end date before start date: no partial data saved | Pass |
| Rejects future education start date | Pass |
| Rejects future education start date: no partial data saved | Pass |
| Rejects certification expiry before issue date | Pass |
| Rejects certification expiry before issue date: no partial data saved | Pass |
| Rejects unsafe portfolio URL | Pass |
| Rejects unsafe portfolio URL: no partial data saved | Pass |
| Rejects current employment with an end date | Pass |
| Rejects current employment with an end date: no partial data saved | Pass |
| Rejects duplicate skills regardless of case and spaces | Pass |
| Rejects duplicate skills regardless of case and spaces: no partial data saved | Pass |
| Rejects profile save without CSRF token | Pass |
| Complete profile saves and redirects to the profile page | Pass |
| Saved profile displays Backend developer | Python and Django | Pass |
| Saved profile displays Python | Pass |
| Saved profile displays Django | Pass |
| Saved profile displays Git | Pass |
| Saved profile displays BSc Computer Science | Pass |
| Saved profile displays Example Learning Centre | Pass |
| Saved profile displays Python Web Development | Pass |
| Saved profile displays Example Professional Training | Pass |
| Saved profile displays Backend Developer | Pass |
| Saved profile displays Mawingu Product Studio | Pass |
| Saved profile displays Software development portfolio | Pass |
| Saved profile displays grace.cheruiyot.007@people.kaziforce.test | Pass |
| Reopened edit form retains saved headline and contact details | Pass |
| All five repeatable sections persist | Pass |
| Reopening pages does not duplicate entries or modify data | Pass |
| Earlier submitted applications retain their original snapshots | Pass |
| Anonymous users cannot open profile edit page | Pass |
| No emails were sent during profile testing | Pass |
| Profile remains saved after signing out and signing back in | Pass |

Still pending; agent-operated functional testing only.

CV/degree/certificate file uploads and browser add-row/tab interactions require a separate test.
