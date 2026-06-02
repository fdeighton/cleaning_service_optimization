"""Data loading layer.

Auto-discovers every conforming CSV in ``schedule_data/`` and concatenates them
into one portfolio DataFrame. Adding a new property is a file drop — no code
change (Phase 5 reusability).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config


def discover_datasets(data_dir: Path | None = None) -> list[Path]:
    """Return the sorted list of candidate dataset files."""
    data_dir = data_dir or config.SCHEDULE_DATA_DIR
    return sorted(data_dir.glob(config.DATASET_GLOB))


def load_dataset(path: Path) -> pd.DataFrame:
    """Load one CSV as strings (no type coercion that could lose source fidelity)."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[])
    df["__source_file"] = path.name
    return df


def load_portfolio(data_dir: Path | None = None) -> pd.DataFrame:
    """Load and concatenate all discovered datasets into one DataFrame.

    Columns are left exactly as they appear in source. Validation and
    enrichment are separate steps so loading stays a pure I/O concern.
    """
    paths = discover_datasets(data_dir)
    if not paths:
        searched = (data_dir or config.SCHEDULE_DATA_DIR)
        raise FileNotFoundError(
            f"No datasets matching '{config.DATASET_GLOB}' found in {searched}."
        )
    frames = [load_dataset(p) for p in paths]
    portfolio = pd.concat(frames, ignore_index=True)
    return portfolio
