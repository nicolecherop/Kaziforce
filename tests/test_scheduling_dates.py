"""Calendar minimums and submitted date boundaries for upcoming work."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from applications.interview_forms import InterviewForm
from freelance.forms import BookingForm, FreelancerForm, ProjectForm
from freelance.search_forms import FreelancerSearchForm


class SchedulingDateTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.later = self.today + timedelta(days=7)

    def test_calendars_start_at_today_and_end_at_selected_start(self):
        for form_class in (BookingForm, ProjectForm, FreelancerSearchForm):
            with self.subTest(form=form_class.__name__):
                form = form_class(initial={"start_date": self.later})
                self.assertEqual(
                    form.fields["start_date"].widget.attrs["min"],
                    self.today.isoformat(),
                )
                self.assertEqual(
                    form.fields["end_date"].widget.attrs["min"], self.later.isoformat()
                )
                self.assertIn('data-range-end="end_date"', str(form["start_date"]))

    def test_prefixed_date_fields_link_to_their_own_end_date(self):
        form = BookingForm(prefix="booking")
        self.assertEqual(
            form.fields["start_date"].widget.attrs["data-range-end"], "booking-end_date"
        )

    def test_invalid_or_past_start_cannot_lower_calendar_floor(self):
        for value in ("invalid", self.today - timedelta(days=1)):
            form = BookingForm(data={"start_date": value})
            self.assertEqual(
                form.fields["end_date"].widget.attrs["min"], self.today.isoformat()
            )

    def test_search_rejects_both_past_dates_and_reversed_range(self):
        yesterday = self.today - timedelta(days=1)
        past = FreelancerSearchForm({"start_date": yesterday, "end_date": yesterday})
        self.assertFalse(past.is_valid())
        self.assertIn("start_date", past.errors)
        self.assertIn("end_date", past.errors)
        reversed_range = FreelancerSearchForm(
            {"start_date": self.later, "end_date": self.today}
        )
        self.assertFalse(reversed_range.is_valid())
        self.assertIn("end_date", reversed_range.errors)

    def test_search_accepts_today_and_same_day_work(self):
        form = FreelancerSearchForm({"start_date": self.today, "end_date": self.today})
        self.assertTrue(form.is_valid(), form.errors)

    def test_booking_and_project_reject_manually_submitted_invalid_dates(self):
        for form_class in (BookingForm, ProjectForm):
            with self.subTest(form=form_class.__name__):
                form = form_class(
                    data={
                        "start_date": self.today - timedelta(days=1),
                        "end_date": self.today - timedelta(days=2),
                    }
                )
                self.assertFalse(form.is_valid())
                self.assertIn("start_date", form.errors)
                self.assertIn("end_date", form.errors)

    def test_new_availability_rejects_past_dates(self):
        form = FreelancerForm(data={"available_from": self.today - timedelta(days=1)})
        self.assertEqual(
            form.fields["available_from"].widget.attrs["min"], self.today.isoformat()
        )
        self.assertFalse(form.is_valid())
        self.assertIn("available_from", form.errors)

    def test_interview_calendar_disables_past_date_and_time(self):
        before = timezone.localtime().strftime("%Y-%m-%dT%H:%M")
        form = InterviewForm()
        after = timezone.localtime().strftime("%Y-%m-%dT%H:%M")
        self.assertTrue(before <= form.fields["starts_at"].widget.attrs["min"] <= after)

    def test_historical_profile_dates_are_not_restricted_to_today(self):
        from candidates.forms import EducationForm, ExperienceForm

        for form_class in (EducationForm, ExperienceForm):
            with self.subTest(form=form_class.__name__):
                form = form_class()
                self.assertNotIn(
                    "data-date-floor", form.fields["start_date"].widget.attrs
                )
