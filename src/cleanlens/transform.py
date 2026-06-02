"""Transformation layer.

Takes a validated raw portfolio DataFrame and returns a *new* DataFrame with the
derived analytical columns added. The source columns are copied through
untouched — this layer never mutates source data (per project constraint).
"""
from __future__ import annotations

import re

import pandas as pd

from . import config, mappings

_TIME_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*([AaPp][Mm])?\s*$")


# ---------------------------------------------------------------------------
# Scalar helpers
# ---------------------------------------------------------------------------
def parse_hour(time_str: str) -> int | None:
    """Parse '8:00 AM' / '13:30' to a 24h hour int; None if unparseable."""
    m = _TIME_RE.match(str(time_str or ""))
    if not m:
        return None
    hour = int(m.group(1))
    meridiem = (m.group(3) or "").lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    return hour if 0 <= hour <= 23 else None


def is_placeholder_employee(name: str) -> bool:
    low = (name or "").strip().lower()
    if not low:
        return True
    return any(tok in low for tok in config.EMPLOYEE_PLACEHOLDER_TOKENS)


def is_bundled_task(task: str) -> bool:
    return any(marker in (task or "").lower() for marker in config.BUNDLED_TASK_MARKERS)


def is_explicit_task(task: str) -> bool:
    """A task is explicit if it carries text and isn't a parenthetical note."""
    t = (task or "").strip()
    if not t:
        return False
    if t.startswith("(") and t.endswith(")"):
        return False
    return True


def expand_days(day_value: str) -> list[str]:
    """Expand 'Mon-Fri', 'Tue-Thu', single days, etc. into full day names.

    Unparseable values return an empty list (never guesses a day).
    """
    raw = (day_value or "").strip()
    if not raw:
        return []
    # Full single day name (e.g. "Monday").
    titled = raw.title()
    if titled in config.WEEK_ORDER:
        return [titled]
    # Range like "Mon-Fri" / "Sat-Sun".
    if "-" in raw:
        start_tok, _, end_tok = raw.lower().partition("-")
        start = config.DAY_ABBREV.get(start_tok.strip())
        end = config.DAY_ABBREV.get(end_tok.strip())
        if start and end:
            i, j = config.WEEK_ORDER.index(start), config.WEEK_ORDER.index(end)
            if i <= j:
                return config.WEEK_ORDER[i : j + 1]
            return config.WEEK_ORDER[i:] + config.WEEK_ORDER[: j + 1]  # wrap
    # Abbreviated single token (e.g. "Mon").
    abbrev = config.DAY_ABBREV.get(raw.lower())
    if abbrev:
        return [abbrev]
    return []


# ---------------------------------------------------------------------------
# Frame-level enrichment
# ---------------------------------------------------------------------------
def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``df`` with all derived columns added."""
    out = df.copy()

    out["property_name"] = out["property"].apply(mappings.canonical_property)

    freq = out["frequency"].apply(mappings.canonical_frequency)
    out["frequency_canonical"] = freq.apply(lambda t: t[0])
    out["is_defined_frequency"] = freq.apply(lambda t: t[1])

    hours = out["start_time"].apply(parse_hour) if "start_time" in out else None
    out["start_hour"] = hours if hours is not None else None
    out["shift_band"] = (out["start_hour"] if "start_hour" in out else pd.Series([None] * len(out))).apply(
        config.shift_band_for_hour
    )

    out["is_real_employee"] = ~out["employee_name"].apply(is_placeholder_employee)
    out["is_explicit_task"] = out["task"].apply(is_explicit_task)
    out["is_bundled"] = out["task"].apply(is_bundled_task)

    out["area_type"] = out["location"].apply(mappings.classify_area)
    out["task_category"] = out["task"].apply(mappings.classify_task)

    if "day_of_week" in out:
        out["day_list"] = out["day_of_week"].apply(expand_days)
    else:
        out["day_list"] = [[] for _ in range(len(out))]

    return out


def explode_days(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (assignment x scheduled day). Use for per-day metrics only.

    Rows whose day pattern could not be parsed keep a single row with day=None,
    so nothing is silently dropped.
    """
    out = df.copy()
    out["day"] = out["day_list"].apply(lambda d: d if d else [None])
    out = out.explode("day", ignore_index=True)
    return out
