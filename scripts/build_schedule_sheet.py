"""Parker_Schedule.xlsx — one clean sheet, verbatim from the source CSV.

No classification, no aggregation, no charts, no derived columns. Each output row
is built from exactly one source row, so a task can never be carried onto the
wrong row. Built with the stdlib csv reader (not pandas) and verified against the
source before saving.
"""
from __future__ import annotations

import csv
import os
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "schedule_data", "Parker_cleaning_responsibilities.csv")
OUT_DIR = os.path.join(REPO, "Working_excels") if os.path.isdir(os.path.join(REPO, "Working_excels")) else REPO
OUT = os.path.join(OUT_DIR, "Parker_Schedule.xlsx")

# source column -> output header
COLS = [
    ("employee_name", "Employee"),
    ("day_of_week", "Day"),
    ("start_time", "Start Time"),
    ("end_time", "End Time"),
    ("location", "Location"),
    ("task", "Task"),
    ("frequency", "Frequency"),
]

WEEK = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
FULL = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6}
ABBR = {"mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3,
        "thurs": 3, "fri": 4, "sat": 5, "sun": 6}


def day_key(v: str) -> int:
    low = v.strip().lower()
    if low in FULL:
        return FULL[low]
    first = low.split("-")[0].strip()
    return ABBR.get(first, 99)


def time_key(v: str) -> int:
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*([AP]M)?\s*$", v.strip(), re.I)
    if not m:
        return 10 ** 9
    h = int(m.group(1)) % 12
    if (m.group(3) or "").upper() == "PM":
        h += 12
    return h * 60 + int(m.group(2))


def main() -> None:
    with open(SRC, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        src_rows = list(reader)

    # Build output rows — each from a single source row (no cross-row ops).
    out_rows = [[r[src] for src, _ in COLS] for r in src_rows]
    # Sort Employee -> Day -> Start Time for readability (row integrity preserved).
    order = sorted(range(len(out_rows)),
                   key=lambda i: (out_rows[i][0].lower(),
                                  day_key(out_rows[i][1]), time_key(out_rows[i][2])))
    out_rows = [out_rows[i] for i in order]

    # --- integrity check against source (multiset of full rows must match) ---
    src_multiset = sorted(tuple(r[src] for src, _ in COLS) for r in src_rows)
    out_multiset = sorted(tuple(row) for row in out_rows)
    assert len(out_rows) == len(src_rows), "row count changed"
    assert out_multiset == src_multiset, "row content changed — task/row mismatch!"

    # --- write one clean sheet ---
    wb = Workbook()
    ws = wb.active
    ws.title = "Parker Schedule"
    ws.sheet_view.showGridLines = False

    headers = [h for _, h in COLS]
    head_fill = PatternFill("solid", fgColor="1A1A1A")
    head_font = Font(bold=True, color="FFFFFF")
    stripe = PatternFill("solid", fgColor="F6F6F6")
    thin = Side(style="thin", color="E2E2E2")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    wrap = Alignment(wrap_text=True, vertical="top")

    for j, h in enumerate(headers, start=1):
        c = ws.cell(1, j, h)
        c.fill = head_fill; c.font = head_font; c.border = border
        c.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 20

    for i, row in enumerate(out_rows, start=2):
        for j, val in enumerate(row, start=1):
            c = ws.cell(i, j, val)
            c.border = border
            if headers[j - 1] in ("Location", "Task"):
                c.alignment = wrap
            else:
                c.alignment = Alignment(vertical="top")
            if i % 2 == 0:
                c.fill = stripe

    # column widths: fixed for the long wrapped columns, autosize the rest
    widths = {"Employee": 14, "Day": 10, "Start Time": 11, "End Time": 11,
              "Location": 40, "Task": 60, "Frequency": 13}
    for j, h in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(j)].width = widths[h]

    last = len(out_rows) + 1
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{last}"
    ws.freeze_panes = "A2"

    wb.save(OUT)
    print("saved:", os.path.relpath(OUT, REPO))
    print(f"rows: {len(out_rows)}  (verified identical to source, no row/task mismatch)")
    print("columns:", headers)


if __name__ == "__main__":
    main()
