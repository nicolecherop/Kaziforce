from django.db.models.signals import post_delete
from django.dispatch import receiver
from candidates.signals import remove_file_after_commit
from .models import ApplicationAttachment


@receiver(post_delete, sender=ApplicationAttachment)
def remove_attachment_file(sender, instance, **kwargs):
    remove_file_after_commit(instance.file)
