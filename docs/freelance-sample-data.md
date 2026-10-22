# Trying freelance work

Open <http://127.0.0.1:8001/freelance/> after signing in with an existing sample account. Existing passwords, professional profiles, job applications and matching results are unchanged.

| Account | Sign-in email | What to try |
| --- | --- | --- |
| Sarah Mwangi, recruiter | recruiter@demo.kaziforce.test | Find workers, review messages, manage projects and bookings |
| Amina Hassan | amina@demo.kaziforce.test | Accept or decline the inventory API booking request |
| Brian Otieno | brian@demo.kaziforce.test | View a confirmed reporting assignment and request completion |
| Chloe Wanjiru | chloe@demo.kaziforce.test | View website work awaiting the recruiter's completion approval |
| David Kamau | david@demo.kaziforce.test | View completed work, a confirmed cash receipt and a five-star review |
| Esther Achieng | esther@demo.kaziforce.test | Reply to an enquiry and agree a new booking |
| Felix Mutua | felix@demo.kaziforce.test | View an unavailable listing; enable accepting bookings to appear in search |

Use the existing password supplied when these accounts were created. The original local credential record is `.backups/demo-data-v1.json`; keep it private. The new seed does not reset passwords or create privileged accounts.

## Suggested walkthrough

1. As Sarah, open **Freelance work → Find freelancers**. Five workers accept bookings; Felix is excluded. David has a completed-work rating. Select an open project to try skill-based recommendations.
2. Open **Messages** and the Esther conversation. Before an accepted booking, obvious contact details and web links cannot be sent. Agree the scope and request a booking without a deposit.
3. Sign in as Amina to review her pending booking. Acceptance shares the contacts saved on the agreement with both parties. Declining leaves contacts locked.
4. As Brian, request completion of the confirmed booking. As Sarah, confirm completion or request changes.
5. As Sarah, open Chloe's booking and confirm completion. You can then record a cash/direct payment. Chloe must confirm receipt before it counts as received. Sarah can leave a rating for completed work.
6. David's completed booking shows the final agreement, payment and rating history.

Dates are relative to the day the batch is first created: Brian and Chloe start that day, Amina starts two days later, Esther's project starts five days later. Requests are subject to normal date/availability checks, so try Amina's request before its start date. The seed does not move dates forward on reruns or reset changes made during this walkthrough.

The example cash receipt is a database record only: no money was transferred. Agreement emails use the reserved `.example` domain and do not deliver email. Sign-in emails remain unchanged. There are no deposits, payment gateway calls or externally delivered messages.

## Local maintenance

Run with the project's virtual environment, from the project root:

```powershell
.\.venv\Scripts\python.exe scripts/freelance_data.py
.\.venv\Scripts\python.exe scripts/freelance_data.py --check
```

Creation is transactional and limited to the seven identities recorded by the original account seed. An existing freelance listing, changed identity, inactive account or privileged account stops creation. The ignored `.backups/freelance-data-v1.json` records the exact new row IDs and contains no password. Rerunning verifies the batch and retains edits; it never creates replacement rows for a partially deleted batch. Retain both manifests and the pre-seed database backup. Do not run the original account seed's removal option while these agreements reference those accounts.
