"""API pagination must never silently produce a partial reference catalogue."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from scripts.download_esco import download


def page(offset, ids, total=3):
    concepts = [
        {"uri": f"http://data.europa.eu/esco/skill/00000000-0000-0000-0000-{i:012d}"}
        for i in ids
    ]
    return {
        "offset": offset,
        "count": len(concepts),
        "total": total,
        "concepts": concepts,
        "_embedded": {
            entry["uri"]: {
                "uri": entry["uri"],
                "className": "Skill",
                "_links": {
                    "isInScheme": [
                        {
                            "uri": "http://data.europa.eu/esco/concept-scheme/member-skills"
                        }
                    ]
                },
                "status": "released",
                "preferredLabel": {"en": f"Skill {i}"},
                "alternativeLabel": {"en": []},
                "description": {"en": {"literal": "Test fixture"}},
            }
            for i, entry in zip(ids, concepts)
        },
    }


class EscoDownloadTests(TestCase):
    def test_hierarchy_groups_are_excluded_from_individual_skill_export(self):
        response = page(0, [1, 2, 3])
        group_uri = response["concepts"][1]["uri"]
        response["_embedded"][group_uri]["_links"] = {
            "isInScheme": [
                {"uri": "http://data.europa.eu/esco/concept-scheme/skills-hierarchy"}
            ]
        }
        with TemporaryDirectory() as directory:
            output = Path(directory) / "skills.csv"
            with patch("scripts.download_esco.fetch_page", return_value=response):
                metadata = download(output, limit=3)
            self.assertEqual(metadata["bulk_concept_count"], 3)
            self.assertEqual(metadata["skill_count"], 2)
            self.assertEqual(metadata["excluded_group_count"], 1)
            self.assertNotIn(group_uri, output.read_text())

    def test_uses_page_numbers_and_writes_verified_manifest(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "skills.csv"
            with patch(
                "scripts.download_esco.fetch_page",
                side_effect=[page(0, [1, 2]), page(1, [3])],
            ) as fetch:
                metadata = download(output, limit=2)
            self.assertEqual(
                [call.args for call in fetch.call_args_list], [(0, 2), (1, 2)]
            )
            self.assertEqual(metadata["skill_count"], 3)
            self.assertEqual(
                json.loads(output.with_suffix(".json").read_text())["checksum"],
                metadata["checksum"],
            )
            self.assertTrue(output.exists())

    def test_duplicates_changed_totals_and_missing_pages_never_publish_partial_csv(
        self,
    ):
        for second in (page(1, [2]), page(1, [3], total=4), page(1, [])):
            with self.subTest(page=second), TemporaryDirectory() as directory:
                output = Path(directory) / "skills.csv"
                with patch(
                    "scripts.download_esco.fetch_page",
                    side_effect=[page(0, [1, 2]), second],
                ):
                    with self.assertRaises(ValueError):
                        download(output, limit=2)
                self.assertFalse(output.exists())
                self.assertFalse(output.with_suffix(".csv.part").exists())
