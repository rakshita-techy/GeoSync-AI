"""
resolution.py
Maps each detected issue type to a human-readable suggested resolution
workflow. Purely rule-based (a lookup + light templating) -- this module
never claims legal or ownership determinations; it only proposes the next
GIS/field-verification step for a human reviewer.
"""

RESOLUTION_LOOKUP = {
    "Cadastral Overlap": (
        "Two cadastral boundaries overlap. Recommend re-verifying the shared "
        "boundary against GNSS/CORS control points and the original survey (FMB) "
        "sketch, then correcting the digitized boundary of the plot with lower "
        "positional confidence."
    ),
    "Duplicate Building": (
        "Two building footprints are near-identical. Recommend merging the "
        "duplicate records, retaining the one derived from the most recent / "
        "highest-resolution source (e.g. drone orthophoto over legacy GIS layer)."
    ),
    "Building Crosses Boundary": (
        "This building footprint spans two cadastral parcels. Recommend a field "
        "verification visit to confirm actual ownership/usage split, and updating "
        "either the parcel boundary or the building attribution accordingly."
    ),
    "Building Outside All Plots": (
        "This building does not fall inside any known cadastral parcel. Recommend "
        "checking for an unmapped/informal parcel, a cadastral survey gap, or a "
        "digitization offset, and scheduling ground verification."
    ),
    "Invalid Geometry": (
        "This feature has an invalid (e.g. self-intersecting / bowtie) geometry. "
        "Recommend re-digitizing the polygon from source imagery, or applying an "
        "automated geometry-repair tool and re-validating the topology."
    ),
    "Misplaced GNSS Point": (
        "This GNSS observation lies far from any known building or parcel. "
        "Recommend flagging the reading as a potential outlier and re-surveying "
        "the control point in the field."
    ),
    "Unmatched Building": (
        "This building could not be confidently matched to any cadastral plot. "
        "Recommend manual review against municipal GIS and revenue records."
    ),
}

DEFAULT_RESOLUTION = (
    "No automatic recommendation available for this issue type. Recommend manual "
    "GIS review."
)


def suggest_resolution(issue_type: str) -> str:
    return RESOLUTION_LOOKUP.get(issue_type, DEFAULT_RESOLUTION)


def build_resolution_table(conflict_summary_df, validation_df, gnss_link_df):
    """Combine every open issue across modules into one resolution worklist."""
    import pandas as pd
    rows = []

    if conflict_summary_df is not None:
        for _, r in conflict_summary_df.iterrows():
            rows.append({
                "issue_type": r["conflict_type"],
                "entities": r["entities"],
                "details": r["details"],
                "suggested_resolution": suggest_resolution(r["conflict_type"]),
            })

    if validation_df is not None:
        invalid_rows = validation_df[~validation_df["is_valid"]]
        for _, r in invalid_rows.iterrows():
            rows.append({
                "issue_type": "Invalid Geometry",
                "entities": f"{r['layer']}: {r['feature_id']}",
                "details": r["issue"],
                "suggested_resolution": suggest_resolution("Invalid Geometry"),
            })

    if gnss_link_df is not None and len(gnss_link_df):
        misplaced = gnss_link_df[gnss_link_df["is_misplaced"]]
        for _, r in misplaced.iterrows():
            rows.append({
                "issue_type": "Misplaced GNSS Point",
                "entities": r["point_id"],
                "details": f"Nearest feature is {r['nearest_building_distance_m']}m away (building) "
                           f"/ {r['nearest_plot_distance_m']}m (plot)",
                "suggested_resolution": suggest_resolution("Misplaced GNSS Point"),
            })

    return pd.DataFrame(rows, columns=["issue_type", "entities", "details", "suggested_resolution"])
