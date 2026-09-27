# GeoSync AI
**Intelligent Urban Land Data Integration Platform**

An AI-assisted, rule-based prototype demonstrating automated integration of
multi-source geospatial datasets (drone imagery, ORI, DSM/DTM, cadastral
maps, municipal GIS layers, utility networks, GNSS/CORS survey points and
building footprints) for urban land administration.

> ⚠️ **This is an academic / hackathon prototype, NOT a production
> government system.** It does not claim government-certified positional
> accuracy or legal ownership verification. All "AI" matching, conflict
> detection and confidence scoring is done with transparent, explainable,
> rule-based spatial algorithms (overlap ratios, IoU, centroid distances,
> geometry validity) -- not deep learning.

## Quick Start

```bash
# 1. Create and activate a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

The app opens in your browser (usually http://localhost:8501). Synthetic
demo data (17 cadastral plots, 18 buildings, 16 GNSS points, with
intentionally embedded spatial defects) is generated automatically on
first launch -- no upload is required to explore every page.

## Project Structure

```
geosync_ai/
├── app.py                # Streamlit entry point / page router
├── ui_pages.py            # All 12 page render functions
├── pipeline.py            # Orchestrates validation -> matching -> conflicts -> confidence -> resolution
├── data_gen.py            # Synthetic demo data generator (with embedded defects)
├── crs_utils.py           # CRS detection/harmonization + safe file readers
├── topology.py            # Geometry validity / topology checks
├── matching.py             # Explainable rule-based spatial matching engine
├── conflicts.py            # Cadastral overlap / duplicate / boundary-crossing detection
├── change_detection.py    # Two-epoch building layer comparison
├── confidence.py           # Weighted confidence scoring + status classification
├── resolution.py           # Suggested-resolution lookup/table builder
├── db.py                   # SQLite persistence for Integrated Land Records
├── reports.py               # CSV / PDF (ReportLab) report generation
├── map_utils.py             # Folium interactive map builder
├── utils.py                  # Shared constants, thresholds, status helpers
├── requirements.txt
└── README.md
```

## Application Pages

1. 🏠 Dashboard -- live KPIs, workflow diagram, status breakdown
2. 📂 Data Upload & Management -- upload your own GeoJSON/Shapefile/CSV data
3. 🗺️ Integrated GIS Map -- interactive Folium map colored by status
4. 🤖 AI Spatial Matching -- explainable building-to-plot scoring
5. ⚠️ Conflict Detection -- overlaps, duplicates, boundary-crossing buildings
6. 🔍 Topology & Data Validation -- geometry validity (incl. bowtie detection)
7. 🔄 Change Detection -- compares two simulated survey epochs
8. 📊 Confidence Analysis -- transparent weighted confidence scoring
9. 🛠️ Suggested Resolution -- rule-based next-step recommendations
10. 🏘️ Integrated Land Records -- final harmonized record set (SQLite-backed)
11. 📄 Reports & Export -- CSV and PDF exports
12. ℹ️ About / Help -- project overview, disclaimer, page guide

## Embedded Demo Defects

The synthetic dataset intentionally contains six detectable issues so every
page has something real to show:

1. One cadastral polygon overlap (PLOT-003 / PLOT-004)
2. One building outside all cadastral plots (BLD-015)
3. One building crossing two cadastral plots (BLD-016)
4. One duplicate building (BLD-017 duplicates BLD-001)
5. One invalid bowtie (self-intersecting) polygon (BLD-018)
6. One deliberately misplaced GNSS point (GNSS-016)

## Notes

- No API keys or paid services are required; everything runs fully offline
  once dependencies are installed.
- The SQLite database file (`geosync_ai.db`) is created automatically in the
  working directory the first time you click "Build / Refresh Integrated
  Records".
- Uploaded shapefiles must be provided as a single `.zip` archive containing
  the `.shp`, `.shx`, `.dbf` (and ideally `.prj`) files.
