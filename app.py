"""
app.py
GeoSync AI -- Intelligent Urban Land Data Integration Platform
Main Streamlit entry point: sets up the page, ensures demo data exists,
runs the processing pipeline once per rerun, and routes to the selected
sidebar page.

Run with:
    streamlit run app.py
"""

import streamlit as st

import data_gen
import pipeline
import ui_pages

st.set_page_config(
    page_title="GeoSync AI",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def ensure_demo_data():
    """Generate the synthetic demo dataset on first run if nothing is loaded yet."""
    if "cadastral_gdf" not in st.session_state or "buildings_gdf" not in st.session_state \
            or "gnss_gdf" not in st.session_state:
        cad, bld, gnss = data_gen.generate_demo_data()
        st.session_state.cadastral_gdf = cad
        st.session_state.buildings_gdf = bld
        st.session_state.gnss_gdf = gnss
        st.session_state.buildings_gdf_v2 = None
        st.session_state.data_source = {"cadastral": "Demo", "buildings": "Demo", "gnss": "Demo"}


def main():
    ensure_demo_data()

    st.sidebar.title("🗺️ GeoSync AI")
    st.sidebar.caption("Intelligent Urban Land Data Integration Platform")
    st.sidebar.divider()

    pages = [
        "🏠 Dashboard",
        "📂 Data Upload & Management",
        "🗺️ Integrated GIS Map",
        "🤖 AI Spatial Matching",
        "⚠️ Conflict Detection",
        "🔍 Topology & Data Validation",
        "🔄 Change Detection",
        "📊 Confidence Analysis",
        "🛠️ Suggested Resolution",
        "🏘️ Integrated Land Records",
        "📄 Reports & Export",
        "ℹ️ About / Help",
    ]
    choice = st.sidebar.radio("Navigate", pages, label_visibility="collapsed")

    st.sidebar.divider()
    st.sidebar.caption(
        "Prototype only -- not a production government system. "
        "No government-certified accuracy or legal ownership verification is provided."
    )

    cadastral_gdf = st.session_state.cadastral_gdf
    buildings_gdf = st.session_state.buildings_gdf
    gnss_gdf = st.session_state.gnss_gdf

    # Run the full processing pipeline once per page load, shared by all pages.
    results = pipeline.run_pipeline(cadastral_gdf, buildings_gdf, gnss_gdf)
    kpis = pipeline.compute_kpis(cadastral_gdf, buildings_gdf, gnss_gdf, results)

    if choice == "🏠 Dashboard":
        ui_pages.render_dashboard(kpis, results)
    elif choice == "📂 Data Upload & Management":
        ui_pages.render_data_upload()
    elif choice == "🗺️ Integrated GIS Map":
        ui_pages.render_gis_map(cadastral_gdf, buildings_gdf, gnss_gdf, results)
    elif choice == "🤖 AI Spatial Matching":
        ui_pages.render_ai_matching(results)
    elif choice == "⚠️ Conflict Detection":
        ui_pages.render_conflict_detection(results)
    elif choice == "🔍 Topology & Data Validation":
        ui_pages.render_topology_validation(results)
    elif choice == "🔄 Change Detection":
        ui_pages.render_change_detection(buildings_gdf)
    elif choice == "📊 Confidence Analysis":
        ui_pages.render_confidence_analysis(results)
    elif choice == "🛠️ Suggested Resolution":
        ui_pages.render_suggested_resolution(results)
    elif choice == "🏘️ Integrated Land Records":
        ui_pages.render_integrated_records(cadastral_gdf, buildings_gdf, results)
    elif choice == "📄 Reports & Export":
        ui_pages.render_reports_export(cadastral_gdf, buildings_gdf, gnss_gdf, results, kpis)
    elif choice == "ℹ️ About / Help":
        ui_pages.render_about()


if __name__ == "__main__":
    main()
