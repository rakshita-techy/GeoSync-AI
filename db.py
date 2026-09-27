"""
db.py
Lightweight SQLite persistence for the "Integrated Land Record" table.
Stored at /home/claude/geosync_ai/geosync.db by default (or wherever the
app is run from) so records survive across a single local session's reruns.
"""

import sqlite3
import datetime
import pandas as pd

DB_PATH = "geosync_ai.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS integrated_records (
    record_id TEXT PRIMARY KEY,
    building_id TEXT,
    plot_id TEXT,
    owner_name TEXT,
    land_use TEXT,
    building_type TEXT,
    match_score REAL,
    confidence REAL,
    status TEXT,
    has_conflict INTEGER,
    is_valid_geometry INTEGER,
    last_updated TEXT
);
"""


def get_connection(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def rebuild_integrated_records(conn, confidence_df: pd.DataFrame, cadastral_gdf, buildings_gdf):
    """Clear and repopulate the integrated_records table from the latest pipeline output."""
    cur = conn.cursor()
    cur.execute("DELETE FROM integrated_records")

    plot_lookup = {}
    if cadastral_gdf is not None and "plot_id" in cadastral_gdf.columns:
        plot_lookup = dict(zip(cadastral_gdf["plot_id"], zip(cadastral_gdf.get("owner_name", []), cadastral_gdf.get("land_use", []))))

    building_type_lookup = {}
    if buildings_gdf is not None and "building_id" in buildings_gdf.columns:
        building_type_lookup = dict(zip(buildings_gdf["building_id"], buildings_gdf.get("building_type", [])))

    now = datetime.datetime.now().isoformat(timespec="seconds")

    if confidence_df is not None:
        for _, r in confidence_df.iterrows():
            owner_name, land_use = plot_lookup.get(r["plot_id"], (None, None))
            record_id = f"REC-{r['building_id']}"
            cur.execute(
                """INSERT OR REPLACE INTO integrated_records
                   (record_id, building_id, plot_id, owner_name, land_use, building_type,
                    match_score, confidence, status, has_conflict, is_valid_geometry, last_updated)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record_id, r["building_id"], r["plot_id"], owner_name, land_use,
                    building_type_lookup.get(r["building_id"]),
                    float(r["match_score"]), float(r["confidence"]), r["status"],
                    int(bool(r["has_conflict"])), int(bool(r["is_valid_geometry"])), now,
                )
            )
    conn.commit()


def fetch_integrated_records(conn) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM integrated_records ORDER BY confidence DESC", conn)
