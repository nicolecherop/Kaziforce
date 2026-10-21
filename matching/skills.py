"""Resolve exact preferred/alternative labels without guessing missing skills."""

from .models import SkillCatalogue, SkillLabel
from .normalization import NORMALIZATION_VERSION, normalize_skill
from django.db.models.functions import Length


def standardize_skills(names, catalogue=None):
    names = list(names)
    catalogue = catalogue or SkillCatalogue.objects.filter(active=True).first()
    matches = {}
    if catalogue:
        for label in (
            SkillLabel.objects.filter(
                skill__catalogue=catalogue,
                normalized__in={normalize_skill(name) for name in names},
            )
            .select_related("skill")
            .order_by("skill__uri")
        ):
            matches.setdefault(label.normalized, {})[label.skill.uri] = label.skill
    results = []
    for name in names:
        options = list(matches.get(normalize_skill(name), {}).values())
        # A label shared by multiple concepts needs review even when it is a
        # preferred label of one concept and an alternative of another.
        if not catalogue:
            status = "not_checked"
        elif len(options) == 1:
            status = "mapped"
        elif options:
            status = "ambiguous"
        else:
            status = "unrecognized"
        results.append(
            {
                "name": name,
                "status": status,
                "uri": options[0].uri if len(options) == 1 else None,
                "preferred_label": (
                    options[0].preferred_label if len(options) == 1 else None
                ),
            }
        )
    return {
        "normalization_version": NORMALIZATION_VERSION,
        "catalogue": catalogue.provenance() if catalogue else None,
        "skills": results,
    }


def skill_suggestions(query, maximum=10):
    catalogue = SkillCatalogue.objects.filter(active=True).first()
    normalized = normalize_skill(query)
    if not catalogue or len(normalized) < 2 or len(normalized) > 80:
        return []
    # Prefix matches provide predictable suggestions without expensive fuzzy
    # inference. Return reference concepts only, never other users' skill text.
    labels = (
        SkillLabel.objects.filter(
            skill__catalogue=catalogue, normalized__startswith=normalized
        )
        .annotate(label_length=Length("skill__preferred_label"))
        .filter(label_length__lte=80)
        .select_related("skill")
        .order_by("normalized", "skill__uri")[:100]
    )
    seen, results = set(), []
    for label in labels:
        if label.skill.uri in seen:
            continue
        seen.add(label.skill.uri)
        results.append(
            {"label": label.skill.preferred_label, "matched_label": label.label}
        )
        if len(results) >= maximum:
            break
    return results
