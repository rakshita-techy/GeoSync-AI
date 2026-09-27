"""
topology.py
Rule-based topology / geometry validation. Uses Shapely's own validity
engine (is_valid / explain_validity) -- no black-box ML involved.
"""

import pandas as pd
import geopandas as gpd
from shapely.validation import explain_validity

try:
    from shapely.validation import make_valid
    HAS_MAKE_VALID = True
except ImportError:
    HAS_MAKE_VALID = False


def validate_geometries(gdf: gpd.GeoDataFrame, id_col: str, layer_name: str):
    """
    Check every geometry in a layer for validity, emptiness and geometry-type
    consistency. Returns a DataFrame with one row per feature.
    """
    rows = []
    if gdf is None or len(gdf) == 0:
        return pd.DataFrame(columns=["layer", "feature_id", "is_valid", "issue", "suggested_fix"])

    expected_type = gdf.geometry.geom_type.mode().iloc[0] if len(gdf) else None

    for _, row in gdf.iterrows():
        geom = row.geometry
        feature_id = row[id_col] if id_col in row else str(row.name)
        issue = ""
        is_valid = True
        suggested_fix = ""

        if geom is None or geom.is_empty:
            is_valid = False
            issue = "Empty or missing geometry"
            suggested_fix = "Re-digitize or re-import this feature from source data."
        elif not geom.is_valid:
            is_valid = False
            reason = explain_validity(geom)
            if "Self-intersection" in reason or "ring self-intersection" in reason.lower():
                issue = f"Invalid geometry (bowtie / self-intersecting polygon) -- {reason}"
            else:
                issue = f"Invalid geometry -- {reason}"
            suggested_fix = ("Apply geometry repair (e.g. buffer(0) / make_valid) "
                              "and re-verify against source imagery.")
        elif geom.geom_type != expected_type:
            issue = f"Unexpected geometry type: {geom.geom_type} (layer is mostly {expected_type})"
            suggested_fix = "Confirm this feature was digitized with the correct tool."
        else:
            issue = "OK"

        rows.append({
            "layer": layer_name,
            "feature_id": feature_id,
            "is_valid": is_valid,
            "issue": issue,
            "suggested_fix": suggested_fix,
        })

    return pd.DataFrame(rows)


def repair_geometry(geom):
    """Attempt to repair an invalid geometry. Returns the repaired geometry (or original)."""
    if geom is None:
        return geom
    if geom.is_valid:
        return geom
    if HAS_MAKE_VALID:
        try:
            return make_valid(geom)
        except Exception:
            pass
    try:
        return geom.buffer(0)
    except Exception:
        return geom


def validation_summary(*validation_dfs):
    """Combine multiple per-layer validation DataFrames and summarize counts."""
    if not validation_dfs:
        return pd.DataFrame(), {"total": 0, "invalid": 0}
    combined = pd.concat([d for d in validation_dfs if d is not None and len(d)], ignore_index=True)
    invalid_count = int((~combined["is_valid"]).sum()) if len(combined) else 0
    return combined, {"total": len(combined), "invalid": invalid_count}
