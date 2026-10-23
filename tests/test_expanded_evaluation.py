"""Expanded fixture integrity, blind-review safety and retrieval denominators."""

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from evaluation.expanded import export_reviews, quality, stable_id
from evaluation.expanded_dataset import build_dataset


class ExpandedEvaluationTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = build_dataset()

    def test_frozen_dataset_matches_deterministic_generator(self):
        path = Path(__file__).resolve().parent.parent / "evaluation/dataset-v2.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), self.dataset)
        self.assertEqual(build_dataset(), self.dataset)

    def test_counts_complete_labels_and_independent_baseline_version(self):
        data = self.dataset
        self.assertEqual(
            [
                len(data[key])
                for key in (
                    "profiles",
                    "jobs",
                    "freelancers",
                    "projects",
                    "labels",
                    "freelance_labels",
                )
            ],
            [200, 40, 60, 20, 8000, 1200],
        )
        for queries, profiles, labels in (
            ("jobs", "profiles", "labels"),
            ("projects", "freelancers", "freelance_labels"),
        ):
            expected = {
                (j["id"], p["id"]) for j in data[queries] for p in data[profiles]
            }
            actual = {(r["job_id"], r["profile_id"]) for r in data[labels]}
            self.assertEqual(actual, expected)
            self.assertEqual(len(actual), len(data[labels]))
            self.assertTrue(
                all(
                    type(r["grade"]) is int
                    and r["grade"] in range(4)
                    and r["rationale"]
                    for r in data[labels]
                )
            )

    def test_variants_and_holdout_are_declared_before_scoring(self):
        data = self.dataset
        self.assertEqual(len({p["domain"] for p in data["profiles"]}), 10)
        self.assertEqual(len({p["variant"] for p in data["profiles"]}), 10)
        self.assertEqual(sum(p["split"] == "holdout" for p in data["profiles"]), 60)
        self.assertEqual(sum(j["split"] == "holdout" for j in data["jobs"]), 10)
        self.assertEqual(
            len({json.dumps(p["snapshot"], sort_keys=True) for p in data["profiles"]}),
            200,
        )
        self.assertTrue(any(not w["ratings"] for w in data["freelancers"]))
        self.assertTrue(any(w["busy"] for w in data["freelancers"]))
        self.assertTrue(any(not w["accepting_bookings"] for w in data["freelancers"]))

    def test_review_packets_are_blind_and_all_400_grades_start_blank(self):
        with TemporaryDirectory() as directory:
            output = Path(directory)
            status = export_reviews(output, self.dataset)
            self.assertEqual(status["total"], 400)
            with (output / "reviewer-1.csv").open(
                encoding="utf-8-sig", newline=""
            ) as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len({r["pair_id"] for r in rows}), 400)
            self.assertEqual(sum(r["section"] == "employment" for r in rows), 300)
            self.assertTrue(
                all(not r["grade_0_to_3"] and not r["reviewer_id"] for r in rows)
            )
            packets = json.loads(
                (output / "blind-review-packets.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                {r["pair_id"] for r in packets}, {r["pair_id"] for r in rows}
            )
            self.assertTrue(
                all(set(r) == {"pair_id", "opportunity", "evidence"} for r in packets)
            )
            text = json.dumps(packets)
            for hidden in (
                '"grade"',
                '"score"',
                '"variant"',
                '"rationale"',
                '"domain"',
            ):
                self.assertNotIn(hidden, text)

    def test_filtered_out_relevant_items_do_not_receive_retrieval_credit(self):
        self.assertEqual(quality([0], [3, 0])["recall_at_5"], 0)
        self.assertEqual(quality([0], [3, 0])["ndcg_at_10"], 0)
        empty = quality([], [3])
        self.assertEqual(empty["recall_at_5"], 0)
        self.assertEqual(empty["ndcg_at_10"], 0)
        self.assertIsNone(empty["precision_at_5"])

    def test_precision_and_recall_use_different_documented_denominators(self):
        result = quality([3, 1], [3, 2, 1])
        self.assertEqual(result["precision_at_5"], 0.5)
        self.assertEqual(result["recall_at_5"], 0.5)
        self.assertEqual(quality([3, 2], [3, 2])["ndcg_at_10"], 1)

    def test_stable_ids_allow_reproducible_freelance_tie_order(self):
        self.assertEqual(stable_id("worker-1"), stable_id("worker-1"))
        self.assertNotEqual(stable_id("worker-1"), stable_id("worker-2"))
