"""Hand-calculated metric cases and completeness of the frozen evaluation labels."""

import json
from math import log2
from pathlib import Path

from django.test import SimpleTestCase

from evaluation.matching import validate_dataset
from evaluation.metrics import macro_average, ranking_metrics


class EvaluationTests(SimpleTestCase):
    def test_ideal_ranking_and_relevant_threshold(self):
        result = ranking_metrics([3, 2, 1, 0], [0, 1, 2, 3])
        self.assertEqual(result["precision_at_3"], 2 / 3)
        self.assertEqual(result["recall_at_3"], 1)
        self.assertEqual(result["ndcg_at_10"], 1)
        self.assertEqual(result["mrr_at_10_ideal"], 1)
        self.assertEqual(result["pairwise_concordance"], 1)

    def test_reversed_ranking_has_hand_calculated_discount(self):
        result = ranking_metrics([0, 1, 2, 3], [3, 2, 1, 0])
        ideal = 7 + 3 / log2(3) + 1 / log2(4)
        observed = 1 / log2(3) + 3 / log2(4) + 7 / log2(5)
        self.assertAlmostEqual(result["ndcg_at_10"], observed / ideal)
        self.assertEqual(result["recall_at_3"], 0.5)
        self.assertEqual(result["mrr_at_10_ideal"], 0.25)
        self.assertEqual(result["pairwise_concordance"], 0)

    def test_small_and_no_relevance_queries_have_explicit_denominators(self):
        self.assertEqual(ranking_metrics([2], [2])["precision_at_3"], 1)
        empty = ranking_metrics([0, 0], [0, 0])
        self.assertIsNone(empty["recall_at_3"])
        self.assertIsNone(empty["ndcg_at_10"])
        self.assertIsNone(empty["pairwise_concordance"])
        self.assertEqual(empty["mrr_at_10_ideal"], 0)
        self.assertEqual(
            macro_average([{"value": None}, {"value": 0.5}]), {"value": 0.5}
        )

    def test_cutoff_ignores_ideal_item_beyond_ten(self):
        self.assertEqual(
            ranking_metrics([0] * 10 + [3], [3] + [0] * 10)["mrr_at_10_ideal"], 0
        )

    def test_grade_ties_do_not_create_pairwise_errors(self):
        self.assertEqual(
            ranking_metrics([3, 2, 2, 0], [0, 2, 3, 2])["pairwise_concordance"], 1
        )

    def test_incomplete_or_invalid_rankings_are_rejected(self):
        for ranked, labelled in (([3], [3, 2]), ([4], [4]), ([True], [True])):
            with self.subTest(ranked=ranked), self.assertRaises(ValueError):
                ranking_metrics(ranked, labelled)

    def test_dataset_has_complete_labels_and_predeclared_winners(self):
        path = Path(__file__).resolve().parent.parent / "evaluation/dataset-v1.json"
        dataset = json.loads(path.read_text(encoding="utf-8"))
        validate_dataset(dataset)
        self.assertEqual(len(dataset["labels"]), 100)
        self.assertEqual(len(dataset["expected_top_profile_by_job"]), 5)
        dataset["labels"].pop()
        with self.assertRaises(ValueError):
            validate_dataset(dataset)
