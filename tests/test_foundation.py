from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse


class FoundationTests(TestCase):
    def test_public_pages_render(self):
        for name, template in [
            ("pages:home", "pages/landing.html"),
            ("accounts:sign_in", "accounts/sign_in.html"),
            ("accounts:create_account", "accounts/create_account.html"),
        ]:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template)

    def test_passwords_are_hashed(self):
        user = get_user_model().objects.create_user(username="nicole", email="nicole@example.com", password="sample-secret-123")
        self.assertNotEqual(user.password, "sample-secret-123")
        self.assertTrue(user.check_password("sample-secret-123"))

    def test_email_uniqueness_ignores_case(self):
        model = get_user_model()
        model.objects.create_user(username="first", email="person@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            model.objects.create_user(username="second", email="PERSON@example.com")
