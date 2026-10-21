"""Ranking metrics with explicit relevance thresholds and cutoff conventions."""

from itertools import combinations
from math import log2
from statistics import mean


def ranking_metrics(ordered_grades, all_grades):
    """Grade >= 2 is relevant; grade 3 is ideal. Lists must be complete rankings.

    Precision divides by min(3, available items). Recall uses all relevant items.
    NDCG uses exponential gains at 10. Pairwise concordance excludes grade ties;
    prediction ties must already have a deterministic secondary ordering.
    Undefined recall/NDCG/concordance is None and omitted from macro averages.
    """
    if sorted(ordered_grades) != sorted(all_grades):
        raise ValueError("The ranking must contain every labelled item exactly once.")
    if any(type(grade) is not int or grade not in range(4) for grade in all_grades):
        raise ValueError("Grades must be integers between 0 and 3.")
    count = min(3, len(ordered_grades))
    hits = sum(grade >= 2 for grade in ordered_grades[:3])
    relevant = sum(grade >= 2 for grade in all_grades)

    def dcg(grades):
        return sum(
            (2**grade - 1) / log2(rank + 2) for rank, grade in enumerate(grades[:10])
        )

    ideal = dcg(sorted(all_grades, reverse=True))
    pairs = [
        (left, right)
        for left, right in combinations(ordered_grades, 2)
        if left != right
    ]
    return {
        "precision_at_3": hits / count if count else None,
        "recall_at_3": hits / relevant if relevant else None,
        "ndcg_at_10": dcg(ordered_grades) / ideal if ideal else None,
        "mrr_at_10_ideal": next(
            (
                1 / rank
                for rank, grade in enumerate(ordered_grades[:10], 1)
                if grade == 3
            ),
            0.0,
        ),
        "pairwise_concordance": (
            sum(left > right for left, right in pairs) / len(pairs) if pairs else None
        ),
    }


def macro_average(rows):
    """Each query has equal weight, excluding undefined values per metric."""
    keys = list(rows[0]) if rows else []
    return {
        key: (
            mean(values)
            if (values := [row[key] for row in rows if row[key] is not None])
            else None
        )
        for key in keys
    }
