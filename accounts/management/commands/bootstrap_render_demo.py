"""Prepare the hosted demo's reference data and initial administrator."""

import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from matching.models import MatchingCorpus, SkillCatalogue
from accounts.render_demo_listings import seed_demo_listings


class Command(BaseCommand):
    help = "Prepare matching data and create the initial demo administrator."

    def handle(self, *args, **options):
        if not getattr(settings, "PRIVATE_DOCUMENTS_IN_DATABASE", False):
            raise CommandError("Use this command with the hosted demo settings.")
        if not SkillCatalogue.objects.filter(active=True).exists():
            call_command(
                "import_esco",
                str(settings.BASE_DIR / "data/esco/esco-v1.2.0-en.csv"),
                "--release",
                "v1.2.0",
                activate=True,
            )
        if not MatchingCorpus.objects.exists():
            call_command("build_matching_corpus")
        seed_demo_listings()
        User = get_user_model()
        if User.objects.filter(is_superuser=True, is_active=True).exists():
            return
        email = os.environ["DEMO_ADMIN_EMAIL"].strip().lower()
        password = os.environ["DEMO_ADMIN_PASSWORD"]
        user = User(email=email, username=email, role=User.Role.ADMINISTRATOR)
        validate_password(password, user)
        User.objects.create_superuser(
            username=email, email=email, password=password, role=user.role
        )
