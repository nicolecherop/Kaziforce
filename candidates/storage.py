"""Private originals and application copies have no public media URLs."""

import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateDocumentStorage(Storage):
    def backend(self):
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
