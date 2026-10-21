# Local demonstration data

The fictional dataset includes five labelled jobs, six candidate profiles, education and certification entries, work experience, sixteen submitted applications, candidate recommendations and recruiter rankings. It includes backend development, data analysis, frontend development, project coordination and customer support, with different levels of skill coverage and experience. It contains no CV or certificate files and no privileged accounts.

Run from the project directory after preparing the matching corpus:

```powershell
.\.venv\Scripts\python.exe scripts/demo_data.py
```

The script records its exact account and job IDs, together with a generated demo-only password, in `.backups/demo-data-v1.json`. This local file is ignored by Git. Existing accounts are never reused or overwritten; rerunning the script preserves the demo batch and any edits. Demo emails use the reserved `.test` domain and no email is sent.

Sign in as `recruiter@demo.kaziforce.test` to open **Jobs & applicants → View applicants → Review applicant rankings**. Every demo job already has submitted applications and a saved ranking. Sign in as `amina@demo.kaziforce.test` or `felix@demo.kaziforce.test` to open **My matches**, read explanations and apply for remaining jobs. The same generated demo password works for all seven demo accounts.

The other candidate emails are `brian@demo.kaziforce.test`, `chloe@demo.kaziforce.test`, `david@demo.kaziforce.test` and `esther@demo.kaziforce.test`. All six candidates have the surname Demo. Education, certification issuers and previous employers are explicitly fictional. The scores illustrate this implementation and do not establish hiring accuracy.

To remove this recorded batch later:

```powershell
.\.venv\Scripts\python.exe scripts/demo_data.py --remove
```

Removal refuses to proceed if real accounts have applied to demo jobs, demo candidates have applied to other jobs, additional jobs were created under the demo recruiter, or documents were uploaded. This preserves interactions that need manual review. Keep the manifest private and do not use these demonstration credentials for real accounts.
