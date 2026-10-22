"""Recruiter price ranges compare starting rates using the same pricing basis."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from freelance.models import FreelancerProfile
from freelance.search_forms import FreelancerSearchForm
from freelance.selectors import freelance_search


class FreelancePriceFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.recruiter = User.objects.create_user(
            username="price-recruiter", email="recruiter@example.test", role="recruiter"
        )
        cls.profiles = []
        for index, (rate, unit) in enumerate(
            ((1000, "day"), (2000, "day"), (3000, "day"), (2000, "hour"))
        ):
            user = User.objects.create_user(
                username=f"price-worker-{index}", email=f"worker{index}@example.test"
            )
            cls.profiles.append(
                FreelancerProfile.objects.create(
                    user=user,
                    title="Professional services",
                    about="Project support",
                    location="Nairobi",
                    rate=rate,
                    rate_unit=unit,
                    available_from=timezone.localdate(),
                    accepting_bookings=True,
                    share_professional_profile=True,
                )
            )

    def test_inclusive_range_excludes_other_pricing_units(self):
        form = FreelancerSearchForm(
            {"rate_unit": "day", "minimum_rate": "1000", "maximum_rate": "2000"}
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            {p.pk for p in freelance_search(form.cleaned_data)},
            {p.pk for p in self.profiles[:2]},
        )

    def test_either_limit_can_be_used_on_its_own(self):
        self.assertEqual(
            len(freelance_search({"rate_unit": "day", "minimum_rate": 2000})), 2
        )
        self.assertEqual(
            len(freelance_search({"rate_unit": "day", "maximum_rate": 1000})), 1
        )
        self.assertEqual(len(freelance_search({})), 4)

    def test_missing_unit_reversed_range_and_invalid_values_are_rejected(self):
        for data, field in [
            ({"minimum_rate": "1000"}, "rate_unit"),
            ({"maximum_rate": "1000"}, "rate_unit"),
            (
                {"rate_unit": "day", "minimum_rate": "2000", "maximum_rate": "1000"},
                "maximum_rate",
            ),
            ({"rate_unit": "day", "minimum_rate": "-1"}, "minimum_rate"),
            ({"rate_unit": "day", "maximum_rate": "abc"}, "maximum_rate"),
        ]:
            with self.subTest(data=data):
                form = FreelancerSearchForm(data)
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_recruiter_page_renders_and_retains_applied_price_range(self):
        self.client.force_login(self.recruiter)
        response = self.client.get(
            reverse("freelance:find"),
            {"rate_unit": "day", "minimum_rate": "1500", "maximum_rate": "2500"},
        )
        self.assertContains(response, "Minimum price (KES)")
        self.assertContains(response, "Maximum price (KES)")
        self.assertEqual(response.context["form"]["minimum_rate"].value(), "1500")
        self.assertEqual(
            [p.pk for p in response.context["page"]], [self.profiles[1].pk]
        )
