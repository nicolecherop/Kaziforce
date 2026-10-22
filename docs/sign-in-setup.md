# Connect Google sign-in and Gmail verification

The code is integrated; real Google and Gmail delivery require your own credentials. Existing accounts and passwords remain valid. No account is opted into email codes automatically during migration. Once email verification is activated globally, staff password and Google sign-ins both require the emailed code. Ordinary users opt in to repeated sign-in codes from **Account security**. All new public accounts, including Google registrations, must first confirm their email with a six-digit code before accessing a workspace. Codes expire after five minutes; resending is available after one minute and replaces the previous code. An unfinished registration can resume by signing in with the same credentials. Email delivery failures leave the account pending, without signing it in. Existing accounts keep their current sign-in flow. Confirmation uses the existing account email-address records, so no new database migration is required.

## Gmail sender

The selected sender is `kaziforce1@gmail.com`. Enter secrets only in the ignored local `.env`, never in chat, source control, screenshots or reports.

1. Enable Google's own 2-Step Verification for the sender account, then create an app password named KaziForce. Use that app password for SMTP, not your normal Google password. Google documents account eligibility at <https://support.google.com/accounts/answer/185833>.
2. Configure these local `.env` fields, leaving `EMAIL_TWO_STEP_ENABLED=false` initially:

```dotenv
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=kaziforce1@gmail.com
EMAIL_HOST_PASSWORD=enter-app-password-locally
DEFAULT_FROM_EMAIL='KaziForce <kaziforce1@gmail.com>'
EMAIL_TWO_STEP_ENABLED=false
```

3. From the project folder, run:

```powershell
.\.venv\Scripts\python.exe scripts/check_signin_setup.py --test-email
```

This explicitly sends one setup message to the sender's own address. SMTP acceptance does not prove inbox receipt: check the inbox/spam folder yourself. After receipt, set:

```dotenv
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_TWO_STEP_ENABLED=true
```

4. Restart Django after changing `.env`. Sign in to an ordinary existing account, open **Account security**, and enable email verification. Your current password and a successfully entered email code are required. Test signing out and signing in again. Staff verification is required once globally activated.

Candidate CV/contact email fields are separate from sign-in identity. Codes go to the account's sign-in email, not to an editable CV or application contact address. The existing sample accounts use non-deliverable test addresses; use an account with an inbox you control for real delivery tests. Do not opt sample addresses into email codes.

## Google identity

1. In Google Cloud, create/configure an OAuth project and consent screen for KaziForce. Create a **Web application** OAuth client. If Google keeps the app in testing, add the intended test users there.
2. Register this exact local authorized redirect URI:

```text
http://127.0.0.1:8001/accounts/auth/google/login/callback/
```

3. Enter `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`, then restart Django. Only basic profile and email scopes are requested. Tokens are not retained for Gmail or Calendar access.
4. **Continue with Google** appears on sign-in and registration once both fields are present. New users choose Candidate/Recruiter and accept the terms. Existing users first sign in normally, then connect Google from **Account security**, confirming their current password. Matching email addresses are never automatically linked. Profile records and roles stay attached to the original user.
5. Use a normal Chrome/Edge browser if Google's account page does not allow an embedded browser. For deployment, register the exact HTTPS callback for the deployed host as well.

Google users without a local password retain their Google sign-in. Disconnecting from the security page requires a usable local password. KaziForce does not ask ordinary Google users for a duplicate code to the same mailbox; they manage Google's security through Google. Staff accounts still require the KaziForce email challenge when globally activated.

Google setup reference: <https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid>.

## Controls and recovery

- Six-digit codes expire five minutes after the initial request, allow five incorrect attempts, and are tied to the requesting session. Resends wait one minute, replace the previous code and do not extend the original deadline. At most three resends are allowed.
- Workspaces are not authenticated while verification is pending. The same staged sign-in protects `/admin/login/`. Existing password-only sessions are rejected once that account requires verification.
- Changing the password or deactivating an account while a challenge is pending invalidates it. Password reset does not sign users in or disable their email verification. Enabling/disabling requires password and inbox confirmation. Losing access to the sign-in inbox is therefore not resolved by disabling the feature flag; use an independently verified account-recovery procedure. No public bypass or administrator reset control is provided.
- Rate limits use the shared `security_rate_limits` database cache table, rather than per-process memory. Allauth keeps the pending login/code in the server-side Django session; keep session storage and backups private. No code is rendered into page HTML or intentionally logged.
- Missing email credentials or an SMTP failure produces an unavailable message and never grants access. Disabling delivery does not silently bypass verification for accounts already enrolled.
- The added user field is `users.email_two_step_enabled`. Allauth's framework-owned `account_emailaddress`, `account_emailconfirmation` and `socialaccount_*` tables hold verified addresses and provider identity links; employment and freelance records are unchanged.

This is email-based **two-step verification**, not phishing-resistant MFA. Google sign-in is separate from Gmail sending. Real-inbox receipt, Google consent/redirect behavior and deployment configuration still require checks with the actual connected accounts.
