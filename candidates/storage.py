"""Private originals and application copies have no public media URLs."""

import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models.functions import Length
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.deconstruct import deconstructible


class DatabaseDocumentStorage(Storage):
    @property
    def records(self):
        from .models import PrivateDocumentBlob

        return PrivateDocumentBlob.objects

    def _open(self, name, mode="rb"):
        try:
            item = self.records.get(pk=name)
        except self.records.model.DoesNotExist:
            raise FileNotFoundError(name) from None
        return ContentFile(bytes(item.content), name=name)

    def _save(self, name, content):
        self.records.create(name=name, content=b"".join(content.chunks()))
        return name

    def exists(self, name):
        return self.records.filter(pk=name).exists()

    def delete(self, name):
        self.records.filter(pk=name).delete()

    def size(self, name):
        return self.records.annotate(length=Length("content")).values_list(
            "length", flat=True
        ).get(pk=name)


@deconstructible
class PrivateDocumentStorage(Storage):
    def backend(self):
        if getattr(settings, "PRIVATE_DOCUMENTS_IN_DATABASE", False):
            return DatabaseDocumentStorage()
        return FileSystemStorage(location=settings.PRIVATE_DOCUMENT_ROOT)

    def _open(self, name, mode="rb"):
        return self.backend().open(name, mode)

    def _save(self, name, content):
        return self.backend().save(name, content)

    def exists(self, name):
        return self.backend().exists(name)

    def delete(self, name):
        self.backend().delete(name)

    def size(self, name):
        return self.backend().size(name)

    def path(self, name):
        return self.backend().path(name)

    def url(self, name):
        raise ValueError("Private documents have no public URL.")


@deconstructible
class PrivateCVStorage(PrivateDocumentStorage):
    """Compatibility for the already-applied 0002 migration only."""

    def backend(self):
        return FileSystemStorage(location=settings.PRIVATE_DOCUMENT_ROOT / "cvs")


def cv_upload_path(instance, filename):
    """Historical migration callable; new documents use document_upload_path."""
    return f"{instance.user_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


def document_upload_path(instance, filename):
    return f"documents/{instance.user_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


def application_upload_path(instance, filename):
    return f"applications/{instance.application_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
