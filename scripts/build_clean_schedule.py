"""output/clean schedule/<Property>_Clean_Schedule.xlsx — one clean worksheet per
property schedule, generated from every CSV in schedule_data/.

Each workbook has a single sheet "Clean Schedule", one row per scheduled
assignment, read verbatim from the source (only obvious spacing cleanup).
No second tab, no summary/chart/pivot/analysis.

Two requested columns are not in the source schema and are derived, not invented:
  * Time Block = a readable "Start - End" window (formatting of existing times)
  * Area Type  = classification of the existing Location via the shared keyword
                 vocabulary (Other / Unknown when it doesn't match)
"""
from __future__ import annotations

import csv
import glob
import os
import re
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_area_inventory import classify_area, clean_location  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Prefer the normalized copies (redundancy-reduced) when present; else raw source.
_NORM = os.path.join(REPO, "schedule_data", "normalized")
SRC_DIR = (_NORM if os.path.isdir(_NORM)
           and glob.glob(os.path.join(_NORM, "*_cleaning_responsibilities.csv"))
           else os.path.join(REPO, "schedule_data"))
OUT_DIR = os.path.join(REPO, "output", "clean schedule")

HEADERS = ["Employee", "Day", "Start Time", "End Time", "Time Block",
           "Location", "Area Type", "Task", "Frequency", "Notes"]
WRAP_COLS = {"Location", "Task", "Notes", "Time Block"}
WIDTHS = {"Employee": 16, "Day": 10, "Start Time": 11, "End Time": 11,
          "Time Block": 22, "Location": 38, "Area Type": 20,
          "Task": 52, "Frequency": 13, "Notes": 40}

WEEK = {"mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3, "thurs": 3,
        "fri": 4, "sat": 5, "sun": 6}
FULL = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4,
        "saturday": 5, "sunday": 6}


def clean(s: str) -> str:
    """Obvious spacing cleanup only — trim, collapse runs of spaces, drop leading
    bullet/dash. Capitalization left as-is to avoid damaging proper nouns/abbrevs."""
    s = (s or "").strip()
    s = re.sub(r"^[\s\-–•*]+", "", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()


def day_key(v: str) -> int:
    low = clean(v).lower()
    if low in FULL:
        return FULL[low]
    return WEEK.get(low.split("-")[0].strip(), 99)


def time_key(v: str) -> int:
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*([AP]M)?\s*$", (v or "").strip(), re.I)
    if not m:
        return 10 ** 9
    h = int(m.group(1)) % 12
    if (m.group(3) or "").upper() == "PM":
        h += 12
    return h * 60 + int(m.group(2))


def build_one(src_path: str) -> dict:
    with open(src_path, newline="", encoding="utf-8-sig") as f:
        src = list(csv.DictReader(f))

    rows = []
    for r in src:
        start = clean(r.get("start_time", ""))
        end = clean(r.get("end_time", ""))
        loc = clean(r.get("location", ""))
        rows.append([
            clean(r.get("employee_name", "")),
            clean(r.get("day_of_week", "")),
            start, end,
            f"{start} – {end}" if start and end else (start or end),
            loc,
            classify_area(clean_location(loc)),
            clean(r.get("task", "")),
            clean(r.get("frequency", "")),
            clean(r.get("notes", "")),
        ])
    rows.sort(key=lambda x: (x[0].lower(), day_key(x[1]), time_key(x[2]), x[5].lower()))

    wb = Workbook()
    ws = wb.active
    ws.title = "Clean Schedule"
    ws.sheet_view.showGridLines = False

    head_fill = PatternFill("solid", fgColor="1A1A1A")
    head_font = Font(bold=True, color="FFFFFF")
    stripe = PatternFill("solid", fgColor="F6F6F6")
    thin = Side(style="thin", color="E2E2E2")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    wrap = Alignment(wrap_text=True, vertical="top")
    plain = Alignment(vertical="top")

    for j, h in enumerate(HEADERS, start=1):
        c = ws.cell(1, j, h)
        c.fill = head_fill; c.font = head_font; c.border = border
        c.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 20

    for i, row in enumerate(rows, start=2):
        for j, val in enumerate(row, start=1):
            c = ws.cell(i, j, val)
            c.border = border
            c.alignment = wrap if HEADERS[j - 1] in WRAP_COLS else plain
            if i % 2 == 0:
                c.fill = stripe

    for j, h in enumerate(HEADERS, start=1):
        ws.column_dimensions[get_column_letter(j)].width = WIDTHS[h]

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(HEADERS))}{len(rows) + 1}"

    base = os.path.basename(src_path).replace("_cleaning_responsibilities.csv", "")
    out_path = os.path.join(OUT_DIR, f"{base}_Clean_Schedule.xlsx")
    try:
        wb.save(out_path)
    except PermissionError:
        return {"name": base, "error": "file open/locked — close it and rerun"}

    return {
        "name": base,
        "path": os.path.relpath(out_path, REPO),
        "rows": len(rows),
        "employees": len({r[0] for r in rows if r[0]}),
        "locations": len({r[5] for r in rows if r[5]}),
        "unknown_freq": sum(1 for r in rows if r[8].lower() == "unknown"),
        "blank_task": sum(1 for r in rows if not r[7]),
        "other_area": sum(1 for r in rows if r[6] == "Other / Unknown"),
    }


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(SRC_DIR, "*_cleaning_responsibilities.csv")))
    if not files:
        print("No source schedules found in", SRC_DIR)
        return

    stats = [build_one(p) for p in files]

    print(f"output folder: {os.path.relpath(OUT_DIR, REPO)}")
    print(f"workbooks created: {sum(1 for s in stats if 'error' not in s)} of {len(stats)}")
    print(f"{'Property':<16}{'rows':>6}{'emps':>6}{'locs':>6}{'unkFreq':>9}{'blankTask':>11}{'OtherArea':>11}")
    for s in stats:
        if "error" in s:
            print(f"{s['name']:<16}  ERROR: {s['error']}")
            continue
        print(f"{s['name']:<16}{s['rows']:>6}{s['employees']:>6}{s['locations']:>6}"
              f"{s['unknown_freq']:>9}{s['blank_task']:>11}{s['other_area']:>11}")
    ok = [s for s in stats if "error" not in s]
    print(f"\nTOTAL rows across {len(ok)} workbooks: {sum(s['rows'] for s in ok)}")


if __name__ == "__main__":
    main()
