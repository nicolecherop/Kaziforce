# M-Pesa sandbox setup

The M-Pesa integration is restricted to Safaricom's Daraja sandbox. There is no production endpoint, live-mode switch, worker payout, deposit or escrow feature.

## Payment flow

1. The freelancer accepts the booking and completes the work. The recruiter confirms completion.
2. Open **M-Pesa sandbox payments** on the completed booking.
3. The recruiter enters a supported Daraja test phone number and whole-shilling test amount. Never enter an M-Pesa PIN on KaziForce.
4. The server checks ownership, booking status, balance and any pending request before submitting the STK request.
5. An accepted request means only that submission succeeded. Select **Check sandbox status** to query Daraja for the final result.
6. Successful results mean a sandbox business collection, not worker receipt. Actual payment reports and booking balances remain unchanged.

Sandbox behaviour and supported test numbers depend on the provider's current tooling. Do not promise a real handset prompt or use real money to validate this integration.

## Connect Daraja

Create a sandbox application at <https://developer.safaricom.co.ke/> with M-Pesa Express access. Enter the sandbox consumer key, consumer secret, business shortcode and Lipa na M-Pesa passkey locally in the ignored `.env`:

```dotenv
MPESA_SANDBOX_ENABLED=true
MPESA_CONSUMER_KEY=
MPESA_CONSUMER_SECRET=
MPESA_SANDBOX_SHORTCODE=
MPESA_SANDBOX_PASSKEY=
MPESA_SANDBOX_CALLBACK_URL=https://your-sandbox-host.example/payments/mpesa/callback/
```

Keep these values out of source control and chat. Use credentials supplied by your Daraja sandbox account, not a production shortcode or live passkey. Restart Django after changing `.env`.

Safaricom cannot call a localhost address. A deployed test endpoint or an approved public HTTPS forwarding arrangement is required for callbacks. Expose only the callback endpoint where possible; do not publish the local administrator panel or private documents. Configure the matching hostname in `DJANGO_ALLOWED_HOSTS` when needed. Creating a tunnel or publishing the local site is a separate setup step; this integration does not do that automatically.

Run `python scripts/check_mpesa_setup.py` to inspect readiness without printing secrets. It makes no network request and sends no payment. Automated tests use provider mocks, never real accounts.

## Status and duplicate handling

- Amounts are limited to KES 1–100,000 in whole shillings and cannot exceed the remaining test balance. Price decimals are not rounded automatically.
- The `mpesa_transactions` table stores the booking, initiating recruiter, request key, amount, test phone, merchant/checkout references and state. It is separate from `payments`, which records participant-confirmed worker receipts.
- Each form submission has a unique request key. Repeating it returns the original request. A database constraint and booking lock allow only one pending/uncertain request per booking.
- Transport failures after submission are uncertain, not automatically failed. Do not resubmit them. If there is no checkout reference, inspect the Daraja dashboard; operational reconciliation is required before safely allowing a retry. No automatic expiry treats uncertainty as permission to collect again.
- Public callbacks record only that a matching request notification arrived. They never mark a collection successful, store a claimed receipt number or alter worker balances. Final status comes from an authenticated STK status query whose merchant and checkout references match the stored request.
- Status checks are POST-only for the owning recruiter, have CSRF and rate limits, and wait at least 15 seconds between checks. Both booking participants can read the masked sandbox history. Other users cannot access it.
- No raw provider payloads, authorization headers, passkeys or PINs are intentionally logged. Administration shows read-only transaction records with masked test phone numbers.
- A worker payment ledger entry is never created by a sandbox success. Refunds and disbursements are not implemented here.

## Verification

Run `python manage.py test tests.test_mpesa --keepdb`. Tests cover request construction, isolated sandbox hosting, access control, CSRF, replayed submissions, invalid amounts, pending requests, provider failures, forged callbacks and unchanged worker balances.

External Daraja connectivity and callback delivery require the configured account and public HTTPS endpoint. Passing mocked tests does not establish that these external steps work.

Provider references: [M-Pesa Express](https://developer.safaricom.co.ke/apis/MpesaExpressSimulate), [STK status query](https://developer.safaricom.co.ke/APIs/MpesaExpressQuery). Recheck provider requirements before any future live-payment design.

On 22 October 2026, all 20 M-Pesa tests and the complete 327-test PostgreSQL suite passed. The new `mpesa_transactions` migration was applied after a verified private database backup. External Daraja testing remains pending credentials and a reachable HTTPS callback. No sandbox or real payment request was sent during these checks.


## Temporary callback-only HTTPS tunnel

The local setup uses a gateway on `127.0.0.1:8014` rather than exposing Django's port 8001. Start it from the project directory:

```powershell
.\.venv\Scripts\python.exe scripts/serve_mpesa_callback.py --port 8014
```

In another terminal, use the official Cloudflare `cloudflared` executable:

```powershell
cloudflared tunnel --url http://127.0.0.1:8014 --no-autoupdate --protocol http2
```

Set `MPESA_SANDBOX_CALLBACK_URL` to the generated HTTPS origin followed by `/payments/mpesa/callback/`. Keep the gateway, Django and tunnel running while testing. Quick Tunnel URLs are temporary and must be updated in `.env` when a new origin is generated; restart Django afterward. Do not point this tunnel at port 8001.

Only a JSON POST to the exact callback path is forwarded. The gateway rejects other paths, limits payload size and request rate, discards phone/receipt metadata, and forwards only checkout and merchant request IDs. It does not forward browser cookies or authorization headers. The homepage, account pages, administrator panel and private files remain inaccessible through this origin. Stop the tunnel when testing is finished.

Gateway verification: five additional tests passed alongside the 20 payment tests. External connectivity checks returned 200 for a harmless unknown-reference callback and 404 for `/`, `/admin/` and `/accounts/sign-in/`. No payment was initiated. Provider authentication remains pending a valid saved sandbox shortcode.

Reference: <https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/>.


## Completion and commission calculation

A successful recruiter **Confirm completion** action now redirects directly to the payment page. The worker's **Mark work complete** action still waits for recruiter confirmation. Failed or unauthorized completion requests never redirect to payment. The booking header no longer contains a payment button; the payment-summary link and completed-bookings list provide return access.

The current sandbox calculation uses a fixed 10% KaziForce commission included in the agreed price. The worker share is the remaining 90% before transaction fees. For KES 10,000, the breakdown is KES 1,000 commission and KES 9,000 worker share. Decimal calculations round commission to two decimal places using ROUND_HALF_UP; the worker share is the total minus commission so the amounts always sum to the agreed total.

Both parties can see the booking breakdown before acceptance. The payment page shows it again, and each sandbox request has a split based on that request's amount. These are calculations, not settlement or proof of worker receipt. No commission revenue entry, automatic deduction from an actual cash/direct-payment record or B2C payout is created. Existing payment reports remain unchanged. The fixed calculation is computed on demand; any later variable-rate/live accounting design needs immutable agreed-rate and settlement records.

Verification: 71 focused M-Pesa, freelance and callback-gateway tests passed after this change. Coverage includes redirect timing, unchanged worker-completion flow, invalid transitions, two-decimal rounding, partial-request splits, pre-acceptance visibility and unchanged worker-payment balances. No provider payment request was sent by these checks.


## STK tests and actual wallet deductions

Sandbox hosting does not justify promising that a test cannot debit a personal M-Pesa wallet. The user reported an actual wallet deduction during an STK test on 22 October 2026. The configured collection shortcode was confirmed to be Safaricom's standard Express test shortcode 174379. It is not a KaziForce-owned collection account or worker payout destination.

Safaricom's Daraja FAQ identifies 174379 as the Lipa na M-Pesa online test shortcode and states that STK test funds are scheduled for automatic reversal at 6 a.m. the next day; it also lists APIfeedback@safaricom.co.ke and APIsupport@safaricom.co.ke for reversal requests. Actual receipt and reversal must be checked in the user's M-Pesa messages/history; KaziForce cannot promise or initiate that reversal. Keep receipt references private and use official Safaricom support channels.

The payment page now states that approving a test STK prompt with a personal number may debit the wallet. Use mocked provider responses for demonstrations that must avoid all monetary movement. No additional STK request was sent when investigating this report.

Source: <https://developer.safaricom.co.ke/faqs>.


## Payment presentation and balance updates

The user-facing payment page uses normal payment language. The integration still targets Daraja's sandbox exclusively; removing environment labels does not change the provider endpoint or turn it into a live KaziForce merchant account. The pay form displays the configured recipient shortcode. Worker payout remains explicitly separate.

Confirmed M-Pesa collections contribute to the displayed booking collection balance together with participant-confirmed direct receipts, less their recorded refunds. Pending, uncertain and unsuccessful M-Pesa requests never count as received. A partial collection shows the remainder; fully collected bookings show Payment complete and no new payment form. The separate worker receipt ledger remains unchanged and is not evidence of a worker payout from KaziForce. Provider test-fund reversals are not automatically reconciled into this collection history; full provider reversal reconciliation remains future work.

An authenticated recruiter viewing a pending request gets a status-only POST check every 16 seconds, up to ten attempts, while the page is visible. Checks use the current CSRF token and only call the existing check endpoint. They cannot initiate or resend payment. A terminal provider result refreshes the page to display the updated balance/history. Manual checks remain available. The worker's view does not initiate provider checks.

Both M-Pesa initiation and direct-payment reporting reserve the same remaining gross balance under the booking lock, so pending reports/requests cannot be used to reserve it twice. Repeated status checks do not create a duplicate receipt or increase the collected amount twice.

Verification after this change: payment/freelance/gateway/concurrency regression tests and JavaScript checks cover partial/full collection, rejected and pending results, repeat checks, scoped JSON status responses, cross-method reservations, CSRF, terminal refresh and bounded polling. No new external payment request was sent during implementation or verification.


## Recruiter completion without a worker request

The owning recruiter can confirm completion directly from a Confirmed booking, without waiting for the worker to mark it complete. The same option remains available after a worker completion request. A successful confirmation records completion and redirects to the payment page; it never initiates a payment automatically.

The button remains visible but disabled before the booking start date or while cancellation is unresolved. Server validation enforces the same rules. Other users cannot confirm completion, and completed/declined/cancelled/unaccepted bookings cannot be completed again. Workers retain their existing Mark work complete action to request recruiter confirmation.

Verification: 98 focused payment, freelance and contact-privacy tests passed, including direct confirmation, payment redirect, future dates, cancellation, ownership and repeated confirmation.
