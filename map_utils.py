"""
map_utils.py
Builds the interactive Folium map used on the Integrated GIS Map page
(and, in a simplified form, elsewhere). Cadastral plots, buildings and
GNSS points are each rendered as toggleable layers; buildings can
optionally be colored by their pipeline status.
"""

import folium
from utils import STATUS_ICON, STATUS_VERIFIED, STATUS_REVIEW, STATUS_CONFLICT, STATUS_UNMATCHED, STATUS_INVALID
from utils import DEMO_CENTER_LAT, DEMO_CENTER_LON

STATUS_COLOR = {
    STATUS_VERIFIED: "#2e7d32",
    STATUS_REVIEW: "#f9a825",
    STATUS_CONFLICT: "#c62828",
    STATUS_UNMATCHED: "#9e9e9e",
    STATUS_INVALID: "#000000",
}


def _map_center(cadastral_gdf, buildings_gdf, gnss_gdf):
    for gdf in (cadastral_gdf, buildings_gdf, gnss_gdf):
        if gdf is not None and len(gdf):
            c = gdf.unary_union.centroid
            return [c.y, c.x]
    return [DEMO_CENTER_LAT, DEMO_CENTER_LON]


def build_integrated_map(cadastral_gdf, buildings_gdf, gnss_gdf,
                          building_status_lookup=None,
                          cadastral_overlap_ids=None,
                          invalid_ids=None):
    """
    building_status_lookup: dict building_id -> status string (for coloring)
    cadastral_overlap_ids: set of plot_ids involved in an overlap conflict
    invalid_ids: set of feature ids (building or plot) with invalid geometry
    """
    building_status_lookup = building_status_lookup or {}
    cadastral_overlap_ids = cadastral_overlap_ids or set()
    invalid_ids = invalid_ids or set()

    center = _map_center(cadastral_gdf, buildings_gdf, gnss_gdf)
    fmap = folium.Map(location=center, zoom_start=17, tiles="OpenStreetMap", control_scale=True)

    # --- Cadastral layer ---
    if cadastral_gdf is not None and len(cadastral_gdf):
        cad_layer = folium.FeatureGroup(name="🗺️ Cadastral Plots", show=True)
        for _, row in cadastral_gdf.iterrows():
            plot_id = row.get("plot_id", "")
            is_invalid = plot_id in invalid_ids
            is_overlap = plot_id in cadastral_overlap_ids
            color = "#000000" if is_invalid else ("#c62828" if is_overlap else "#1565c0")
            tooltip = (f"<b>{plot_id}</b><br>Owner: {row.get('owner_name','')}<br>"
                       f"Land use: {row.get('land_use','')}<br>Survey No: {row.get('survey_no','')}")
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda x, color=color: {
                    "fillColor": color, "color": color, "weight": 2, "fillOpacity": 0.15
                },
                tooltip=tooltip,
            ).add_to(cad_layer)
        cad_layer.add_to(fmap)

    # --- Buildings layer ---
    if buildings_gdf is not None and len(buildings_gdf):
        bld_layer = folium.FeatureGroup(name="🏢 Buildings", show=True)
        for _, row in buildings_gdf.iterrows():
            bld_id = row.get("building_id", "")
            status = building_status_lookup.get(bld_id)
            is_invalid = bld_id in invalid_ids
            if is_invalid:
                color = STATUS_COLOR[STATUS_INVALID]
            elif status:
                color = STATUS_COLOR.get(status, "#616161")
            else:
                color = "#616161"
            tooltip = (f"<b>{bld_id}</b><br>Type: {row.get('building_type','')}<br>"
                       f"Floors: {row.get('floors','')}<br>Source: {row.get('source','')}"
                       f"{'<br>Status: ' + status if status else ''}")
            try:
                geo_iface = row.geometry.__geo_interface__
            except Exception:
                continue
            folium.GeoJson(
                geo_iface,
                style_function=lambda x, color=color: {
                    "fillColor": color, "color": color, "weight": 2, "fillOpacity": 0.55
                },
                tooltip=tooltip,
            ).add_to(bld_layer)
        bld_layer.add_to(fmap)

    # --- GNSS layer ---
    if gnss_gdf is not None and len(gnss_gdf):
        gnss_layer = folium.FeatureGroup(name="📡 GNSS / CORS Points", show=True)
        for _, row in gnss_gdf.iterrows():
            pt = row.geometry
            tooltip = (f"<b>{row.get('point_id','')}</b><br>Type: {row.get('point_type','')}<br>"
                       f"Accuracy: {row.get('accuracy_cm','')} cm")
            folium.CircleMarker(
                location=[pt.y, pt.x],
                radius=5,
                color="#6a1b9a",
                fill=True,
                fill_color="#ce93d8",
                fill_opacity=0.9,
                tooltip=tooltip,
            ).add_to(gnss_layer)
        gnss_layer.add_to(fmap)

    folium.LayerControl(collapsed=False).add_to(fmap)
    return fmap


def add_legend(fmap):
    legend_html = """
    <div style="position: fixed; bottom: 20px; left: 20px; z-index: 9999;
                background: white; padding: 10px 14px; border-radius: 8px;
                box-shadow: 0 1px 6px rgba(0,0,0,0.3); font-size: 12px;">
      <b>Status Legend</b><br>
      <span style="color:#2e7d32;">&#9679;</span> Verified &nbsp;
      <span style="color:#f9a825;">&#9679;</span> Review Required<br>
      <span style="color:#c62828;">&#9679;</span> Conflict &nbsp;
      <span style="color:#9e9e9e;">&#9679;</span> Unmatched<br>
      <span style="color:#000000;">&#9679;</span> Invalid Geometry
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(legend_html))
    return fmap
