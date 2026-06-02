"""Add the 'Coverage Structure Review' worksheet to Parker_Operations_Workbook.xlsx.

STRICTLY DESCRIPTIVE. This sheet answers "How is cleaning coverage distributed
across Parker?" — never "How should Parker be optimized?". It contains no
optimization, no redundancy analysis, no effort/SLA/sqft inference, and makes no
recommendations. It reuses the approved area-type classification from the other
deliverables so categories stay consistent.

Idempotent: re-running replaces the sheet without touching the other six.
"""
from __future__ import annotations

import os
import sys

import pandas as pd
from openpyxl import load_workbook
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_parker_workbook import (  # noqa: E402
    OUTPUT_XLSX, REPO, compress_days, expand_days, load_parker, needs_review,
)


def _resolve_workbook() -> str:
    """Find the workbook wherever it lives (it may have been moved/organized)."""
    import glob
    candidates = [
        OUTPUT_XLSX,
        os.path.join(REPO, "Working_excels", "Parker_Operations_Workbook.xlsx"),
        os.path.join(REPO, "output", "Parker_Operations_Workbook.xlsx"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    hits = [p for p in glob.glob(os.path.join(REPO, "**", "Parker_Operations_Workbook.xlsx"),
                                 recursive=True) if ".git" not in p]
    if hits:
        return hits[0]
    raise FileNotFoundError(
        "Parker_Operations_Workbook.xlsx not found — run build_parker_workbook.py first.")


WORKBOOK = _resolve_workbook()
SHEET = "Coverage Structure Review"
SPAN = 6  # columns spanned by section-header merges
BUNDLE_MARKERS = (",", "&", " etc", "/")

# Styles (minimal colour, per spec)
TITLE_FONT = Font(bold=True, size=14, color="1F4E78")
BANNER_FONT = Font(italic=True, size=10, color="595959")
SECTION_FONT = Font(bold=True, size=12, color="1F4E78")
SECTION_FILL = PatternFill("solid", fgColor="D9E1F2")
SUBTITLE_FONT = Font(italic=True, size=9, color="7F7F7F")
HEAD_FONT = Font(bold=True, color="FFFFFF")
HEAD_FILL = PatternFill("solid", fgColor="1F4E78")
THIN = Side(style="thin", color="D9D9D9")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def is_bundled(task: str) -> bool:
    return any(m in (task or "").lower() for m in BUNDLE_MARKERS)


# ---------------------------------------------------------------------------
# Sheet writer with width tracking + count ranges for conditional formatting
# ---------------------------------------------------------------------------
class SheetBuilder:
    def __init__(self, ws):
        self.ws = ws
        self.row = 1
        self.widths: dict[int, int] = {}
        self.count_ranges: list[tuple[str, int, int]] = []
        self.layout_rows: set[int] = set()

    def _w(self, col_idx: int, text: str) -> None:
        longest = max((len(p) for p in str(text).split("\n")), default=0)
        self.widths[col_idx] = max(self.widths.get(col_idx, 0), longest)

    def blank(self, n: int = 1) -> None:
        self.row += n

    def title(self, text: str, banner: str) -> None:
        ws = self.ws
        ws.merge_cells(start_row=self.row, start_column=1, end_row=self.row, end_column=SPAN)
        c = ws.cell(self.row, 1, text); c.font = TITLE_FONT
        self.layout_rows.add(self.row); self.row += 1
        ws.merge_cells(start_row=self.row, start_column=1, end_row=self.row, end_column=SPAN)
        c = ws.cell(self.row, 1, banner); c.font = BANNER_FONT
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[self.row].height = 28
        self.layout_rows.add(self.row); self.row += 1
        self.blank()

    def section(self, text: str, subtitle: str) -> None:
        ws = self.ws
        ws.merge_cells(start_row=self.row, start_column=1, end_row=self.row, end_column=SPAN)
        c = ws.cell(self.row, 1, text); c.font = SECTION_FONT; c.fill = SECTION_FILL
        self.layout_rows.add(self.row); self.row += 1
        ws.merge_cells(start_row=self.row, start_column=1, end_row=self.row, end_column=SPAN)
        c = ws.cell(self.row, 1, subtitle); c.font = SUBTITLE_FONT
        c.alignment = Alignment(wrap_text=True, vertical="top")
        self.layout_rows.add(self.row); self.row += 1

    def table(self, headers: list[str], rows: list[list], count_cols: set[int] | None = None,
              wrap_cols: set[int] | None = None) -> None:
        ws = self.ws
        count_cols = count_cols or set()
        wrap_cols = wrap_cols or set()
        # header
        for j, h in enumerate(headers, start=1):
            c = ws.cell(self.row, j, h); c.font = HEAD_FONT; c.fill = HEAD_FILL
            c.alignment = Alignment(vertical="center"); c.border = BORDER
            self._w(j, h)
        header_row = self.row
        self.row += 1
        first_data = self.row
        for r in rows:
            for j, v in enumerate(r, start=1):
                c = ws.cell(self.row, j, v)
                c.border = BORDER
                if j in wrap_cols:
                    c.alignment = Alignment(wrap_text=True, vertical="top")
                self._w(j, v)
            self.row += 1
        last_data = self.row - 1
        # record count columns for data-bar conditional formatting
        if last_data >= first_data:
            for j in count_cols:
                letter = get_column_letter(j)
                self.count_ranges.append((letter, first_data, last_data))
        return header_row

    def finalize(self, freeze_at: str = "A4") -> None:
        ws = self.ws
        ws.freeze_panes = freeze_at
        for j, w in self.widths.items():
            ws.column_dimensions[get_column_letter(j)].width = min(max(w + 2, 10), 60)
        for letter, r1, r2 in self.count_ranges:
            rule = DataBarRule(start_type="min", end_type="max", color="8EAADB",
                               showValue=True, minLength=None, maxLength=None)
            ws.conditional_formatting.add(f"{letter}{r1}:{letter}{r2}", rule)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def main() -> None:
    df = load_parker()

    g = df.groupby("location")
    emps_by_loc = g["employee_name"].apply(lambda s: sorted(set(s)))
    cnt_by_loc = emps_by_loc.apply(len)
    assign_by_loc = g.size()
    area_by_loc = g["area_type"].agg(lambda s: s.mode().iat[0])
    tasks_by_loc = g["task"].nunique()
    freqs_by_loc = g["frequency"].apply(lambda s: sorted(set(s)))
    blocks_by_loc = g.apply(
        lambda x: x[["day_of_week", "start_time", "end_time"]].drop_duplicates().shape[0],
        include_groups=False,
    )
    bundled_by_loc = g["task"].apply(lambda s: int(s.apply(is_bundled).sum()))

    locations = list(cnt_by_loc.index)
    single = [l for l in locations if cnt_by_loc[l] == 1]
    multi = [l for l in locations if cnt_by_loc[l] > 1]
    unknown_owner = [l for l, es in emps_by_loc.items()
                     if all((not e) or "all staff" in e.lower() or "not stated" in e.lower()
                            for e in es)]
    max_share = int(cnt_by_loc.max())
    most_shared_n = int((cnt_by_loc == max_share).sum())
    isolated = [l for l in single if blocks_by_loc[l] == 1]

    def days_for(sub: pd.DataFrame) -> str:
        d = set()
        for v in sub["day_of_week"]:
            d.update(expand_days(v))
        return compress_days(d)

    wb = load_workbook(WORKBOOK)
    if SHEET in wb.sheetnames:
        del wb[SHEET]
    ws = wb.create_sheet(SHEET)
    b = SheetBuilder(ws)

    b.title(
        "Coverage Structure Review — The Parker",
        "Descriptive coverage map. Answers: 'How is cleaning coverage distributed across "
        "Parker?'  It does NOT answer 'How should Parker be optimized?'. No square footage, "
        "service standards (SLA), task times, or performance data are used. Sections 1-4, 6-7 "
        "are facts; Section 5 lists descriptive patterns to look at later, not findings.",
    )

    # Section 1 — Coverage Summary -----------------------------------------
    b.section("Section 1 — Coverage Summary",
              "Counts only. How responsibility is spread across the property's locations.")
    b.table(
        ["Metric", "Count", "Detail"],
        [
            ["Total Unique Locations", len(locations), ""],
            ["Single-Employee Locations", len(single), "serviced by exactly one employee"],
            ["Multi-Employee Locations", len(multi), "serviced by two or more employees"],
            ["Locations With Unknown Ownership", len(unknown_owner),
             "no rows with a blank/placeholder employee"],
            ["Average Employees Per Location", round(float(cnt_by_loc.mean()), 2),
             "mean distinct employees per location"],
            ["Most Shared Locations", most_shared_n,
             f"location(s) reaching the maximum of {max_share} employees"],
            ["Most Isolated Locations", len(isolated),
             "single employee and a single schedule block"],
        ],
        wrap_cols={3},
    )
    b.blank()

    # Section 2 — Single Employee Coverage ---------------------------------
    b.section("Section 2 — Single Employee Coverage",
              "Locations serviced by only one employee across the schedule. "
              "Describes concentration of responsibility — not labelled as risk.")
    rows = []
    for loc in sorted(single, key=lambda l: (-assign_by_loc[l], l)):
        sub = df[df["location"] == loc]
        unk = int((sub["frequency"].str.lower() == "unknown").sum())
        note = []
        if needs_review(loc, area_by_loc[loc]):
            note.append("ambiguous / unclassified name")
        if unk:
            note.append(f"{unk} Unknown-frequency assignment(s)")
        rows.append([loc, area_by_loc[loc], emps_by_loc[loc][0],
                     int(assign_by_loc[loc]), days_for(sub), "; ".join(note)])
    b.table(["Location", "Area Type", "Employee", "Assignment Count", "Days Covered", "Notes"],
            rows, count_cols={4}, wrap_cols={6})
    b.blank()

    # Section 3 — Shared Coverage ------------------------------------------
    b.section("Section 3 — Shared Coverage",
              "Locations serviced by multiple employees, sorted by employee count then "
              "assignment count.")
    rows = []
    for loc in multi:
        rows.append([loc, area_by_loc[loc], int(cnt_by_loc[loc]),
                     ", ".join(emps_by_loc[loc]), int(assign_by_loc[loc])])
    rows.sort(key=lambda r: (-r[2], -r[4], r[0]))
    b.table(["Location", "Area Type", "Employee Count", "Employees", "Assignment Count"],
            rows, count_cols={3, 5}, wrap_cols={4})
    b.blank()

    # Section 4 — Area Ownership Distribution ------------------------------
    b.section("Section 4 — Area Ownership Distribution",
              "Each employee's footprint within the property. Descriptive counts only.")
    rows = []
    for emp in sorted(df["employee_name"].unique()):
        sub = df[df["employee_name"] == emp]
        emp_locs = set(sub["location"])
        shared = sum(1 for l in emp_locs if cnt_by_loc[l] > 1)
        exclusive = sum(1 for l in emp_locs if cnt_by_loc[l] == 1)
        rows.append([emp, sub["location"].nunique(), sub["area_type"].nunique(),
                     len(sub), shared, exclusive])
    rows.sort(key=lambda r: -r[3])
    b.table(["Employee", "Distinct Locations", "Distinct Area Types", "Assignment Count",
             "Shared Locations", "Exclusive Locations"],
            rows, count_cols={2, 3, 4, 5, 6})
    b.blank()

    # Section 5 — Candidate Review Items -----------------------------------
    b.section("Section 5 — Candidate Review Items",
              "Descriptive schedule patterns that may warrant future review. Every row is a "
              "'Candidate Review Item' — a pattern to look at later, NOT a finding of any kind.")
    rows = []
    for loc in locations:
        sub = df[df["location"] == loc]
        patterns, evidence = [], []
        if cnt_by_loc[loc] > 1:
            patterns.append("Serviced by multiple employees")
            evidence.append(f"{cnt_by_loc[loc]} employees")
        if blocks_by_loc[loc] > 1:
            patterns.append("Appears in multiple schedule blocks")
            evidence.append(f"{blocks_by_loc[loc]} schedule blocks")
        if any(f.lower() == "daily" for f in freqs_by_loc[loc]):
            patterns.append("Includes daily-frequency assignments")
            evidence.append("Daily present")
        if needs_review(loc, area_by_loc[loc]):
            patterns.append("Ambiguous or unclassified location name")
            evidence.append(f"area type = {area_by_loc[loc]}")
        if not patterns:
            continue  # only list locations matching at least one pattern
        if bundled_by_loc[loc]:
            patterns.append("Bundled task description(s) present")
            evidence.append(f"{bundled_by_loc[loc]} bundled task row(s)")
        evidence.append(f"{int(assign_by_loc[loc])} assignments total")
        rows.append(["Candidate Review Item", loc, "; ".join(patterns), "; ".join(evidence)])
    rows.sort(key=lambda r: r[1])
    b.table(["Review Type", "Location", "Description", "Evidence"], rows,
            wrap_cols={3, 4})
    b.blank()

    # Section 6 — Coverage Network Summary ---------------------------------
    b.section("Section 6 — Coverage Network Summary",
              "Rankings only (top 5 each). No recommendations.")
    emp_loc_rank = df.groupby("employee_name")["location"].nunique().sort_values(ascending=False)
    emp_area_rank = df.groupby("employee_name")["area_type"].nunique().sort_values(ascending=False)

    def top(series, n=5):
        return "\n".join(f"{i+1}. {name}  ({int(val)})"
                         for i, (name, val) in enumerate(series.head(n).items()))

    b.table(
        ["Ranking", "Top 5"],
        [
            ["Most Shared Locations (by employee count)", top(cnt_by_loc.sort_values(ascending=False))],
            ["Most Frequently Scheduled Locations", top(assign_by_loc.sort_values(ascending=False))],
            ["Employees Covering The Most Locations", top(emp_loc_rank)],
            ["Employees Covering The Most Area Types", top(emp_area_rank)],
        ],
        wrap_cols={2},
    )
    b.blank()

    # Section 7 — Data Quality Notes ---------------------------------------
    b.section("Section 7 — Data Quality Notes",
              "Limitations of this descriptive analysis — what makes some patterns uncertain.")
    # naming inconsistencies: same case-insensitive name, >1 raw spelling
    norm = df["location"].str.strip().str.lower()
    clusters = df.assign(_n=norm).groupby("_n")["location"].nunique()
    incons = clusters[clusters > 1]
    example_pair = ""
    if len(incons):
        variants = sorted(df[norm == incons.index[0]]["location"].unique())
        example_pair = " / ".join(variants[:2])
    ambiguous_locs = [l for l in locations if needs_review(l, area_by_loc[l])]
    bundled_rows = int(df["task"].apply(is_bundled).sum())
    bundled_locs = int((bundled_by_loc > 0).sum())
    unknown_freq_rows = int((df["frequency"].str.lower() == "unknown").sum())
    review_rows = int(df.apply(
        lambda r: needs_review(r["location"], area_by_loc[r["location"]])
        or r["frequency"].lower() == "unknown", axis=1).sum())
    b.table(
        ["Item", "Count", "Detail / Example"],
        [
            ["Location naming inconsistencies (clusters)", len(incons),
             f"e.g. {example_pair}" if example_pair else "none detected"],
            ["Ambiguous / unclassified locations", len(ambiguous_locs),
             "surface-only or building-wide names (e.g. Carpets, 38th Floor)"],
            ["Bundled task descriptions (assignment rows)", bundled_rows,
             f"across {bundled_locs} locations; one cell lists several actions"],
            ["Missing frequency information (Unknown)", unknown_freq_rows,
             "frequency recorded as 'Unknown'"],
            ["Schedule records requiring manual review", review_rows,
             "rows with ambiguous location or Unknown frequency"],
        ],
        count_cols={2}, wrap_cols={3},
    )

    b.finalize(freeze_at="A4")
    try:
        wb.save(WORKBOOK)
    except PermissionError:
        print("WARNING: could not save — Parker_Operations_Workbook.xlsx is open in Excel. "
              "Close it and rerun.")
        return

    print(f"Added worksheet '{SHEET}' to {os.path.relpath(WORKBOOK, REPO)}")
    print(f"  Section 1 metrics: {len(locations)} locations | "
          f"{len(single)} single-employee | {len(multi)} multi-employee | "
          f"{len(unknown_owner)} unknown-ownership")
    print(f"  Section 2 rows: {len(single)} | Section 3 rows: {len(multi)} | "
          f"Section 4 rows: {df['employee_name'].nunique()}")
    print(f"  Section 5 candidate review items: {len(rows) if False else sum(1 for l in locations if (cnt_by_loc[l]>1 or blocks_by_loc[l]>1 or any(f.lower()=='daily' for f in freqs_by_loc[l]) or needs_review(l, area_by_loc[l])))}")
    print(f"  Section 7: {len(incons)} naming clusters, {len(ambiguous_locs)} ambiguous, "
          f"{unknown_freq_rows} Unknown-frequency rows")


if __name__ == "__main__":
    main()
