"""CleanLens — Streamlit entry point.

Run with:  streamlit run app/streamlit_app.py

Pages live in app/pages/ and are auto-discovered by Streamlit. This home page
loads the portfolio, surfaces the schema-validation report, and explains scope.
"""
from __future__ import annotations

import streamlit as st

from _shared import get_data

st.set_page_config(page_title="CleanLens", page_icon="🧹", layout="wide")

st.title("🧹 CleanLens")
st.subheader("Fitzrovia cleaning schedule — visual analytics")
st.caption(
    "Schedule-data only: counts and cadences. No labour effort, no durations, "
    "no square footage, no optimization — by design."
)

df, report = get_data()

# --- Portfolio snapshot --------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Assignments", f"{len(df):,}")
c2.metric("Properties", df["property_name"].nunique())
c3.metric("Employees", df.loc[df["is_real_employee"], "employee_name"].nunique())
c4.metric("Distinct locations", df["location"].nunique())

st.divider()

# --- Schema validation report -------------------------------------------
st.subheader("Schema validation")
if report["ok"]:
    st.success("All datasets conform to the canonical 10-field schema.")
else:
    st.error("Schema errors detected:")
    for e in report["errors"]:
        st.write(f"- {e}")

if report["warnings"]:
    with st.expander(f"Data-quality warnings ({len(report['warnings'])})", expanded=False):
        for w in report["warnings"]:
            st.write(f"- {w}")

st.divider()

st.subheader("Properties loaded")
prop_counts = (
    df.groupby("property_name").size().reset_index(name="assignments")
    .sort_values("assignments", ascending=False, ignore_index=True)
)
st.dataframe(prop_counts, hide_index=True, width='stretch')

st.info(
    "Use the pages in the sidebar:\n\n"
    "1. **Executive Overview** — portfolio/property health read\n"
    "2. **Employee Allocation** — who is assigned how much and where\n"
    "3. **Area Coverage** — which areas get scheduled attention\n\n"
    "New properties appear automatically: drop a conforming "
    "`*_cleaning_responsibilities.csv` into `schedule_data/`."
)
