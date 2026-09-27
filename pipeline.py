"""
pipeline.py
Runs the full GeoSync AI processing pipeline (validation -> matching ->
conflict detection -> confidence scoring -> suggested resolution) in one
place, so every page reads from the same consistent set of results.
"""

import topology
import matching
import conflicts as conflicts_mod
import confidence as confidence_mod
import resolution as resolution_mod


def run_pipeline(cadastral_gdf, buildings_gdf, gnss_gdf):
    results = {}

    # 1. Topology / geometry validation
    cad_validation = topology.validate_geometries(cadastral_gdf, "plot_id", "Cadastral")
    bld_validation = topology.validate_geometries(buildings_gdf, "building_id", "Buildings")
    validation_df, validation_summary = topology.validation_summary(cad_validation, bld_validation)
    results["cad_validation"] = cad_validation
    results["bld_validation"] = bld_validation
    results["validation_df"] = validation_df
    results["validation_summary"] = validation_summary

    # 2. AI-assisted spatial matching (buildings <-> cadastral plots)
    match_df = matching.match_buildings_to_plots(buildings_gdf, cadastral_gdf)
    results["match_df"] = match_df

    # 3. GNSS point linking
    gnss_link_df = matching.link_gnss_points(gnss_gdf, buildings_gdf, cadastral_gdf)
    results["gnss_link_df"] = gnss_link_df

    # 4. Conflict detection
    cad_overlaps_df = conflicts_mod.detect_cadastral_overlaps(cadastral_gdf)
    duplicate_df = conflicts_mod.detect_duplicate_buildings(buildings_gdf)
    conflict_summary_df = conflicts_mod.build_conflict_summary(cad_overlaps_df, duplicate_df, match_df)
    results["cad_overlaps_df"] = cad_overlaps_df
    results["duplicate_df"] = duplicate_df
    results["conflict_summary_df"] = conflict_summary_df

    # 5. Confidence scoring
    conflict_entities = confidence_mod.conflict_entity_set(conflict_summary_df)
    confidence_df = confidence_mod.compute_confidence(match_df, bld_validation, conflict_entities)
    results["conflict_entities"] = conflict_entities
    results["confidence_df"] = confidence_df

    # 6. Suggested resolution worklist
    resolution_df = resolution_mod.build_resolution_table(conflict_summary_df, validation_df, gnss_link_df)
    results["resolution_df"] = resolution_df

    return results


def compute_kpis(cadastral_gdf, buildings_gdf, gnss_gdf, results):
    match_df = results["match_df"]
    confidence_df = results["confidence_df"]
    validation_df = results["validation_df"]

    total_plots = len(cadastral_gdf) if cadastral_gdf is not None else 0
    total_buildings = len(buildings_gdf) if buildings_gdf is not None else 0
    total_gnss = len(gnss_gdf) if gnss_gdf is not None else 0

    matched = int(match_df["matched"].sum()) if len(match_df) else 0
    unmatched = total_buildings - matched

    conflicts_count = len(results["conflict_summary_df"]) if results.get("conflict_summary_df") is not None else 0
    invalid_geoms = results["validation_summary"]["invalid"] if results.get("validation_summary") else 0

    new_changed = None  # populated by change-detection page when it has run

    verified = int((confidence_df["status"] == "VERIFIED").sum()) if len(confidence_df) else 0
    review = int((confidence_df["status"] == "REVIEW REQUIRED").sum()) if len(confidence_df) else 0
    avg_conf = round(confidence_df["confidence"].mean(), 1) if len(confidence_df) else 0.0

    return {
        "Total Cadastral Plots": total_plots,
        "Total Buildings": total_buildings,
        "Total GNSS Points": total_gnss,
        "Matched Buildings": matched,
        "Unmatched Buildings": unmatched,
        "Conflicts": conflicts_count,
        "Invalid Geometries": invalid_geoms,
        "Verified Records": verified,
        "Records Requiring Review": review,
        "Average Confidence": avg_conf,
    }
