def minmax_normalize_scores(scores: dict) -> dict:
    """Min-max normalize a {candidate_id: score} dict to 0-1.

    Used by the live Hybrid blend (RecommendationService.get_recommendations)
    to put its two source models' scores -- different similarity measures on
    different raw scales -- on a common footing before combining them. A
    single-item dict normalizes to 1.0 -- there's no spread to divide by,
    but the one candidate is still the best (only) one available.
    """
    if not scores:
        return {}
    values = list(scores.values())
    lo, hi = min(values), max(values)
    if hi == lo:
        return {k: 1.0 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}
