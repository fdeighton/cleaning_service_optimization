"""Shared app utilities: path bootstrap, cached data access, sidebar filters.

This is the only place Streamlit and the ``cleanlens`` package meet. Keeping the
caching here lets the core package stay framework-agnostic and unit-testable.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Make ``src/cleanlens`` importable when Streamlit runs from any cwd.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from cleanlens import loader, schema, transform  # noqa: E402


@st.cache_data(show_spinner="Loading schedule data…")
def get_data() -> tuple[pd.DataFrame, dict]:
    """Load -> validate -> enrich the whole portfolio. Cached across reruns."""
    raw = loader.load_portfolio()
    report = schema.validate(raw)
    enriched = transform.enrich(raw)
    report_dict = {
        "ok": report.ok,
        "errors": report.errors,
        "warnings": report.warnings,
        "stats": report.stats,
    }
    return enriched, report_dict


def sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Render global slicers (Property is first-class) and return filtered data."""
    st.sidebar.header("Filters")

    properties = sorted(df["property_name"].unique())
    chosen_props = st.sidebar.multiselect(
        "Property", properties, default=properties,
        help="property_name is a first-class dimension — works for Parker and "
             "any future Fitzrovia property automatically.",
    )

    freqs = sorted(df["frequency_canonical"].unique())
    chosen_freqs = st.sidebar.multiselect("Frequency", freqs, default=freqs)

    area_types = sorted(df["area_type"].unique())
    chosen_areas = st.sidebar.multiselect("Area type", area_types, default=area_types)

    real_only = st.sidebar.toggle(
        "Real employees only", value=True,
        help="Exclude placeholder assignees like '(all staff)'.",
    )

    mask = (
        df["property_name"].isin(chosen_props)
        & df["frequency_canonical"].isin(chosen_freqs)
        & df["area_type"].isin(chosen_areas)
    )
    if real_only:
        mask &= df["is_real_employee"]

    filtered = df[mask].copy()
    st.session_state["real_only"] = real_only
    return filtered


def empty_guard(df: pd.DataFrame) -> bool:
    """Show a notice and return True if there's nothing to plot."""
    if len(df) == 0:
        st.warning("No assignments match the current filters.")
        return True
    return False


def page_header(title: str, subtitle: str) -> None:
    st.title(title)
    st.caption(subtitle)
