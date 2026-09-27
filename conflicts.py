"""
conflicts.py
Detects spatial conflicts across layers:
  - Cadastral-plot vs cadastral-plot overlaps
  - Duplicate buildings (near-identical geometry, IoU based)
  - Buildings crossing two or more cadastral plots (uses matching.py output)
  - Buildings lying entirely outside all cadastral plots (uses matching.py output)
"""

import itertools
import pandas as pd
import geopandas as gpd

from crs_utils import to_metric
from utils import DUPLICATE_IOU_THRESHOLD


def detect_cadastral_overlaps(cadastral_gdf: gpd.GeoDataFrame):
    """Pairwise check for cadastral polygons that overlap by area (not just touching)."""
    rows = []
    if len(cadastral_gdf) < 2:
        return pd.DataFrame(columns=["plot_id_a", "plot_id_b", "overlap_area_sqm", "overlap_pct_of_smaller"])

    p_m = to_metric(cadastral_gdf).reset_index(drop=True)
    ids = cadastral_gdf["plot_id"].reset_index(drop=True) if "plot_id" in cadastral_gdf.columns else p_m.index.astype(str)

    for i, j in itertools.combinations(range(len(p_m)), 2):
        g1, g2 = p_m.geometry.iloc[i], p_m.geometry.iloc[j]
        if not g1.is_valid or not g2.is_valid or g1.is_empty or g2.is_empty:
            continue
        if not g1.intersects(g2):
            continue
        inter = g1.intersection(g2)
        if inter.is_empty or inter.area <= 0:
            continue
        smaller_area = min(g1.area, g2.area)
        pct = (inter.area / smaller_area) * 100 if smaller_area > 0 else 0
        if pct < 0.5:
            continue  # ignore negligible sliver overlaps from shared-edge rounding
        rows.append({
            "plot_id_a": ids.iloc[i],
            "plot_id_b": ids.iloc[j],
            "overlap_area_sqm": round(inter.area, 1),
            "overlap_pct_of_smaller": round(pct, 1),
        })
    return pd.DataFrame(rows)


def detect_duplicate_buildings(buildings_gdf: gpd.GeoDataFrame):
    """Pairwise IoU check to find near-identical duplicate building footprints."""
    rows = []
    if len(buildings_gdf) < 2:
        return pd.DataFrame(columns=["building_id_a", "building_id_b", "iou"])

    b_m = to_metric(buildings_gdf).reset_index(drop=True)
    ids = buildings_gdf["building_id"].reset_index(drop=True) if "building_id" in buildings_gdf.columns else b_m.index.astype(str)

    for i, j in itertools.combinations(range(len(b_m)), 2):
        g1, g2 = b_m.geometry.iloc[i], b_m.geometry.iloc[j]
        if not g1.is_valid or not g2.is_valid or g1.is_empty or g2.is_empty:
            continue
        if not g1.intersects(g2):
            continue
        inter = g1.intersection(g2).area
        union = g1.union(g2).area
        if union == 0:
            continue
        iou = inter / union
        if iou >= DUPLICATE_IOU_THRESHOLD:
            rows.append({
                "building_id_a": ids.iloc[i],
                "building_id_b": ids.iloc[j],
                "iou": round(iou, 3),
            })
    return pd.DataFrame(rows)


def build_conflict_summary(cadastral_overlaps_df, duplicate_df, match_df):
    """
    Consolidate all conflict types into one flat DataFrame:
    columns = conflict_type, entity_ids, details
    """
    rows = []

    for _, r in cadastral_overlaps_df.iterrows():
        rows.append({
            "conflict_type": "Cadastral Overlap",
            "entities": f"{r['plot_id_a']} <-> {r['plot_id_b']}",
            "details": f"{r['overlap_pct_of_smaller']}% overlap ({r['overlap_area_sqm']} sqm)",
        })

    for _, r in duplicate_df.iterrows():
        rows.append({
            "conflict_type": "Duplicate Building",
            "entities": f"{r['building_id_a']} <-> {r['building_id_b']}",
            "details": f"IoU = {r['iou']}",
        })

    if match_df is not None and len(match_df):
        crossing = match_df[match_df["crosses_boundary"]]
        for _, r in crossing.iterrows():
            rows.append({
                "conflict_type": "Building Crosses Boundary",
                "entities": r["building_id"],
                "details": f"Overlaps plots: {r['candidate_plots']}",
            })

        outside = match_df[(~match_df["matched"]) & (match_df["num_candidate_plots"] == 0)]
        for _, r in outside.iterrows():
            rows.append({
                "conflict_type": "Building Outside All Plots",
                "entities": r["building_id"],
                "details": "No cadastral plot intersects this building footprint",
            })

    return pd.DataFrame(rows, columns=["conflict_type", "entities", "details"])
