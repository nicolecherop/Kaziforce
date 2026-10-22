"""End-to-end freelance agreements, isolation, availability and payment integrity."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from candidates.models import CandidateProfile, CandidateSkill
from freelance.models import (
    FreelancerProfile,
    FreelanceService,
    FreelanceProject,
    Conversation,
    Message,
    Booking,
    Payment,
    Review,
    ConversationReport,
)
from freelance.services import (
    start_conversation,
    request_booking,
    booking_transition,
    report_payment,
    payment_transition,
    payment_totals,
    leave_review,
    send_message,
)
from freelance.selectors import freelance_search, inbox_for


class FreelanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.worker = User.objects.create_user(
            username="free-worker", email="worker@example.test", first_name="Wanjiku"
        )
        cls.recruiter = User.objects.create_user(
            username="free-recruiter", email="recruiter@example.test", role="recruiter"
        )
        cls.stranger = User.objects.create_user(
            username="free-stranger", email="stranger@example.test", role="recruiter"
        )
        cls.other_worker = User.objects.create_user(
            username="free-other-worker", email="otherworker@example.test"
        )
        cls.admin = User.objects.create_superuser(
            username="free-admin", email="admin@example.test", role="administrator"
        )
        cls.professional = CandidateProfile.objects.create(
            user=cls.worker,
            headline="Analyst",
            contact_email="private@example.test",
            phone_number="+254712345678",
        )
        CandidateSkill.objects.create(profile=cls.professional, name="SQL")
        CandidateSkill.objects.create(profile=cls.professional, name="Python")
        cls.today = timezone.localdate()
        cls.profile = FreelancerProfile.objects.create(
            user=cls.worker,
            title="Data consultancy",
            about="Data insights for your team",
            location="Nairobi",
            rate=1000,
            rate_unit="day",
            work_mode="remote",
            available_from=cls.today,
            accepting_bookings=True,
            share_professional_profile=True,
        )
        cls.thread = start_conversation(
            cls.recruiter, cls.profile.pk, "Can you help with our data?"
        )

    def fields(self, **overrides):
        data = {
            "title": "Reporting assignment",
            "scope": "Deliver a dashboard and handover notes",
            "location": "Remote",
            "start_date": self.today,
            "end_date": self.today + timedelta(days=2),
            "total_price": Decimal("10000"),
            "deposit_amount": Decimal("0"),
            "cancellation_terms": "Unstarted work is refundable by agreement.",
            "recruiter_name": "Sarah Mwangi",
            "recruiter_email": "hiring@example.test",
            "recruiter_phone": "+254711222333",
        }
        return {**data, **overrides}

    def booking(self, **overrides):
        return request_booking(self.thread.pk, self.recruiter, self.fields(**overrides))

    def accept(self, booking):
        return booking_transition(
            booking.pk,
            self.worker,
            "accept",
            {
                "agree": True,
                "freelancer_name": "Wanjiku",
                "freelancer_email": "work@example.test",
                "freelancer_phone": "+254712345678",
            },
        )

    def complete(self, booking):
        booking.refresh_from_db()
        if booking.status == "requested":
            self.accept(booking)
        booking_transition(booking.pk, self.worker, "request_completion")
        return booking_transition(booking.pk, self.recruiter, "confirm_completion")

    def payment(self, booking, amount="2000", kind="balance", actor=None):
        return report_payment(
            booking.pk,
            actor or self.recruiter,
            {
                "amount": Decimal(amount),
                "kind": kind,
                "method": "cash",
                "reference": "Paid in person",
            },
        )

    def test_end_to_end_booking_receipts_completion_and_rating(self):
        booking = self.booking()
        self.assertEqual(booking.status, "requested")
        self.assertFalse(booking.freelancer_email)
        self.complete(booking)
        first_payment = self.payment(booking)
        self.assertEqual(payment_totals(booking)["received"], 0)
        payment_transition(first_payment.pk, self.worker, "confirm")
        self.assertEqual(payment_totals(booking)["remaining"], 8000)
        balance = self.payment(booking, "8000", "balance")
        payment_transition(balance.pk, self.worker, "confirm")
        review = leave_review(
            booking.pk,
            self.recruiter,
            {"rating": 5, "comment": "Clear communication and excellent work."},
        )
        self.assertEqual(review.rating, 5)
        self.assertEqual(payment_totals(booking)["remaining"], 0)
        self.assertTrue(
            self.thread.messages.filter(
                is_system=True, body__contains="Booking requested"
            ).exists()
        )

    def test_overlapping_acceptance_is_rejected_but_requests_do_not_reserve(self):
        first = self.booking()
        second = self.booking()
        self.accept(first)
        with self.assertRaisesMessage(ValidationError, "confirmed booking"):
            self.accept(second)
        second.refresh_from_db()
        self.assertEqual(second.status, "requested")

    def test_non_overlapping_booking_is_allowed(self):
        self.accept(self.booking())
        later = self.booking(
            start_date=self.today + timedelta(days=3),
            end_date=self.today + timedelta(days=4),
        )
        self.assertEqual(self.accept(later).status, "accepted")

    def test_contact_details_are_not_in_listing_and_snapshot_is_preserved(self):
        self.client.force_login(self.recruiter)
        response = self.client.get(reverse("freelance:worker", args=[self.profile.pk]))
        self.assertNotContains(response, "private@example.test")
        self.assertNotContains(response, "+254712345678")
        booking = self.accept(self.booking())
        self.professional.contact_email = "changed@example.test"
        self.professional.save()
        booking.refresh_from_db()
        self.assertEqual(booking.freelancer_email, "work@example.test")

    def test_inactive_listing_hides_new_work_but_preserves_existing_messages(self):
        booking = self.accept(self.booking())
        self.profile.accepting_bookings = False
        self.profile.save()
        self.assertNotIn(self.profile, freelance_search({}))
        with self.assertRaises(ValidationError):
            start_conversation(self.stranger, self.profile.pk, "New enquiry")
        send_message(self.thread.pk, self.recruiter, "Discuss our existing work")
        self.client.force_login(self.worker)
        self.assertEqual(
            self.client.get(
                reverse("freelance:booking", args=[booking.pk])
            ).status_code,
            200,
        )
        self.client.force_login(self.recruiter)
        self.assertEqual(
            self.client.get(
                reverse("freelance:worker", args=[self.profile.pk])
            ).status_code,
            404,
        )

    def test_other_users_cannot_read_or_mutate_private_records(self):
        booking = self.complete(self.booking())
        payment = self.payment(booking)
        for user in (self.stranger, self.other_worker):
            self.client.force_login(user)
            for name, args in [
                ("conversation", [self.thread.pk]),
                ("booking", [booking.pk]),
                ("conversation_controls", [self.thread.pk]),
            ]:
                self.assertEqual(
                    self.client.get(
                        reverse("freelance:" + name, args=args)
                    ).status_code,
                    404,
                )
            self.assertEqual(
                self.client.post(
                    reverse("freelance:booking", args=[booking.pk]),
                    {"action": "confirm_completion"},
                ).status_code,
                404,
            )
            self.assertEqual(
                self.client.post(
                    reverse("freelance:payment_action", args=[booking.pk, payment.pk]),
                    {"action": "confirm"},
                ).status_code,
                404,
            )

    def test_roles_and_anonymous_access(self):
        self.assertEqual(self.client.get(reverse("freelance:inbox")).status_code, 302)
        self.client.force_login(self.worker)
        self.assertEqual(self.client.get(reverse("freelance:find")).status_code, 403)
        self.client.force_login(self.recruiter)
        self.assertEqual(
            self.client.get(reverse("freelance:profile_edit")).status_code, 403
        )
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("freelance:inbox")).status_code, 403)

    def test_cannot_accept_others_booking_or_change_price(self):
        booking = self.booking()
        with self.assertRaises(ValidationError):
            booking_transition(booking.pk, self.recruiter, "accept", {"agree": True})
        with self.assertRaises(PermissionDenied):
            booking_transition(booking.pk, self.other_worker, "decline")
        self.client.force_login(self.worker)
        response = self.client.post(
            reverse("freelance:booking", args=[booking.pk]),
            {
                "action": "accept",
                "agree": "on",
                "freelancer_name": "Worker",
                "freelancer_email": "work@example.test",
                "total_price": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.total_price, 10000)

    def test_accept_requires_consent_and_valid_contact(self):
        booking = self.booking()
        self.client.force_login(self.worker)
        response = self.client.post(
            reverse("freelance:booking", args=[booking.pk]),
            {"action": "accept", "freelancer_email": "invalid"},
        )
        self.assertEqual(response.status_code, 400)
        booking.refresh_from_db()
        self.assertEqual(booking.status, "requested")

    def test_booking_form_rejects_bad_dates(self):
        self.client.force_login(self.recruiter)
        response = self.client.post(
            reverse("freelance:book", args=[self.thread.pk]),
            {
                **self.fields(),
                "share_contacts": "on",
                "end_date": self.today - timedelta(days=1),
                "deposit_amount": "15000",
            },
        )
        self.assertContains(response, "end date must be on or after", status_code=200)
        self.assertFalse(Booking.objects.exists())

    def test_new_advance_requirements_and_reports_are_rejected(self):
        with self.assertRaisesMessage(ValidationError, "not supported"):
            self.booking(deposit_amount=Decimal("2000"))
        booking = self.complete(self.booking())
        with self.assertRaisesMessage(ValidationError, "not supported"):
            self.payment(booking, "2000", "deposit")
        self.assertFalse(Payment.objects.exists())

    def test_contacts_unlock_only_after_acceptance_without_payment(self):
        booking = self.booking()
        url = reverse("freelance:booking", args=[booking.pk])
        self.client.force_login(self.worker)
        response = self.client.get(url)
        self.assertNotContains(response, "hiring@example.test")
        self.assertNotContains(response, "+254711222333")
        self.assertContains(response, "Shared when you accept")
        self.accept(booking)
        response = self.client.get(url)
        self.assertContains(response, "hiring@example.test")
        self.assertContains(response, "+254711222333")
        self.client.force_login(self.recruiter)
        self.assertContains(self.client.get(url), "work@example.test")
        self.assertFalse(Payment.objects.exists())

    def test_no_deposit_option_or_payment_form_before_completion(self):
        booking = self.accept(self.booking())
        self.client.force_login(self.recruiter)
        self.assertNotContains(
            self.client.get(reverse("freelance:book", args=[self.thread.pk])),
            'name="deposit_amount"',
        )
        response = self.client.get(reverse("freelance:booking", args=[booking.pk]))
        self.assertNotContains(response, "Report a payment you have made")
        response = self.client.post(
            reverse("freelance:booking", args=[booking.pk]),
            {
                "action": "report_payment",
                "kind": "balance",
                "method": "cash",
                "amount": "10000",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Payment.objects.exists())
        self.complete(booking)
        response = self.client.get(reverse("freelance:booking", args=[booking.pk]))
        self.assertContains(response, "Report a payment you have made")
        self.assertNotContains(response, 'value="deposit"')

    def test_future_completion_action_is_replaced_by_start_date_guidance(self):
        start = self.today + timedelta(days=2)
        booking = self.accept(self.booking(start_date=start, end_date=start))
        self.client.force_login(self.worker)
        url = reverse("freelance:booking", args=[booking.pk])
        response = self.client.get(url)
        self.assertNotContains(response, 'value="request_completion"')
        self.assertContains(response, "You can mark work complete from")
        self.assertEqual(response.context["completion_available_from"], start)
        self.assertContains(response, "Request cancellation")
        # A direct POST still goes through the original server-side date check.
        response = self.client.post(url, {"action": "request_completion"})
        self.assertContains(response, "before its start date", status_code=400)
        booking.refresh_from_db()
        self.assertEqual(booking.status, "accepted")
        self.client.force_login(self.recruiter)
        self.assertNotContains(self.client.get(url), "You can mark work complete from")

    def test_completion_action_is_available_on_the_start_date(self):
        booking = self.accept(self.booking())
        self.client.force_login(self.worker)
        url = reverse("freelance:booking", args=[booking.pk])
        response = self.client.get(url)
        self.assertContains(response, 'value="request_completion"')
        self.assertNotContains(response, "You can mark work complete from")
        self.assertEqual(
            self.client.post(url, {"action": "request_completion"}).status_code, 302
        )
        booking.refresh_from_db()
        self.assertEqual(booking.status, "completion_requested")

    def test_earlier_pending_advance_request_is_not_silently_accepted(self):
        legacy = Booking.objects.create(
            conversation=self.thread, **self.fields(deposit_amount=Decimal("2000"))
        )
        with self.assertRaisesMessage(ValidationError, "withdraw"):
            self.accept(legacy)
        legacy.refresh_from_db()
        self.assertEqual(legacy.deposit_amount, 2000)
        self.assertEqual(legacy.status, "requested")
        self.assertIsNone(legacy.accepted_at)

    def test_no_payment_before_completion_and_no_self_confirmation(self):
        booking = self.booking()
        with self.assertRaises(ValidationError):
            self.payment(booking)
        self.accept(booking)
        with self.assertRaisesMessage(ValidationError, "confirms completion"):
            self.payment(booking)
        self.complete(booking)
        payment = self.payment(booking)
        with self.assertRaises(ValidationError):
            payment_transition(payment.pk, self.recruiter, "confirm")

    def test_payment_bounds_dispute_and_withdrawal(self):
        booking = self.complete(self.booking())
        payment = self.payment(booking, "2000")
        with self.assertRaises(ValidationError):
            self.payment(booking, "1", "deposit")
        with self.assertRaises(ValidationError):
            self.payment(booking, "9000", "balance")
        payment_transition(payment.pk, self.worker, "dispute")
        self.assertEqual(payment_totals(booking)["received"], 0)
        payment_transition(payment.pk, self.recruiter, "withdraw")
        new = self.payment(booking, "2000")
        payment_transition(new.pk, self.worker, "confirm")
        with self.assertRaises(ValidationError):
            payment_transition(new.pk, self.recruiter, "withdraw")
        with self.assertRaises(ValidationError):
            payment_transition(new.pk, self.worker, "confirm")

    def test_refunds_require_confirmed_receipts_and_recipient_confirmation(self):
        booking = self.complete(self.booking())
        payment = self.payment(booking)
        with self.assertRaises(ValidationError):
            self.payment(booking, "100", "refund", self.worker)
        payment_transition(payment.pk, self.worker, "confirm")
        refund = self.payment(booking, "500", "refund", self.worker)
        self.assertEqual(payment_totals(booking)["net"], 2000)
        payment_transition(refund.pk, self.recruiter, "confirm")
        self.assertEqual(payment_totals(booking)["net"], 1500)
        with self.assertRaises(PermissionDenied):
            self.payment(booking, "100", "refund", self.recruiter)

    def test_cancellation_is_mutual_and_refunds_remain_possible(self):
        booking = self.accept(self.booking())
        # An earlier report remains confirmable and refundable without rewriting its evidence.
        payment = Payment.objects.create(
            booking=booking,
            reported_by=self.recruiter,
            amount=2000,
            kind="deposit",
            method="cash",
        )
        payment_transition(payment.pk, self.worker, "confirm")
        booking_transition(
            booking.pk, self.worker, "request_cancel", {"reason": "Unable to attend."}
        )
        booking.refresh_from_db()
        self.assertEqual(booking.status, "accepted")
        with self.assertRaises(PermissionDenied):
            booking_transition(booking.pk, self.worker, "agree_cancel")
        booking_transition(booking.pk, self.recruiter, "agree_cancel")
        booking.refresh_from_db()
        self.assertEqual(booking.status, "cancelled")
        with self.assertRaises(ValidationError):
            self.payment(booking, "100", "balance")
        self.payment(booking, "2000", "refund", self.worker)

    def test_declined_cancellation_and_requested_changes_keep_work_active(self):
        booking = self.accept(self.booking())
        booking_transition(
            booking.pk, self.worker, "request_cancel", {"reason": "Discuss dates"}
        )
        booking_transition(booking.pk, self.recruiter, "decline_cancel")
        booking_transition(booking.pk, self.worker, "request_completion")
        booking_transition(booking.pk, self.recruiter, "request_changes")
        booking.refresh_from_db()
        self.assertEqual(booking.status, "accepted")
        self.assertIsNone(booking.cancellation_requested_by_id)

    def test_reviews_require_completion_unique_and_recruiter_ownership(self):
        booking = self.booking()
        with self.assertRaises(ValidationError):
            leave_review(
                booking.pk, self.recruiter, {"rating": 5, "comment": "Too early"}
            )
        self.complete(booking)
        with self.assertRaises(PermissionDenied):
            leave_review(booking.pk, self.worker, {"rating": 5, "comment": "Self"})
        leave_review(booking.pk, self.recruiter, {"rating": 4, "comment": "Good work"})
        with self.assertRaises(ValidationError):
            leave_review(booking.pk, self.recruiter, {"rating": 5, "comment": "Again"})

    def test_blocking_stops_messages_and_new_bookings_not_existing_actions(self):
        booking = self.accept(self.booking())
        self.client.force_login(self.worker)
        self.client.post(
            reverse("freelance:conversation_controls", args=[self.thread.pk]),
            {"action": "block"},
        )
        with self.assertRaises(ValidationError):
            send_message(self.thread.pk, self.recruiter, "Blocked message")
        with self.assertRaises(ValidationError):
            self.booking()
        booking_transition(booking.pk, self.worker, "request_completion")
        self.assertEqual(
            self.client.get(
                reverse("freelance:booking", args=[booking.pk])
            ).status_code,
            200,
        )

    def test_report_is_private_and_message_html_is_escaped(self):
        send_message(self.thread.pk, self.recruiter, "<script>alert('x')</script>")
        self.client.force_login(self.worker)
        self.client.post(
            reverse("freelance:conversation_controls", args=[self.thread.pk]),
            {"action": "report", "reason": "Private report detail"},
        )
        self.assertEqual(ConversationReport.objects.count(), 1)
        self.client.force_login(self.recruiter)
        response = self.client.get(
            reverse("freelance:conversation", args=[self.thread.pk])
        )
        self.assertNotContains(response, "Private report detail")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert")

    def test_booking_updates_appear_as_unread_messages(self):
        self.client.force_login(self.worker)
        self.client.get(reverse("freelance:conversation", args=[self.thread.pk]))
        self.assertFalse(inbox_for(self.worker).get(pk=self.thread.pk).unread)
        self.booking()
        self.assertTrue(inbox_for(self.worker).get(pk=self.thread.pk).unread)

    def test_project_proposal_creates_scoped_conversation_and_closed_blocks_new(self):
        project = FreelanceProject.objects.create(
            recruiter=self.recruiter,
            title="Analytics",
            description="Build reports",
            location="Remote",
            work_mode="remote",
            budget=5000,
            start_date=self.today,
            end_date=self.today + timedelta(days=1),
            skills=["SQL"],
        )
        thread = start_conversation(
            self.worker, self.profile.pk, "My approach", project.pk
        )
        self.assertEqual(thread.project_id, project.pk)
        project.status = "closed"
        project.save()
        with self.assertRaises(ValidationError):
            start_conversation(self.worker, self.profile.pk, "New proposal", project.pk)
        send_message(thread.pk, self.worker, "Existing enquiry continues")

    def test_search_uses_skill_fit_then_ratings_and_respects_dates(self):
        other = FreelancerProfile.objects.create(
            user=self.other_worker,
            title="Writer",
            about="Copywriting",
            location="Nairobi",
            rate=1000,
            available_from=self.today,
            accepting_bookings=True,
            share_professional_profile=True,
        )
        other_professional = CandidateProfile.objects.create(user=self.other_worker)
        CandidateSkill.objects.create(profile=other_professional, name="SQL")
        project = FreelanceProject.objects.create(
            recruiter=self.recruiter,
            title="Data",
            description="SQL analysis",
            location="Remote",
            work_mode="flexible",
            budget=10000,
            start_date=self.today,
            end_date=self.today + timedelta(days=2),
            skills=["SQL", "Python"],
        )
        self.assertEqual(freelance_search({}, project)[0].pk, self.profile.pk)
        self.accept(self.booking())
        self.assertNotIn(self.profile, freelance_search({}, project))
        self.assertIn(other, freelance_search({}, project))

    def test_hidden_reviews_do_not_contribute_to_ratings(self):
        booking = self.complete(self.booking())
        review = leave_review(
            booking.pk, self.recruiter, {"rating": 5, "comment": "Excellent"}
        )
        self.assertEqual(freelance_search({})[0].review_count, 1)
        review.is_hidden = True
        review.save()
        self.assertEqual(freelance_search({})[0].review_count, 0)

    def test_search_rejects_malformed_project_and_rate_comparison(self):
        self.client.force_login(self.recruiter)
        self.assertEqual(
            self.client.get(
                reverse("freelance:find"), {"project": "invalid"}
            ).status_code,
            200,
        )
        response = self.client.get(reverse("freelance:find"), {"maximum_rate": 500})
        self.assertContains(response, "Choose a pricing basis")

    def test_valid_booking_form_saves_only_explicit_agreement_fields(self):
        self.client.force_login(self.recruiter)
        response = self.client.post(
            reverse("freelance:book", args=[self.thread.pk]),
            {
                **self.fields(),
                "share_contacts": "on",
                "status": "completed",
                "freelancer_email": "forged@example.test",
                "deposit_amount": "9999",
            },
        )
        self.assertEqual(response.status_code, 302)
        booking = Booking.objects.get()
        self.assertEqual(booking.status, "requested")
        self.assertEqual(booking.deposit_amount, 0)
        self.assertEqual(booking.freelancer_email, "")
        self.assertEqual(booking.conversation.recruiter_id, self.recruiter.pk)

    def test_new_profile_requires_opt_in_and_ignores_posted_owner(self):
        self.client.force_login(self.other_worker)
        response = self.client.get(reverse("freelance:profile_edit"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            FreelancerProfile.objects.filter(user=self.other_worker).exists()
        )
        data = {
            "title": "Consultancy",
            "about": "My services",
            "location": "Nairobi",
            "rate": "2500",
            "rate_unit": "day",
            "work_mode": "on_site",
            "available_from": self.today,
            "accepting_bookings": "on",
            "services-TOTAL_FORMS": 1,
            "services-INITIAL_FORMS": 0,
            "services-0-title": "Reporting",
            "services-0-description": "Analysis",
            "user": self.worker.pk,
        }
        self.client.post(reverse("freelance:profile_edit"), data)
        self.assertFalse(
            FreelancerProfile.objects.filter(user=self.other_worker).exists()
        )
        response = self.client.post(
            reverse("freelance:profile_edit"),
            {**data, "share_professional_profile": "on"},
        )
        self.assertEqual(response.status_code, 302)
        listing = FreelancerProfile.objects.get(user=self.other_worker)
        self.assertEqual(listing.services.get().title, "Reporting")
        self.assertEqual(listing.user_id, self.other_worker.pk)

    def test_services_from_another_profile_are_rejected(self):
        other = FreelancerProfile.objects.create(
            user=self.other_worker,
            title="Writer",
            about="Services",
            location="Nairobi",
            rate=1000,
            available_from=self.today,
        )
        private_service = FreelanceService.objects.create(
            profile=other, title="Original service"
        )
        from freelance.forms import ServiceFormSet

        forms = ServiceFormSet(
            {
                "services-TOTAL_FORMS": 1,
                "services-INITIAL_FORMS": 1,
                "services-0-id": private_service.pk,
                "services-0-title": "Forged edit",
            },
            instance=self.profile,
            prefix="services",
        )
        self.assertFalse(forms.is_valid())
        private_service.refresh_from_db()
        self.assertEqual(private_service.title, "Original service")

    def test_project_form_saves_owner_and_closes_past_project(self):
        self.client.force_login(self.recruiter)
        data = {
            "title": "Consultancy",
            "description": "Deliver reports",
            "location": "Nairobi",
            "work_mode": "remote",
            "budget": "5000",
            "skill_names": "SQL, Python, SQL",
            "start_date": self.today,
            "end_date": self.today + timedelta(days=2),
            "status": "open",
            "recruiter": self.stranger.pk,
        }
        response = self.client.post(reverse("freelance:project_create"), data)
        self.assertEqual(response.status_code, 302)
        project = FreelanceProject.objects.get()
        self.assertEqual(project.recruiter_id, self.recruiter.pk)
        self.assertEqual(project.skills, ["SQL", "Python"])
        past = self.today - timedelta(days=5)
        project.start_date, project.end_date = past, self.today - timedelta(days=1)
        project.save()
        response = self.client.post(
            reverse("freelance:project_edit", args=[project.pk]),
            {
                **data,
                "start_date": past,
                "end_date": project.end_date,
                "status": "closed",
            },
        )
        self.assertEqual(response.status_code, 302)
        project.refresh_from_db()
        self.assertEqual(project.status, "closed")
        self.client.force_login(self.stranger)
        self.assertEqual(
            self.client.post(
                reverse("freelance:project_edit", args=[project.pk]), data
            ).status_code,
            404,
        )

    def test_irrelevant_skills_do_not_become_recommended_through_ratings(self):
        project = FreelanceProject.objects.create(
            recruiter=self.recruiter,
            title="Design",
            description="Brand identity",
            location="Remote",
            work_mode="remote",
            budget=5000,
            start_date=self.today,
            end_date=self.today,
            skills=["Graphic design"],
        )
        self.assertEqual(freelance_search({}, project), [])

    def test_search_pagination_preserves_filters(self):
        for index in range(13):
            worker = get_user_model().objects.create_user(
                username=f"extra-{index}", email=f"extra-{index}@example.test"
            )
            FreelancerProfile.objects.create(
                user=worker,
                title="Data analyst",
                about="Reporting",
                location="Nairobi",
                rate=1000,
                available_from=self.today,
                accepting_bookings=True,
                share_professional_profile=True,
            )
        self.client.force_login(self.recruiter)
        response = self.client.get(reverse("freelance:find"), {"q": "Data", "page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "q=Data")
        self.assertEqual(response.context["page"].number, 2)

    def test_all_new_get_pages_render_for_both_roles(self):
        booking = self.booking()
        project = FreelanceProject.objects.create(
            recruiter=self.recruiter,
            title="Project",
            description="Description",
            location="Nairobi",
            work_mode="remote",
            budget=5000,
            start_date=self.today,
            end_date=self.today,
        )
        for user, pages in [
            (
                self.worker,
                [
                    ("profile", []),
                    ("profile_edit", []),
                    ("projects", []),
                    ("project_detail", [project.pk]),
                ],
            ),
            (
                self.recruiter,
                [
                    ("find", []),
                    ("worker", [self.profile.pk]),
                    ("project_create", []),
                    ("projects", []),
                    ("project_detail", [project.pk]),
                    ("project_edit", [project.pk]),
                    ("book", [self.thread.pk]),
                ],
            ),
        ]:
            self.client.force_login(user)
            for name, args in pages + [
                ("bookings", []),
                ("booking", [booking.pk]),
                ("inbox", []),
                ("conversation", [self.thread.pk]),
                ("conversation_controls", [self.thread.pk]),
            ]:
                with self.subTest(role=user.role, page=name):
                    response = self.client.get(reverse("freelance:" + name, args=args))
                    self.assertEqual(response.status_code, 200)

    def test_post_only_and_csrf_on_mutations(self):
        booking = self.complete(self.booking())
        payment = self.payment(booking)
        self.client.force_login(self.worker)
        self.assertEqual(
            self.client.get(
                reverse("freelance:payment_action", args=[booking.pk, payment.pk])
            ).status_code,
            405,
        )
        secure_client = Client(enforce_csrf_checks=True)
        secure_client.force_login(self.worker)
        self.assertEqual(
            secure_client.post(
                reverse("freelance:booking", args=[booking.pk]),
                {"action": "request_completion"},
            ).status_code,
            403,
        )

    def test_admin_evidence_readonly_and_moderation_fields_limited(self):
        booking = self.complete(self.booking())
        payment = self.payment(booking)
        review = leave_review(
            booking.pk, self.recruiter, {"rating": 4, "comment": "Good"}
        )
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("admin:freelance_booking_change", args=[booking.pk])
        )
        self.assertContains(response, "Reporting assignment")
        self.assertNotContains(response, 'name="_save"')
        response = self.client.get(
            reverse("admin:freelance_review_change", args=[review.pk])
        )
        self.assertContains(response, 'name="is_hidden"')
        self.assertNotContains(response, 'name="rating"')
        self.assertEqual(
            self.client.post(
                reverse("admin:freelance_payment_change", args=[payment.pk]),
                {"status": "confirmed"},
            ).status_code,
            403,
        )
