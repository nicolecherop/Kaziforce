"""Read CV text in a short-lived worker; never execute embedded content."""

import json
import re
import sys
from pathlib import Path
from zipfile import ZipFile

from defusedxml import ElementTree
from pypdf import PdfReader

MAX_BYTES = 5 * 1024 * 1024
MAX_TEXT = 100_000
MAX_PAGES = 20
MAX_XML = 10 * 1024 * 1024
WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class CVReadError(ValueError):
    """A safe, actionable explanation suitable for the upload form."""


def word_text(path):
    with ZipFile(path) as archive:
        entries = archive.infolist()
        if (
            len(entries) > 1000
            or sum(item.file_size for item in entries) > 25 * 1024 * 1024
            or any("vbaproject" in item.filename.lower() for item in entries)
            or any(item.flag_bits & 1 for item in entries)
        ):
            raise CVReadError(
                "This Word file cannot be imported. Save a simpler copy without macros or a password."
            )
        names = [item.filename for item in entries]
        if "word/document.xml" not in names:
            raise CVReadError("Choose a valid Word document saved as .docx.")
        # Read headers too: many CV templates put contact details there. Do not
        # follow relationships, URLs, embedded objects or document instructions.
        parts = sorted(
            name for name in names if re.fullmatch(r"word/header\d+\.xml", name)
        )
        parts.append("word/document.xml")
        output = []
        for name in parts:
            if archive.getinfo(name).file_size > MAX_XML:
                raise CVReadError(
                    "This document is too complex to import. Try a simpler Word or PDF copy."
                )
            root = ElementTree.fromstring(archive.read(name))
            # Document-order paragraphs include tables and text boxes.
            for paragraph in root.iter(WORD + "p"):
                pieces = []
                for node in paragraph.iter():
                    if node.tag == WORD + "t":
                        pieces.append(node.text or "")
                    elif node.tag in {WORD + "br", WORD + "cr"}:
                        pieces.append("\n")
                    elif node.tag == WORD + "tab":
                        pieces.append(" | ")
                output.append("".join(pieces))
        return "\n".join(output), []


def pdf_text(path):
    reader = PdfReader(path, strict=False)
    if reader.is_encrypted:
        raise CVReadError(
            "This PDF is password-protected. Upload an unlocked copy to fill your profile."
        )
    if len(reader.pages) > MAX_PAGES:
        raise CVReadError("Choose a CV with 20 pages or fewer for profile import.")
    pages = []
    empty = 0
    for page in reader.pages:
        contents = page.get_contents()
        if contents is not None and len(contents.get_data()) > MAX_XML:
            raise CVReadError(
                "This PDF is too complex to import. Try a simpler PDF or Word copy."
            )
        value = (
            page.extract_text(
                extraction_mode="layout", layout_mode_space_vertically=False
            )
            or ""
        )
        if len(value.strip()) < 20:
            empty += 1
        pages.append(value)
        if sum(map(len, pages)) > MAX_TEXT:
            raise CVReadError(
                "This CV contains too much text to import. Choose a shorter copy."
            )
    warnings = []
    if empty:
        warnings.append(
            "Some pages have little or no readable text. Compare the suggestions with your original CV."
        )
    return "\n\n".join(pages), warnings


def read_cv(path, extension):
    if Path(path).stat().st_size > MAX_BYTES:
        raise CVReadError("Choose a CV of 5 MB or less.")
    if extension == ".docx":
        text, warnings = word_text(path)
    elif extension == ".pdf":
        text, warnings = pdf_text(path)
    else:
        raise CVReadError("Choose a PDF or Word (.docx) CV.")
    text = "".join(char for char in text if char.isprintable() or char in "\n\t")
    if len(text) > MAX_TEXT:
        raise CVReadError(
            "This CV contains too much text to import. Choose a shorter copy."
        )
    if len(re.sub(r"\W", "", text)) < 40:
        raise CVReadError(
            "We could not find enough readable text. For a scanned CV, upload a Word copy or a PDF with selectable text, or fill in your profile manually."
        )
    return {"text": text, "warnings": warnings}


def main():
    try:
        result = read_cv(sys.argv[1], sys.argv[2])
    except CVReadError as error:
        result = {"error": str(error)}
    except Exception:
        # Never send parser tracebacks, private paths or document text to logs.
        result = {
            "error": "We could not read this file. Try saving a fresh PDF or Word copy. Your saved profile has not changed."
        }
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
