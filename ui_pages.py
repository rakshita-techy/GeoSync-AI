"""
ui_pages.py
Render functions for every sidebar page of GeoSync AI. Each function is
fully self-contained and works against real (synthetic or uploaded) data
-- there are no placeholder pages.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium

import data_gen
import crs_utils
import change_detection
import reports
import db as db_mod
import map_utils
from utils import (
    status_badge, show_error_box, show_info_box,
    STATUS_VERIFIED, STATUS_REVIEW, STATUS_CONFLICT, STATUS_UNMATCHED, STATUS_INVALID,
)


# ------------------------------------------------------------------------
# 1. DASHBOARD
# ------------------------------------------------------------------------
def render_dashboard(kpis, results):
    st.title("🏠 Dashboard")
    st.caption("Live overview of the current integration run.")

    labels = list(kpis.keys())
    values = list(kpis.values())
    cols = st.columns(4)
    for i, (label, value) in enumerate(kpis.items()):
        cols[i % 4].metric(label, value)

    st.divider()
    st.subheader("Processing Workflow")
    steps = ["DATA", "VALIDATION", "HARMONIZATION", "AI MATCHING",
             "CONFLICT DETECTION", "CHANGE DETECTION", "CONFIDENCE",
             "RESOLUTION", "INTEGRATED RECORD"]
    cols2 = st.columns(len(steps))
    for c, s in zip(cols2, steps):
        c.markdown(f"<div style='text-align:center;font-size:11px;font-weight:600;"
                    f"background:#eef2f7;border-radius:6px;padding:8px 2px;'>{s}</div>",
                    unsafe_allow_html=True)

    st.divider()
    st.subheader("Record Status Breakdown")
    confidence_df = results["confidence_df"]
    if len(confidence_df):
        status_counts = confidence_df["status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        color_map = {
            STATUS_VERIFIED: "#2e7d32", STATUS_REVIEW: "#f9a825",
            STATUS_CONFLICT: "#c62828", STATUS_UNMATCHED: "#9e9e9e", STATUS_INVALID: "#000000",
        }
        fig = px.bar(status_counts, x="status", y="count", color="status",
                     color_discrete_map=color_map, text="count")
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Buildings")
        st.plotly_chart(fig, use_container_width=True)
    else:
        show_info_box("No building records yet -- generate or upload data first.")

    st.divider()
    legend_cols = st.columns(5)
    for c, s in zip(legend_cols, [STATUS_VERIFIED, STATUS_REVIEW, STATUS_CONFLICT, STATUS_UNMATCHED, STATUS_INVALID]):
        c.markdown(f"**{status_badge(s)}**")


# ------------------------------------------------------------------------
# 2. DATA UPLOAD & MANAGEMENT
# ------------------------------------------------------------------------
def render_data_upload():
    st.title("📂 Data Upload & Management")
    st.caption("Upload real datasets to replace the synthetic demo layers, or keep using the demo data.")

    colA, colB = st.columns(2)
    with colA:
        if st.button("🔁 Generate Demo Data", use_container_width=True):
            cad, bld, gnss = data_gen.generate_demo_data()
            st.session_state.cadastral_gdf = cad
            st.session_state.buildings_gdf = bld
            st.session_state.gnss_gdf = gnss
            st.session_state.buildings_gdf_v2 = None
            st.session_state.data_source = {"cadastral": "Demo", "buildings": "Demo", "gnss": "Demo"}
            st.success("Demo data (re)generated.")
            st.rerun()
    with colB:
        if st.button("🗑️ Reset Demo Data", use_container_width=True):
            for key in ["cadastral_gdf", "buildings_gdf", "gnss_gdf", "buildings_gdf_v2", "data_source"]:
                st.session_state.pop(key, None)
            st.success("Demo data cleared. It will regenerate automatically.")
            st.rerun()

    st.divider()
    st.subheader("Upload Cadastral Data")
    cad_file = st.file_uploader("Cadastral (GeoJSON or zipped Shapefile)", type=["geojson", "json", "zip"], key="cad_up")
    _handle_vector_upload(cad_file, "cadastral", required_id="plot_id")

    st.subheader("Upload Building Footprints")
    bld_file = st.file_uploader("Buildings (GeoJSON or zipped Shapefile)", type=["geojson", "json", "zip"], key="bld_up")
    _handle_vector_upload(bld_file, "buildings", required_id="building_id")

    st.subheader("Upload GNSS / CORS Survey Points")
    gnss_file = st.file_uploader("GNSS points (CSV with lat/lon columns)", type=["csv"], key="gnss_up")
    if gnss_file is not None:
        try:
            gdf = crs_utils.read_csv_points(gnss_file)
            if "point_id" not in gdf.columns:
                gdf["point_id"] = [f"GNSS-{i+1:03d}" for i in range(len(gdf))]
            st.success(f"Loaded {len(gdf)} GNSS points.")
            st.dataframe(gdf.drop(columns="geometry").head(10), use_container_width=True)
            if st.button("Use this GNSS dataset", key="use_gnss"):
                st.session_state.gnss_gdf = gdf
                st.session_state.setdefault("data_source", {})["gnss"] = "Uploaded"
                st.success("GNSS dataset activated.")
                st.rerun()
        except crs_utils.DatasetLoadError as e:
            show_error_box(str(e))

    st.divider()
    st.subheader("Optional Supplementary Layers")
    st.caption("Municipal GIS layers, utility networks and orthophoto imagery can be attached for reference "
               "(displayed as metadata; not used in the automated matching pipeline in this prototype).")

    opt_col1, opt_col2 = st.columns(2)
    with opt_col1:
        muni_file = st.file_uploader("Municipal / Utility GIS layer (GeoJSON or zip)", type=["geojson", "json", "zip"], key="muni_up")
        if muni_file is not None:
            try:
                gdf = crs_utils.read_vector_upload(muni_file)
                st.success(f"Loaded {len(gdf)} features, geometry type: {gdf.geom_type.mode().iloc[0]}")
                st.session_state.setdefault("optional_layers", {})["municipal"] = gdf
            except crs_utils.DatasetLoadError as e:
                show_error_box(str(e))
    with opt_col2:
        ortho_file = st.file_uploader("Orthophoto (GeoTIFF)", type=["tif", "tiff"], key="ortho_up")
        if ortho_file is not None:
            try:
                import rasterio
                with rasterio.MemoryFile(ortho_file.read()) as memfile:
                    with memfile.open() as src:
                        st.success("GeoTIFF read successfully.")
                        st.write({
                            "width": src.width, "height": src.height,
                            "bands": src.count, "crs": str(src.crs),
                            "bounds": src.bounds,
                        })
            except Exception:
                show_error_box("Unable to read this file. Please upload a valid GeoTIFF orthophoto.")

    st.divider()
    st.subheader("Active Datasets")
    source = st.session_state.get("data_source", {"cadastral": "Demo", "buildings": "Demo", "gnss": "Demo"})
    active = pd.DataFrame([
        {"Layer": "Cadastral", "Source": source.get("cadastral", "Demo"),
         "Features": len(st.session_state.get("cadastral_gdf", []))},
        {"Layer": "Buildings", "Source": source.get("buildings", "Demo"),
         "Features": len(st.session_state.get("buildings_gdf", []))},
        {"Layer": "GNSS", "Source": source.get("gnss", "Demo"),
         "Features": len(st.session_state.get("gnss_gdf", []))},
    ])
    st.table(active)


def _handle_vector_upload(uploaded_file, layer_key, required_id):
    if uploaded_file is None:
        return
    try:
        gdf = crs_utils.read_vector_upload(uploaded_file)
    except crs_utils.DatasetLoadError as e:
        show_error_box(str(e))
        return

    harmonized, report = crs_utils.harmonize_to_working_crs(gdf, layer_key)
    st.write(f"**CRS Report -- {layer_key.title()}**")
    st.table(pd.DataFrame([report]))

    if gdf.crs is None:
        show_error_box("CRS information is missing. Please define the CRS before spatial analysis.")

    if required_id not in harmonized.columns:
        harmonized[required_id] = [f"{layer_key.upper()[:3]}-{i+1:03d}" for i in range(len(harmonized))]
        show_info_box(f"No '{required_id}' column found -- auto-generated identifiers were assigned.")

    st.write(f"Feature count: **{len(harmonized)}** | Geometry type: **{harmonized.geom_type.mode().iloc[0]}**")
    st.dataframe(harmonized.drop(columns="geometry").head(10), use_container_width=True)

    if st.button(f"Use this {layer_key} dataset", key=f"use_{layer_key}"):
        st.session_state[f"{layer_key}_gdf"] = harmonized
        st.session_state.setdefault("data_source", {})[layer_key] = "Uploaded"
        st.success(f"{layer_key.title()} dataset activated.")
        st.rerun()


# ------------------------------------------------------------------------
# 3. INTEGRATED GIS MAP
# ------------------------------------------------------------------------
def render_gis_map(cadastral_gdf, buildings_gdf, gnss_gdf, results):
    st.title("🗺️ Integrated GIS Map")
    st.caption("Cadastral, building and GNSS layers overlaid with pipeline status coloring. Use the layer control to toggle layers.")

    confidence_df = results["confidence_df"]
    status_lookup = dict(zip(confidence_df["building_id"], confidence_df["status"])) if len(confidence_df) else {}

    invalid_ids = set()
    validation_df = results["validation_df"]
    if len(validation_df):
        invalid_ids = set(validation_df.loc[~validation_df["is_valid"], "feature_id"])

    overlap_ids = set()
    cad_overlaps_df = results["cad_overlaps_df"]
    if len(cad_overlaps_df):
        overlap_ids = set(cad_overlaps_df["plot_id_a"]) | set(cad_overlaps_df["plot_id_b"])

    fmap = map_utils.build_integrated_map(
        cadastral_gdf, buildings_gdf, gnss_gdf,
        building_status_lookup=status_lookup,
        cadastral_overlap_ids=overlap_ids,
        invalid_ids=invalid_ids,
    )
    map_utils.add_legend(fmap)
    st_folium(fmap, use_container_width=True, height=560, returned_objects=[])


# ------------------------------------------------------------------------
# 4. AI SPATIAL MATCHING
# ------------------------------------------------------------------------
def render_ai_matching(results):
    st.title("🤖 AI Spatial Matching")
    st.caption("Explainable rule-based scoring -- not a black-box model.")

    st.markdown(
        "**Scoring formula:** `score = 0.70 × overlap_ratio + 0.30 × (1 − normalized_centroid_distance)`\n\n"
        "A building is considered *matched* to the cadastral plot with the highest score, "
        "provided that score clears the match threshold."
    )

    match_df = results["match_df"]
    if not len(match_df):
        show_info_box("No buildings available to match yet.")
        return

    threshold = st.slider("What-if match threshold", 0.0, 1.0, 0.30, 0.05,
                           help="Preview only -- does not change the stored pipeline results.")
    preview_matched = (match_df["match_score"] >= threshold).sum()
    st.write(f"At threshold **{threshold:.2f}**, **{preview_matched} / {len(match_df)}** buildings would match "
             f"(pipeline currently uses threshold 0.30).")

    fig = px.histogram(match_df, x="match_score", nbins=20, title="Distribution of Match Scores")
    fig.add_vline(x=0.30, line_dash="dash", line_color="red", annotation_text="pipeline threshold")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Match Details")
    display_df = match_df.copy()
    display_df["matched"] = display_df["matched"].map({True: "✅ Matched", False: "⚪ Unmatched"})
    st.dataframe(display_df, use_container_width=True)

    st.subheader("GNSS Point Linking")
    gnss_link_df = results["gnss_link_df"]
    if len(gnss_link_df):
        gdisp = gnss_link_df.copy()
        gdisp["is_misplaced"] = gdisp["is_misplaced"].map({True: "❌ Misplaced", False: "✅ OK"})
        st.dataframe(gdisp, use_container_width=True)


# ------------------------------------------------------------------------
# 5. CONFLICT DETECTION
# ------------------------------------------------------------------------
def render_conflict_detection(results):
    st.title("⚠️ Conflict Detection")

    conflict_summary_df = results["conflict_summary_df"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Conflicts", len(conflict_summary_df))
    c2.metric("Cadastral Overlaps", len(results["cad_overlaps_df"]))
    c3.metric("Duplicate Buildings", len(results["duplicate_df"]))
    match_df = results["match_df"]
    crossing = int(match_df["crosses_boundary"].sum()) if len(match_df) else 0
    c4.metric("Boundary-Crossing Buildings", crossing)

    st.divider()
    st.subheader("All Detected Conflicts")
    if len(conflict_summary_df):
        st.dataframe(conflict_summary_df, use_container_width=True)
    else:
        show_info_box("No conflicts detected in the current dataset.")

    with st.expander("🔎 Cadastral Overlap Details"):
        if len(results["cad_overlaps_df"]):
            st.dataframe(results["cad_overlaps_df"], use_container_width=True)
        else:
            st.write("None found.")

    with st.expander("🔎 Duplicate Building Details"):
        if len(results["duplicate_df"]):
            st.dataframe(results["duplicate_df"], use_container_width=True)
        else:
            st.write("None found.")

    with st.expander("🔎 Boundary-Crossing / Outside-Plot Buildings"):
        if len(match_df):
            problem = match_df[(match_df["crosses_boundary"]) | (~match_df["matched"])]
            st.dataframe(problem, use_container_width=True)
        else:
            st.write("None found.")


# ------------------------------------------------------------------------
# 6. TOPOLOGY & DATA VALIDATION
# ------------------------------------------------------------------------
def render_topology_validation(results):
    st.title("🔍 Topology & Data Validation")

    summary = results["validation_summary"]
    c1, c2 = st.columns(2)
    c1.metric("Total Features Checked", summary["total"])
    c2.metric("Invalid Geometries", summary["invalid"])

    st.divider()
    for label, df in [("Cadastral", results["cad_validation"]), ("Buildings", results["bld_validation"])]:
        st.subheader(f"{label} Layer")
        if len(df):
            def _highlight(row):
                return ["background-color: #fdecea" if not row["is_valid"] else "" for _ in row]
            st.dataframe(df.style.apply(_highlight, axis=1), use_container_width=True)
        else:
            show_info_box(f"No {label.lower()} features to validate.")

    csv_bytes = reports.dataframe_to_csv_bytes(results["validation_df"]) if len(results["validation_df"]) else b""
    if csv_bytes:
        st.download_button("⬇️ Download Validation Report (CSV)", csv_bytes, "validation_report.csv", "text/csv")


# ------------------------------------------------------------------------
# 7. CHANGE DETECTION
# ------------------------------------------------------------------------
def render_change_detection(buildings_gdf):
    st.title("🔄 Change Detection")
    st.caption("Compares the current building layer against a simulated newer survey/drone capture.")

    if st.button("🛰️ Simulate New Survey Update"):
        st.session_state.buildings_gdf_v2 = data_gen.simulate_survey_update(buildings_gdf)
        st.success("Simulated updated survey generated (1 removed, 1 extended, 1 new building).")

    v2 = st.session_state.get("buildings_gdf_v2")
    if v2 is None:
        show_info_box("Click 'Simulate New Survey Update' to generate a second epoch for comparison.")
        return

    change_df = change_detection.detect_changes(buildings_gdf, v2)
    if not len(change_df):
        show_info_box("No differences detected.")
        return

    counts = change_df["change_type"].value_counts()
    cols = st.columns(4)
    cols[0].metric("New", int(counts.get("NEW", 0)))
    cols[1].metric("Removed", int(counts.get("REMOVED", 0)))
    cols[2].metric("Geometry Changed", int(counts.get("GEOMETRY CHANGED", 0)))
    cols[3].metric("Unchanged", int(counts.get("UNCHANGED", 0)))

    fig = px.pie(change_df, names="change_type", title="Change Type Breakdown")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Change Details")
    st.dataframe(change_df, use_container_width=True)


# ------------------------------------------------------------------------
# 8. CONFIDENCE ANALYSIS
# ------------------------------------------------------------------------
def render_confidence_analysis(results):
    st.title("📊 Confidence Analysis")

    st.markdown(
        "**Confidence formula (0-100, all weights transparent):**\n\n"
        "`confidence = 100 × (0.30 × geometry_valid + 0.40 × match_score + 0.30 × conflict_free)`"
    )

    confidence_df = results["confidence_df"]
    if not len(confidence_df):
        show_info_box("No confidence scores available yet.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Average Confidence", f"{confidence_df['confidence'].mean():.1f}")
    c2.metric("Highest Confidence", f"{confidence_df['confidence'].max():.1f}")
    c3.metric("Lowest Confidence", f"{confidence_df['confidence'].min():.1f}")

    fig = px.histogram(confidence_df, x="confidence", nbins=20, color="status",
                        title="Confidence Score Distribution")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Per-Building Confidence")
    st.dataframe(confidence_df.sort_values("confidence", ascending=False), use_container_width=True)


# ------------------------------------------------------------------------
# 9. SUGGESTED RESOLUTION
# ------------------------------------------------------------------------
def render_suggested_resolution(results):
    st.title("🛠️ Suggested Resolution")
    st.caption("Rule-based recommendations for each detected issue. A human reviewer should confirm every action.")

    resolution_df = results["resolution_df"]
    if not len(resolution_df):
        show_info_box("No open issues -- nothing requires resolution right now.")
        return

    for issue_type, group in resolution_df.groupby("issue_type"):
        with st.expander(f"{issue_type} ({len(group)})", expanded=False):
            for _, row in group.iterrows():
                st.markdown(f"**{row['entities']}** -- {row['details']}")
                st.write(f"➡️ {row['suggested_resolution']}")
                st.markdown("---")

    csv_bytes = reports.dataframe_to_csv_bytes(resolution_df)
    st.download_button("⬇️ Download Resolution Worklist (CSV)", csv_bytes, "resolution_worklist.csv", "text/csv")


# ------------------------------------------------------------------------
# 10. INTEGRATED LAND RECORDS
# ------------------------------------------------------------------------
def render_integrated_records(cadastral_gdf, buildings_gdf, results):
    st.title("🏘️ Integrated Land Records")
    st.caption("The final harmonized record set, persisted to a local SQLite database.")

    conn = db_mod.get_connection()

    if st.button("🔨 Build / Refresh Integrated Records"):
        db_mod.rebuild_integrated_records(conn, results["confidence_df"], cadastral_gdf, buildings_gdf)
        st.success("Integrated records rebuilt from the latest pipeline output.")

    records_df = db_mod.fetch_integrated_records(conn)
    if not len(records_df):
        show_info_box("No integrated records yet -- click 'Build / Refresh Integrated Records' above.")
        return

    status_filter = st.multiselect("Filter by status", sorted(records_df["status"].unique()),
                                    default=list(records_df["status"].unique()))
    filtered = records_df[records_df["status"].isin(status_filter)]
    st.dataframe(filtered, use_container_width=True)
    st.caption(f"Showing {len(filtered)} of {len(records_df)} records.")


# ------------------------------------------------------------------------
# 11. REPORTS & EXPORT
# ------------------------------------------------------------------------
def render_reports_export(cadastral_gdf, buildings_gdf, gnss_gdf, results, kpis):
    st.title("📄 Reports & Export")

    st.subheader("CSV Exports")
    c1, c2, c3, c4 = st.columns(4)
    if len(results["confidence_df"]):
        c1.download_button("Confidence Scores", reports.dataframe_to_csv_bytes(results["confidence_df"]),
                            "confidence_scores.csv", "text/csv", use_container_width=True)
    if len(results["conflict_summary_df"]):
        c2.download_button("Conflicts", reports.dataframe_to_csv_bytes(results["conflict_summary_df"]),
                            "conflicts.csv", "text/csv", use_container_width=True)
    if len(results["resolution_df"]):
        c3.download_button("Resolutions", reports.dataframe_to_csv_bytes(results["resolution_df"]),
                            "resolutions.csv", "text/csv", use_container_width=True)
    if len(results["validation_df"]):
        c4.download_button("Validation", reports.dataframe_to_csv_bytes(results["validation_df"]),
                            "validation.csv", "text/csv", use_container_width=True)

    st.divider()
    st.subheader("PDF Summary Report")
    if st.button("📄 Generate PDF Report"):
        pdf_bytes = reports.build_pdf_report(
            kpis, results["conflict_summary_df"], results["confidence_df"],
            results["resolution_df"], results["validation_summary"],
        )
        st.session_state["_pdf_report_bytes"] = pdf_bytes
        st.success("PDF report generated.")

    if "_pdf_report_bytes" in st.session_state:
        st.download_button("⬇️ Download PDF Report", st.session_state["_pdf_report_bytes"],
                            "geosync_ai_report.pdf", "application/pdf")


# ------------------------------------------------------------------------
# 12. ABOUT / HELP
# ------------------------------------------------------------------------
def render_about():
    st.title("ℹ️ About / Help")
    st.markdown("""
### GeoSync AI
**Intelligent Urban Land Data Integration Platform**

GeoSync AI is an academic / hackathon-style **prototype** that demonstrates how
multi-source geospatial datasets used in urban land administration -- drone imagery,
orthorectified imagery, DSM/DTM, cadastral maps, revenue records, municipal GIS
layers, utility networks, ground-truth data, GNSS/CORS survey points and building
footprints -- can be automatically integrated, validated, matched and harmonized.

> ⚠️ **Disclaimer:** This is a prototype for demonstration purposes only. It does
> **not** provide government-certified positional accuracy and it does **not**
> perform legal ownership verification. All matching, conflict detection and
> confidence scoring is done with transparent, **rule-based spatial algorithms**
> (overlap ratios, centroid distances, IoU, geometry validity) -- not deep learning.

#### Pipeline
`DATA → CRS HARMONIZATION → VALIDATION → AI MATCHING → CONFLICT DETECTION →
TOPOLOGY VALIDATION → CHANGE DETECTION → CONFIDENCE SCORING → SUGGESTED
RESOLUTION → INTEGRATED LAND RECORD → REPORT / EXPORT`

#### Page Guide
- **Dashboard** -- live KPIs and status overview
- **Data Upload & Management** -- bring your own GeoJSON/Shapefile/CSV datasets
- **Integrated GIS Map** -- layered Folium map colored by pipeline status
- **AI Spatial Matching** -- explainable building-to-plot scoring engine
- **Conflict Detection** -- overlaps, duplicates, boundary-crossing buildings
- **Topology & Data Validation** -- geometry validity checks (incl. bowtie detection)
- **Change Detection** -- compares two survey epochs of the buildings layer
- **Confidence Analysis** -- transparent weighted confidence scoring
- **Suggested Resolution** -- rule-based next-step recommendations
- **Integrated Land Records** -- the harmonized record set (SQLite-backed)
- **Reports & Export** -- CSV and PDF exports

#### Technology Stack
Streamlit · Folium / streamlit-folium · GeoPandas · Shapely · PyProj · Rasterio ·
Pandas · NumPy · Plotly · SQLite · ReportLab

#### Status Legend
🟢 Verified &nbsp;&nbsp; 🟡 Review Required &nbsp;&nbsp; 🔴 Conflict &nbsp;&nbsp;
⚪ Unmatched &nbsp;&nbsp; ❌ Invalid
""")
