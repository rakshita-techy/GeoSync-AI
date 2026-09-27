"""
crs_utils.py
CRS detection / harmonization helpers and safe (never-crash) file readers
for uploaded cadastral / building / GNSS datasets.
"""

import os
import tempfile
import zipfile

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from utils import WORKING_CRS_GEO


class DatasetLoadError(Exception):
    """Raised for any problem reading/parsing an uploaded dataset."""
    pass


def read_vector_upload(uploaded_file):
    """
    Safely read an uploaded GeoJSON or zipped Shapefile into a GeoDataFrame.
    Never raises a raw traceback to the caller -- raises DatasetLoadError
    with a friendly message instead.
    """
    name = uploaded_file.name.lower()
    try:
        if name.endswith(".geojson") or name.endswith(".json"):
            gdf = gpd.read_file(uploaded_file)
        elif name.endswith(".zip"):
            with tempfile.TemporaryDirectory() as tmpdir:
                zip_path = os.path.join(tmpdir, "upload.zip")
                with open(zip_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(tmpdir)
                shp_files = [f for f in os.listdir(tmpdir) if f.lower().endswith(".shp")]
                if not shp_files:
                    raise DatasetLoadError(
                        "The uploaded zip file does not contain a .shp shapefile."
                    )
                gdf = gpd.read_file(os.path.join(tmpdir, shp_files[0]))
        elif name.endswith(".shp"):
            raise DatasetLoadError(
                "Please upload the shapefile as a single .zip archive "
                "containing the .shp, .shx, .dbf (and .prj) files."
            )
        else:
            raise DatasetLoadError(
                "Unsupported file type. Please upload a valid GeoJSON (.geojson) "
                "or a zipped Shapefile (.zip)."
            )
    except DatasetLoadError:
        raise
    except Exception:
        raise DatasetLoadError(
            "Unable to read this file. Please upload a valid GeoJSON or Shapefile."
        )

    if gdf is None or len(gdf) == 0:
        raise DatasetLoadError("The uploaded file was read but contains no features.")

    return gdf


def read_csv_points(uploaded_file, lat_col=None, lon_col=None):
    """
    Safely read a CSV of GNSS points into a GeoDataFrame (assumed EPSG:4326
    unless the caller specifies otherwise). Auto-detects common lat/lon
    column names if not provided.
    """
    try:
        df = pd.read_csv(uploaded_file)
    except Exception:
        raise DatasetLoadError(
            "Unable to read this CSV file. Please check the file is comma-separated "
            "and not corrupted."
        )

    if df.empty:
        raise DatasetLoadError("The uploaded CSV file contains no rows.")

    candidates_lat = ["lat", "latitude", "y"]
    candidates_lon = ["lon", "lng", "longitude", "x"]
    cols_lower = {c.lower(): c for c in df.columns}

    if lat_col is None:
        for c in candidates_lat:
            if c in cols_lower:
                lat_col = cols_lower[c]
                break
    if lon_col is None:
        for c in candidates_lon:
            if c in cols_lower:
                lon_col = cols_lower[c]
                break

    if lat_col is None or lon_col is None:
        raise DatasetLoadError(
            "Could not find latitude/longitude columns in the CSV. "
            "Expected column names such as 'lat'/'lon' or 'latitude'/'longitude'."
        )

    try:
        geometry = [Point(xy) for xy in zip(df[lon_col].astype(float), df[lat_col].astype(float))]
    except Exception:
        raise DatasetLoadError(
            "The latitude/longitude columns contain non-numeric values."
        )

    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=WORKING_CRS_GEO)
    return gdf


def detect_crs(gdf: gpd.GeoDataFrame):
    """Return the CRS object of a GeoDataFrame, or None if undefined."""
    return gdf.crs


def harmonize_to_working_crs(gdf: gpd.GeoDataFrame, dataset_name: str):
    """
    Reproject a GeoDataFrame to the common working CRS (EPSG:4326).
    Returns (harmonized_gdf, report_dict). Never guesses a missing CRS --
    if CRS is undefined, the report flags it and the original geometry is
    returned unmodified.
    """
    original_crs = gdf.crs
    report = {
        "dataset": dataset_name,
        "original_crs": str(original_crs) if original_crs else "UNDEFINED",
        "working_crs": WORKING_CRS_GEO,
        "status": "",
    }

    if original_crs is None:
        report["status"] = "⚠️ CRS information is missing. Please define the CRS before spatial analysis."
        return gdf, report

    try:
        if str(original_crs) == WORKING_CRS_GEO:
            report["status"] = "✅ Already in working CRS"
            return gdf, report
        harmonized = gdf.to_crs(WORKING_CRS_GEO)
        report["status"] = "✅ Reprojected successfully"
        return harmonized, report
    except Exception:
        report["status"] = "❌ Reprojection failed -- CRS may be invalid or unsupported"
        return gdf, report


def to_metric(gdf: gpd.GeoDataFrame):
    """Project a (working-CRS) GeoDataFrame to the metric CRS for area/distance math."""
    from utils import WORKING_CRS_METRIC
    if gdf.crs is None:
        gdf = gdf.set_crs(WORKING_CRS_GEO)
    return gdf.to_crs(WORKING_CRS_METRIC)
