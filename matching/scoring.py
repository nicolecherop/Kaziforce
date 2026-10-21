"""Pure scoring functions; no database, identity, documents or status decisions."""

from copy import deepcopy
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from .normalization import normalize_skill
from .vectorization import cosine, tokens

CONFIGURATION = {
    "version": "matching-v1",
    "tf": "1 + ln(count)",
    "idf": "ln((1 + document_count) / (1 + document_frequency)) + 1",
    "normalization": "L2",
    "vocabulary": "fixed public ESCO vocabulary; out-of-vocabulary text ignored",
    "weights": {"skills": 50, "text": 20, "education": 15, "experience": 15},
    "required_multiplier": 2,
    "experience_duration_share": 0.5,
    "days_per_year": 365.25,
}


class MatchingError(ValueError):
    """A run cannot be calculated safely from the available reference/input."""


def configuration():
    return deepcopy(CONFIGURATION)


def percentage(value):
    return Decimal(str(value * 100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def canonical_skills(entries, mappings):
    """Collapse aliases to one concept; unresolved terms use exact wording only."""
    result = {}
    for entry, mapping in zip(entries, mappings, strict=True):
        key = (
            mapping["uri"]
            if mapping["status"] == "mapped"
            else "term:" + normalize_skill(entry["name"])
        )
        if not key or key == "term:":
            continue
        item = {
            "name": entry["name"],
            "label": mapping.get("preferred_label") or entry["name"],
            "mapping_status": mapping["status"],
            "priority": int(entry.get("priority", 1)),
            "requirement": entry.get("requirement", "preferred"),
        }
        if key in result:
            item["priority"] = max(item["priority"], result[key]["priority"])
            if result[key]["requirement"] == "required":
                item["requirement"] = "required"
        result[key] = item
    return dict(sorted(result.items()))


def experience_years(entries, as_of):
    """Union declared date intervals so overlapping roles never double-count."""
    periods, incomplete = [], False
    for entry in entries:
        try:
            start = date.fromisoformat(entry.get("start_date") or "")
            end = (
                as_of
                if entry.get("currently_working")
                else date.fromisoformat(entry.get("end_date") or "")
            )
            if end < start or start > as_of:
                raise ValueError("Invalid period")
            periods.append((start, min(end, as_of)))
        except (ValueError, TypeError):
            incomplete = True
    merged = []
    for start, end in sorted(periods):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return (
        sum((end - start).days for start, end in merged)
        / CONFIGURATION["days_per_year"],
        incomplete,
    )


def joined(entries, fields):
    return " ".join(
        str(entry.get(field) or "") for entry in entries for field in fields
    )


def has_evidence(profile):
    return bool(
        profile.get("profile", {}).get("summary")
        or profile.get("profile", {}).get("headline")
        or any(
            profile.get(key)
            for key in ("skills", "education", "certifications", "experience")
        )
    )


def score_pair(profile, job, reference, as_of, config=None):
    config = config or configuration()
    if config != CONFIGURATION:
        raise MatchingError(
            "This scoring configuration is not supported by this engine version."
        )
    if not has_evidence(profile):
        raise MatchingError(
            "Add a summary, skills, education, certifications or experience before requesting matches."
        )
    frequencies, count = reference["document_frequencies"], reference["document_count"]
    if not frequencies or count <= 0:
        raise MatchingError("The matching reference is not ready.")
    candidate = canonical_skills(
        profile.get("skills", []), profile["skill_standardization"]["skills"]
    )
    required = canonical_skills(job["skills"], job["skill_standardization"]["skills"])
    matched, missing, unresolved = [], [], []
    covered = total = 0
    for key, skill in required.items():
        weight = skill["priority"] * (
            config["required_multiplier"] if skill["requirement"] == "required" else 1
        )
        total += weight
        evidence = dict(
            skill, weight=weight, exact_wording_only=skill["mapping_status"] != "mapped"
        )
        if key in candidate:
            covered += weight
            matched.append(evidence)
        else:
            missing.append(evidence)
    for item in [*candidate.values(), *required.values()]:
        if item["mapping_status"] != "mapped" and item["name"] not in unresolved:
            unresolved.append(item["name"])
    profile_text = " ".join(
        [
            profile.get("profile", {}).get("headline", ""),
            profile.get("profile", {}).get("summary", ""),
            " ".join(item["label"] for item in candidate.values()),
            joined(profile.get("education", []), ("qualification", "field_of_study")),
            joined(profile.get("certifications", []), ("name",)),
            joined(profile.get("experience", []), ("job_title", "description")),
        ]
    )
    job_text = " ".join(
        [
            job["title"],
            job["description"],
            job["requirements"],
            " ".join(item["label"] for item in required.values()),
        ]
    )
    similarity = lambda left, right: cosine(left, right, frequencies, count)
    components = []

    def component(key, label, value, active, priority=1):
        weight = config["weights"][key] * priority if active else 0
        components.append(
            {
                "key": key,
                "label": label,
                "score": float(percentage(value)),
                "raw_value": value,
                "weight": weight,
                "active": bool(active),
            }
        )

    component(
        "skills",
        "Priority-weighted skill coverage",
        covered / total if total else 0,
        total,
    )
    component(
        "text",
        "Overall text similarity",
        similarity(profile_text, job_text),
        bool(tokens(job_text)),
    )
    education_target = " ".join(
        [
            job["education_level_label"] if job["education_level"] != "any" else "",
            job["education_field"],
        ]
    )
    component(
        "education",
        "Education wording similarity",
        similarity(
            joined(profile.get("education", []), ("qualification", "field_of_study")),
            education_target,
        ),
        bool(education_target.strip()),
        job["education_priority"],
    )
    years, incomplete_dates = experience_years(profile.get("experience", []), as_of)
    minimum = job["minimum_experience_years"]
    duration = (
        min(years / float(minimum), 1)
        if minimum is not None and float(minimum) > 0
        else 1
    )
    experience_text = similarity(
        joined(profile.get("experience", []), ("job_title", "description")),
        job["experience_details"],
    )
    if minimum is not None and job["experience_details"]:
        experience_score = (
            config["experience_duration_share"] * duration
            + (1 - config["experience_duration_share"]) * experience_text
        )
    else:
        experience_score = duration if minimum is not None else experience_text
    component(
        "experience",
        "Declared experience alignment",
        experience_score,
        minimum is not None or job["experience_details"],
        job["experience_priority"],
    )
    denominator = sum(item["weight"] for item in components)
    if not denominator:
        raise MatchingError(
            "Add job requirements or a meaningful role description before matching."
        )
    # Round once at the final score; component values are stored at full precision
    # below so replay and ranking do not depend on displayed rounded percentages.
    raw = sum(item["raw_value"] * item["weight"] for item in components) / denominator
    for item in components:
        item["share"] = round(item["weight"] / denominator * 100, 4)
    return {
        "score": percentage(raw),
        "raw_score": raw,
        "components": components,
        "explanation": {
            "matched_skills": matched,
            "missing_required_skills": [
                item for item in missing if item["requirement"] == "required"
            ],
            "missing_preferred_skills": [
                item for item in missing if item["requirement"] == "preferred"
            ],
            "unresolved_skills": unresolved,
            "declared_experience_years": round(years, 2),
            "minimum_experience_years": minimum,
            "incomplete_experience_dates": incomplete_dates,
            "education_review": bool(education_target.strip()),
            "experience_review": minimum is not None or bool(job["experience_details"]),
            "ignored_text_terms": len(
                set(tokens(profile_text + " " + job_text)) - frequencies.keys()
            ),
        },
    }
