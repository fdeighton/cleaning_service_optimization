"""Page 1 — Executive Overview.

60-second health read: totals, distinct counts, frequency mix, task mix.
"""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from _shared import empty_guard, get_data, page_header, sidebar_filters
from cleanlens import metrics

st.set_page_config(page_title="Executive Overview · CleanLens", page_icon="📊", layout="wide")
page_header("📊 Executive Overview", "Total scheduled work and how it splits by cadence and task type.")

df, _ = get_data()
df = sidebar_filters(df)
if empty_guard(df):
    st.stop()

# --- KPI cards -----------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total assignments", f"{metrics.assignment_count(df):,}")
k2.metric("Distinct employees", metrics.distinct_employees(df))
k3.metric("Distinct locations", metrics.distinct_locations(df))
k4.metric("Distinct tasks", metrics.distinct_tasks(df))
k5.metric("Defined-frequency rate", f"{metrics.defined_frequency_rate(df):.0%}")

st.divider()

# --- Frequency + task distributions -------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("Frequency distribution")
    freq = metrics.frequency_distribution(df)
    fig = px.pie(freq, names="frequency", values="assignments", hole=0.5)
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, width='stretch')

with right:
    st.subheader("Task distribution")
    tasks = metrics.task_distribution(df)
    fig = px.bar(tasks, x="assignments", y="task_category", orientation="h")
    fig.update_layout(yaxis=dict(categoryorder="total ascending"),
                      margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, width='stretch')

st.divider()

# --- Area-type treemap + per-property breakdown -------------------------
left, right = st.columns(2)

with left:
    st.subheader("Assignments by area type")
    areas = metrics.assignments_by_area_type(df)
    fig = px.treemap(areas, path=["area_type"], values="assignments")
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, width='stretch')

with right:
    st.subheader("Assignments by property")
    props = metrics.assignments_by_property(df)
    fig = px.bar(props, x="property", y="assignments")
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, width='stretch')

with st.expander("Data-quality summary (governance metrics)"):
    st.json(metrics.data_quality_summary(df))
