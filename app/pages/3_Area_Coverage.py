"""Page 3 — Area Coverage.

Which areas/area-types receive the most scheduled attention, and at what cadence.
"""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from _shared import empty_guard, get_data, page_header, sidebar_filters
from cleanlens import metrics

st.set_page_config(page_title="Area Coverage · CleanLens", page_icon="🗺️", layout="wide")
page_header("🗺️ Area Coverage", "Where scheduled attention concentrates, by area and area type.")

df, _ = get_data()
df = sidebar_filters(df)
if empty_guard(df):
    st.stop()

# --- Assignments by location --------------------------------------------
st.subheader("Assignments by location (top 20)")
loc = metrics.assignments_by_location(df, top_n=20)
fig = px.bar(loc, x="assignments", y="location", orientation="h")
fig.update_layout(yaxis=dict(categoryorder="total ascending"),
                  height=600, margin=dict(t=10, b=10, l=10, r=10))
st.plotly_chart(fig, width='stretch')

st.divider()

# --- Task mix by location + area x task heatmap -------------------------
left, right = st.columns(2)

with left:
    st.subheader("Task mix by area type")
    mix = metrics.task_mix_by_location(df)
    fig = px.bar(mix, x="area_type", y="assignments", color="task_category")
    fig.update_layout(xaxis=dict(tickangle=-40), margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, width='stretch')

with right:
    st.subheader("Area type × task category heatmap")
    m = metrics.area_task_matrix(df)
    if m.empty:
        st.info("No data for this heatmap.")
    else:
        fig = px.imshow(m, aspect="auto", text_auto=True,
                        labels=dict(x="Task category", y="Area type", color="Assignments"),
                        color_continuous_scale="Oranges")
        fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, width='stretch')

st.divider()

# --- Frequency by location ----------------------------------------------
st.subheader("Frequency by area type")
st.caption("Cadence mix per area type. A large 'Unknown' band flags a governance gap.")
m = metrics.frequency_by_location(df)
if m.empty:
    st.info("No data.")
else:
    fig = px.imshow(m, aspect="auto", text_auto=True,
                    labels=dict(x="Frequency", y="Area type", color="Assignments"),
                    color_continuous_scale="Purples")
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, width='stretch')

with st.expander("Area-type coverage table"):
    st.dataframe(metrics.area_type_coverage(df), hide_index=True, width='stretch')
