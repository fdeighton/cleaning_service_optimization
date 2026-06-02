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
from collections import Counter
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


def normalize_task(t):
    """Collapse case/spacing variants; group long general-cleaning strings;
    keep facility notes visible as 'No Explicit Task'. Display only — does not
    change the underlying data."""
    low = " ".join(str(t).strip().lower().split())
    if not low or "no explicit" in low or low in ("n/a", "none", "-"):
        return "No Explicit Task"
    if low.startswith("empty trash") or ("dust" in low and "disinfect" in low):
        return "General Cleaning"
    return low[:1].upper() + low[1:]


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
    else:
        df["Area Type"] = df["Location"].apply(_classify)

    report = {"found": found, "rows": len(df),
              "updated": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%b %d, %Y · %H:%M"),
              "missing_required": [c for c in ("Employee", "Location") if c not in found]}
    return df, report


def coverage_split(df):
    if df["Employee"].eq("").all():
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
        out.append({"Employee": emp, "Assignments": len(g),
                    "Locations": g["Location"].nunique(),
                    "Areas": ", ".join(g["Area Type"].value_counts().index[:2]),
                    "TopLocations": "; ".join(g["Location"].value_counts().index[:3])})
    return sorted(out, key=lambda r: -r["Assignments"])


def area_ownership(df):
    rows = []
    for loc, g in df.groupby("Location"):
        emps = g.loc[g["Employee"] != "", "Employee"]
        ec = emps.nunique()
        rows.append({"Area": loc,
                     "Area Type": g["Area Type"].mode().iat[0] if len(g) else "",
                     "Primary Employee": emps.value_counts().index[0] if len(emps) else "—",
                     "Shared / Exclusive": "Shared" if ec > 1 else "Exclusive",
                     "Assignment Count": len(g)})
    return pd.DataFrame(rows).sort_values("Assignment Count", ascending=False, ignore_index=True)


def shared_coverage_table(df, shared):
    rows = [{"Location": loc,
             "Employees": ", ".join(sorted(df[df["Location"] == loc]["Employee"].unique())),
             "Employee Count": int(n)} for loc, n in shared.sort_values(ascending=False).items()]
    return pd.DataFrame(rows or None, columns=["Location", "Employees", "Employee Count"])


def exclusive_coverage_table(df, exclusive):
    rows = [{"Location": loc, "Employee": df[df["Location"] == loc]["Employee"].iloc[0]}
            for loc in exclusive.index]
    return pd.DataFrame(rows or None, columns=["Location", "Employee"])


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
    df_out = (pd.DataFrame(rows, columns=cols)
              .sort_values("Location", ignore_index=True) if rows else pd.DataFrame(columns=cols))
    # sort detailed rows by assignment volume hint (extract leading int)
    if len(df_out):
        df_out["_n"] = df_out["Detail"].str.extract(r"(\d+)").astype(int)
        df_out = df_out.sort_values("_n", ascending=False, ignore_index=True).drop(columns="_n")
    return df_out


def review_pattern_summary(rev):
    pat = Counter()
    for p in rev["Pattern"]:
        for x in str(p).split("; "):
            if x:
                pat[x] += 1
    return pd.DataFrame(sorted(pat.items(), key=lambda kv: -kv[1]),
                        columns=["Review Pattern", "Locations"])


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
    [data-testid="stSidebar"] div[data-baseweb="select"] > div {{
        background: #FFFFFF !important; border-color: {LINE} !important; border-radius: 8px; }}
    [data-testid="stSidebar"] div[data-baseweb="select"] * {{ color: {INK} !important; }}
    [data-testid="stSidebar"] div[data-baseweb="select"] svg {{ fill: {INK} !important; }}
    [data-testid="stSidebar"] div[data-baseweb="select"] [data-baseweb="tag"] {{ background: {ACCENT} !important; }}
    [data-testid="stSidebar"] div[data-baseweb="select"] [data-baseweb="tag"] * {{ color: #FFFFFF !important; }}

    .hero {{ background: {INK}; border-radius: 16px; padding: 30px 34px; margin-bottom: 20px;
        position: relative; overflow: hidden; }}
    .hero:before {{ content:''; position:absolute; left:0; top:0; bottom:0; width:6px; background:{ACCENT}; }}
    .hero-eyebrow {{ color:{ACCENT}; font-weight:700; letter-spacing:.22em; font-size:.72rem; text-transform:uppercase; }}
    .hero-title {{ color:#FFF; font-size:2.15rem; font-weight:800; line-height:1.1; margin:.25rem 0 .15rem; }}
    .hero-sub {{ color:#B9B1A6; font-size:1.02rem; font-weight:400; }}
    .hero-meta {{ margin-top:18px; display:flex; gap:34px; flex-wrap:wrap; }}
    .hero-meta div {{ color:#8F887E; font-size:.74rem; text-transform:uppercase; letter-spacing:.1em; }}
    .hero-meta b {{ display:block; color:#FFF; font-size:1.05rem; letter-spacing:0; text-transform:none;
        font-weight:600; margin-top:3px; }}

    .takeaways {{ background:{CARD}; border:1px solid {LINE}; border-left:5px solid {ACCENT};
        border-radius:13px; padding:18px 24px 16px; margin-bottom:6px; box-shadow:0 1px 2px rgba(20,20,18,.04); }}
    .takeaways h4 {{ margin:0 0 8px; font-size:.74rem; text-transform:uppercase; letter-spacing:.14em; color:{ACCENT_DK}; }}
    .takeaways ul {{ margin:0; padding-left:20px; }}
    .takeaways li {{ font-size:.98rem; color:{INK}; margin:7px 0; line-height:1.45; }}
    .takeaways li b {{ color:{ACCENT_DK}; }}

    .sec {{ margin: 28px 0 12px; }}
    .sec h2 {{ font-size:1.18rem; font-weight:700; color:{INK}; margin:0; padding-left:13px;
        border-left:4px solid {ACCENT}; line-height:1.15; }}
    .sec p {{ margin:.3rem 0 0 17px; color:{MUTED}; font-size:.86rem; }}

    .kpis {{ display:grid; grid-template-columns:repeat(6,1fr); gap:14px; }}
    .kpi {{ background:{CARD}; border:1px solid {LINE}; border-radius:13px; padding:18px 18px 16px;
        box-shadow:0 1px 2px rgba(20,20,18,.04); }}
    .kpi .v {{ font-size:1.95rem; font-weight:800; color:{INK}; line-height:1; }}
    .kpi .l {{ font-size:.82rem; font-weight:600; color:{INK}; margin-top:9px; }}
    .kpi .s {{ font-size:.72rem; color:{MUTED}; margin-top:2px; }}
    .kpi.accent .v {{ color:{ACCENT_DK}; }}

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
    .ready h4 {{ font-size:.72rem; text-transform:uppercase; letter-spacing:.12em; color:{MUTED}; margin:0 0 12px; }}
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
        html += (f"<div class='{'kpi accent' if accent else 'kpi'}'><div class='v'>{v}</div>"
                 f"<div class='l'>{l}</div><div class='s'>{s}</div></div>")
    st.markdown(html + "</div>", unsafe_allow_html=True)


def hbar(frame, label, value="Assignment Count"):
    fig = px.bar(frame, x=value, y=label, orientation="h", text=value)
    fig.update_traces(marker_color=ACCENT, marker_line_width=0, textposition="outside",
                      textfont=dict(color=MUTED, size=11), cliponaxis=False)
    fig.update_layout(height=44 * len(frame) + 60, margin=dict(t=6, b=6, l=6, r=30),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Inter, Segoe UI, sans-serif", color=INK, size=13),
                      xaxis=dict(visible=False),
                      yaxis=dict(categoryorder="total ascending", title=None,
                                 tickfont=dict(color=INK, size=12.5)))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def table(frame, height=None):
    if height is None:
        st.dataframe(frame, hide_index=True, width="stretch")
    else:
        st.dataframe(frame, hide_index=True, width="stretch", height=height)


# ===========================================================================
# App
# ===========================================================================
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
if rep["missing_required"]:
    st.warning(f"Missing required field(s): {', '.join(rep['missing_required'])}. Some sections may be limited.")

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
area_counts = df["Area Type"].value_counts()
emp_counts = df.loc[df["Employee"] != "", "Employee"].value_counts()
total_loc = df["Location"].nunique()
sh, ex = int(len(shared)), int(len(exclusive))
sh_pct = round(100 * sh / total_loc) if total_loc else 0

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

# ---- A. Key Takeaways ----
bullets = []
if len(area_counts):
    bullets.append(f"Scheduled attention centers on <b>{area_counts.index[0]}</b> areas — "
                   f"{round(100 * area_counts.iloc[0] / len(df))}% of all assignments.")
if len(emp_counts):
    bullets.append(f"<b>{emp_counts.index[0]}</b> carries the most of the standing schedule "
                   f"({int(emp_counts.iloc[0])} assignments).")
bullets.append(f"<b>{sh} of {total_loc}</b> locations ({sh_pct}%) have shared coverage; "
               f"<b>{ex}</b> are exclusively covered by one person.")
bullets.append("This view describes <b>coverage and ownership</b> only — without square footage, task "
               "times, or service standards, it cannot yet support workload or staffing analysis.")
st.markdown("<div class='takeaways'><h4>Key Takeaways</h4><ul>"
            + "".join(f"<li>{b}</li>" for b in bullets) + "</ul></div>", unsafe_allow_html=True)

# ---- B. Executive Metrics ----
section("Executive Metrics", "The shape of this property's scheduled cleaning operation at a glance.")
kpi_row([
    (f"{len(df):,}", "Schedule Assignments", "scheduled cleaning tasks", True),
    (int(emp_counts.size), "Employees", "people on the schedule", False),
    (total_loc, "Locations", "distinct areas serviced", False),
    (df["Area Type"].nunique(), "Area Types", "categories of space", False),
    (sh, "Shared Locations", "served by 2+ people", False),
    (ex, "Exclusive Locations", "served by one person", False),
])
st.markdown("<div class='note'>This dashboard describes scheduled cleaning coverage and ownership. "
            "It does not measure workload, labor effort, productivity, or staffing efficiency.</div>",
            unsafe_allow_html=True)

# ---- C. Cleaning Volume ----
section("Cleaning Volume", "Where scheduled attention is concentrated — by assignment count, not effort.")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Top Locations**")
    hbar(volume(df["Location"], "Location", 10), "Location")
    st.caption(f"A small set of common areas — led by {df['Location'].value_counts().index[0]} — "
               "receives the most scheduled visits.")
with c2:
    st.markdown("**Area Type Distribution**")
    hbar(volume(df["Area Type"], "Area Type"), "Area Type")
    st.caption(f"{area_counts.index[0]} spaces account for the largest share of scheduled assignments.")
st.markdown("**Top Tasks**")
hbar(volume(df["Task"].apply(normalize_task), "Task", 10), "Task")
st.caption("Task labels are grouped (general-cleaning variants collapse into 'General Cleaning'); "
           "routine general cleaning dominates the schedule.")

# ---- D. Ownership ----
section("Ownership & Responsibility", "Who is responsible for which parts of the building.")
foot = employee_footprint(df)
if foot:
    html = "<div class='emps'>"
    for e in foot:
        html += (f"<div class='emp'><div class='n'>{e['Employee']}</div>"
                 f"<div class='row'><div><div class='v'>{e['Assignments']}</div><div class='l'>Assignments</div></div>"
                 f"<div><div class='v'>{e['Locations']}</div><div class='l'>Locations</div></div></div>"
                 f"<div class='meta'>Primary area types: <b>{e['Areas'] or '—'}</b></div>"
                 f"<div class='meta'>Key areas: {e['TopLocations'] or '—'}</div></div>")
    st.markdown(html + "</div>", unsafe_allow_html=True)
st.caption("Assignment counts show how the standing schedule is distributed across the team — not effort or hours.")
own = area_ownership(df)
st.markdown("<br>**Area Ownership** — top 10 areas by assignment count", unsafe_allow_html=True)
table(own.head(10))
st.caption("Each area's primary employee and whether it is shared or exclusively covered.")
with st.expander("View full detail — all areas"):
    table(own, height=420)

# ---- E. Shared vs Exclusive Coverage ----
section("Shared vs Exclusive Coverage", "How responsibility is distributed across the team.")
kpi_row([
    (sh, "Shared Locations", "two or more employees", True),
    (ex, "Exclusive Locations", "single employee", False),
    (avg_emp, "Avg Employees / Location", "mean coverage breadth", False),
])
shared_df = shared_coverage_table(df, shared)
excl_df = exclusive_coverage_table(df, exclusive)
e1, e2 = st.columns(2)
with e1:
    st.markdown("**Shared Coverage** — top 10")
    table(shared_df.head(10))
    with st.expander("View full detail — all shared locations"):
        table(shared_df, height=400)
with e2:
    st.markdown("**Exclusive Coverage** — top 10")
    table(excl_df.head(10))
    with st.expander("View full detail — all exclusive locations"):
        table(excl_df, height=400)
st.caption(f"{sh_pct}% of locations have shared coverage; the remainder are covered by a single person.")

# ---- F. Candidate Review (compact) ----
section("Candidate Review", "Schedule patterns worth a human glance — informational only, not findings.")
rev = candidate_review(df)
pat_df = review_pattern_summary(rev)
if len(pat_df):
    cap, _spacer = st.columns([2, 1])
    with cap:
        hbar(pat_df, "Review Pattern", value="Locations")
st.caption(f"{len(rev)} locations show at least one pattern to review across "
           f"{len(pat_df)} pattern type(s). These are observations, not problems.")
with st.expander("View candidate locations (top 10 and full detail)"):
    st.markdown("**Top candidate locations**")
    table(rev.head(10))
    st.markdown("**All candidate review items**")
    table(rev, height=360)

# ---- G. Data Readiness ----
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
