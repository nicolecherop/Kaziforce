"""Delete private originals after their database deletion commits."""

import logging
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import CandidateDocument

logger = logging.getLogger(__name__)


def remove_file_after_commit(file):
    storage, name = file.storage, file.name

    def cleanup():
        try:
            if name:
                storage.delete(name)
        except OSError:
            logger.warning("Private document cleanup failed; check file storage.")

    transaction.on_commit(cleanup)


@receiver(post_delete, sender=CandidateDocument)
def remove_document_file(sender, instance, **kwargs):
    remove_file_after_commit(instance.file)
