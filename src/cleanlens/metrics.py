"""Metrics layer — reusable, count/cadence-only aggregations.

Every function takes an enriched DataFrame and returns either a scalar or a tidy
DataFrame ready to plot. No function computes effort, hours, durations, square
footage, or any optimization output — by design and by project constraint.

Grain: one input row = one scheduled assignment (Area x Task x Employee x block).
"""
from __future__ import annotations

import pandas as pd

from . import transform


# ---------------------------------------------------------------------------
# Headline scalars
# ---------------------------------------------------------------------------
def assignment_count(df: pd.DataFrame) -> int:
    return int(len(df))


def distinct_employees(df: pd.DataFrame, real_only: bool = True) -> int:
    d = df[df["is_real_employee"]] if real_only and "is_real_employee" in df else df
    return int(d["employee_name"].nunique())


def distinct_locations(df: pd.DataFrame) -> int:
    return int(df["location"].nunique())


def distinct_tasks(df: pd.DataFrame) -> int:
    return int(df["task"].nunique())


def distinct_properties(df: pd.DataFrame) -> int:
    return int(df["property_name"].nunique())


def defined_frequency_rate(df: pd.DataFrame) -> float:
    """Share of assignments whose frequency is a defined (non-Unknown) cadence."""
    if len(df) == 0:
        return 0.0
    return float(df["is_defined_frequency"].mean())


def bundled_task_rate(df: pd.DataFrame) -> float:
    """[structural] share of assignments whose task text bundles several actions."""
    if len(df) == 0:
        return 0.0
    return float(df["is_bundled"].mean())


# ---------------------------------------------------------------------------
# Distributions (single dimension counts)
# ---------------------------------------------------------------------------
def _count_by(df: pd.DataFrame, column: str, label: str | None = None) -> pd.DataFrame:
    label = label or column
    out = (
        df.groupby(column, dropna=False)
        .size()
        .reset_index(name="assignments")
        .rename(columns={column: label})
        .sort_values("assignments", ascending=False, ignore_index=True)
    )
    return out


def frequency_distribution(df: pd.DataFrame) -> pd.DataFrame:
    return _count_by(df, "frequency_canonical", "frequency")


def task_distribution(df: pd.DataFrame, top_n: int | None = None) -> pd.DataFrame:
    out = _count_by(df, "task_category", "task_category")
    return out.head(top_n) if top_n else out


def top_tasks_raw(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    out = _count_by(df, "task", "task")
    return out.head(top_n)


def assignments_by_employee(df: pd.DataFrame, real_only: bool = True) -> pd.DataFrame:
    d = df[df["is_real_employee"]] if real_only and "is_real_employee" in df else df
    return _count_by(d, "employee_name", "employee")


def assignments_by_location(df: pd.DataFrame, top_n: int | None = None) -> pd.DataFrame:
    out = _count_by(df, "location", "location")
    return out.head(top_n) if top_n else out


def assignments_by_area_type(df: pd.DataFrame) -> pd.DataFrame:
    return _count_by(df, "area_type", "area_type")


def assignments_by_property(df: pd.DataFrame) -> pd.DataFrame:
    return _count_by(df, "property_name", "property")


# ---------------------------------------------------------------------------
# Matrices / heatmaps (two-dimension counts, returned as pivot tables)
# ---------------------------------------------------------------------------
def _matrix(df: pd.DataFrame, index: str, columns: str) -> pd.DataFrame:
    return (
        df.pivot_table(index=index, columns=columns, aggfunc="size", fill_value=0)
        .sort_index()
    )


def employee_location_matrix(df: pd.DataFrame, real_only: bool = True) -> pd.DataFrame:
    """Employee (rows) x Area Type (cols) = assignment count."""
    d = df[df["is_real_employee"]] if real_only and "is_real_employee" in df else df
    return _matrix(d, "employee_name", "area_type")


def employee_task_matrix(df: pd.DataFrame, real_only: bool = True) -> pd.DataFrame:
    """Employee (rows) x Task Category (cols) = assignment count."""
    d = df[df["is_real_employee"]] if real_only and "is_real_employee" in df else df
    return _matrix(d, "employee_name", "task_category")


def area_task_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Area Type (rows) x Task Category (cols) = assignment count."""
    return _matrix(df, "area_type", "task_category")


def frequency_by_location(df: pd.DataFrame) -> pd.DataFrame:
    """Area Type (rows) x Frequency (cols) = assignment count."""
    return _matrix(df, "area_type", "frequency_canonical")


def task_mix_by_location(df: pd.DataFrame) -> pd.DataFrame:
    """Tidy Area Type x Task Category counts (for a stacked bar)."""
    return (
        df.groupby(["area_type", "task_category"], dropna=False)
        .size()
        .reset_index(name="assignments")
    )


# ---------------------------------------------------------------------------
# Coverage analysis
# ---------------------------------------------------------------------------
def employee_coverage(df: pd.DataFrame, real_only: bool = True) -> pd.DataFrame:
    """Per employee: assignments, distinct area types, distinct locations, tasks."""
    d = df[df["is_real_employee"]] if real_only and "is_real_employee" in df else df
    out = (
        d.groupby("employee_name")
        .agg(
            assignments=("location", "size"),
            distinct_area_types=("area_type", "nunique"),
            distinct_locations=("location", "nunique"),
            distinct_task_categories=("task_category", "nunique"),
        )
        .reset_index()
        .rename(columns={"employee_name": "employee"})
        .sort_values("assignments", ascending=False, ignore_index=True)
    )
    return out


def area_type_coverage(df: pd.DataFrame) -> pd.DataFrame:
    """Per area type: assignments, distinct locations, tasks, employees touching it."""
    out = (
        df.groupby("area_type")
        .agg(
            assignments=("location", "size"),
            distinct_locations=("location", "nunique"),
            distinct_task_categories=("task_category", "nunique"),
            distinct_employees=("employee_name", "nunique"),
        )
        .reset_index()
        .sort_values("assignments", ascending=False, ignore_index=True)
    )
    return out


def assignments_by_day(df: pd.DataFrame) -> pd.DataFrame:
    """Assignment count per expanded day of week (uses day explosion)."""
    from . import config

    exploded = transform.explode_days(df)
    out = (
        exploded.groupby("day", dropna=False)
        .size()
        .reset_index(name="assignments")
    )
    # Order Mon..Sun, with unparsed (None) last.
    order = {d: i for i, d in enumerate(config.WEEK_ORDER)}
    out["__order"] = out["day"].map(lambda d: order.get(d, 99))
    out = out.sort_values("__order").drop(columns="__order").reset_index(drop=True)
    return out


# ---------------------------------------------------------------------------
# Data-quality (governance) summary
# ---------------------------------------------------------------------------
def data_quality_summary(df: pd.DataFrame) -> dict[str, float | int]:
    return {
        "assignments": assignment_count(df),
        "defined_frequency_rate": round(defined_frequency_rate(df), 4),
        "unknown_frequency_rows": int((~df["is_defined_frequency"]).sum()),
        "bundled_task_rate": round(bundled_task_rate(df), 4),
        "non_explicit_task_rows": int((~df["is_explicit_task"]).sum()),
        "placeholder_employee_rows": int((~df["is_real_employee"]).sum()),
        "unclassified_area_rows": int((df["area_type"] == "Unclassified").sum()),
    }
