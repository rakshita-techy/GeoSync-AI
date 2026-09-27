"""
matching.py
Explainable, rule-based "AI-assisted" spatial matching engine.

IMPORTANT: this is deliberately NOT deep learning. It is a transparent
weighted-scoring algorithm over standard spatial-overlap and distance
metrics, so every match can be explained feature-by-feature to a
non-technical reviewer.
"""

import math
import pandas as pd
import geopandas as gpd

from crs_utils import to_metric
from utils import MATCH_OVERLAP_THRESHOLD, CROSSING_OVERLAP_THRESHOLD, GNSS_MAX_LINK_DISTANCE_M


def _overlap_ratio(building_geom, plot_geom):
    if not building_geom.intersects(plot_geom):
        return 0.0
    inter = building_geom.intersection(plot_geom)
    if inter.is_empty or building_geom.area == 0:
        return 0.0
    return inter.area / building_geom.area


def _centroid_distance(g1, g2):
    return g1.centroid.distance(g2.centroid)


def match_buildings_to_plots(buildings_gdf: gpd.GeoDataFrame, cadastral_gdf: gpd.GeoDataFrame):
    """
    For every building, score it against every cadastral plot using an
    explainable formula:

        score = 0.70 * overlap_ratio + 0.30 * (1 - normalized_centroid_distance)

    The plot with the highest score becomes the "best match" if its score
    clears MATCH_OVERLAP_THRESHOLD; otherwise the building is UNMATCHED.
    Buildings that overlap two-or-more plots above CROSSING_OVERLAP_THRESHOLD
    are additionally flagged as "crosses boundary".

    Returns a DataFrame: one row per building with match details.
    """
    if len(buildings_gdf) == 0 or len(cadastral_gdf) == 0:
        return pd.DataFrame()

    b_m = to_metric(buildings_gdf)
    p_m = to_metric(cadastral_gdf)

    # normalization distance = diagonal of the combined bounding box (meters)
    minx, miny, maxx, maxy = pd.concat([b_m.geometry, p_m.geometry]).total_bounds
    diag = math.hypot(maxx - minx, maxy - miny) or 1.0

    results = []
    for bi, brow in b_m.iterrows():
        bgeom = brow.geometry
        b_id = buildings_gdf.loc[bi, "building_id"] if "building_id" in buildings_gdf.columns else str(bi)

        candidate_scores = []
        for pi, prow in p_m.iterrows():
            pgeom = prow.geometry
            plot_id = cadastral_gdf.loc[pi, "plot_id"] if "plot_id" in cadastral_gdf.columns else str(pi)

            if not bgeom.is_valid or not pgeom.is_valid:
                continue
            if bgeom.is_empty or pgeom.is_empty:
                continue

            overlap = _overlap_ratio(bgeom, pgeom)
            if overlap == 0.0:
                continue
            dist = _centroid_distance(bgeom, pgeom)
            norm_dist = min(dist / diag, 1.0)
            score = 0.70 * overlap + 0.30 * (1 - norm_dist)
            candidate_scores.append({
                "plot_id": plot_id,
                "overlap_ratio": overlap,
                "centroid_distance_m": dist,
                "score": score,
            })

        candidate_scores.sort(key=lambda d: d["score"], reverse=True)
        crossing_plots = [c["plot_id"] for c in candidate_scores if c["overlap_ratio"] >= CROSSING_OVERLAP_THRESHOLD]

        if candidate_scores and candidate_scores[0]["score"] >= MATCH_OVERLAP_THRESHOLD:
            best = candidate_scores[0]
            matched = True
            best_plot = best["plot_id"]
            best_score = best["score"]
            best_overlap = best["overlap_ratio"]
        else:
            matched = False
            best_plot = None
            best_score = candidate_scores[0]["score"] if candidate_scores else 0.0
            best_overlap = candidate_scores[0]["overlap_ratio"] if candidate_scores else 0.0

        crosses_boundary = len(crossing_plots) >= 2

        results.append({
            "building_id": b_id,
            "matched": matched,
            "best_plot_id": best_plot,
            "match_score": round(best_score, 3),
            "overlap_ratio": round(best_overlap, 3),
            "crosses_boundary": crosses_boundary,
            "candidate_plots": ", ".join(crossing_plots) if crossing_plots else "",
            "num_candidate_plots": len(candidate_scores),
        })

    return pd.DataFrame(results)


def link_gnss_points(gnss_gdf: gpd.GeoDataFrame, buildings_gdf: gpd.GeoDataFrame,
                      cadastral_gdf: gpd.GeoDataFrame):
    """
    Link every GNSS point to its nearest building/plot and flag points
    farther than GNSS_MAX_LINK_DISTANCE_M from anything as misplaced
    outliers.
    """
    if len(gnss_gdf) == 0:
        return pd.DataFrame()

    g_m = to_metric(gnss_gdf)
    b_m = to_metric(buildings_gdf) if len(buildings_gdf) else None
    p_m = to_metric(cadastral_gdf) if len(cadastral_gdf) else None

    rows = []
    for gi, grow in g_m.iterrows():
        gpt = grow.geometry
        point_id = gnss_gdf.loc[gi, "point_id"] if "point_id" in gnss_gdf.columns else str(gi)

        nearest_building_dist = None
        nearest_building_id = None
        if b_m is not None and len(b_m):
            dists = b_m.geometry.distance(gpt)
            j = dists.idxmin()
            nearest_building_dist = dists.loc[j]
            nearest_building_id = buildings_gdf.loc[j, "building_id"] if "building_id" in buildings_gdf.columns else str(j)

        nearest_plot_dist = None
        nearest_plot_id = None
        if p_m is not None and len(p_m):
            dists_p = p_m.geometry.distance(gpt)
            k = dists_p.idxmin()
            nearest_plot_dist = dists_p.loc[k]
            nearest_plot_id = cadastral_gdf.loc[k, "plot_id"] if "plot_id" in cadastral_gdf.columns else str(k)

        best_dist = min([d for d in [nearest_building_dist, nearest_plot_dist] if d is not None], default=None)
        is_misplaced = (best_dist is None) or (best_dist > GNSS_MAX_LINK_DISTANCE_M)

        rows.append({
            "point_id": point_id,
            "nearest_building_id": nearest_building_id,
            "nearest_building_distance_m": round(nearest_building_dist, 1) if nearest_building_dist is not None else None,
            "nearest_plot_id": nearest_plot_id,
            "nearest_plot_distance_m": round(nearest_plot_dist, 1) if nearest_plot_dist is not None else None,
            "is_misplaced": bool(is_misplaced),
        })

    return pd.DataFrame(rows)
