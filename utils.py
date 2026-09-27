"""
utils.py
Shared constants, CRS definitions and small formatting/status helpers
used across every page of GeoSync AI.
"""

import streamlit as st

# ----------------------------------------------------------------------
# CRS configuration
# ----------------------------------------------------------------------
# Geographic working CRS (used for the interactive map / storage)
WORKING_CRS_GEO = "EPSG:4326"
# Metric working CRS used for all area / distance / overlap calculations.
# UTM Zone 43N covers Bengaluru and most of South/Central India.
WORKING_CRS_METRIC = "EPSG:32643"

# Demo dataset location: Bengaluru
DEMO_CENTER_LAT = 12.9716
DEMO_CENTER_LON = 77.5946

# ----------------------------------------------------------------------
# Thresholds used by the rule-based "AI" spatial-matching engine.
# These are intentionally explicit and explainable (no black-box model).
# ----------------------------------------------------------------------
MATCH_OVERLAP_THRESHOLD = 0.30       # min overlap ratio to call it a match
CROSSING_OVERLAP_THRESHOLD = 0.15    # min overlap with 2+ plots => "crosses boundary"
DUPLICATE_IOU_THRESHOLD = 0.90       # IoU above this => duplicate building
GNSS_MAX_LINK_DISTANCE_M = 40.0      # GNSS point farther than this from any building/plot => misplaced
CHANGE_IOU_THRESHOLD = 0.85          # below this (but matched) => "geometry changed"

# Confidence score weights (sum to 1.0) -- rule based, explainable
CONF_WEIGHT_VALIDITY = 0.30
CONF_WEIGHT_MATCH = 0.40
CONF_WEIGHT_CONFLICT_FREE = 0.30

CONF_VERIFIED_MIN = 80
CONF_REVIEW_MIN = 50

# ----------------------------------------------------------------------
# Status labels & icons
# ----------------------------------------------------------------------
STATUS_VERIFIED = "VERIFIED"
STATUS_REVIEW = "REVIEW REQUIRED"
STATUS_CONFLICT = "CONFLICT"
STATUS_UNMATCHED = "UNMATCHED"
STATUS_INVALID = "INVALID"

STATUS_ICON = {
    STATUS_VERIFIED: "🟢",
    STATUS_REVIEW: "🟡",
    STATUS_CONFLICT: "🔴",
    STATUS_UNMATCHED: "⚪",
    STATUS_INVALID: "❌",
}


def status_badge(status: str) -> str:
    """Return 'ICON STATUS' string for a status constant."""
    return f"{STATUS_ICON.get(status, '⚪')} {status}"


def init_page():
    """Common page header helper (title already set once in app.py)."""
    pass


def safe_round(value, digits=1):
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return value


def show_error_box(message: str):
    """Consistent, user-friendly error display (never raw tracebacks)."""
    st.error(f"⚠️ {message}")


def show_info_box(message: str):
    st.info(f"ℹ️ {message}")


def metric_card(col, label, value, help_text=None, delta=None):
    col.metric(label, value, delta=delta, help=help_text)
