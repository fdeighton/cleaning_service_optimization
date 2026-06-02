"""Fitzrovia Residential — Cleaning Operations Overview.

A single-page executive dashboard. CSV-driven, property-agnostic: drop any
standardized schedule CSV into schedule_data/ and it works with no code changes.

Communicates: cleaning volume, ownership, coverage structure, and data readiness.
It does NOT measure workload, productivity, staffing, or cost — and says so.

Run:  streamlit run dashboard.py
"""
from __future__ import annotations

import glob
import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

# ---------------------------------------------------------------------------
# Config + Fitzrovia palette
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
SCHEDULE_DIR = os.path.join(HERE, "schedule_data")
AREA_KEYWORDS_CSV = os.path.join(HERE, "config", "area_type_keywords.csv")

INK = "#161412"        # near-black
ACCENT = "#E8751A"     # Fitzrovia orange
ACCENT_DK = "#B4570F"
MUTED = "#7C756C"
LINE = "#E7E2D9"
CARD = "#FFFFFF"
PAGE = "#F5F2EC"

st.set_page_config(page_title="Fitzrovia · Cleaning Operations",
                   page_icon=None, layout="wide")


# ---------------------------------------------------------------------------
# Reusable data layer (property-agnostic, schema-tolerant)
# ---------------------------------------------------------------------------
def _pick(df, *names):
    low = {c.lower(): c for c in df.columns}
    for n in names:
        if n in low:
            return low[n]
    return None


@st.cache_data(show_spinner=False)
def _area_keywords():
    try:
        k = pd.read_csv(AREA_KEYWORDS_CSV, dtype=str)
        return [(str(a).strip().lower(), str(b).strip())
                for a, b in zip(k.iloc[:, 0], k.iloc[:, 1]) if str(a).strip()]
    except Exception:
        return []


def _classify(loc):
    t = str(loc).lower()
    for kw, area in _area_keywords():
        if kw in t:
            return area
    return "Unknown"


@st.cache_data(show_spinner=False)
def list_datasets():
    return sorted(p for p in glob.glob(os.path.join(SCHEDULE_DIR, "*.csv"))
                  if not os.path.basename(p).startswith("~$"))


@st.cache_data(show_spinner=False)
def load(path):
    """Read a schedule CSV into canonical working columns + a schema report."""
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    raw.columns = [c.strip() for c in raw.columns]
    df = pd.DataFrame(index=raw.index)
    found = {}

    def col(canon, *names, default=""):
        c = _pick(raw, *names)
        if c:
            found[canon] = c
            return raw[c].astype(str).str.strip()
        return default

    df["Employee"] = col("Employee", "employee_name", "employee")
    df["Location"] = col("Location", "clean_location", "location", "raw_location")
    df["Task"] = col("Task", "clean_task", "task", "raw_task")
    df["Property"] = col("Property", "property_name", "property", default="(unspecified)")
    df["Frequency"] = col("Frequency", "frequency")
    at = _pick(raw, "area_type")
    if at:
        df["Area Type"] = raw[at].astype(str).str.strip(); found["Area Type"] = at
        derived_area = False
    else:
        df["Area Type"] = df["Location"].apply(_classify); derived_area = True

    report = {"found": found, "derived_area": derived_area, "rows": len(df),
              "updated": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%b %d, %Y · %H:%M"),
              "missing_required": [c for c in ("Employee", "Location")
                                   if c not in found]}
    return df, report


def coverage_split(df):
    if "" == df["Employee"].iloc[0] and df["Employee"].eq("").all():
        return pd.Series(dtype=int), pd.Series(dtype=int), 0.0
    per = df[df["Employee"] != ""].groupby("Location")["Employee"].nunique()
    return per[per > 1], per[per == 1], (round(float(per.mean()), 2) if len(per) else 0.0)


def volume(series, label, top=None):
    s = series[series != ""].value_counts()
    if top:
        s = s.head(top)
    return s.rename_axis(label).reset_index(name="Assignment Count")


def employee_footprint(df):
    out = []
    for emp, g in df[df["Employee"] != ""].groupby("Employee"):
        out.append({
            "Employee": emp,
            "Assignments": len(g),
            "Locations": g["Location"].nunique(),
            "Areas": ", ".join(g["Area Type"].value_counts().index[:2]),
            "TopLocations": "; ".join(g["Location"].value_counts().index[:3]),
        })
    return sorted(out, key=lambda r: -r["Assignments"])


def area_ownership(df):
    rows = []
    for loc, g in df.groupby("Location"):
        emps = g.loc[g["Employee"] != "", "Employee"]
        ec = emps.nunique()
        rows.append({
            "Area": loc,
            "Area Type": g["Area Type"].mode().iat[0] if len(g) else "",
            "Primary Employee": emps.value_counts().index[0] if len(emps) else "—",
            "Shared / Exclusive": "Shared" if ec > 1 else "Exclusive",
            "Assignment Count": len(g),
        })
    return pd.DataFrame(rows).sort_values("Assignment Count", ascending=False, ignore_index=True)


def candidate_review(df):
    cols = ["Review", "Location", "Area Type", "Pattern", "Detail"]
    bundle = (",", "&", " etc", "/", " and ")
    ambiguous = ("building-wide", "not specified", "all staff", "(all", "various", " etc", "n/a")
    rows = []
    for loc, g in df.groupby("Location"):
        low, area = loc.lower(), (g["Area Type"].mode().iat[0] if len(g) else "")
        ec = g.loc[g["Employee"] != "", "Employee"].nunique()
        pats = []
        if ec > 1:
            pats.append("Shared Coverage Pattern")
        if len(g) >= 4:
            pats.append("Repeated Coverage Pattern")
        if any(m in low for m in ambiguous) or len(loc.strip()) <= 3:
            pats.append("Ambiguous Location")
        if area in ("Unknown", "Other / Unknown", "Unclassified", ""):
            pats.append("Unknown Area Type")
        if g["Task"].apply(lambda t: any(b in (t or "").lower() for b in bundle)).any():
            pats.append("Bundled Task Description")
        if pats:
            rows.append({"Review": "Candidate Review", "Location": loc, "Area Type": area,
                         "Pattern": "; ".join(pats),
                         "Detail": f"{len(g)} assignments · {ec} employee(s)"})
    return pd.DataFrame(rows, columns=cols).sort_values("Location", ignore_index=True) \
        if rows else pd.DataFrame(columns=cols)


# ---------------------------------------------------------------------------
# Presentation layer (Fitzrovia styling)
# ---------------------------------------------------------------------------
def inject_css():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', 'Segoe UI', system-ui, sans-serif; }}
    .stApp {{ background: {PAGE}; }}
    #MainMenu, header, footer {{ visibility: hidden; }}
    .block-container {{ padding-top: 1.1rem; padding-bottom: 3rem; max-width: 1340px; }}
    [data-testid="stSidebar"] {{ background: {INK}; }}
    [data-testid="stSidebar"] * {{ color: #EFEAE2 !important; }}
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ color: {ACCENT} !important;
        text-transform: uppercase; letter-spacing: .12em; font-size: .72rem; }}

    .hero {{ background: {INK}; border-radius: 16px; padding: 30px 34px; margin-bottom: 22px;
        position: relative; overflow: hidden; }}
    .hero:before {{ content:''; position:absolute; left:0; top:0; bottom:0; width:6px; background:{ACCENT}; }}
    .hero-eyebrow {{ color:{ACCENT}; font-weight:700; letter-spacing:.22em; font-size:.72rem;
        text-transform:uppercase; }}
    .hero-title {{ color:#FFF; font-size:2.15rem; font-weight:800; line-height:1.1; margin:.25rem 0 .15rem; }}
    .hero-sub {{ color:#B9B1A6; font-size:1.02rem; font-weight:400; }}
    .hero-meta {{ margin-top:18px; display:flex; gap:34px; flex-wrap:wrap; }}
    .hero-meta div {{ color:#8F887E; font-size:.74rem; text-transform:uppercase; letter-spacing:.1em; }}
    .hero-meta b {{ display:block; color:#FFF; font-size:1.05rem; letter-spacing:0; text-transform:none;
        font-weight:600; margin-top:3px; }}

    .sec {{ margin: 30px 0 12px; }}
    .sec h2 {{ font-size:1.18rem; font-weight:700; color:{INK}; margin:0; padding-left:13px;
        border-left:4px solid {ACCENT}; line-height:1.15; }}
    .sec p {{ margin:.3rem 0 0 17px; color:{MUTED}; font-size:.86rem; }}

    .kpis {{ display:grid; grid-template-columns:repeat(6,1fr); gap:14px; }}
    .kpi {{ background:{CARD}; border:1px solid {LINE}; border-radius:13px; padding:18px 18px 16px;
        box-shadow:0 1px 2px rgba(20,20,18,.04); }}
    .kpi .v {{ font-size:1.95rem; font-weight:800; color:{INK}; line-height:1; }}
    .kpi .l {{ font-size:.82rem; font-weight:600; color:{INK}; margin-top:9px; }}
    .kpi .s {{ font-size:.72rem; color:{MUTED}; margin-top:2px; }}
    .kpi.accent {{ }} .kpi.accent .v {{ color:{ACCENT_DK}; }}

    .note {{ background:#FBF4EC; border:1px solid #F1DBC4; border-left:4px solid {ACCENT};
        border-radius:10px; padding:12px 16px; color:#6B5b48; font-size:.86rem; margin-top:14px; }}

    .emps {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }}
    .emp {{ background:{CARD}; border:1px solid {LINE}; border-radius:13px; padding:16px 18px;
        box-shadow:0 1px 2px rgba(20,20,18,.04); }}
    .emp .n {{ font-weight:700; color:{INK}; font-size:1.02rem; border-bottom:1px solid {LINE};
        padding-bottom:8px; margin-bottom:10px; }}
    .emp .row {{ display:flex; gap:22px; margin-bottom:9px; }}
    .emp .row .v {{ font-size:1.35rem; font-weight:800; color:{ACCENT_DK}; line-height:1; }}
    .emp .row .l {{ font-size:.68rem; color:{MUTED}; text-transform:uppercase; letter-spacing:.08em; }}
    .emp .meta {{ font-size:.78rem; color:{MUTED}; margin-top:4px; }}
    .emp .meta b {{ color:{INK}; font-weight:600; }}

    .ready {{ display:grid; grid-template-columns:1fr 1fr 1.1fr; gap:0; background:{CARD};
        border:1px solid {LINE}; border-radius:13px; overflow:hidden; }}
    .ready > div {{ padding:18px 22px; }}
    .ready > div + div {{ border-left:1px solid {LINE}; }}
    .ready h4 {{ font-size:.72rem; text-transform:uppercase; letter-spacing:.12em; color:{MUTED};
        margin:0 0 12px; }}
    .ready li {{ list-style:none; font-size:.9rem; color:{INK}; margin:7px 0; }}
    .ready .yes:before {{ content:'\\2713'; color:{ACCENT}; font-weight:800; margin-right:9px; }}
    .ready .no:before {{ content:'\\25A1'; color:#B9B1A6; margin-right:9px; }}
    .ready ul {{ padding:0; margin:0; }}
    </style>
    """, unsafe_allow_html=True)


def section(title, subtitle):
    st.markdown(f"<div class='sec'><h2>{title}</h2><p>{subtitle}</p></div>", unsafe_allow_html=True)


def kpi_row(cards):
    html = "<div class='kpis'>"
    for v, l, s, accent in cards:
        cls = "kpi accent" if accent else "kpi"
        html += f"<div class='{cls}'><div class='v'>{v}</div><div class='l'>{l}</div><div class='s'>{s}</div></div>"
    st.markdown(html + "</div>", unsafe_allow_html=True)


def style_chart(frame, label):
    fig = px.bar(frame, x="Assignment Count", y=label, orientation="h", text="Assignment Count")
    fig.update_traces(marker_color=ACCENT, marker_line_width=0, textposition="outside",
                      textfont=dict(color=MUTED, size=11), cliponaxis=False)
    fig.update_layout(
        height=46 * len(frame) + 70, margin=dict(t=6, b=6, l=6, r=30),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, sans-serif", color=INK, size=13),
        xaxis=dict(visible=False),
        yaxis=dict(categoryorder="total ascending", title=None,
                   tickfont=dict(color=INK, size=12.5)),
        bargap=0.32,
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def table(frame, height=None):
    st.dataframe(frame, hide_index=True, width="stretch",
                 height=height if height else None)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
inject_css()

datasets = list_datasets()
if not datasets:
    st.error(f"No schedule CSV files found in {SCHEDULE_DIR}.")
    st.stop()

labels = {os.path.basename(p).replace("_cleaning_responsibilities.csv", "").replace(".csv", ""): p
          for p in datasets}

st.sidebar.markdown("### Property")
choice = st.sidebar.selectbox("Schedule dataset", sorted(labels), label_visibility="collapsed")
df, rep = load(labels[choice])

# graceful schema warnings
if rep["missing_required"]:
    st.warning(f"Missing required field(s): {', '.join(rep['missing_required'])}. "
               "Some sections may be limited.")

# filters
st.sidebar.markdown("### Filters")
if df["Property"].nunique() > 1:
    chosen = st.sidebar.multiselect("Property", sorted(df["Property"].unique()),
                                    default=sorted(df["Property"].unique()))
    df = df[df["Property"].isin(chosen)]
emps_all = sorted(e for e in df["Employee"].unique() if e)
if emps_all:
    pick_e = st.sidebar.multiselect("Employee", emps_all)
    if pick_e:
        df = df[df["Employee"].isin(pick_e)]
areas_all = sorted(a for a in df["Area Type"].unique() if a)
pick_a = st.sidebar.multiselect("Area Type", areas_all)
if pick_a:
    df = df[df["Area Type"].isin(pick_a)]
st.sidebar.markdown("---")
st.sidebar.caption("CSV-driven · drop a new schedule into /schedule_data and reload.")

if df.empty:
    st.warning("No assignments match the current filters.")
    st.stop()

prop_name = " / ".join(sorted(df["Property"].unique()))
shared, exclusive, avg_emp = coverage_split(df)

# ---- Hero ----
st.markdown(f"""
<div class='hero'>
  <div class='hero-eyebrow'>Fitzrovia Residential · Operations Intelligence</div>
  <div class='hero-title'>Cleaning Operations Overview</div>
  <div class='hero-sub'>Schedule-based coverage and ownership analysis</div>
  <div class='hero-meta'>
    <div>Property<b>{prop_name}</b></div>
    <div>Schedule Source<b>{choice}</b></div>
    <div>Last Updated<b>{rep['updated']}</b></div>
  </div>
</div>
""", unsafe_allow_html=True)

# ---- Section 1: Executive Summary ----
section("Executive Summary", "The shape of this property's scheduled cleaning operation at a glance.")
kpi_row([
    (f"{len(df):,}", "Schedule Assignments", "scheduled cleaning tasks", True),
    (df.loc[df["Employee"] != "", "Employee"].nunique(), "Employees", "people on the schedule", False),
    (df["Location"].nunique(), "Locations", "distinct areas serviced", False),
    (df["Area Type"].nunique(), "Area Types", "categories of space", False),
    (int(len(shared)), "Shared Locations", "served by 2+ people", False),
    (int(len(exclusive)), "Exclusive Locations", "served by one person", False),
])
st.markdown("<div class='note'>This dashboard describes scheduled cleaning coverage and ownership. "
            "It does not measure workload, labor effort, productivity, or staffing efficiency.</div>",
            unsafe_allow_html=True)

# ---- Section 2: Cleaning Volume ----
section("Cleaning Volume", "Where scheduled attention is concentrated — by assignment count, not effort.")
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Top Locations**")
    style_chart(volume(df["Location"], "Location", 10), "Location")
with col2:
    st.markdown("**Area Type Distribution**")
    style_chart(volume(df["Area Type"], "Area Type"), "Area Type")
st.markdown("**Top Tasks**")
style_chart(volume(df["Task"], "Task", 10), "Task")

# ---- Section 3: Ownership & Responsibility ----
section("Ownership & Responsibility", "Who is responsible for which parts of the building.")
foot = employee_footprint(df)
if foot:
    html = "<div class='emps'>"
    for e in foot:
        html += (f"<div class='emp'><div class='n'>{e['Employee']}</div>"
                 f"<div class='row'><div><div class='v'>{e['Assignments']}</div>"
                 f"<div class='l'>Assignments</div></div>"
                 f"<div><div class='v'>{e['Locations']}</div><div class='l'>Locations</div></div></div>"
                 f"<div class='meta'>Primary area types: <b>{e['Areas'] or '—'}</b></div>"
                 f"<div class='meta'>Key areas: {e['TopLocations'] or '—'}</div></div>")
    st.markdown(html + "</div>", unsafe_allow_html=True)
st.markdown("<br>**Area Ownership** — who owns each area", unsafe_allow_html=True)
table(area_ownership(df), height=360)

# ---- Section 4: Coverage Structure ----
section("Coverage Structure", "How responsibility is distributed: exclusive vs shared coverage.")
kpi_row([
    (int(len(shared)), "Shared Locations", "two or more employees", True),
    (int(len(exclusive)), "Exclusive Locations", "single employee", False),
    (avg_emp, "Avg Employees / Location", "mean coverage breadth", False),
])
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Shared Coverage**")
    rows = [{"Location": loc, "Employees": ", ".join(sorted(df[df["Location"] == loc]["Employee"].unique())),
             "Employee Count": int(n)} for loc, n in shared.sort_values(ascending=False).items()]
    table(pd.DataFrame(rows or None, columns=["Location", "Employees", "Employee Count"]), height=300)
with c2:
    st.markdown("**Exclusive Coverage**")
    rows = [{"Location": loc, "Employee": df[df["Location"] == loc]["Employee"].iloc[0]}
            for loc in exclusive.index]
    table(pd.DataFrame(rows or None, columns=["Location", "Employee"]), height=300)

# ---- Section 5: Candidate Review Items ----
section("Candidate Review Items", "Schedule patterns worth a human glance. Informational only — not findings.")
rev = candidate_review(df)
table(rev, height=300)
st.caption(f"{len(rev)} location(s) flagged for review. These are patterns to look at, "
           "not waste, redundancy, or inefficiency.")

# ---- Section 6: Data Readiness ----
section("Current Analytical Capability", "What this schedule data can and cannot support today.")
st.markdown("""
<div class='ready'>
  <div><h4>Supported Today</h4><ul>
    <li class='yes'>Cleaning Volume</li><li class='yes'>Area Ownership</li>
    <li class='yes'>Coverage Analysis</li><li class='yes'>Schedule Structure</li></ul></div>
  <div><h4>Not Yet Supported</h4><ul>
    <li class='no'>Workload Analysis</li><li class='no'>Staffing Optimization</li>
    <li class='no'>Productivity Analysis</li><li class='no'>Cost Optimization</li></ul></div>
  <div><h4>Required Data</h4><ul>
    <li class='no'>Area Square Footage</li><li class='no'>Service Standards / SLA</li>
    <li class='no'>Standard Task Times</li><li class='no'>Completion Records</li></ul></div>
</div>
""", unsafe_allow_html=True)
