"""Pure decay computation functions for memory organization.

All functions are pure (no IO), making them easy to test independently.
Decay is based on quality metrics (confidence + validations), not time.
"""


def compute_quality_score(confidence: float, validations: int) -> float:
    """Compute effective quality score: confidence * (1 + validations * 0.1).

    Capped at 1.0. Higher validations boost effective confidence.
    """
    score = confidence * (1 + validations * 0.1)
    return min(score, 1.0)


def should_deprecate(confidence: float, validations: int) -> bool:
    """Return True if entry should be deprecated.

    Criteria: confidence < 0.3 AND validations == 0.
    """
    return confidence < 0.3 and validations == 0


def should_archive(confidence: float, validations: int, age_days: int) -> bool:
    """Return True if entry should be archived.

    Criteria: confidence < 0.5 AND validations == 0 AND age_days > 30.
    """
    return confidence < 0.5 and validations == 0 and age_days > 30


def should_compress(entries: list[dict], similarity_threshold: float = 0.8) -> list[list[dict]]:
    """Group entries that are similar enough to compress.

    Similarity is based on matching (module, exp_type) and overlapping keywords.
    Returns groups of entries that should be compressed together.
    """
    if not entries:
        return []

    # Group by (module, exp_type)
    groups: dict[tuple[str, str], list[dict]] = {}
    for entry in entries:
        key = (entry.get("module", ""), entry.get("exp_type", ""))
        if key not in groups:
            groups[key] = []
        groups[key].append(entry)

    # Only return groups with more than one entry (worth compressing)
    result: list[list[dict]] = []
    for group_entries in groups.values():
        if len(group_entries) > 1:
            result.append(group_entries)

    return result

def should_promote_to_global(confidence: float, validations: int, abstraction: str) -> bool:
    """Return True if wiki entry should be promoted to global wiki.

    Criteria: confidence >= 0.95 AND (abstraction == 'universal' or abstraction == 'framework').
    """
    return confidence >= 0.95 and abstraction in ("universal", "framework")
