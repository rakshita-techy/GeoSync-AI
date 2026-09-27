"""
data_gen.py
Generates a fully synthetic (no real personal data) demo dataset for
GeoSync AI: 17 cadastral plots, 18 building footprints and 16 GNSS
points, laid out on a small grid near Bengaluru.

The dataset intentionally contains exactly these detectable defects:
  1. One cadastral polygon overlap        (PLOT-003 overlaps PLOT-004)
  2. One building outside all plots       (BLD-015)
  3. One building crossing two plots      (BLD-016, spans PLOT-016/PLOT-017)
  4. One duplicate building                (BLD-017 duplicates BLD-001)
  5. One invalid bowtie polygon            (BLD-018, self-intersecting)
  6. One deliberately misplaced GNSS point (GNSS-016)
"""

import random
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon, Point

from utils import DEMO_CENTER_LAT, DEMO_CENTER_LON, WORKING_CRS_GEO

RANDOM_SEED = 42

LAND_USES = ["Residential", "Commercial", "Mixed Use"]
BUILDING_TYPES = ["Residential", "Commercial", "Institutional"]
BUILDING_SOURCES = ["Drone Imagery", "Municipal GIS Layer", "Orthorectified Imagery (ORI)"]
GNSS_TYPES = ["Control Point", "Check Point"]

# Grid geometry (degrees)
DX = 0.0014       # plot width
DY = 0.0011       # plot height
GAP = 0.00035      # street gap between plots
COLS = 5
ROWS = 4


def _cell_origin(r, c):
    x0 = DEMO_CENTER_LON + c * (DX + GAP)
    y0 = DEMO_CENTER_LAT + r * (DY + GAP)
    return x0, y0


def _rect(x0, y0, w, h):
    return Polygon([(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h), (x0, y0)])


def generate_demo_data(seed: int = RANDOM_SEED):
    """Return (cadastral_gdf, buildings_gdf, gnss_gdf) with embedded defects."""
    rng = random.Random(seed)

    # ------------------------------------------------------------------
    # 1. CADASTRAL PLOTS (17 total)
    # ------------------------------------------------------------------
    cells = [(r, c) for r in range(ROWS) for c in range(COLS)]  # 20 cells
    used_cells = cells[:17]  # take 17 of the 20

    plot_records = []
    plot_geoms = []
    for i, (r, c) in enumerate(used_cells):
        x0, y0 = _cell_origin(r, c)
        geom = _rect(x0, y0, DX, DY)
        plot_id = f"PLOT-{i+1:03d}"
        plot_records.append({
            "plot_id": plot_id,
            "survey_no": f"SY/{100+i}",
            "owner_name": f"Registered Owner RO-{i+1:03d}",
            "land_use": LAND_USES[i % len(LAND_USES)],
        })
        plot_geoms.append(geom)

    # --- Defect 1: cadastral polygon overlap ---
    # Shift PLOT-003 (index 2) to the right so it substantially overlaps PLOT-004 (index 3)
    r2, c2 = used_cells[2]
    x0_2, y0_2 = _cell_origin(r2, c2)
    overlap_shift = 0.65 * (DX + GAP)
    plot_geoms[2] = _rect(x0_2 + overlap_shift, y0_2, DX, DY)

    cadastral_gdf = gpd.GeoDataFrame(plot_records, geometry=plot_geoms, crs=WORKING_CRS_GEO)

    # ------------------------------------------------------------------
    # 2. BUILDING FOOTPRINTS (18 total)
    # ------------------------------------------------------------------
    building_records = []
    building_geoms = []

    # 14 "normal" buildings, correctly matched inside a plot each.
    # Skip index 2 (the overlapping plot) and indices 15, 16 (reserved for
    # the crossing-boundary defect below).
    normal_plot_indices = [i for i in range(17) if i not in (2, 15, 16)][:14]

    for j, idx in enumerate(normal_plot_indices):
        r, c = used_cells[idx]
        x0, y0 = _cell_origin(r, c)
        bw, bh = DX * 0.55, DY * 0.55
        bx0 = x0 + DX * 0.2
        by0 = y0 + DY * 0.2
        geom = _rect(bx0, by0, bw, bh)
        bld_id = f"BLD-{j+1:03d}"
        building_records.append({
            "building_id": bld_id,
            "building_type": BUILDING_TYPES[j % len(BUILDING_TYPES)],
            "floors": rng.choice([1, 2, 2, 3]),
            "source": BUILDING_SOURCES[j % len(BUILDING_SOURCES)],
        })
        building_geoms.append(geom)

    # --- Defect 2: building outside all cadastral plots ---
    outside_x0 = DEMO_CENTER_LON - 0.010
    outside_y0 = DEMO_CENTER_LAT - 0.008
    building_records.append({
        "building_id": "BLD-015",
        "building_type": "Residential",
        "floors": 1,
        "source": "Drone Imagery",
    })
    building_geoms.append(_rect(outside_x0, outside_y0, DX * 0.5, DY * 0.5))

    # --- Defect 3: building crossing two cadastral plots (PLOT-016 / PLOT-017) ---
    r15, c15 = used_cells[15]
    x0_15, y0_15 = _cell_origin(r15, c15)
    cross_x0 = x0_15 + DX * 0.55
    cross_y0 = y0_15 + DY * 0.2
    cross_w = (DX + GAP) * 0.9
    cross_h = DY * 0.55
    building_records.append({
        "building_id": "BLD-016",
        "building_type": "Commercial",
        "floors": 2,
        "source": "Municipal GIS Layer",
    })
    building_geoms.append(_rect(cross_x0, cross_y0, cross_w, cross_h))

    # --- Defect 4: duplicate building (exact copy of BLD-001) ---
    dup_geom = building_geoms[0]
    building_records.append({
        "building_id": "BLD-017",
        "building_type": building_records[0]["building_type"],
        "floors": building_records[0]["floors"],
        "source": "Orthorectified Imagery (ORI)",
    })
    building_geoms.append(dup_geom)

    # --- Defect 5: invalid bowtie (self-intersecting) polygon ---
    r16, c16 = used_cells[16]
    x0_16, y0_16 = _cell_origin(r16, c16)
    bw, bh = DX * 0.6, DY * 0.6
    bx0 = x0_16 + DX * 0.15
    by0 = y0_16 + DY * 0.15
    bowtie = Polygon([
        (bx0, by0),
        (bx0 + bw, by0 + bh),
        (bx0 + bw, by0),
        (bx0, by0 + bh),
        (bx0, by0),
    ])
    building_records.append({
        "building_id": "BLD-018",
        "building_type": "Residential",
        "floors": 1,
        "source": "Drone Imagery",
    })
    building_geoms.append(bowtie)

    buildings_gdf = gpd.GeoDataFrame(building_records, geometry=building_geoms, crs=WORKING_CRS_GEO)

    # ------------------------------------------------------------------
    # 3. GNSS / CORS SURVEY POINTS (16 total)
    # ------------------------------------------------------------------
    gnss_records = []
    gnss_geoms = []

    # 15 good points near the centroid of the first 15 buildings
    # (the 14 normal buildings + the duplicate, which is geometrically identical to BLD-001)
    good_source_geoms = building_geoms[:14] + [dup_geom]
    for k, geom in enumerate(good_source_geoms):
        c = geom.centroid
        jitter_x = rng.uniform(-0.00008, 0.00008)
        jitter_y = rng.uniform(-0.00008, 0.00008)
        gnss_id = f"GNSS-{k+1:03d}"
        gnss_records.append({
            "point_id": gnss_id,
            "point_type": GNSS_TYPES[k % len(GNSS_TYPES)],
            "accuracy_cm": round(rng.uniform(1.5, 4.5), 1),
        })
        gnss_geoms.append(Point(c.x + jitter_x, c.y + jitter_y))

    # --- Defect 6: deliberately misplaced GNSS point, far from everything ---
    gnss_records.append({
        "point_id": "GNSS-016",
        "point_type": "Check Point",
        "accuracy_cm": 3.2,
    })
    gnss_geoms.append(Point(DEMO_CENTER_LON + 0.02, DEMO_CENTER_LAT - 0.015))

    gnss_gdf = gpd.GeoDataFrame(gnss_records, geometry=gnss_geoms, crs=WORKING_CRS_GEO)

    return cadastral_gdf, buildings_gdf, gnss_gdf


def simulate_survey_update(buildings_gdf: gpd.GeoDataFrame, seed: int = 7):
    """
    Produce a second-epoch ("current survey") version of the buildings layer
    for the Change Detection page: one building removed, one new building
    added, and one existing building's footprint shifted/extended.
    Returns a new GeoDataFrame (does not mutate the input).
    """
    rng = random.Random(seed)
    gdf = buildings_gdf.copy(deep=True)

    # 1. Remove a building (simulate demolition) -- drop BLD-009 if present
    gdf = gdf[gdf["building_id"] != "BLD-009"].reset_index(drop=True)

    # 2. Shift/extend an existing footprint slightly (simulate a verified extension) -- BLD-002
    idx = gdf.index[gdf["building_id"] == "BLD-002"]
    if len(idx) > 0:
        i = idx[0]
        geom = gdf.at[i, "geometry"]
        minx, miny, maxx, maxy = geom.bounds
        extended = Polygon([
            (minx, miny), (maxx + 0.0004, miny),
            (maxx + 0.0004, maxy), (minx, maxy), (minx, miny)
        ])
        gdf.at[i, "geometry"] = extended

    # 3. Add a brand-new building (simulate new construction)
    new_x0 = DEMO_CENTER_LON + 0.006
    new_y0 = DEMO_CENTER_LAT + 0.006
    new_geom = _rect(new_x0, new_y0, DX * 0.5, DY * 0.5)
    new_row = pd.DataFrame([{
        "building_id": "BLD-019",
        "building_type": "Residential",
        "floors": 1,
        "source": "Drone Imagery",
        "geometry": new_geom,
    }])
    new_gdf = gpd.GeoDataFrame(new_row, geometry="geometry", crs=gdf.crs)
    gdf = pd.concat([gdf, new_gdf], ignore_index=True)
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=buildings_gdf.crs)
    return gdf
