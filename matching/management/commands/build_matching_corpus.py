from django.core.management.base import BaseCommand, CommandError
from matching.corpus import build_corpus
from matching.scoring import MatchingError


class Command(BaseCommand):
    help = "Build the immutable public ESCO TF-IDF reference for the active catalogue."

    def handle(self, *args, **options):
        try:
            corpus, created = build_corpus()
        except MatchingError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Built' if created else 'Verified'} reference: {corpus.document_count} documents, {len(corpus.document_frequencies)} terms, checksum {corpus.checksum}."
            )
        )
