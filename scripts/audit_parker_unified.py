"""Audit output/clean schedule/Parker_Clean_Schedule.xlsx for correctness.

Checks, each independent of the build step:
  A. Clean Schedule == source CSV (same 448 assignments, verbatim key fields).
  B. Every (day, time-block, employee) present in the Clean Schedule appears as a
     NON-empty grid cell, and every non-empty grid cell traces to real rows
     (grid <-> clean schedule presence sets match exactly).
  C. Each grid label equals the label the rule produces from that cell's actual
     Clean-Schedule rows (no mislabeling in the written file).
  D. No 'Review Needed' cells remain.
"""
from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict

from openpyxl import load_workbook

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_schedule_grid import cell_label, expand_days, resolve_source_csv  # noqa: E402
from build_clean_schedule import clean  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WB = os.path.join(REPO, "output", "clean schedule", "Parker_Clean_Schedule.xlsx")

KEY7 = ["employee_name", "day_of_week", "start_time", "end_time", "location", "task", "frequency"]


def nb(block: str) -> str:          # normalize a time-block string for comparison
    return (block or "").replace(" ", "")


def main() -> None:
    wb = load_workbook(WB)
    print("file:", os.path.relpath(WB, REPO))
    print("sheets:", wb.sheetnames)
    assert wb.sheetnames == ["Schedule Grid", "Clean Schedule"], "unexpected sheets"
    grid, cs = wb["Schedule Grid"], wb["Clean Schedule"]
    passes = []

    # ---- read Clean Schedule rows ----
    cs_rows = []
    for r in range(2, cs.max_row + 1):
        cs_rows.append([cs.cell(r, c).value for c in range(1, 11)])
    cs_rows = [r for r in cs_rows if any(r)]
    # cols: 0 Emp 1 Day 2 Start 3 End 4 Block 5 Loc 6 Area 7 Task 8 Freq 9 Notes

    # ---- A. Clean Schedule == source ----
    with open(resolve_source_csv(), newline="", encoding="utf-8-sig") as f:
        src = list(csv.DictReader(f))
    src_emps = {clean(s["employee_name"]) for s in src if clean(s["employee_name"])}
    src_ms = sorted(tuple(clean(s[k]) for k in KEY7) for s in src)
    cs_ms = sorted((r[0] or "", r[1] or "", r[2] or "", r[3] or "",
                    r[5] or "", r[7] or "", r[8] or "") for r in cs_rows)
    a_ok = (len(cs_rows) == len(src)) and (cs_ms == src_ms)
    passes.append(("A. Clean Schedule == source (448 verbatim rows)", a_ok))
    if not a_ok:
        print("   rows: cs", len(cs_rows), "src", len(src))
        diff = [x for x in cs_ms if x not in set(src_ms)][:3]
        print("   sample cs-not-in-src:", diff)

    # ---- build cell -> items from Clean Schedule (expand day ranges) ----
    cells = defaultdict(list)
    for r in cs_rows:
        emp, day_field, start, block = r[0], r[1], r[2], r[4]
        item = {"loc": r[5] or "", "area": r[6] or "", "task": r[7] or ""}
        for day in expand_days(day_field):
            cells[(day, nb(block), emp)].append(item)
    expected_presence = set(cells.keys())

    # ---- read grid non-empty cells + labels ----
    headers = [grid.cell(2, c).value for c in range(1, grid.max_column + 1)]
    # only real employee columns (ignore the gap + legend columns to the right)
    emp_cols = {c: headers[c - 1] for c in range(3, len(headers) + 1)
                if headers[c - 1] in src_emps}
    grid_presence = set()
    label_mismatches, review = [], 0
    for r in range(3, grid.max_row + 1):
        day = grid.cell(r, 1).value
        block = nb(grid.cell(r, 2).value)
        for c, emp in emp_cols.items():
            label = grid.cell(r, c).value
            if not label:
                continue
            if label == "Review Needed":
                review += 1
            grid_presence.add((day, block, emp))
            expected = cell_label(cells.get((day, block, emp), []))
            if label != expected:
                label_mismatches.append((day, grid.cell(r, 2).value, emp, label, expected))

    # ---- B. presence sets match ----
    b_ok = grid_presence == expected_presence
    passes.append(("B. Grid cells <-> Clean Schedule presence match", b_ok))
    if not b_ok:
        only_grid = list(grid_presence - expected_presence)[:5]
        only_cs = list(expected_presence - grid_presence)[:5]
        print("   in grid not in schedule:", only_grid)
        print("   in schedule not in grid:", only_cs)

    # ---- C. labels correct ----
    c_ok = not label_mismatches
    passes.append(("C. Every grid label matches the rule on its rows", c_ok))
    for m in label_mismatches[:10]:
        print("   mismatch:", m)

    # ---- D. no Review Needed ----
    passes.append(("D. No 'Review Needed' cells", review == 0))

    print()
    for name, ok in passes:
        print(f"  [{'PASS' if ok else 'FAIL'}]  {name}")
    print(f"\nClean Schedule rows: {len(cs_rows)} | Grid non-empty cells: {len(grid_presence)} | Review Needed: {review}")
    print("AUDIT:", "ALL PASS" if all(ok for _, ok in passes) else "FAILURES ABOVE")


if __name__ == "__main__":
    main()
