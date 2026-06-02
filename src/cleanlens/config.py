"""Central configuration: paths, the canonical schema, and controlled vocabularies.

Nothing here touches Streamlit. Edit the CSVs under ``config/`` to retune mappings
without changing code.
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# src/cleanlens/config.py -> repo root is three parents up.
REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEDULE_DATA_DIR = REPO_ROOT / "schedule_data"
CONFIG_DIR = REPO_ROOT / "config"

FREQUENCY_MAP_CSV = CONFIG_DIR / "frequency_map.csv"
AREA_TYPE_KEYWORDS_CSV = CONFIG_DIR / "area_type_keywords.csv"
TASK_CATEGORY_KEYWORDS_CSV = CONFIG_DIR / "task_category_keywords.csv"
PROPERTY_NAME_MAP_CSV = CONFIG_DIR / "property_name_map.csv"

# Glob used to auto-discover datasets. Any CSV that matches and conforms to the
# canonical schema is loaded automatically — this is what makes the app reusable
# for future properties (Phase 5): drop a conforming CSV in, it just appears.
DATASET_GLOB = "*_cleaning_responsibilities.csv"

# ---------------------------------------------------------------------------
# Canonical schema — the 10 source fields, kept verbatim for provenance.
# ---------------------------------------------------------------------------
SOURCE_COLUMNS = [
    "property",
    "employee_name",
    "day_of_week",
    "start_time",
    "end_time",
    "location",
    "task",
    "frequency",
    "notes",
    "source_text",
]

# Columns the app cannot function without (validation fails hard if missing).
REQUIRED_COLUMNS = ["property", "employee_name", "location", "task", "frequency"]

# ---------------------------------------------------------------------------
# Derived columns added by the transformation layer (source is never mutated).
# ---------------------------------------------------------------------------
DERIVED_COLUMNS = [
    "property_name",          # trimmed, first-class dimension
    "frequency_canonical",    # controlled vocabulary
    "is_defined_frequency",   # governance flag (Unknown -> False)
    "shift_band",             # AM / PM / Overnight, from start_time
    "is_real_employee",       # excludes "(all staff)" style placeholders
    "is_explicit_task",       # task carries an actual verb vs. facility note
    "is_bundled",             # structural: task text contains "," "&" or "etc"
    "area_type",              # mapped via config/area_type_keywords.csv
    "task_category",          # mapped via config/task_category_keywords.csv
    "day_list",               # day_of_week expanded to a list of single days
]

# Tokens that mark a non-person assignee (kept in data, flagged not-real).
EMPLOYEE_PLACEHOLDER_TOKENS = ("all staff", "name not stated", "not stated", "n/a")

# Structural markers that flag a task string as bundling several actions.
BUNDLED_TASK_MARKERS = (",", "&", " etc", "/")

# Day-of-week handling -------------------------------------------------------
WEEK_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_ABBREV = {
    "mon": "Monday", "tue": "Tuesday", "tues": "Tuesday", "wed": "Wednesday",
    "thu": "Thursday", "thur": "Thursday", "thurs": "Thursday", "fri": "Friday",
    "sat": "Saturday", "sun": "Sunday",
}
WEEKEND_DAYS = {"Saturday", "Sunday"}

# Shift bands by start hour (24h). Overnight wraps midnight.
def shift_band_for_hour(hour: int | None) -> str:
    if hour is None:
        return "Unknown"
    if 5 <= hour < 12:
        return "AM"
    if 12 <= hour < 18:
        return "PM"
    return "Overnight"


UNKNOWN_AREA_TYPE = "Unclassified"
UNKNOWN_TASK_CATEGORY = "Uncategorized"
