"""Pre-booking contact controls, legacy display safety and pair-scoped unlocking."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from candidates.models import CandidateProfile, PortfolioLink, WorkExperience
from freelance.contact_rules import (
    redact_contacts,
    validate_no_contacts,
    contact_sharing_allowed,
)
from freelance.forms import (
    FreelancerForm,
    ProjectForm,
    ServiceForm,
    BookingForm,
    ReviewForm,
)
from freelance.models import (
    FreelancerProfile,
    FreelanceProject,
    FreelanceService,
    Conversation,
    Message,
    Booking,
)
from freelance.services import (
    start_conversation,
    send_message,
    request_booking,
    booking_transition,
    leave_review,
)


class ContactDetectionTests(SimpleTestCase):
    def test_obvious_contact_formats_are_rejected_and_fully_masked(self):
        details = [
            "person@example.test",
            "person+work@example.co.ke",
            "person [at] example [dot] com",
            "+254712345678",
            "+254 712 345 678",
            "0712345678",
            "0112 345 678",
            "(020) 123 4567",
            "+44 20 7946 0958",
            "call: 7123456",
            "https://wa.me/254712345678",
            "wa.me/254712345678",
            "t.me/worker",
            "www.worker.example.com",
            "worker.example.com",
            "https://github.com/worker",
            "mailto:person@example.test",
            "tel:+254712345678",
            "skype:worker?call",
            "Instagram: @worker",
            "ｐｅｒｓｏｎ＠ｅｘａｍｐｌｅ．ｃｏｍ",
            "person@exam\u200bple.com",
            "07\u200b12345678",
        ]
        for value in details:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validate_no_contacts("Reach me at " + value)
                self.assertNotIn(value, redact_contacts("Reach me at " + value))
                self.assertIn("hidden until booking", redact_contacts(value))

    def test_work_terms_prices_dates_and_technology_names_are_allowed(self):
        texts = [
            "Python 3.12, Django 5.2, SQL, Node.js, ASP.NET and VB.NET",
            "Budget KES 10000 - 15000 for 3 days",
            "The budget is KES 1000000000",
            "Meet at 10:30 on 2026-10-21",
            "2026-10-21 - 2026-10-22",
            "From 21/10/2026 to 22/10/2026",
            "Room 204, building 12, Nairobi",
            "I can deliver the report in 7-10 days. Use @login_required for the view.",
            "Data analysis and a handover session. 50% after the first review.",
        ]
        for text in texts:
            with self.subTest(text=text):
                validate_no_contacts(text)
                self.assertEqual(redact_contacts(text), text)

    def test_a_date_does_not_hide_a_phone_next_to_it(self):
        value = "2026-10-21 0712345678"
        with self.assertRaises(ValidationError):
            validate_no_contacts(value)
        self.assertNotIn("0712345678", redact_contacts(value))
        self.assertIn("2026-10-21", redact_contacts(value))


class FreelanceContactPrivacyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.worker = User.objects.create_user(
            username="privacy-worker", email="worker@example.test", first_name="Alex"
        )
        cls.recruiter = User.objects.create_user(
            username="privacy-recruiter",
            email="recruiter@example.test",
            first_name="Sarah",
            role="recruiter",
        )
        cls.other = User.objects.create_user(
            username="privacy-other",
            email="other@example.test",
            first_name="Brian",
            role="recruiter",
        )
        cls.today = timezone.localdate()
        cls.professional = CandidateProfile.objects.create(
            user=cls.worker, headline="Analyst"
        )
        cls.portfolio = PortfolioLink.objects.create(
            profile=cls.professional,
            title="Reporting portfolio",
            url="https://portfolio.example.test/work",
        )
        cls.profile = FreelancerProfile.objects.create(
            user=cls.worker,
            title="Data consultancy",
            about="Clear business reports",
            location="Nairobi",
            rate=5000,
            rate_unit="day",
            work_mode="remote",
            available_from=cls.today,
            accepting_bookings=True,
            share_professional_profile=True,
        )
        cls.thread = Conversation.objects.create(
            recruiter=cls.recruiter, freelancer=cls.profile
        )

    def profile_data(self, **changes):
        return {
            "title": "Data consultancy",
            "about": "Clear business reports",
            "location": "Nairobi",
            "rate": "5000",
            "rate_unit": "day",
            "work_mode": "remote",
            "available_from": self.today,
            "accepting_bookings": "on",
            "share_professional_profile": "on",
            **changes,
        }

    def project(self, **changes):
        return FreelanceProject.objects.create(
            recruiter=self.recruiter,
            title="Reporting review",
            description="Build reports",
            location="Nairobi",
            work_mode="remote",
            budget=10000,
            start_date=self.today,
            end_date=self.today + timedelta(days=1),
            **changes
        )

    def book(self):
        return request_booking(
            self.thread.pk,
            self.recruiter,
            {
                "title": "Reporting review",
                "scope": "Build a dashboard",
                "location": "Remote",
                "start_date": self.today,
                "end_date": self.today + timedelta(days=1),
                "total_price": Decimal("10000"),
                "cancellation_terms": "Cancel only by agreement",
                "recruiter_name": "Sarah",
                "recruiter_email": "hiring@example.test",
                "recruiter_phone": "+254711222333",
            },
        )

    def accept(self, booking):
        return booking_transition(
            booking.pk,
            self.worker,
            "accept",
            {
                "agree": True,
                "freelancer_name": "Alex",
                "freelancer_email": "work@example.test",
                "freelancer_phone": "+254712345678",
            },
        )

    def test_public_profile_and_service_fields_reject_contacts(self):
        for field in ("title", "about", "location"):
            with self.subTest(field=field):
                form = FreelancerForm(
                    self.profile_data(**{field: "Contact person@example.test"}),
                    instance=self.profile,
                )
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)
        for field in ("title", "description"):
            form = ServiceForm(
                {
                    "title": "Reporting",
                    "description": "Useful dashboards",
                    field: "Call 0712345678",
                }
            )
            self.assertFalse(form.is_valid())
            self.assertIn(field, form.errors)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.about, "Clear business reports")

    def test_project_text_and_skill_list_reject_contacts(self):
        data = {
            "title": "Reporting",
            "description": "Useful dashboards",
            "location": "Remote",
            "work_mode": "remote",
            "budget": "10000",
            "start_date": self.today,
            "end_date": self.today,
            "status": "open",
            "skill_names": "SQL, Python",
        }
        for field in ("title", "description", "location", "skill_names"):
            with self.subTest(field=field):
                form = ProjectForm({**data, field: "worker.example.com"})
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)
        self.assertFalse(FreelanceProject.objects.exists())

    def test_invalid_profile_post_does_not_publish_a_service_or_profile(self):
        self.client.force_login(self.worker)
        data = {
            **self.profile_data(),
            "services-TOTAL_FORMS": 1,
            "services-INITIAL_FORMS": 0,
            "services-0-title": "Data reporting",
            "services-0-description": "Call 0712345678",
        }
        response = self.client.post(reverse("freelance:profile_edit"), data)
        self.assertContains(response, "Keep contact details and web links out")
        self.assertFalse(FreelanceService.objects.exists())

    def test_initial_enquiry_rejection_rolls_back_the_new_conversation(self):
        with self.assertRaisesMessage(ValidationError, "after a booking is accepted"):
            start_conversation(self.other, self.profile.pk, "Email person@example.test")
        self.assertFalse(Conversation.objects.filter(recruiter=self.other).exists())
        self.assertFalse(Message.objects.exists())

    def test_project_proposal_and_direct_messages_are_guarded(self):
        project = self.project()
        self.client.force_login(self.worker)
        response = self.client.post(
            reverse("freelance:project_detail", args=[project.pk]),
            {"body": "Reach me at wa.me/254712345678"},
        )
        self.assertContains(
            response, "Contact details and web links can be shared after"
        )
        self.assertFalse(Conversation.objects.filter(project=project).exists())
        self.client.force_login(self.recruiter)
        response = self.client.post(
            reverse("freelance:conversation", args=[self.thread.pk]),
            {"body": "Call 0712345678"},
        )
        self.assertContains(
            response, "Contact details and web links can be shared after"
        )
        self.assertFalse(Message.objects.exists())

    def test_plain_work_discussion_is_saved_before_booking(self):
        send_message(
            self.thread.pk,
            self.recruiter,
            "Can you deliver 3 reports by 2026-10-21? Budget KES 15000.",
        )
        self.assertEqual(Message.objects.count(), 1)

    def test_acceptance_unlocks_messages_and_portfolio_without_payment(self):
        self.client.force_login(self.recruiter)
        url = reverse("freelance:worker", args=[self.profile.pk])
        response = self.client.get(url)
        self.assertNotContains(response, self.portfolio.url)
        self.assertNotContains(response, "Reporting portfolio")
        self.assertContains(response, "Portfolio links become available")
        booking = self.book()
        self.assertNotContains(self.client.get(url), self.portfolio.url)
        self.accept(booking)
        self.assertContains(self.client.get(url), self.portfolio.url)
        send_message(
            self.thread.pk,
            self.recruiter,
            "Email hiring@example.test or call 0712345678",
        )
        self.assertTrue(
            self.thread.messages.filter(body__contains="hiring@example.test").exists()
        )
        self.assertEqual(booking.payments.count(), 0)

    def test_another_recruiter_cannot_use_someone_elses_booking(self):
        self.accept(self.book())
        self.client.force_login(self.other)
        self.assertNotContains(
            self.client.get(reverse("freelance:worker", args=[self.profile.pk])),
            self.portfolio.url,
        )
        self.assertFalse(contact_sharing_allowed(self.other.pk, self.profile.pk))
        with self.assertRaises(ValidationError):
            start_conversation(self.other, self.profile.pk, "Email other@example.test")

    def test_declined_or_withdrawn_requests_do_not_unlock_contacts(self):
        booking = self.book()
        booking_transition(booking.pk, self.worker, "decline")
        self.assertFalse(contact_sharing_allowed(self.recruiter.pk, self.profile.pk))
        booking = self.book()
        booking_transition(booking.pk, self.recruiter, "cancel")
        self.assertFalse(contact_sharing_allowed(self.recruiter.pk, self.profile.pk))
        with self.assertRaises(ValidationError):
            send_message(self.thread.pk, self.worker, "Call 0712345678")

    def test_unlock_is_shared_across_this_pairs_project_conversations(self):
        self.accept(self.book())
        project = self.project()
        thread = start_conversation(
            self.worker,
            self.profile.pk,
            "See https://portfolio.example.test/work",
            project.pk,
        )
        self.assertTrue(thread.messages.exists())
        self.client.force_login(self.recruiter)
        self.assertContains(
            self.client.get(reverse("freelance:inbox")), "Reporting review"
        )

    def test_past_accepted_contacts_are_not_falsely_revoked_on_cancellation(self):
        booking = self.accept(self.book())
        booking_transition(
            booking.pk, self.worker, "request_cancel", {"reason": "Unavailable"}
        )
        booking_transition(booking.pk, self.recruiter, "agree_cancel")
        self.assertTrue(contact_sharing_allowed(self.recruiter.pk, self.profile.pk))
        send_message(
            self.thread.pk, self.worker, "Discuss the cancellation at work@example.test"
        )

    def test_booking_text_cannot_bypass_the_private_contact_fields(self):
        for field in (
            "title",
            "scope",
            "location",
            "cancellation_terms",
            "recruiter_name",
        ):
            data = {
                "title": "Reporting",
                "scope": "Review data",
                "location": "Nairobi",
                "start_date": self.today,
                "end_date": self.today,
                "total_price": "5000",
                "cancellation_terms": "Cancel by agreement",
                "recruiter_name": "Sarah",
                "recruiter_email": "hiring@example.test",
                "recruiter_phone": "+254711222333",
                "share_contacts": "on",
                field: "Call 0712345678",
            }
            form = BookingForm(data)
            self.assertFalse(form.is_valid())
            self.assertIn(field, form.errors)
        self.assertFalse(Booking.objects.exists())

    def test_older_public_text_is_hidden_without_rewriting_it(self):
        self.profile.about = "Write to old@example.test for details"
        self.profile.save()
        service = FreelanceService.objects.create(
            profile=self.profile, title="Reporting", description="Call 0712345678"
        )
        WorkExperience.objects.create(
            profile=self.professional,
            job_title="Analyst",
            company="Acacia",
            start_date=self.today,
            currently_working=True,
            description="Email experience@example.test",
        )
        self.client.force_login(self.recruiter)
        for url in (
            reverse("freelance:find"),
            reverse("freelance:worker", args=[self.profile.pk]),
        ):
            response = self.client.get(url)
            self.assertNotContains(response, "old@example.test")
            self.assertNotContains(response, "0712345678")
            self.assertNotContains(response, "experience@example.test")
            self.assertContains(response, "Contact details hidden until booking")
        self.profile.refresh_from_db()
        service.refresh_from_db()
        self.assertIn("old@example.test", self.profile.about)
        self.assertIn("0712345678", service.description)

    def test_older_project_and_message_text_is_hidden_in_all_pre_booking_views(self):
        project = self.project()
        project.description = "Reach project@example.test"
        project.save()
        self.client.force_login(self.worker)
        for url in (
            reverse("freelance:projects"),
            reverse("freelance:project_detail", args=[project.pk]),
        ):
            self.assertNotContains(self.client.get(url), "project@example.test")
        message = Message.objects.create(
            conversation=self.thread,
            sender=self.recruiter,
            body="Email archive@example.test",
        )
        response = self.client.get(
            reverse("freelance:conversation", args=[self.thread.pk])
        )
        self.assertNotContains(response, "archive@example.test")
        message.refresh_from_db()
        self.assertIn("archive@example.test", message.body)
        self.accept(self.book())
        self.assertContains(
            self.client.get(reverse("freelance:conversation", args=[self.thread.pk])),
            "archive@example.test",
        )

    def test_pending_booking_text_is_masked_in_detail_and_list(self):
        booking = self.book()
        booking.scope = "Call 0712345678"
        booking.title = "Email title@example.test"
        booking.save()
        self.client.force_login(self.worker)
        for url in (
            reverse("freelance:bookings"),
            reverse("freelance:booking", args=[booking.pk]),
        ):
            response = self.client.get(url)
            self.assertNotContains(response, "0712345678")
            self.assertNotContains(response, "title@example.test")
        booking.refresh_from_db()
        self.assertEqual(booking.scope, "Call 0712345678")

    def test_public_reviews_cannot_disclose_contacts_after_booking(self):
        booking = self.accept(self.book())
        booking_transition(booking.pk, self.worker, "request_completion")
        booking_transition(booking.pk, self.recruiter, "confirm_completion")
        form = ReviewForm(
            {"rating": 5, "comment": "Find this worker at worker.example.com"}
        )
        self.assertFalse(form.is_valid())
        with self.assertRaises(ValidationError):
            leave_review(
                booking.pk, self.recruiter, {"rating": 5, "comment": "Call 0712345678"}
            )

    def test_display_masking_does_not_disable_html_escaping(self):
        Message.objects.create(
            conversation=self.thread,
            sender=self.recruiter,
            body="<script>alert('x')</script> Call 0712345678",
        )
        self.client.force_login(self.worker)
        response = self.client.get(
            reverse("freelance:conversation", args=[self.thread.pk])
        )
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert")
        self.assertNotContains(response, "0712345678")
