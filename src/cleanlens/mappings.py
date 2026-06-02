"""Mapping-table layer (Phase 3 standardization).

Mappings are data, not code: they live in editable CSVs under ``config/``.

  * frequency_map.csv          raw frequency  -> canonical + is_defined
  * area_type_keywords.csv     keyword        -> area_type     (first match wins)
  * task_category_keywords.csv keyword        -> task_category (first match wins)

The keyword maps are *recommendations*: they classify free-text location/task
strings without ever editing the source. Order in the CSV is precedence —
list more specific keywords above generic ones.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from . import config


@lru_cache(maxsize=1)
def frequency_map() -> dict[str, tuple[str, bool]]:
    """raw frequency (lowercased) -> (canonical_label, is_defined)."""
    df = pd.read_csv(config.FREQUENCY_MAP_CSV, dtype=str)
    out: dict[str, tuple[str, bool]] = {}
    for _, row in df.iterrows():
        raw = str(row["raw_frequency"]).strip().lower()
        defined = str(row["is_defined"]).strip().lower() in ("true", "1", "yes")
        out[raw] = (str(row["frequency_canonical"]).strip(), defined)
    return out


@lru_cache(maxsize=1)
def property_name_map() -> dict[str, str]:
    """raw property label -> canonical property_name (unmapped labels pass through).

    Resolves Elm/Ledbury: 'Elm', 'Ledbury', 'Elm/Ledbury' -> 'Elm/Ledbury'.
    """
    try:
        df = pd.read_csv(config.PROPERTY_NAME_MAP_CSV, dtype=str)
    except FileNotFoundError:
        return {}
    return {str(r["raw_property"]).strip(): str(r["property_name"]).strip()
            for _, r in df.iterrows()}


def canonical_property(raw: str) -> str:
    label = (raw or "").strip()
    return property_name_map().get(label, label)


@lru_cache(maxsize=1)
def _area_type_keywords() -> list[tuple[str, str]]:
    df = pd.read_csv(config.AREA_TYPE_KEYWORDS_CSV, dtype=str)
    return [(str(k).strip().lower(), str(v).strip()) for k, v in
            zip(df["keyword"], df["area_type"])]


@lru_cache(maxsize=1)
def _task_category_keywords() -> list[tuple[str, str]]:
    df = pd.read_csv(config.TASK_CATEGORY_KEYWORDS_CSV, dtype=str)
    return [(str(k).strip().lower(), str(v).strip()) for k, v in
            zip(df["keyword"], df["task_category"])]


def canonical_frequency(raw: str) -> tuple[str, bool]:
    key = (raw or "").strip().lower()
    return frequency_map().get(key, ("Unknown", False))


def classify_area(location: str) -> str:
    text = (location or "").lower()
    for kw, area_type in _area_type_keywords():
        if kw in text:
            return area_type
    return config.UNKNOWN_AREA_TYPE


def classify_task(task: str) -> str:
    text = (task or "").lower()
    for kw, category in _task_category_keywords():
        if kw in text:
            return category
    return config.UNKNOWN_TASK_CATEGORY


def clear_cache() -> None:
    """Drop cached mapping tables (call after editing a config CSV)."""
    frequency_map.cache_clear()
    property_name_map.cache_clear()
    _area_type_keywords.cache_clear()
    _task_category_keywords.cache_clear()
