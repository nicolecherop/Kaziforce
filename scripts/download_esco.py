"""Export a pinned official ESCO API release to the English skills CSV format.

This explicit maintenance command downloads public reference data only. Normal
application requests never contact ESCO or send candidate/recruiter information.
"""

import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import gzip
from hashlib import sha256
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://ec.europa.eu/esco/api/resource/skill"
VERSION = "v1.2.0"


def fetch_page(offset, limit):
    url = (
        API
        + "?"
        + urlencode(
            {
                "isInScheme": "http://data.europa.eu/esco/concept-scheme/skills",
                "language": "en",
                "selectedVersion": VERSION,
                "viewObsolete": "false",
                "offset": offset,
                "limit": limit,
            }
        )
    )
    for attempt in range(3):
        try:
            with urlopen(
                Request(
                    url,
                    headers={"Accept": "application/json", "Accept-Encoding": "gzip"},
                ),
                timeout=30,
            ) as response:
                raw = response.read(64 * 1024 * 1024 + 1)
                if len(raw) > 64 * 1024 * 1024:
                    raise ValueError("ESCO returned an oversized page.")
                if response.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
            return json.loads(raw)
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def catalogue_pages(limit):
    """Keep at most three public API pages in flight, yielding in page order."""
    first = fetch_page(0, limit)
    yield first
    total = first["total"]
    count = (total + limit - 1) // limit
    executor = ThreadPoolExecutor(max_workers=3)
    pending = deque()
    next_page = 1
    try:
        while next_page < min(count, 4):
            pending.append(executor.submit(fetch_page, next_page, limit))
            next_page += 1
        while pending:
            future = pending.popleft()
            page = future.result()
            if next_page < count:
                pending.append(executor.submit(fetch_page, next_page, limit))
                next_page += 1
            yield page
    finally:
        for future in pending:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)


def download(output, limit=500):
    output = Path(output)
    if output.exists():
        raise ValueError(
            "The output already exists. Preserve it and choose a different output path."
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".csv.part")
    if temporary.exists():
        raise ValueError(
            "A partial output already exists; choose a different output path."
        )
    seen, exported, offset, total = set(), set(), 0, None
    try:
        with temporary.open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=[
                    "conceptUri",
                    "preferredLabel",
                    "altLabels",
                    "description",
                    "status",
                ],
            )
            writer.writeheader()
            for page in catalogue_pages(limit):
                page_total = page.get("total")
                if (
                    not isinstance(page_total, int)
                    or not 1 <= page_total <= 40000
                    or page.get("offset") != offset
                    or (total is not None and total != page_total)
                ):
                    raise ValueError(
                        "ESCO pagination changed or returned an invalid total."
                    )
                total = page_total
                concepts = page.get("concepts", [])
                if (
                    not concepts
                    or len(concepts) != page.get("count")
                    or len(concepts) != min(limit, total - offset * limit)
                ):
                    raise ValueError("ESCO returned an incomplete page.")
                for reference in concepts:
                    uri = reference["uri"]
                    value = page.get("_embedded", {}).get(uri, {})
                    label = value.get("preferredLabel", {}).get("en")
                    if (
                        uri in seen
                        or value.get("uri") != uri
                        or value.get("className") != "Skill"
                        or not label
                        or value.get("status") != "released"
                    ):
                        raise ValueError(
                            "ESCO returned a duplicate, obsolete or incomplete concept."
                        )
                    seen.add(uri)
                    # The bulk scheme also contains hierarchy groups. Only
                    # individual member skills/knowledge belong in matching.
                    schemes = value.get("_links", {}).get("isInScheme", [])
                    if not any(
                        scheme.get("uri")
                        == "http://data.europa.eu/esco/concept-scheme/member-skills"
                        for scheme in schemes
                    ):
                        continue
                    exported.add(uri)
                    writer.writerow(
                        {
                            "conceptUri": uri,
                            "preferredLabel": label,
                            "altLabels": "\n".join(
                                value.get("alternativeLabel", {}).get("en", [])
                            ),
                            "description": value.get("description", {})
                            .get("en", {})
                            .get("literal", ""),
                            "status": "released",
                        }
                    )
                # ESCO's offset is a zero-based page number, not a row offset.
                offset += 1
                print(f"Downloaded {len(seen)}/{total} ESCO concepts.", flush=True)
        if len(seen) != total or not exported:
            raise ValueError("The downloaded catalogue is incomplete.")
        temporary.replace(output)
        metadata = {
            "version": VERSION,
            "language": "en",
            "source_url": API,
            "query": {
                "isInScheme": "http://data.europa.eu/esco/concept-scheme/skills",
                "selectedVersion": VERSION,
                "language": "en",
                "viewObsolete": False,
            },
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "skill_count": len(exported),
            "bulk_concept_count": total,
            "excluded_group_count": len(seen) - len(exported),
            "classification_filter": "Individual member-skills concepts only; hierarchy groups excluded",
            "checksum": sha256(output.read_bytes()).hexdigest(),
        }
        output.with_suffix(".json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
        return metadata
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = download(args.output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"ESCO download failed: {exc}") from exc
    print(
        f"Verified {result['skill_count']} unique English skills from ESCO {VERSION}."
    )
