# CleanLens — schedule analytics prototype

A reusable, property-agnostic Streamlit app over Fitzrovia cleaning schedules.
**Schedule-data only:** counts and cadences. No labour effort, no durations, no
square footage, no optimization — by design and by project constraint.

## Run

```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

The home page loads every conforming dataset, shows the schema-validation report,
and links to three pages: **Executive Overview**, **Employee Allocation**,
**Area Coverage**. Sidebar slicers (Property, Frequency, Area type, real-employees
toggle) apply to every page.

## Project structure

```
config/                         # editable mapping tables (not source data)
  frequency_map.csv             # raw frequency -> canonical + is_defined
  area_type_keywords.csv        # location keyword -> area_type (first match wins)
  task_category_keywords.csv    # task keyword    -> task_category
schedule_data/                  # source CSVs (read-only, never mutated)
  *_cleaning_responsibilities.csv
src/cleanlens/                  # Streamlit-agnostic core (unit-testable)
  config.py                     # paths, canonical schema, vocabularies
  loader.py                     # data loading layer (auto-discovers datasets)
  schema.py                     # schema validation layer (non-destructive)
  mappings.py                   # mapping-table layer (Phase 3 standardization)
  transform.py                  # transformation layer (adds derived columns)
  metrics.py                    # reusable count/cadence metric functions
app/                            # Streamlit UI (the only place that imports streamlit)
  streamlit_app.py              # entry point + validation report
  _shared.py                    # cached data access + global sidebar filters
  pages/
    1_Executive_Overview.py
    2_Employee_Allocation.py
    3_Area_Coverage.py
requirements.txt
```

## Canonical schema

The 10 source fields are kept verbatim for provenance:
`property, employee_name, day_of_week, start_time, end_time, location, task,
frequency, notes, source_text`.

The transformation layer **adds** (never overwrites) derived columns:
`property_name, frequency_canonical, is_defined_frequency, shift_band,
is_real_employee, is_explicit_task, is_bundled, area_type, task_category, day_list`.

## Reusability (Phase 5)

`property_name` is a first-class, row-level dimension (the Elm file alone carries
`Elm`, `Ledbury`, and `Elm/Ledbury`). To add a property, drop a conforming
`*_cleaning_responsibilities.csv` into `schedule_data/` — it is discovered,
validated, enriched, and filterable automatically. No code change.

To retune classification, edit the CSVs in `config/` (precedence = file order)
and rerun; source data is never touched.
```
