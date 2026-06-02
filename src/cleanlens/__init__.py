"""CleanLens — reusable, property-agnostic analytics over Fitzrovia cleaning schedules.

Pipeline (all Streamlit-agnostic, pure functions):

    loader.load_portfolio()  ->  raw DataFrame (all properties, source columns only)
    schema.validate(df)      ->  ValidationReport (does not mutate)
    transform.enrich(df)     ->  DataFrame + derived columns (source never mutated)
    metrics.*                ->  aggregations for the dashboard

Hard constraints honoured everywhere: no labour effort, no task durations,
no square footage, no optimization. Every measure is count- or cadence-based.
"""

from . import config, loader, schema, transform, mappings, metrics  # noqa: F401

__all__ = ["config", "loader", "schema", "transform", "mappings", "metrics"]
