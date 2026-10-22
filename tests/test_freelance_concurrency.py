"""Independent PostgreSQL transactions protect capacity and payment limits."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, close_old_connections, connections
from django.test import TransactionTestCase
from django.utils import timezone
from freelance.models import FreelancerProfile, Booking, Payment
from freelance.services import (
    start_conversation,
    request_booking,
    booking_transition,
    report_payment,
)


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL row locks")
class FreelanceConcurrencyTests(TransactionTestCase):
    def setUp(self):
        User = get_user_model()
        self.worker = User.objects.create_user(
            username="capacity-worker", email="capacity@example.test"
        )
        self.recruiter = User.objects.create_user(
            username="capacity-recruiter",
            email="booking@example.test",
            role="recruiter",
        )
        self.today = timezone.localdate()
        self.profile = FreelancerProfile.objects.create(
            user=self.worker,
            title="Consultant",
            about="Services",
            location="Nairobi",
            rate=1000,
            available_from=self.today,
            accepting_bookings=True,
            share_professional_profile=True,
        )
        self.thread = start_conversation(self.recruiter, self.profile.pk, "Enquiry")
        self.fields = {
            "title": "Consultancy",
            "scope": "Agreed work",
            "location": "Nairobi",
            "start_date": self.today,
            "end_date": self.today + timedelta(days=2),
            "total_price": Decimal("10000"),
            "deposit_amount": Decimal("0"),
            "cancellation_terms": "Agree cancellation first.",
            "recruiter_name": "Recruiter",
            "recruiter_email": "booking@example.test",
        }

    def parallel(self, operation):
        barrier = Barrier(2)

        def run(index):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                operation(index)
                return "saved"
            except ValidationError:
                return "rejected"
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, index) for index in range(2)]
            return [future.result(timeout=20) for future in futures]

    def test_simultaneous_overlapping_acceptances_reserve_dates_once(self):
        bookings = [
            request_booking(self.thread.pk, self.recruiter, self.fields)
            for _ in range(2)
        ]

        def accept(index):
            worker = get_user_model().objects.get(pk=self.worker.pk)
            booking_transition(
                bookings[index].pk,
                worker,
                "accept",
                {
                    "agree": True,
                    "freelancer_name": "Worker",
                    "freelancer_email": "work@example.test",
                },
            )

        self.assertCountEqual(self.parallel(accept), ["saved", "rejected"])
        self.assertEqual(Booking.objects.filter(status="accepted").count(), 1)

    def test_simultaneous_payment_reports_cannot_over_report_balance(self):
        booking = request_booking(self.thread.pk, self.recruiter, self.fields)
        booking_transition(
            booking.pk,
            self.worker,
            "accept",
            {
                "agree": True,
                "freelancer_name": "Worker",
                "freelancer_email": "work@example.test",
            },
        )

        booking_transition(booking.pk, self.worker, "request_completion")
        booking_transition(booking.pk, self.recruiter, "confirm_completion")

        def pay(index):
            recruiter = get_user_model().objects.get(pk=self.recruiter.pk)
            report_payment(
                booking.pk,
                recruiter,
                {
                    "amount": Decimal("7000"),
                    "kind": "balance",
                    "method": "direct",
                    "reference": "Transfer",
                },
            )

        self.assertCountEqual(self.parallel(pay), ["saved", "rejected"])
        self.assertEqual(Payment.objects.count(), 1)

    def test_simultaneous_enquiries_share_one_conversation(self):
        def enquire(index):
            recruiter = get_user_model().objects.get(pk=self.recruiter.pk)
            start_conversation(recruiter, self.profile.pk, f"Enquiry {index}")

        self.assertCountEqual(self.parallel(enquire), ["saved", "saved"])
        self.assertEqual(self.profile.conversations.count(), 1)
        self.assertEqual(self.thread.messages.count(), 3)
