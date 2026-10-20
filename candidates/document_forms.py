"""Attachment validation without reading or extracting document text."""

from pathlib import Path, PureWindowsPath
from zipfile import BadZipFile, ZipFile
from django import forms
from .models import CandidateDocument

MAX_FILE_BYTES = 5 * 1024 * 1024


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = CandidateDocument
        fields = ["kind", "title", "file"]
        labels = {"kind": "Document type", "title": "Document title", "file": "File"}
        help_texts = {
            "title": "For example, My CV or BSc Computer Science.",
            "file": "Up to 5 MB. CVs: PDF or DOCX. Degrees and certificates: PDF, JPG or PNG.",
        }
        widgets = {
            "file": forms.ClearableFileInput(
                attrs={"accept": ".pdf,.docx,.jpg,.jpeg,.png"}
            )
        }

    def clean(self):
        data = super().clean()
        upload = data.get("file")
        if not upload:
            return data
        if upload.size > MAX_FILE_BYTES:
            self.add_error("file", "Choose a file of 5 MB or less.")
            return data
        upload.name = "".join(
            char for char in PureWindowsPath(upload.name).name if char.isprintable()
        )[:200]
        extension = Path(upload.name).suffix.lower()
        allowed = (
            {".pdf", ".docx"}
            if data.get("kind") == "cv"
            else {".pdf", ".jpg", ".jpeg", ".png"}
        )
        if extension not in allowed:
            self.add_error("file", "Choose a supported format for this document type.")
            return data
        signature = upload.read(8)
        upload.seek(0)
        signatures = {
            ".pdf": b"%PDF-",
            ".docx": b"PK\x03\x04",
            ".jpg": b"\xff\xd8\xff",
            ".jpeg": b"\xff\xd8\xff",
            ".png": b"\x89PNG\r\n\x1a\n",
        }
        if not signature.startswith(signatures[extension]):
            self.add_error("file", "The file contents do not match its extension.")
        elif extension == ".docx":
            try:
                with ZipFile(upload) as archive:
                    names = archive.namelist()
                    if (
                        len(names) > 1000
                        or "word/document.xml" not in names
                        or any("vbaproject" in name.lower() for name in names)
                    ):
                        raise BadZipFile()
            except (BadZipFile, OSError):
                self.add_error(
                    "file",
                    "Choose a valid Word document saved without macros as .docx.",
                )
            finally:
                upload.seek(0)
        return data
