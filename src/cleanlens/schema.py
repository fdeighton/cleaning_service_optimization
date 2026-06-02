"""Schema validation layer.

Validation is non-destructive: it reports problems, it never edits the data.
A hard failure (missing required column) raises; soft issues (placeholder
employees, unknown frequencies) are surfaced as warnings the app can display.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import config


@dataclass
class ValidationReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        head = "VALID" if self.ok else "INVALID"
        lines = [f"Schema: {head}"]
        lines += [f"  ERROR: {e}" for e in self.errors]
        lines += [f"  warn:  {w}" for w in self.warnings]
        return "\n".join(lines)


def validate(df: pd.DataFrame) -> ValidationReport:
    """Validate a raw portfolio DataFrame against the canonical schema."""
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict[str, int] = {}

    present = set(df.columns)

    missing_required = [c for c in config.REQUIRED_COLUMNS if c not in present]
    if missing_required:
        errors.append(f"missing required columns: {missing_required}")

    missing_optional = [
        c for c in config.SOURCE_COLUMNS
        if c not in present and c not in config.REQUIRED_COLUMNS
    ]
    if missing_optional:
        warnings.append(
            f"missing optional source columns (degraded, not fatal): {missing_optional}"
        )

    # Only run row-level checks if the required columns exist.
    if not missing_required:
        stats["rows"] = len(df)
        stats["properties"] = df["property"].str.strip().nunique()

        blank_task = df["task"].fillna("").str.strip().eq("").sum()
        if blank_task:
            warnings.append(f"{blank_task} rows have a blank task")
        stats["blank_task_rows"] = int(blank_task)

        known_freqs = set(_known_raw_frequencies())
        seen_freqs = set(df["frequency"].fillna("").str.strip().unique())
        unmapped = sorted(f for f in seen_freqs if f and f not in known_freqs)
        if unmapped:
            warnings.append(
                f"frequency values not in config/frequency_map.csv "
                f"(treated as Unknown): {unmapped}"
            )

        placeholder = df["employee_name"].fillna("").str.lower().apply(
            lambda v: any(tok in v for tok in config.EMPLOYEE_PLACEHOLDER_TOKENS)
        ).sum()
        if placeholder:
            warnings.append(
                f"{placeholder} rows use a placeholder employee (e.g. '(all staff)')"
            )
        stats["placeholder_employee_rows"] = int(placeholder)

    return ValidationReport(ok=not errors, errors=errors, warnings=warnings, stats=stats)


def _known_raw_frequencies() -> list[str]:
    try:
        fmap = pd.read_csv(config.FREQUENCY_MAP_CSV, dtype=str)
        return fmap["raw_frequency"].str.strip().tolist()
    except FileNotFoundError:
        return []
