"""Normalize schedule CSVs to reduce *formatting* redundancy without losing data.

What it does (safe, meaning-preserving):
  * Whitespace cleanup on every shown field — trim, collapse runs of spaces,
    drop leading bullet/dash.
  * Case canonicalization for location / task / frequency: values that are
    identical except for case/whitespace are collapsed to ONE consistent label
    (the most common spelling, first letter capitalised).

What it never does:
  * It never merges two values that differ in actual words (e.g. "4 Elevators"
    vs "4 Elevator" stay separate — different content, possibly meaningful).
  * It never drops or reorders rows, and leaves `source_text` byte-for-byte
    intact as the provenance/audit trail.

Run directly to write normalized copies into schedule_data/normalized/.
"""
from __future__ import annotations

import csv
import glob
import os
import re
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO, "schedule_data")
NORM_DIR = os.path.join(SRC_DIR, "normalized")

COLUMNS = ["property", "employee_name", "day_of_week", "start_time", "end_time",
           "location", "task", "frequency", "notes", "source_text"]
# columns whose case is canonicalised (whitespace-cleaned on all the rest too)
CANON_COLS = ["location", "task", "frequency"]
# source_text is preserved verbatim — never touched
PRESERVE = {"source_text"}


def normalize_text(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"^[\s\-–•*]+", "", s)        # leading bullets/dashes
    s = re.sub(r"\s+", " ", s)               # collapse all whitespace runs
    s = s.replace(" ,", ",").replace(" ;", ";")
    return s.strip()


def _choose_canonical(counter: Counter) -> str:
    """Pick the representative spelling: most frequent, then longest, then A-Z."""
    best = sorted(counter.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))[0][0]
    if best and best[0].isalpha() and best[0].islower():
        best = best[0].upper() + best[1:]    # capitalise first letter only
    return best


def build_canonical_map(values: list[str]) -> dict[str, str]:
    """value(after whitespace-norm) -> canonical label, grouped case-insensitively."""
    groups: dict[str, Counter] = defaultdict(Counter)
    for v in values:
        groups[v.casefold()][v] += 1
    canon_by_key = {k: _choose_canonical(c) for k, c in groups.items()}
    return {v: canon_by_key[v.casefold()] for v in set(values)}


def normalize_dataset(rows: list[dict]) -> tuple[list[dict], dict]:
    # 1) whitespace-normalize every shown field (preserve source_text)
    cleaned = []
    for r in rows:
        nr = {c: (r.get(c, "") if c in PRESERVE else normalize_text(r.get(c, "")))
              for c in COLUMNS}
        cleaned.append(nr)

    # 2) build case-canonical maps per CANON_COL and apply
    report = {"rows": len(cleaned)}
    for col in CANON_COLS:
        raw_distinct = len({r.get(col, "") for r in rows})            # before (raw)
        ws_vals = [r[col] for r in cleaned]
        cmap = build_canonical_map(ws_vals)
        for r in cleaned:
            r[col] = cmap[r[col]]
        report[col] = (raw_distinct, len(set(cmap.values())))         # (before, after)
    return cleaned, report


def normalize_file(src_path: str) -> dict:
    with open(src_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    norm, report = normalize_dataset(rows)
    os.makedirs(NORM_DIR, exist_ok=True)
    out_path = os.path.join(NORM_DIR, os.path.basename(src_path))
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(norm)
    report["name"] = os.path.basename(src_path).replace("_cleaning_responsibilities.csv", "")
    report["out"] = os.path.relpath(out_path, REPO)
    return report


def main() -> None:
    files = sorted(glob.glob(os.path.join(SRC_DIR, "*_cleaning_responsibilities.csv")))
    print(f"normalizing {len(files)} files -> {os.path.relpath(NORM_DIR, REPO)}/\n")
    print(f"{'Property':<16}{'rows':>6}{'locations(raw>norm)':>22}{'tasks(raw>norm)':>20}{'freq(raw>norm)':>18}")
    for p in files:
        r = normalize_file(p)
        lc, tk, fr = r["location"], r["task"], r["frequency"]
        print(f"{r['name']:<16}{r['rows']:>6}"
              f"{f'{lc[0]} > {lc[1]}':>22}{f'{tk[0]} > {tk[1]}':>20}{f'{fr[0]} > {fr[1]}':>18}")
    print("\n(originals untouched; source_text preserved verbatim; no rows dropped)")


if __name__ == "__main__":
    main()
