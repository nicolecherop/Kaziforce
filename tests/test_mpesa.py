"""Sandbox collection never settles freelancer payments or trusts a callback claim."""

from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch
import base64
import json
from urllib.error import URLError

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from freelance.models import Booking, Conversation, FreelancerProfile
from freelance.services import payment_totals
from mpesa.client import (
    DarajaSandboxClient,
    ProviderError,
    ProviderRejected,
    normalize_phone,
    sandbox_ready,
    SANDBOX_HOST,
)
from mpesa.forms import SandboxPaymentForm
from mpesa.models import MpesaTransaction
from mpesa.services import initiate_payment, reconcile_payment

CONFIG = {
    "enabled": True,
    "consumer_key": "fictional-key",
    "consumer_secret": "fictional-secret",
    "shortcode": "174379",
    "passkey": "fictional-passkey",
    "callback_url": "https://callback.example/payments/mpesa/callback/",
}
ACCEPTED = {
    "ResponseCode": "0",
    "CheckoutRequestID": "test-checkout",
    "MerchantRequestID": "test-merchant",
}


@override_settings(MPESA_SANDBOX=CONFIG)
class MpesaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.recruiter = User.objects.create_user(
            username="mpesa-recruiter", email="recruiter@example.test", role="recruiter"
        )
        cls.worker = User.objects.create_user(
            username="mpesa-worker", email="worker@example.test"
        )
        cls.stranger = User.objects.create_user(
            username="mpesa-stranger", email="stranger@example.test", role="recruiter"
        )
        profile = FreelancerProfile.objects.create(
            user=cls.worker,
            title="Reporting",
            about="Data services",
            location="Nairobi",
            rate=1000,
            rate_unit="project",
            available_from=timezone.localdate(),
            accepting_bookings=True,
            share_professional_profile=True,
        )
        thread = Conversation.objects.create(
            recruiter=cls.recruiter, freelancer=profile
        )
        cls.booking = Booking.objects.create(
            conversation=thread,
            title="Reporting assignment",
            scope="Prepare results",
            location="Remote",
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
            total_price=1000,
            cancellation_terms="Agree changes",
            status="completed",
            accepted_at=timezone.now(),
            completed_at=timezone.now(),
            recruiter_name="Recruiter",
            recruiter_email=cls.recruiter.email,
        )

    def setUp(self):
        cache.clear()
        self.fields = {
            "phone_number": "0712345678",
            "amount": Decimal("500"),
            "request_key": uuid4(),
        }

    def begin(self):
        with patch(
            "mpesa.client.DarajaSandboxClient.initiate", return_value=ACCEPTED
        ) as provider:
            attempt = initiate_payment(self.booking.pk, self.recruiter, self.fields)
        return attempt

    def result(self, **changes):
        return {
            "ResponseCode": "0",
            "CheckoutRequestID": "test-checkout",
            "MerchantRequestID": "test-merchant",
            "ResultCode": "0",
            **changes,
        }

    def test_valid_submission_records_pending_and_preserves_worker_ledger(self):
        attempt = self.begin()
        self.assertEqual(attempt.status, "pending")
        self.assertEqual(attempt.phone_number, "254712345678")
        self.assertEqual(self.booking.payments.count(), 0)
        self.assertEqual(payment_totals(self.booking)["remaining"], 1000)

    def test_replayed_request_returns_original_without_second_provider_call(self):
        first = self.begin()
        with patch("mpesa.client.DarajaSandboxClient.initiate") as provider:
            second = initiate_payment(self.booking.pk, self.recruiter, self.fields)
        self.assertEqual(first.pk, second.pk)
        provider.assert_not_called()
        self.fields["amount"] = 400
        with self.assertRaises(ValidationError):
            initiate_payment(self.booking.pk, self.recruiter, self.fields)

    def test_second_pending_request_is_blocked(self):
        self.begin()
        self.fields["request_key"] = uuid4()
        with self.assertRaises(ValidationError):
            initiate_payment(self.booking.pk, self.recruiter, self.fields)
        self.assertEqual(MpesaTransaction.objects.count(), 1)

    def test_worker_stranger_and_unfinished_booking_cannot_initiate(self):
        for actor in (self.worker, self.stranger):
            with self.assertRaises(PermissionDenied):
                initiate_payment(self.booking.pk, actor, self.fields)
        self.booking.status = "accepted"
        self.booking.save()
        with self.assertRaises(ValidationError):
            initiate_payment(self.booking.pk, self.recruiter, self.fields)

    def test_invalid_amounts_and_excess_balance_are_rejected(self):
        for amount in ("0", "-1", "0.5", "1001", "100001", "NaN"):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                initiate_payment(
                    self.booking.pk, self.recruiter, {**self.fields, "amount": amount}
                )
        self.assertFalse(MpesaTransaction.objects.exists())

    def test_provider_uncertainty_is_not_failed_or_automatically_retried(self):
        with patch(
            "mpesa.client.DarajaSandboxClient.initiate",
            side_effect=ProviderError("private provider response"),
        ):
            attempt = initiate_payment(self.booking.pk, self.recruiter, self.fields)
        self.assertEqual(attempt.status, "unknown")
        with self.assertRaises(ValidationError):
            reconcile_payment(attempt.pk, self.recruiter)
        self.fields["request_key"] = uuid4()
        with self.assertRaises(ValidationError):
            initiate_payment(self.booking.pk, self.recruiter, self.fields)

    def test_explicit_provider_rejection_can_be_retried(self):
        with patch(
            "mpesa.client.DarajaSandboxClient.initiate",
            side_effect=ProviderRejected("Rejected"),
        ):
            attempt = initiate_payment(self.booking.pk, self.recruiter, self.fields)
        self.assertEqual(attempt.status, "failed")
        self.fields["request_key"] = uuid4()
        self.assertEqual(self.begin().status, "pending")

    def test_authenticated_query_confirms_only_sandbox_collection(self):
        attempt = self.begin()
        with patch(
            "mpesa.client.DarajaSandboxClient.query", return_value=self.result()
        ):
            result = reconcile_payment(attempt.pk, self.recruiter)
        self.assertEqual(result.status, "success")
        self.assertEqual(self.booking.payments.count(), 0)
        self.assertEqual(payment_totals(self.booking)["remaining"], 1000)
        with patch("mpesa.client.DarajaSandboxClient.query") as query:
            reconcile_payment(attempt.pk, self.recruiter)
            query.assert_not_called()

    def test_unmatched_result_does_not_confirm_collection(self):
        attempt = self.begin()
        with patch(
            "mpesa.client.DarajaSandboxClient.query",
            return_value=self.result(CheckoutRequestID="wrong"),
        ):
            with self.assertRaises(ValidationError):
                reconcile_payment(attempt.pk, self.recruiter)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "pending")

    def test_cancelled_provider_result_is_unsuccessful(self):
        attempt = self.begin()
        with patch(
            "mpesa.client.DarajaSandboxClient.query",
            return_value=self.result(ResultCode=1032),
        ):
            self.assertEqual(
                reconcile_payment(attempt.pk, self.recruiter).status, "failed"
            )

    def test_query_failure_remains_pending_and_rechecks_have_cooldown(self):
        attempt = self.begin()
        with patch("mpesa.client.DarajaSandboxClient.query", side_effect=ProviderError):
            with self.assertRaises(ValidationError):
                reconcile_payment(attempt.pk, self.recruiter)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "pending")
        with self.assertRaises(ValidationError):
            reconcile_payment(attempt.pk, self.recruiter)

    def test_callback_claims_cannot_mark_payment_successful(self):
        attempt = self.begin()
        payload = {
            "Body": {
                "stkCallback": {
                    **ACCEPTED,
                    "ResultCode": 0,
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 1000},
                            {"Name": "MpesaReceiptNumber", "Value": "FORGED"},
                        ]
                    },
                }
            }
        }
        for _ in range(2):
            self.assertEqual(
                self.client.post(
                    reverse("mpesa:callback"),
                    json.dumps(payload),
                    content_type="application/json",
                ).status_code,
                200,
            )
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "pending")
        self.assertIsNotNone(attempt.callback_received_at)
        self.assertEqual(self.booking.payments.count(), 0)

    def test_callback_invalid_unknown_and_large_requests(self):
        url = reverse("mpesa:callback")
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(
            self.client.post(url, "[]", content_type="application/json").status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                url, "x" * 17000, content_type="application/json"
            ).status_code,
            413,
        )
        data = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "unknown",
                    "MerchantRequestID": "unknown",
                }
            }
        }
        self.assertEqual(
            self.client.post(
                url, json.dumps(data), content_type="application/json"
            ).status_code,
            200,
        )
        self.assertFalse(MpesaTransaction.objects.exists())

    def test_pages_are_participant_scoped_and_phone_is_masked(self):
        self.begin()
        url = reverse("mpesa:booking", args=[self.booking.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.worker)
        response = self.client.get(url)
        self.assertContains(response, "Payment history")
        self.assertNotContains(response, "Sandbox")
        self.assertNotContains(response, "sandbox")
        self.assertNotContains(response, "254712345678")
        self.assertEqual(self.client.post(url, self.fields).status_code, 403)

    def test_recruiter_post_and_status_checks_require_csrf(self):
        attempt = self.begin()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.recruiter)
        self.assertEqual(
            client.post(
                reverse("mpesa:booking", args=[self.booking.pk]), self.fields
            ).status_code,
            403,
        )
        self.assertEqual(
            client.post(
                reverse("mpesa:check", args=[self.booking.pk, attempt.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            client.get(
                reverse("mpesa:check", args=[self.booking.pk, attempt.pk])
            ).status_code,
            405,
        )

    def test_disabled_configuration_fails_closed(self):
        with override_settings(MPESA_SANDBOX={**CONFIG, "enabled": False}):
            self.assertFalse(sandbox_ready())
            with self.assertRaises(ValidationError):
                initiate_payment(self.booking.pk, self.recruiter, self.fields)
        self.assertFalse(MpesaTransaction.objects.exists())

    def test_phone_normalization_and_fractional_form_rejection(self):
        self.assertEqual(normalize_phone("+254 712 345 678"), "254712345678")
        self.assertEqual(normalize_phone("0112345678"), "254112345678")
        with self.assertRaises(ValidationError):
            normalize_phone("not a phone")
        self.assertFalse(
            SandboxPaymentForm({**self.fields, "amount": "1.5"}).is_valid()
        )

    def test_client_builds_sandbox_payload_and_does_not_send_pin(self):
        attempt = self.begin()
        with patch.object(
            DarajaSandboxClient,
            "_request",
            side_effect=[{"access_token": "fictional-token"}, ACCEPTED],
        ) as request:
            DarajaSandboxClient().initiate(attempt)
        payload = request.call_args.args[2]
        self.assertEqual(SANDBOX_HOST, "https://sandbox.safaricom.co.ke")
        self.assertEqual(payload["Amount"], 500)
        self.assertEqual(payload["PhoneNumber"], "254712345678")
        self.assertLessEqual(len(payload["AccountReference"]), 12)
        self.assertNotIn("PIN", payload)
        decoded = base64.b64decode(payload["Password"]).decode()
        self.assertEqual(decoded, "174379fictional-passkey" + payload["Timestamp"])

    def test_network_failures_do_not_expose_response_or_credentials(self):
        with patch("mpesa.client.build_opener") as opener:
            opener.return_value.open.side_effect = URLError(
                "private credential details"
            )
            with self.assertRaises(ProviderError) as raised:
                DarajaSandboxClient()._token()
        self.assertNotIn("private", str(raised.exception))

    def test_localhost_callback_is_not_ready(self):
        with override_settings(
            MPESA_SANDBOX={
                **CONFIG,
                "callback_url": "http://127.0.0.1:8001/payments/mpesa/callback/",
            }
        ):
            self.assertFalse(sandbox_ready())

    def test_completed_booking_exposes_payment_entry_points(self):
        self.client.force_login(self.recruiter)
        response = self.client.get(reverse("freelance:booking", args=[self.booking.pk]))
        self.assertContains(
            response, 'href="' + reverse("mpesa:booking", args=[self.booking.pk]) + '"'
        )
        self.assertContains(response, "M-Pesa payments")
        listing = self.client.get(reverse("freelance:bookings"))
        self.assertContains(listing, "M-Pesa payments")

    def test_unfinished_booking_explains_payment_availability_without_enabling_submission(
        self,
    ):
        self.booking.status = "accepted"
        self.booking.save()
        self.client.force_login(self.recruiter)
        response = self.client.get(reverse("freelance:booking", args=[self.booking.pk]))
        self.assertContains(response, "M-Pesa payments")
        self.assertContains(response, "after the recruiter confirms work completion")
        payment_page = self.client.get(reverse("mpesa:booking", args=[self.booking.pk]))
        self.assertContains(payment_page, "after the recruiter confirms completion")
        self.assertNotContains(payment_page, ">Pay with M-Pesa</button>")

    def test_recruiter_confirmation_redirects_to_payment_after_state_change(self):
        self.booking.status = "completion_requested"
        self.booking.save()
        self.client.force_login(self.recruiter)
        response = self.client.post(
            reverse("freelance:booking", args=[self.booking.pk]),
            {"action": "confirm_completion"},
        )
        self.assertRedirects(response, reverse("mpesa:booking", args=[self.booking.pk]))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "completed")
        self.assertEqual(self.booking.payments.count(), 0)

    def test_invalid_completion_does_not_redirect_to_payment(self):
        self.booking.status = "requested"
        self.booking.save()
        self.client.force_login(self.recruiter)
        response = self.client.post(
            reverse("freelance:booking", args=[self.booking.pk]),
            {"action": "confirm_completion"},
        )
        self.assertEqual(response.status_code, 400)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "requested")

    def test_worker_completion_request_still_waits_for_recruiter(self):
        self.booking.status = "accepted"
        self.booking.save()
        self.client.force_login(self.worker)
        response = self.client.post(
            reverse("freelance:booking", args=[self.booking.pk]),
            {"action": "request_completion"},
        )
        self.assertRedirects(
            response, reverse("freelance:booking", args=[self.booking.pk])
        )
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "completion_requested")

    def test_commission_is_exact_and_shares_always_sum_to_total(self):
        from freelance.pricing import commission_breakdown

        for amount, expected in (
            ("10000", "1000.00"),
            ("100.05", "10.01"),
            ("1", "0.10"),
            ("0", "0.00"),
        ):
            with self.subTest(amount=amount):
                result = commission_breakdown(amount)
                self.assertEqual(result["commission"], Decimal(expected))
                self.assertEqual(
                    result["commission"] + result["worker_share"], result["gross"]
                )
        for amount in ("NaN", "Infinity", "-1"):
            with self.assertRaises(ValueError):
                commission_breakdown(amount)

    def test_partial_request_has_own_commission_without_mutating_worker_payments(self):
        attempt = self.begin()
        self.assertEqual(attempt.commission["commission"], Decimal("50.00"))
        self.assertEqual(attempt.commission["worker_share"], Decimal("450.00"))
        self.assertEqual(self.booking.payments.count(), 0)

    def test_breakdown_is_visible_before_acceptance_and_on_payment_page(self):
        self.booking.status = "requested"
        self.booking.save()
        self.client.force_login(self.worker)
        response = self.client.get(reverse("freelance:booking", args=[self.booking.pk]))
        self.assertContains(response, "KaziForce commission (10%)")
        self.assertContains(response, "KES 100.00")
        self.assertContains(response, "KES 900.00")
        header = response.content.decode().split("</header>", 1)[0]
        self.assertNotIn("M-Pesa payments", header)
        self.client.force_login(self.recruiter)
        response = self.client.get(reverse("mpesa:booking", args=[self.booking.pk]))
        self.assertContains(response, "Price breakdown")
        self.assertContains(response, "Not sent through KaziForce")

    def test_partial_payment_updates_balance_once_after_verified_result(self):
        from mpesa.services import payment_summary

        attempt = self.begin()
        self.assertEqual(payment_summary(self.booking)["received"], 0)
        with patch(
            "mpesa.client.DarajaSandboxClient.query", return_value=self.result()
        ):
            reconcile_payment(attempt.pk, self.recruiter)
            reconcile_payment(attempt.pk, self.recruiter)
        summary = payment_summary(self.booking)
        self.assertEqual(summary["received"], 500)
        self.assertEqual(summary["remaining"], 500)
        self.assertEqual(summary["label"], "Partially paid")
        self.assertFalse(summary["is_paid"])
        self.assertEqual(self.booking.payments.count(), 0)

    def test_full_payment_displays_completed_and_hides_payment_form(self):
        self.fields["amount"] = 1000
        attempt = self.begin()
        with patch(
            "mpesa.client.DarajaSandboxClient.query", return_value=self.result()
        ):
            reconcile_payment(attempt.pk, self.recruiter)
        self.client.force_login(self.recruiter)
        response = self.client.get(reverse("mpesa:booking", args=[self.booking.pk]))
        self.assertContains(response, "Payment complete")
        self.assertContains(response, "paid in full")
        self.assertNotContains(response, ">Pay with M-Pesa</button>")
        self.assertEqual(response.context["payment_summary"]["remaining"], 0)
        self.assertContains(response, "Not sent through KaziForce")

    def test_json_status_check_updates_balance_and_is_owner_scoped(self):
        attempt = self.begin()
        url = reverse("mpesa:check", args=[self.booking.pk, attempt.pk])
        self.client.force_login(self.recruiter)
        with patch(
            "mpesa.client.DarajaSandboxClient.query", return_value=self.result()
        ):
            response = self.client.post(url, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(Decimal(response.json()["remaining"]), 500)
        self.client.force_login(self.worker)
        self.assertEqual(
            self.client.post(url, HTTP_ACCEPT="application/json").status_code, 403
        )
        self.client.force_login(self.stranger)
        self.assertEqual(
            self.client.post(url, HTTP_ACCEPT="application/json").status_code, 404
        )

    def test_polling_markup_only_exists_for_pending_recruiter_request(self):
        self.begin()
        url = reverse("mpesa:booking", args=[self.booking.pk])
        self.client.force_login(self.recruiter)
        self.assertContains(self.client.get(url), "data-payment-check")
        self.client.force_login(self.worker)
        self.assertNotContains(self.client.get(url), "data-payment-check")

    def test_manual_and_mpesa_requests_cannot_reserve_same_balance(self):
        from freelance.services import report_payment

        self.begin()
        with self.assertRaises(ValidationError):
            report_payment(
                self.booking.pk,
                self.recruiter,
                {
                    "kind": "balance",
                    "method": "cash",
                    "amount": Decimal("501"),
                    "reference": "",
                },
            )
        report_payment(
            self.booking.pk,
            self.recruiter,
            {
                "kind": "balance",
                "method": "cash",
                "amount": Decimal("500"),
                "reference": "",
            },
        )

    def test_pending_direct_report_reserves_balance_without_appearing_paid(self):
        from freelance.services import report_payment
        from mpesa.services import payment_summary, sandbox_remaining

        report_payment(
            self.booking.pk,
            self.recruiter,
            {
                "kind": "balance",
                "method": "cash",
                "amount": Decimal("800"),
                "reference": "",
            },
        )
        self.assertEqual(payment_summary(self.booking)["received"], 0)
        self.assertEqual(sandbox_remaining(self.booking), 200)
        with self.assertRaises(ValidationError):
            self.begin()

    def test_failed_provider_result_never_reduces_balance(self):
        from mpesa.services import payment_summary

        attempt = self.begin()
        with patch(
            "mpesa.client.DarajaSandboxClient.query",
            return_value=self.result(ResultCode=1032),
        ):
            reconcile_payment(attempt.pk, self.recruiter)
        self.assertEqual(payment_summary(self.booking)["remaining"], 1000)
        self.assertEqual(payment_summary(self.booking)["received"], 0)

    def test_recruiter_can_confirm_accepted_work_without_worker_request(self):
        self.booking.status = "accepted"
        self.booking.save()
        self.client.force_login(self.recruiter)
        url = reverse("freelance:booking", args=[self.booking.pk])
        self.assertContains(self.client.get(url), 'value="confirm_completion"')
        response = self.client.post(url, {"action": "confirm_completion"})
        self.assertRedirects(response, reverse("mpesa:booking", args=[self.booking.pk]))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "completed")
        self.assertIsNotNone(self.booking.completed_at)
        self.assertFalse(self.booking.payments.exists())
        self.assertFalse(self.booking.mpesa_transactions.exists())

    def test_worker_cannot_use_recruiter_direct_completion(self):
        self.booking.status = "accepted"
        self.booking.save()
        self.client.force_login(self.worker)
        url = reverse("freelance:booking", args=[self.booking.pk])
        self.assertNotContains(self.client.get(url), 'value="confirm_completion"')
        self.assertEqual(
            self.client.post(url, {"action": "confirm_completion"}).status_code, 400
        )
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "accepted")

    def test_future_booking_has_disabled_completion_and_rejects_direct_post(self):
        from datetime import timedelta

        self.booking.status = "accepted"
        self.booking.start_date = self.booking.end_date = (
            timezone.localdate() + timedelta(days=1)
        )
        self.booking.save()
        self.client.force_login(self.recruiter)
        url = reverse("freelance:booking", args=[self.booking.pk])
        page = self.client.get(url)
        self.assertContains(page, 'value="confirm_completion" disabled')
        self.assertContains(page, "Completion confirmation is available from")
        self.assertEqual(
            self.client.post(url, {"action": "confirm_completion"}).status_code, 400
        )
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "accepted")

    def test_pending_cancellation_disables_recruiter_completion(self):
        self.booking.status = "accepted"
        self.booking.cancellation_requested_by = self.worker
        self.booking.cancellation_reason = "Schedule changed"
        self.booking.save()
        self.client.force_login(self.recruiter)
        url = reverse("freelance:booking", args=[self.booking.pk])
        self.assertContains(self.client.get(url), 'value="confirm_completion" disabled')
        self.assertEqual(
            self.client.post(url, {"action": "confirm_completion"}).status_code, 400
        )
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "accepted")

    def test_completion_cannot_be_confirmed_twice(self):
        self.client.force_login(self.recruiter)
        response = self.client.post(
            reverse("freelance:booking", args=[self.booking.pk]),
            {"action": "confirm_completion"},
        )
        self.assertEqual(response.status_code, 400)
