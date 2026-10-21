"""Validate a complete ESCO CSV before atomically importing immutable versions."""

import csv
from hashlib import sha256
from io import StringIO
from pathlib import Path
import re
from urllib.parse import urlsplit

from django.db import transaction
from .models import CatalogueSkill, SkillCatalogue, SkillLabel
from .normalization import normalize_skill

URI_PATTERN = re.compile(
    r"http://data\.europa\.eu/esco/skill/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)


def import_catalogue(path, version, source_url, activate=False):
    """Return (catalogue, created). Existing versions cannot be overwritten."""
    if not re.fullmatch(r"v?\d+\.\d+\.\d+", version):
        raise ValueError("Use an explicit ESCO release such as v1.2.0.")
    version = "v" + version.lstrip("v")
    parsed = urlsplit(source_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"esco.ec.europa.eu", "ec.europa.eu"}
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Use an official European Commission HTTPS source URL.")
    path = Path(path)
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("The skills CSV must be no larger than 64 MB.")
    raw = path.read_bytes()
    checksum = sha256(raw).hexdigest()
    csv.field_size_limit(2 * 1024 * 1024)
    reader = csv.DictReader(StringIO(raw.decode("utf-8-sig"), newline=""))
    if not {"conceptUri", "preferredLabel", "altLabels", "description"}.issubset(
        reader.fieldnames or []
    ):
        raise ValueError(
            "Expected ESCO skills CSV columns: conceptUri, preferredLabel, altLabels, description."
        )
    rows, seen = [], set()
    label_count = 0
    for number, row in enumerate(reader, start=2):
        if number > 40001:
            raise ValueError("The skills CSV contains too many rows.")
        if None in row or any(
            row.get(key) is None
            for key in ("conceptUri", "preferredLabel", "altLabels", "description")
        ):
            raise ValueError(f"Incomplete or malformed CSV row {number}.")
        uri = (row.get("conceptUri") or "").strip()
        label = (row.get("preferredLabel") or "").strip()
        description = (row.get("description") or "").strip()
        if (
            not URI_PATTERN.fullmatch(uri)
            or uri in seen
            or not label
            or len(label) > 500
            or len(description) > 30000
        ):
            raise ValueError(f"Invalid or duplicate skill at CSV row {number}.")
        seen.add(uri)
        if (row.get("status") or "released").strip().lower() not in {"released", ""}:
            continue
        alternatives = (row.get("altLabels") or "").splitlines()
        label_count += 1 + len(alternatives)
        if len(alternatives) > 500 or label_count > 500000:
            raise ValueError("The CSV contains too many alternative labels.")
        labels = {}
        for value in [label, *alternatives]:
            value = value.strip()
            normalized = normalize_skill(value)
            if not normalized:
                continue
            if len(value) > 500 or len(normalized) > 500:
                raise ValueError(f"A skill label is too long at CSV row {number}.")
            labels.setdefault(normalized, value)
        rows.append((uri, label, description, labels))
    if not rows:
        raise ValueError("The skills CSV contains no released skills.")
    with transaction.atomic():
        # Switching releases is atomic. The conditional unique constraint also
        # protects the first import, when there is no existing row to lock.
        list(SkillCatalogue.objects.select_for_update().values_list("pk", flat=True))
        catalogue = SkillCatalogue.objects.filter(
            version=version, language="en"
        ).first()
        if catalogue:
            if catalogue.checksum != checksum or catalogue.skill_count != len(rows):
                raise ValueError(
                    "This ESCO version already exists with different content. Import a new version instead."
                )
            created = False
        else:
            catalogue = SkillCatalogue.objects.create(
                version=version,
                language="en",
                source_url=source_url,
                checksum=checksum,
                skill_count=len(rows),
            )
            CatalogueSkill.objects.bulk_create(
                [
                    CatalogueSkill(
                        catalogue=catalogue,
                        uri=uri,
                        preferred_label=label,
                        description=description,
                    )
                    for uri, label, description, _ in rows
                ],
                batch_size=500,
            )
            skill_ids = dict(catalogue.skills.values_list("uri", "pk"))
            labels = [
                SkillLabel(
                    skill_id=skill_ids[uri],
                    label=value,
                    normalized=normalized,
                    preferred=normalized == normalize_skill(label),
                )
                for uri, label, _, entries in rows
                for normalized, value in entries.items()
            ]
            SkillLabel.objects.bulk_create(labels, batch_size=1000)
            created = True
        if activate:
            SkillCatalogue.objects.filter(active=True).exclude(pk=catalogue.pk).update(
                active=False
            )
            catalogue.active = True
            catalogue.save(update_fields=["active"])
        return catalogue, created
