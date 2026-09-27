"""
change_detection.py
Compares two epochs of the buildings layer (baseline survey vs a newer
survey/drone capture) and classifies each footprint as NEW, REMOVED,
GEOMETRY CHANGED or UNCHANGED.
"""

import pandas as pd
import geopandas as gpd

from crs_utils import to_metric
from utils import CHANGE_IOU_THRESHOLD


def detect_changes(baseline_gdf: gpd.GeoDataFrame, updated_gdf: gpd.GeoDataFrame):
    if baseline_gdf is None or updated_gdf is None:
        return pd.DataFrame()

    base_m = to_metric(baseline_gdf).reset_index(drop=True)
    upd_m = to_metric(updated_gdf).reset_index(drop=True)

    base_ids = set(baseline_gdf["building_id"]) if "building_id" in baseline_gdf.columns else set()
    upd_ids = set(updated_gdf["building_id"]) if "building_id" in updated_gdf.columns else set()

    rows = []

    # Removed: present in baseline, missing in updated
    for bid in sorted(base_ids - upd_ids):
        rows.append({"building_id": bid, "change_type": "REMOVED", "iou": None, "notes": "Present in baseline only"})

    # New: present in updated, missing in baseline
    for bid in sorted(upd_ids - base_ids):
        rows.append({"building_id": bid, "change_type": "NEW", "iou": None, "notes": "Present in updated survey only"})

    # Compare geometry for buildings present in both
    common_ids = base_ids & upd_ids
    base_lookup = {row["building_id"]: geom for row, geom in zip(baseline_gdf.to_dict("records"), base_m.geometry)}
    upd_lookup = {row["building_id"]: geom for row, geom in zip(updated_gdf.to_dict("records"), upd_m.geometry)}

    for bid in sorted(common_ids):
        g1 = base_lookup.get(bid)
        g2 = upd_lookup.get(bid)
        if g1 is None or g2 is None or g1.is_empty or g2.is_empty:
            continue
        if not g1.is_valid or not g2.is_valid:
            iou = None
            change_type = "GEOMETRY CHANGED"
            notes = "Could not compute IoU (invalid geometry) -- manual review recommended"
        else:
            inter = g1.intersection(g2).area
            union = g1.union(g2).area
            iou = inter / union if union > 0 else 0
            if iou >= CHANGE_IOU_THRESHOLD:
                change_type = "UNCHANGED"
                notes = "Footprint stable between surveys"
            else:
                change_type = "GEOMETRY CHANGED"
                notes = "Footprint area/shape changed between surveys"
        rows.append({
            "building_id": bid,
            "change_type": change_type,
            "iou": round(iou, 3) if iou is not None else None,
            "notes": notes,
        })

    df = pd.DataFrame(rows)
    order = {"NEW": 0, "REMOVED": 1, "GEOMETRY CHANGED": 2, "UNCHANGED": 3}
    if len(df):
        df["_order"] = df["change_type"].map(order)
        df = df.sort_values("_order").drop(columns="_order").reset_index(drop=True)
    return df
