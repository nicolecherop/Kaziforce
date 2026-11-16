# Self-service account deletion

Open Account security → Delete my account. This covers both workspaces.

The user requests a six-digit code at their current sign-in email, then enters it
and explicitly confirms deletion. Google-only users use the same flow. Codes are
hashed, expire after ten minutes, allow five incorrect attempts and have a
one-minute resend cooldown. Resending invalidates the previous code. A change to
the password or email invalidates the pending confirmation. Requests use CSRF
protection; GET does not mutate an account.

Deletion removes the professional profile, original private documents, saved jobs,
application drafts and matching results. It disconnects Google, removes email
identities, replaces the account name/email with a deleted-account marker and
sets an unusable password. The account becomes inactive, loses all permissions,
and cannot sign in on existing sessions. A minimal dated account row remains to
preserve foreign keys. Closed accounts are read-only in administration.

Submitted applications and their attachment copies, listings, conversations,
booking agreements, reviews and payment records remain for the other participants
and authorised administrators. These may still contain previous names/contact
details. This is disclosed before confirmation; this feature is not a claim of
complete erasure from historical records or backups. No retention period is
automatically enforced. Jobs/projects close, the freelance profile becomes hidden
and blank, conversations are blocked, and future interviews are marked cancelled.
No additional cancellation email is sent by the deletion operation.

Outstanding booking requests/agreements, unresolved payments, pending M-Pesa
transactions and unpaid completed work block deletion until resolved. The last
active superuser cannot delete their account. Database changes are atomic and
original file cleanup runs after commit. Existing shared files remain unchanged.

Verification tests use fictional users and an in-memory email backend; no live
accounts or payment transactions are removed during testing.
