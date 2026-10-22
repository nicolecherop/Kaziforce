"""Sample creation must be repeatable and must not alter existing account data."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from freelance.contact_rules import contact_sharing_allowed
from freelance.models import (
    FreelancerProfile,
    FreelanceProject,
    Booking,
    Payment,
    Review,
)
from freelance.services import send_message, payment_totals
from scripts.freelance_data import seed, KEYS


class FreelanceDataTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.accounts = Path(self.directory.name) / "accounts.json"
        self.manifest = Path(self.directory.name) / "freelance.json"
        rows = []
        for key in ("recruiter", *KEYS):
            role = "recruiter" if key == "recruiter" else "candidate"
            user = get_user_model().objects.create_user(
                username=f"kaziforce-demo-{key}-v1",
                email=f"{key}@demo.kaziforce.test",
                first_name=key.title(),
                last_name="Demo",
                role=role,
            )
            rows.append(
                {
                    "id": user.pk,
                    "username": user.username,
                    "email": user.email,
                    "role": role,
                }
            )
        self.accounts.write_text(
            json.dumps(
                {
                    "version": 1,
                    "database": str(settings.DATABASES["default"]["NAME"]),
                    "accounts": rows,
                }
            )
        )

    def run_seed(self, **kwargs):
        return seed(self.accounts, self.manifest, **kwargs)

    def test_seed_has_useful_stages_and_retains_all_existing_account_fields(self):
        before = list(get_user_model().objects.order_by("pk").values())
        record = self.run_seed()
        self.assertEqual(before, list(get_user_model().objects.order_by("pk").values()))
        self.assertEqual(FreelancerProfile.objects.count(), 6)
        self.assertEqual(
            FreelancerProfile.objects.filter(accepting_bookings=True).count(), 5
        )
        self.assertEqual(FreelanceProject.objects.filter(status="open").count(), 4)
        self.assertCountEqual(
            Booking.objects.values_list("status", flat=True),
            ["requested", "accepted", "completion_requested", "completed"],
        )
        self.assertFalse(Booking.objects.exclude(deposit_amount=0).exists())
        completed = Booking.objects.get(status="completed")
        self.assertEqual(Payment.objects.get().status, "confirmed")
        self.assertEqual(payment_totals(completed)["remaining"], 0)
        self.assertEqual(Review.objects.get().rating, 5)
        self.assertNotIn("password", json.dumps(record))
        for title in FreelanceProject.objects.values_list("title", flat=True):
            self.assertNotRegex(title.lower(), r"demo|sample|prototype")

    def test_rerun_keeps_user_edits_and_does_not_duplicate_records(self):
        first = self.run_seed()
        profile = FreelancerProfile.objects.get(user__email="amina@demo.kaziforce.test")
        profile.title = "Updated consultancy title"
        profile.save()
        self.assertEqual(self.run_seed(), first)
        self.assertEqual(self.run_seed(check_only=True), first)
        profile.refresh_from_db()
        self.assertEqual(profile.title, "Updated consultancy title")
        self.assertEqual(Booking.objects.count(), 4)

    def test_pending_and_enquiry_contacts_stay_locked(self):
        self.run_seed()
        pending = Booking.objects.get(status="requested")
        thread = pending.conversation
        self.assertFalse(
            contact_sharing_allowed(thread.recruiter_id, thread.freelancer_id)
        )
        with self.assertRaises(ValidationError):
            send_message(
                thread.pk, thread.recruiter, "Contact me at person@example.com"
            )
        accepted = Booking.objects.get(status="accepted").conversation
        self.assertTrue(
            contact_sharing_allowed(accepted.recruiter_id, accepted.freelancer_id)
        )

    def test_existing_listing_is_never_overwritten(self):
        self.run_seed()
        self.manifest.unlink()
        with self.assertRaisesMessage(ValueError, "already has a freelance profile"):
            self.run_seed()
        self.assertFalse(self.manifest.exists())
        self.assertEqual(FreelancerProfile.objects.count(), 6)

    def test_failure_rolls_back_the_entire_batch_and_removes_its_manifest(self):
        with patch(
            "freelance.services.request_booking", side_effect=ValidationError("stop")
        ):
            with self.assertRaises(ValidationError):
                self.run_seed()
        self.assertFalse(self.manifest.exists())
        self.assertEqual(FreelancerProfile.objects.count(), 0)
        self.assertEqual(FreelanceProject.objects.count(), 0)

    def test_privileged_identity_is_refused_before_creating_anything(self):
        get_user_model().objects.filter(role="recruiter").update(is_staff=True)
        with self.assertRaisesMessage(ValueError, "access level changed"):
            self.run_seed()
        self.assertFalse(self.manifest.exists())
        self.assertFalse(FreelancerProfile.objects.exists())

    def test_missing_record_does_not_trigger_a_second_batch(self):
        self.run_seed()
        Review.objects.all().delete()
        with self.assertRaisesMessage(ValueError, "Recorded rows are missing"):
            self.run_seed()
        self.assertEqual(Booking.objects.count(), 4)
