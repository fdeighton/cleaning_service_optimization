"""Build Parker_Operations_Workbook_Clean.xlsx — an executive-friendly rebuild.

Built fresh from the Parker schedule data (single source of truth) so the original
workbook is never overwritten and content stays consistent with the other
deliverables. Strictly descriptive: scheduled volume, ownership footprint, and
exclusive-vs-shared coverage. No labour hours, workload, optimization, or
efficiency claims anywhere.

Final sheet order:
  1. Start Here          5. Exclusive vs Shared Coverage
  2. Executive Summary   6. Area Inventory Request
  3. Volume by Area      7. Raw Schedule Detail
  4. Ownership Matrix
"""
from __future__ import annotations

import os
import re
import sys

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.formatting.rule import ColorScaleRule, DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_parker_workbook import (  # noqa: E402
    REPO, compress_days, expand_days, load_parker, needs_review,
)

OUT_DIR = os.path.join(REPO, "Working_excels") if os.path.isdir(os.path.join(REPO, "Working_excels")) else REPO
OUT_PATH = os.path.join(OUT_DIR, "Parker_Operations_Workbook_Clean.xlsx")

# ---- Fitzrovia brand theme (orange + black) -------------------------------
# Every sheet reads from these constants, so one edit re-themes the whole
# workbook. Swap the hex values for exact brand codes if you have them.
PRIMARY = "1A1A1A"     # near-black — titles, table headers, sheet tabs
ACCENT = "E8751A"      # orange — KPI values, chart bars, data bars, highlights
ACCENT_DK = "C25E12"   # deeper orange — KPI numbers
BAND = "FBE3D2"        # light orange — section header bands
CARD_BG = "FDF1E7"     # pale orange — KPI cards
STRIPE = "FDF7F1"      # very light orange — banded table rows
HIGHLIGHT = "FAD7B4"   # soft orange — highlighted rows (top 10)
BORDER_C = "E0D8D0"    # warm grey — borders
NOTE_C = "595959"      # grey — notes
WHITE = "FFFFFF"

CARD_FILL = PatternFill("solid", fgColor=CARD_BG)
STRIPE_FILL = PatternFill("solid", fgColor=STRIPE)
SECTION_FILL = PatternFill("solid", fgColor=BAND)
HEAD_FILL = PatternFill("solid", fgColor=PRIMARY)
HIGHLIGHT_FILL = PatternFill("solid", fgColor=HIGHLIGHT)
TITLE_FONT = Font(bold=True, size=16, color=PRIMARY)
SECTION_FONT = Font(bold=True, size=12, color=PRIMARY)
NOTE_FONT = Font(italic=True, size=9, color=NOTE_C)
HEAD_FONT = Font(bold=True, color=WHITE)
CARD_LABEL_FONT = Font(size=9, color=NOTE_C)
CARD_VALUE_FONT = Font(bold=True, size=20, color=ACCENT_DK)
BOLD = Font(bold=True)
THIN = Side(style="thin", color=BORDER_C)
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center")


class Sheet:
    """Row-cursor writer with width tracking, tables, KPI cards, charts, CF."""

    def __init__(self, wb: Workbook, name: str, span: int = 6):
        self.ws = wb.create_sheet(name)
        self.ws.sheet_view.showGridLines = False
        self.ws.sheet_properties.tabColor = ACCENT  # consistent gold tab strip
        self.span = span
        self.row = 1
        self.widths: dict[int, int] = {}
        self.fixed: set[int] = set()  # columns with a fixed (wrap) width

    # -- width bookkeeping --
    def _w(self, col: int, text) -> None:
        if col in self.fixed:
            return
        longest = max((len(p) for p in str(text).split("\n")), default=0)
        self.widths[col] = max(self.widths.get(col, 0), longest)

    def _merge(self, row: int, cols: int):
        self.ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=cols)

    # -- layout helpers --
    def title(self, text: str):
        self._merge(self.row, self.span)
        c = self.ws.cell(self.row, 1, text); c.font = TITLE_FONT
        self.row += 1

    def note(self, text: str, height: int | None = None):
        self._merge(self.row, self.span)
        c = self.ws.cell(self.row, 1, text); c.font = NOTE_FONT; c.alignment = WRAP
        if height:
            self.ws.row_dimensions[self.row].height = height
        self.row += 1

    def section(self, text: str):
        self._merge(self.row, self.span)
        c = self.ws.cell(self.row, 1, text); c.font = SECTION_FONT; c.fill = SECTION_FILL
        c.alignment = Alignment(vertical="center")
        self.ws.row_dimensions[self.row].height = 20
        self.row += 1

    def blank(self, n: int = 1):
        self.row += n

    def kpi_cards(self, cards: list[tuple[str, object]], per_row: int = 3, card_w: int = 2):
        """Render KPI cards in a grid; each card = label cell over a big value cell."""
        start = self.row
        for idx, (label, value) in enumerate(cards):
            r = idx // per_row
            col = 1 + (idx % per_row) * card_w
            top = start + r * 3
            lc = col + card_w - 1
            self.ws.merge_cells(start_row=top, start_column=col, end_row=top, end_column=lc)
            self.ws.merge_cells(start_row=top + 1, start_column=col, end_row=top + 1, end_column=lc)
            a = self.ws.cell(top, col, label); a.font = CARD_LABEL_FONT
            a.fill = CARD_FILL; a.alignment = Alignment(horizontal="center", vertical="bottom")
            b = self.ws.cell(top + 1, col, value); b.font = CARD_VALUE_FONT
            b.fill = CARD_FILL; b.alignment = CENTER
            for rr in (top, top + 1):
                for cc in range(col, lc + 1):
                    self.ws.cell(rr, cc).border = BORDER
                    if self.ws.cell(rr, cc).fill.fgColor.rgb in (None, "00000000"):
                        self.ws.cell(rr, cc).fill = CARD_FILL
            for cc in range(col, lc + 1):
                self.widths[cc] = max(self.widths.get(cc, 0), 14)
        rows_used = ((len(cards) - 1) // per_row + 1) * 3
        self.row = start + rows_used + 1

    def table(self, headers, rows, *, count_cols=None, wrap_cols=None,
              highlight_first=0, make_filter=False, start_col=1, banded=True):
        count_cols = count_cols or set()
        wrap_cols = wrap_cols or set()
        ws = self.ws
        hr = self.row
        for j, h in enumerate(headers):
            col = start_col + j
            c = ws.cell(hr, col, h); c.font = HEAD_FONT; c.fill = HEAD_FILL
            c.alignment = Alignment(vertical="center", wrap_text=True); c.border = BORDER
            self._w(col, h)
        ws.row_dimensions[hr].height = 20
        self.row += 1
        first = self.row
        for ri, r in enumerate(rows):
            stripe = banded and (ri % 2 == 1)
            for j, v in enumerate(r):
                col = start_col + j
                c = ws.cell(self.row, col, v); c.border = BORDER
                if col in wrap_cols:
                    c.alignment = WRAP
                    self.fixed.add(col)
                    ws.column_dimensions[get_column_letter(col)].width = 38
                else:
                    self._w(col, v)
                if ri < highlight_first:
                    c.fill = HIGHLIGHT_FILL
                elif stripe:
                    c.fill = STRIPE_FILL
            self.row += 1
        last = self.row - 1
        # filters via the sheet auto-filter (one per sheet — set on the main table)
        if make_filter and last >= first:
            ws.auto_filter.ref = (f"{get_column_letter(start_col)}{hr}:"
                                  f"{get_column_letter(start_col + len(headers) - 1)}{last}")
        for j in count_cols:
            if last >= first:
                col = get_column_letter(j)
                ws.conditional_formatting.add(
                    f"{col}{first}:{col}{last}",
                    DataBarRule(start_type="min", end_type="max", color=ACCENT, showValue=True))
        return hr, first, last

    def color_scale(self, c1: int, r1: int, c2: int, r2: int):
        rng = f"{get_column_letter(c1)}{r1}:{get_column_letter(c2)}{r2}"
        self.ws.conditional_formatting.add(rng, ColorScaleRule(
            start_type="num", start_value=0, start_color="FFFFFF",
            end_type="max", end_color=ACCENT))

    def bar_chart(self, anchor: str, title: str, hr: int, first: int, last: int,
                  val_col: int, cat_col: int, horizontal=False):
        try:
            ch = BarChart(); ch.type = "bar" if horizontal else "col"
            ch.title = title; ch.legend = None
            ch.height = 7.0; ch.width = 12.5; ch.gapWidth = 60
            data = Reference(self.ws, min_col=val_col, min_row=hr, max_row=last)
            cats = Reference(self.ws, min_col=cat_col, min_row=first, max_row=last)
            ch.add_data(data, titles_from_data=True); ch.set_categories(cats)
            if ch.series:
                ch.series[0].graphicalProperties = GraphicalProperties(solidFill=ACCENT)
            # Horizontal bars: show the largest at the top (Excel defaults to bottom).
            if horizontal:
                ch.y_axis.scaling.orientation = "maxMin"
                ch.x_axis.delete = False
                ch.y_axis.delete = False
            self.ws.add_chart(ch, anchor)
        except Exception as e:  # never let a chart break the build
            print(f"  (chart '{title}' skipped: {e})")

    def finalize(self, freeze: str | None = None):
        if freeze:
            self.ws.freeze_panes = freeze
        for j, w in self.widths.items():
            self.ws.column_dimensions[get_column_letter(j)].width = min(max(w + 2, 9), 55)


# ===========================================================================
# Data preparation
# ===========================================================================
def prepare(df: pd.DataFrame):
    g = df.groupby("location")
    d = {}
    d["emps_by_loc"] = g["employee_name"].apply(lambda s: sorted(set(s)))
    d["cnt_emps"] = d["emps_by_loc"].apply(len)
    d["assign"] = g.size()
    d["area"] = g["area_type"].agg(lambda s: s.mode().iat[0])
    d["tasks"] = g["task"].nunique()
    d["freqs"] = g["frequency"].apply(lambda s: sorted(set(s)))
    d["locations"] = list(d["assign"].index)
    d["single"] = [l for l in d["locations"] if d["cnt_emps"][l] == 1]
    d["shared"] = [l for l in d["locations"] if d["cnt_emps"][l] > 1]
    return d


# ===========================================================================
# Sheet builders
# ===========================================================================
def build_start_here(wb, df, d):
    s = Sheet(wb, "Start Here")
    s.title("The Parker — Cleaning Operations Workbook")
    s.note("An executive view of the scheduled cleaning plan. Plain-English summary of "
           "what is cleaned, who is responsible, and how coverage is shared.", height=30)
    s.blank()

    s.section("Property")
    s.note("The Parker (single property).")
    s.blank()

    s.section("What this workbook shows")
    for t in ["• How much scheduled cleaning activity each area and task represents (counts).",
              "• Which employee is associated with which areas (ownership footprint).",
              "• Which locations are covered by one employee vs. several (exclusive vs. shared)."]:
        s.note(t)
    s.blank()

    s.section("What this workbook does NOT show")
    for t in ["• Labour hours, effort, or workload — counts are scheduled references, not time.",
              "• Whether any area is over- or under-cleaned.",
              "• Cost, staffing adequacy, or optimization recommendations."]:
        s.note(t)
    s.blank()

    s.section("Three key questions answered")
    for t in ["1. What work is most common?  →  Executive Summary, Volume by Area",
              "2. Who owns which areas?  →  Ownership Matrix",
              "3. Which areas are exclusive vs shared?  →  Exclusive vs Shared Coverage"]:
        s.note(t)
    s.blank()

    s.section("Three limitations (needed for deeper analysis)")
    for t in ["• No square footage — cannot normalise or compare area sizes.",
              "• No standard task times — cannot convert counts into effort or hours.",
              "• No SLA / service standard — cannot judge whether cadence is appropriate."]:
        s.note(t)
    s.blank()

    s.section("Navigation")
    nav = [
        ["Volume", "Executive Summary", "KPIs and the top tasks, areas, and employee footprints at a glance"],
        ["Volume", "Volume by Area", "Where scheduled cleaning activity is concentrated"],
        ["Ownership", "Ownership Matrix", "Which employee is associated with which areas"],
        ["Coverage", "Exclusive vs Shared Coverage", "Locations covered by one vs. multiple employees"],
        ["Data Request", "Area Inventory Request", "Blank square-footage request to send to Development"],
        ["Detail", "Raw Schedule Detail", "The full row-by-row schedule (supporting detail)"],
    ]
    s.table(["Section", "Sheet", "What to Look For"], nav, wrap_cols={3})
    s.finalize()


def build_executive_summary(wb, df, d):
    s = Sheet(wb, "Executive Summary", span=6)
    s.title("Executive Summary — The Parker")
    s.note("Counts are scheduled assignment references, not labour hours. Descriptive only.")
    s.blank()

    s.kpi_cards([
        ("Total Schedule Assignments", len(df)),
        ("Distinct Employees", df["employee_name"].nunique()),
        ("Distinct Locations", df["location"].nunique()),
        ("Distinct Tasks", df["task"].nunique()),
        ("Single-Employee Locations", len(d["single"])),
        ("Shared Locations", len(d["shared"])),
    ], per_row=3, card_w=2)

    # A. Top 10 locations
    s.section("A. Top 10 Locations by Assignment Count")
    top_loc = d["assign"].sort_values(ascending=False).head(10)
    hr, fr, lr = s.table(["Location", "Assignment Count"],
                         [[k, int(v)] for k, v in top_loc.items()], count_cols={2})
    s.bar_chart("H" + str(hr), "Top 10 Locations", hr, fr, lr, 2, 1, horizontal=True)
    s.row = max(s.row, lr + 16)
    s.blank()

    # B. Top 10 tasks
    s.section("B. Top 10 Tasks by Assignment Count")
    top_task = df["task"].value_counts().head(10)
    s.table(["Task", "Assignment Count"],
            [[k, int(v)] for k, v in top_task.items()], count_cols={2}, wrap_cols={1})
    s.blank()

    # C. Assignment count by area type
    s.section("C. Assignment Count by Area Type")
    by_area = df["area_type"].value_counts()
    hr, fr, lr = s.table(["Area Type", "Assignment Count"],
                         [[k, int(v)] for k, v in by_area.items()], count_cols={2})
    s.bar_chart("H" + str(hr), "Assignments by Area Type", hr, fr, lr, 2, 1, horizontal=True)
    s.row = max(s.row, lr + 16)
    s.blank()

    # D. Frequency distribution
    s.section("D. Frequency Distribution")
    by_freq = df["frequency"].value_counts()
    hr, fr, lr = s.table(["Frequency", "Assignment Count"],
                         [[k, int(v)] for k, v in by_freq.items()], count_cols={2})
    s.bar_chart("H" + str(hr), "Assignments by Frequency", hr, fr, lr, 2, 1)
    s.row = max(s.row, lr + 16)
    s.blank()

    # E. Employee footprint
    s.section("E. Employee Footprint Summary")
    rows = []
    for emp in sorted(df["employee_name"].unique()):
        sub = df[df["employee_name"] == emp]
        elocs = set(sub["location"])
        excl = sum(1 for l in elocs if d["cnt_emps"][l] == 1)
        shar = sum(1 for l in elocs if d["cnt_emps"][l] > 1)
        rows.append([emp, len(sub), sub["location"].nunique(),
                     sub["area_type"].nunique(), excl, shar])
    rows.sort(key=lambda r: -r[1])
    s.table(["Employee", "Assignment Count", "Distinct Locations", "Distinct Area Types",
             "Exclusive Locations", "Shared Locations"], rows, count_cols={2, 3, 4, 5, 6},
            make_filter=True)
    s.finalize(freeze="A3")


def build_volume_by_area(wb, df, d):
    s = Sheet(wb, "Volume by Area", span=6)
    s.title("Volume by Area — The Parker")
    s.note("Where scheduled cleaning activity is concentrated. Counts are scheduled assignment "
           "references, not labour hours. High volume does NOT imply over-cleaning.", height=30)
    s.blank()

    top_loc = d["assign"].sort_values(ascending=False)
    by_area = df["area_type"].value_counts()
    one_assign = int((d["assign"] == 1).sum())
    unclear = int((d["area"] == "Other / Unknown").sum())
    s.section("At a glance")
    s.table(["Metric", "Value"], [
        ["Highest-volume location", f"{top_loc.index[0]}  ({int(top_loc.iloc[0])})"],
        ["Highest-volume area type", f"{by_area.index[0]}  ({int(by_area.iloc[0])})"],
        ["Locations with only one assignment", one_assign],
        ["Locations with unknown/unclear area type", unclear],
    ], make_filter=False, wrap_cols={2})
    s.blank()

    s.section("Assignment Count by Area Type")
    s.table(["Area Type", "Locations", "Assignment Count"],
            [[a, int((d["area"] == a).sum()), int(by_area[a])] for a in by_area.index],
            count_cols={3})
    s.blank()

    s.section("All Locations by Assignment Count (top 10 highlighted)")
    rows = []
    for loc in top_loc.index:
        rows.append([loc, d["area"][loc], int(d["assign"][loc]), int(d["tasks"][loc]),
                     ", ".join(d["emps_by_loc"][loc]), ", ".join(d["freqs"][loc])])
    hr, fr, lr = s.table(
        ["Location", "Area Type", "Assignment Count", "Task Count",
         "Employees Assigned", "Frequency Types"],
        rows, count_cols={3}, wrap_cols={5, 6}, highlight_first=10, make_filter=True)
    s.finalize(freeze=f"A{fr}")


def build_ownership_matrix(wb, df, d):
    s = Sheet(wb, "Ownership Matrix", span=8)
    s.title("Ownership Matrix — The Parker")
    s.note("Which employee is associated with which areas. Counts represent scheduled "
           "assignment references, not labour hours.", height=28)
    s.blank()

    employees = sorted(df["employee_name"].unique())
    piv = (df.pivot_table(index="location", columns="employee_name",
                          aggfunc="size", fill_value=0))
    piv["Total"] = piv.sum(axis=1)
    area = d["area"]
    piv["Area Type"] = [area[l] for l in piv.index]
    piv = piv.sort_values(["Area Type", "Total"], ascending=[True, False])

    headers = ["Location", "Area Type"] + employees + ["Total"]
    rows = []
    for loc, r in piv.iterrows():
        rows.append([loc, r["Area Type"]] + [int(r[e]) for e in employees] + [int(r["Total"])])
    hr, fr, lr = s.table(headers, rows, make_filter=True, wrap_cols=set())
    # color-scale intensity over employee columns + Total (cols 3..3+len(emp))
    first_emp_col = 3
    last_total_col = 3 + len(employees)  # employees then Total
    s.color_scale(first_emp_col, fr, last_total_col, lr)
    # narrow the numeric columns
    for j in range(first_emp_col, last_total_col + 1):
        s.widths[j] = max(s.widths.get(j, 0), 7)
    s.finalize(freeze=f"B{fr}")  # freeze header rows + first column (Location)


def build_exclusive_shared(wb, df, d):
    s = Sheet(wb, "Exclusive vs Shared Coverage", span=5)
    s.title("Exclusive vs Shared Coverage — The Parker")
    s.note("Descriptive view of which locations are covered by one employee (Exclusive) vs. "
           "multiple employees (Shared). Not a redundancy or staffing assessment.", height=28)
    s.blank()

    s.section("A. Summary")
    s.table(["Metric", "Count"], [
        ["Total Locations", len(d["locations"])],
        ["Exclusive Locations", len(d["single"])],
        ["Shared Locations", len(d["shared"])],
        ["Average Employees Per Location", round(float(d["cnt_emps"].mean()), 2)],
    ], make_filter=False)
    s.blank()

    s.section("B. Exclusive Coverage")
    s.note("Locations serviced by a single employee across the schedule.")
    rows = [[l, d["area"][l], d["emps_by_loc"][l][0], int(d["assign"][l])]
            for l in sorted(d["single"], key=lambda x: (-d["assign"][x], x))]
    s.table(["Location", "Area Type", "Employee", "Assignment Count"], rows, count_cols={4})
    s.blank()

    s.section("C. Shared Coverage")
    s.note("Locations serviced by multiple employees, sorted by employee count then assignment count.")
    rows = [[l, d["area"][l], int(d["cnt_emps"][l]), ", ".join(d["emps_by_loc"][l]),
             int(d["assign"][l])] for l in d["shared"]]
    rows.sort(key=lambda r: (-r[2], -r[4], r[0]))
    s.table(["Location", "Area Type", "Employee Count", "Employees", "Assignment Count"],
            rows, count_cols={3, 5}, wrap_cols={4}, make_filter=True)
    s.finalize(freeze="A3")


def build_area_inventory(wb, df, d):
    s = Sheet(wb, "Area Inventory Request", span=5)
    s.title("Area Inventory Request — The Parker")
    s.note("Data request for Development. Please complete Square Footage and Development Notes. "
           "One row per location.", height=28)
    s.blank()
    rows = []
    for loc in sorted(d["locations"]):
        rows.append([df["property"].iat[0], loc, d["area"][loc], "", ""])
    hr, fr, lr = s.table(
        ["Property Name", "Location", "Proposed Area Type", "Square Footage", "Development Notes"],
        rows, wrap_cols={5}, make_filter=True)
    s.finalize(freeze=f"A{fr}")


def build_raw_detail(wb, df, d):
    s = Sheet(wb, "Raw Schedule Detail", span=7)
    s.title("Raw Schedule Detail — The Parker")
    s.note("Supporting detail: the full row-by-row schedule. One row per assignment.")
    s.blank()
    WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def daykey(v):
        ds = expand_days(v)
        return WEEK.index(ds[0]) if ds else 99
    t = df.copy()
    t["_d"] = t["day_of_week"].apply(daykey)
    t["_s"] = t["start_min"].fillna(10**9)
    t = t.sort_values(["employee_name", "_d", "_s", "location"])
    rows = t[["employee_name", "day_of_week", "start_time", "end_time",
              "location", "task", "frequency"]].values.tolist()
    hr, fr, lr = s.table(
        ["Employee", "Day", "Start Time", "End Time", "Location", "Task", "Frequency"],
        rows, wrap_cols={6}, make_filter=True)
    s.finalize(freeze=f"A{fr}")


def main():
    df = load_parker()
    d = prepare(df)
    wb = Workbook()
    wb.remove(wb.active)  # drop default sheet

    build_start_here(wb, df, d)
    build_executive_summary(wb, df, d)
    build_volume_by_area(wb, df, d)
    build_ownership_matrix(wb, df, d)
    build_exclusive_shared(wb, df, d)
    build_area_inventory(wb, df, d)
    build_raw_detail(wb, df, d)

    try:
        wb.save(OUT_PATH)
    except PermissionError:
        print(f"WARNING: {os.path.basename(OUT_PATH)} is open — close it and rerun.")
        return

    print("saved:", os.path.relpath(OUT_PATH, REPO))
    print("sheets:", wb.sheetnames)
    print(f"assignments={len(df)} employees={df['employee_name'].nunique()} "
          f"locations={df['location'].nunique()} tasks={df['task'].nunique()} "
          f"exclusive={len(d['single'])} shared={len(d['shared'])}")


if __name__ == "__main__":
    main()
