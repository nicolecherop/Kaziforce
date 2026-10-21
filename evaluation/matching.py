"""Evaluate frozen expectations using the unmodified production scoring engine."""

from copy import deepcopy
from datetime import date

from matching.inputs import professional_profile, standardize_pairs
from matching.scoring import MatchingError, experience_years, score_pair
from matching.skills import standardize_skills
from matching.vectorization import cosine

from .metrics import macro_average, ranking_metrics


def validate_dataset(dataset):
    jobs, profiles, labels = dataset["jobs"], dataset["profiles"], dataset["labels"]
    for rows in (jobs, profiles):
        if len({row["id"] for row in rows}) != len(rows):
            raise ValueError("Duplicate scenario ID.")
    expected = {(job["id"], profile["id"]) for job in jobs for profile in profiles}
    actual = {(row["job_id"], row["profile_id"]) for row in labels}
    if actual != expected or len(labels) != len(expected):
        raise ValueError("Every job/profile pair needs exactly one predeclared label.")
    if any(
        type(row["grade"]) is not int
        or row["grade"] not in range(4)
        or not row["rationale"]
        for row in labels
    ):
        raise ValueError("Each label needs a valid grade and rationale.")
    date.fromisoformat(dataset["as_of"])


def evaluate_rankings(dataset, catalogue, reference):
    validate_dataset(dataset)
    labels = {(row["job_id"], row["profile_id"]): row for row in dataset["labels"]}
    pairs = [
        {
            "job_id": job["id"],
            "profile_id": profile["id"],
            "profile": professional_profile(profile["snapshot"]),
            "job": deepcopy(job["requirements"]),
        }
        for job in dataset["jobs"]
        for profile in dataset["profiles"]
    ]
    standardize_pairs(pairs, catalogue)
    rows = []
    for pair in pairs:
        result = score_pair(
            pair["profile"],
            pair["job"],
            reference,
            date.fromisoformat(dataset["as_of"]),
        )
        rows.append(
            {
                "job_id": pair["job_id"],
                "profile_id": pair["profile_id"],
                "grade": labels[pair["job_id"], pair["profile_id"]]["grade"],
                "rationale": labels[pair["job_id"], pair["profile_id"]]["rationale"],
                "score": str(result["score"]),
                "raw_score": result["raw_score"],
                "components": result["components"],
                "explanation": result["explanation"],
            }
        )
    directions = {}
    for direction, query_key, item_key in (
        ("recruiter", "job_id", "profile_id"),
        ("candidate", "profile_id", "job_id"),
    ):
        queries = []
        for query_id in sorted({row[query_key] for row in rows}):
            ranked = sorted(
                (row for row in rows if row[query_key] == query_id),
                key=lambda row: (-row["raw_score"], row[item_key]),
            )
            grades = [row["grade"] for row in ranked]
            for rank, row in enumerate(ranked, 1):
                row[f"{direction}_rank"] = rank
            queries.append(
                {
                    "query_id": query_id,
                    "metrics": ranking_metrics(grades, grades),
                    "ranking": [
                        {
                            "item_id": row[item_key],
                            "grade": row["grade"],
                            "score": row["score"],
                        }
                        for row in ranked
                    ],
                }
            )
        directions[direction] = {
            "queries": queries,
            "macro": macro_average([row["metrics"] for row in queries]),
        }
    return {"pairs": rows, "directions": directions}


def behavioral_checks(dataset, catalogue, reference):
    """Assertions about documented behavior, separate from relevance judgements."""
    results = []
    as_of = date.fromisoformat(dataset["as_of"])

    def check(name, passed, evidence):
        results.append({"name": name, "passed": bool(passed), "evidence": evidence})

    def score(profile, job):
        pair = {"profile": professional_profile(profile), "job": deepcopy(job)}
        standardize_pairs([pair], catalogue)
        return score_pair(pair["profile"], pair["job"], reference, as_of)

    # No text/education/experience targets, to isolate priority-weighted coverage.
    job = {
        **dataset["jobs"][0]["requirements"],
        "title": "",
        "description": "",
        "requirements": "",
        "education_level": "any",
        "education_field": "",
        "minimum_experience_years": None,
        "experience_details": "",
        "skills": [
            {"name": "Python", "requirement": "required", "priority": 3},
            {"name": "JavaScript", "requirement": "required", "priority": 1},
        ],
    }
    # Scoring still includes the skill label text; symmetric profile text cancels
    # that component between these two candidates while coverage changes.
    left = {
        "profile": {"headline": "Python JavaScript", "summary": ""},
        "skills": [{"name": "Python"}],
    }
    right = {"profile": left["profile"], "skills": [{"name": "JavaScript"}]}
    before = [score(profile, job)["raw_score"] for profile in (left, right)]
    job["skills"][0]["priority"], job["skills"][1]["priority"] = 1, 3
    after = [score(profile, job)["raw_score"] for profile in (left, right)]
    check(
        "Recruiter priority changes ranking",
        before[0] > before[1] and after[1] > after[0],
        {"before": before, "after": after},
    )

    aliases = standardize_skills(
        ["Python", "Python (computer programming)"], catalogue
    )["skills"]
    check(
        "Python aliases map to the same concept",
        all(row["status"] == "mapped" for row in aliases)
        and aliases[0]["uri"] == aliases[1]["uri"],
        aliases,
    )
    baseline = deepcopy(dataset["jobs"][0]["requirements"])
    profile = deepcopy(dataset["profiles"][0]["snapshot"])
    once = score(profile, baseline)
    baseline["skills"].append(
        {**baseline["skills"][0], "name": "Python (computer programming)"}
    )
    twice = score(profile, baseline)
    check(
        "Duplicate aliases do not inflate score",
        once["raw_score"] == twice["raw_score"],
        {"once": str(once["score"]), "twice": str(twice["score"])},
    )
    sql = standardize_skills(["SQL"], catalogue)["skills"][0]
    check(
        "Ambiguous SQL remains unresolved",
        sql["status"] == "ambiguous" and sql["uri"] is None,
        sql,
    )

    job["skills"] = [
        {"name": "KaziForceFixtureSkillXYZ", "requirement": "required", "priority": 1}
    ]
    exact = score({"skills": [{"name": "KaziForceFixtureSkillXYZ"}]}, job)
    different = score({"skills": [{"name": "KaziForceFixtureSkillXY"}]}, job)
    check(
        "Unknown skills require exact wording",
        bool(exact["explanation"]["matched_skills"])
        and not different["explanation"]["matched_skills"],
        {"matched": exact["explanation"]["matched_skills"]},
    )
    try:
        score({}, job)
    except MatchingError:
        empty_rejected = True
    else:
        empty_rejected = False
    check(
        "Empty profile is explicitly unscorable",
        empty_rejected,
        "No manufactured score for missing professional evidence.",
    )
    oov = cosine(
        "KaziForceFixtureSkillXYZ",
        "KaziForceFixtureSkillXYZ",
        reference["document_frequencies"],
        reference["document_count"],
    )
    check(
        "Out-of-vocabulary text contributes no cosine evidence",
        oov == 0,
        {"cosine": oov},
    )
    single = [{"start_date": "2020-01-01", "end_date": "2023-01-01"}]
    overlapping = single + [{"start_date": "2021-01-01", "end_date": "2022-01-01"}]
    years, incomplete = experience_years(overlapping, as_of)
    check(
        "Overlapping roles are not counted twice",
        experience_years(single, as_of)[0] == years and not incomplete,
        {"years": years},
    )

    # A limitation probe, not a claim that years in another field are equivalent.
    unrelated = deepcopy(profile)
    unrelated["experience"] = [
        {
            "job_title": "Retail assistant",
            "description": "Stock shelves and serve customers.",
            "start_date": "2018-01-01",
            "end_date": "2025-01-01",
            "currently_working": False,
        }
    ]
    duration_job = deepcopy(dataset["jobs"][0]["requirements"])
    duration_job["experience_details"] = ""
    duration_result = score(unrelated, duration_job)
    duration_component = next(
        row for row in duration_result["components"] if row["key"] == "experience"
    )
    return results, [
        {
            "name": "Unrelated work still counts towards declared duration",
            "observed_component_score": duration_component["score"],
            "interpretation": "Duration includes all declared roles. Recruiters must assess relevance; duration alone is not evidence of relevant experience.",
        }
    ]
