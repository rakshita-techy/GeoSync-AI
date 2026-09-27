"""
confidence.py
Explainable, weighted confidence scoring for every building record, and
final status classification used across the app (Dashboard, Integrated
Records, Reports).

confidence = 100 * ( w_validity * validity_component
                    + w_match    * match_component
                    + w_conflict * conflict_free_component )

All weights and inputs are transparent -- this is rule-based scoring,
not a trained/black-box model.
"""

import pandas as pd

from utils import (
    CONF_WEIGHT_VALIDITY, CONF_WEIGHT_MATCH, CONF_WEIGHT_CONFLICT_FREE,
    CONF_VERIFIED_MIN, CONF_REVIEW_MIN,
    STATUS_VERIFIED, STATUS_REVIEW, STATUS_CONFLICT, STATUS_UNMATCHED, STATUS_INVALID,
)


def compute_confidence(match_df: pd.DataFrame, validation_df: pd.DataFrame, conflict_entities: set):
    """
    Build one row per building combining:
      - geometry validity (from validation_df, layer='Buildings')
      - AI match quality (match_score from matching.py)
      - presence/absence of a conflict flag (from conflicts.py entity set)
    Returns a DataFrame with confidence (0-100) and final status.
    """
    if match_df is None or len(match_df) == 0:
        return pd.DataFrame()

    valid_lookup = {}
    if validation_df is not None and len(validation_df):
        bld_val = validation_df[validation_df["layer"] == "Buildings"]
        valid_lookup = dict(zip(bld_val["feature_id"], bld_val["is_valid"]))

    rows = []
    for _, r in match_df.iterrows():
        bid = r["building_id"]
        is_valid = bool(valid_lookup.get(bid, True))
        match_component = min(max(r["match_score"], 0.0), 1.0)
        has_conflict = bid in conflict_entities
        conflict_component = 0.0 if has_conflict else 1.0
        validity_component = 1.0 if is_valid else 0.0

        confidence = 100 * (
            CONF_WEIGHT_VALIDITY * validity_component
            + CONF_WEIGHT_MATCH * match_component
            + CONF_WEIGHT_CONFLICT_FREE * conflict_component
        )

        if not is_valid:
            status = STATUS_INVALID
        elif has_conflict:
            status = STATUS_CONFLICT
        elif not r["matched"]:
            status = STATUS_UNMATCHED
        elif confidence >= CONF_VERIFIED_MIN:
            status = STATUS_VERIFIED
        elif confidence >= CONF_REVIEW_MIN:
            status = STATUS_REVIEW
        else:
            status = STATUS_REVIEW

        rows.append({
            "building_id": bid,
            "plot_id": r["best_plot_id"],
            "is_valid_geometry": is_valid,
            "match_score": round(match_component, 3),
            "has_conflict": has_conflict,
            "confidence": round(confidence, 1),
            "status": status,
        })

    return pd.DataFrame(rows)


def conflict_entity_set(conflict_summary_df: pd.DataFrame):
    """Extract the set of building_ids that appear in any conflict row's entities field."""
    entities = set()
    if conflict_summary_df is None or len(conflict_summary_df) == 0:
        return entities
    for val in conflict_summary_df["entities"]:
        for token in str(val).replace("<->", ",").split(","):
            token = token.strip()
            if token.startswith("BLD-"):
                entities.add(token)
    return entities
