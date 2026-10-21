import csv
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError
from matching.catalogue import import_catalogue


class Command(BaseCommand):
    help = "Import an English ESCO skills CSV as an immutable local catalogue."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--release", dest="catalogue_version", required=True)
        parser.add_argument(
            "--source-url", default="https://esco.ec.europa.eu/en/use-esco/download"
        )
        parser.add_argument("--activate", action="store_true")

    def handle(self, *args, **options):
        try:
            catalogue, created = import_catalogue(
                options["path"],
                options["catalogue_version"],
                options["source_url"],
                options["activate"],
            )
        except (OSError, UnicodeError, ValueError, csv.Error, IntegrityError) as exc:
            raise CommandError(f"Catalogue import failed: {exc}") from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Imported' if created else 'Verified existing'} ESCO {catalogue.version}: {catalogue.skill_count} skills. Active: {catalogue.active}."
            )
        )
