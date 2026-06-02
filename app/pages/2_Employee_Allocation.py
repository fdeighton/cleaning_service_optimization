"""Page 2 — Employee Allocation.

Who is assigned how much and where. Counts are allocation, NOT effort.
"""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from _shared import empty_guard, get_data, page_header, sidebar_filters
from cleanlens import metrics

st.set_page_config(page_title="Employee Allocation · CleanLens", page_icon="👥", layout="wide")
page_header("👥 Employee Allocation", "Assignment counts by employee. Counts describe allocation, not effort.")

df, _ = get_data()
df = sidebar_filters(df)
if empty_guard(df):
    st.stop()

real_only = st.session_state.get("real_only", True)

# --- Assignments by employee --------------------------------------------
st.subheader("Assignments by employee")
emp = metrics.assignments_by_employee(df, real_only=real_only)
fig = px.bar(emp, x="assignments", y="employee", orientation="h")
fig.update_layout(yaxis=dict(categoryorder="total ascending"),
                  margin=dict(t=10, b=10, l=10, r=10))
st.plotly_chart(fig, width='stretch')

st.divider()

# --- Employee x area and employee x task matrices -----------------------
left, right = st.columns(2)

with left:
    st.subheader("Employee × area type")
    m = metrics.employee_location_matrix(df, real_only=real_only)
    if m.empty:
        st.info("No data for this matrix.")
    else:
        fig = px.imshow(m, aspect="auto", text_auto=True,
                        labels=dict(x="Area type", y="Employee", color="Assignments"),
                        color_continuous_scale="Blues")
        fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, width='stretch')

with right:
    st.subheader("Employee × task category")
    m = metrics.employee_task_matrix(df, real_only=real_only)
    if m.empty:
        st.info("No data for this matrix.")
    else:
        fig = px.imshow(m, aspect="auto", text_auto=True,
                        labels=dict(x="Task category", y="Employee", color="Assignments"),
                        color_continuous_scale="Greens")
        fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, width='stretch')

st.divider()

# --- Coverage analysis ---------------------------------------------------
st.subheader("Coverage analysis")
st.caption("Breadth of each employee's assignments. Single-employee area types = key-person dependency.")
cov = metrics.employee_coverage(df, real_only=real_only)
st.dataframe(cov, hide_index=True, width='stretch')

c1, c2 = st.columns(2)
with c1:
    fig = px.bar(cov, x="distinct_area_types", y="employee", orientation="h",
                 title="Distinct area types per employee")
    fig.update_layout(yaxis=dict(categoryorder="total ascending"),
                      margin=dict(t=40, b=10, l=10, r=10))
    st.plotly_chart(fig, width='stretch')
with c2:
    fig = px.bar(cov, x="distinct_task_categories", y="employee", orientation="h",
                 title="Distinct task categories per employee")
    fig.update_layout(yaxis=dict(categoryorder="total ascending"),
                      margin=dict(t=40, b=10, l=10, r=10))
    st.plotly_chart(fig, width='stretch')
