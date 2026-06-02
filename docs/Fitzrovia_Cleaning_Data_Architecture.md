# Portfolio Cleaning Operations — Data Architecture Specification
### Fitzrovia Residential · Pilot: The Parker · Source: WhiteRose schedules
*Scope: analytical foundation only. No effort estimation, no durations, no productivity assumptions. This document defines the data model that will later absorb those inputs.*

---

## Design premise

The current dataset is a **denormalized assignment log**: 448 rows in which `location` and `task` are free text, `frequency` is partially governed (63 rows "Unknown"), and casing alone fragments identical work (`"empty trash, replenish supplies, clean, dust, disinfect etc."` appears as 112 lowercase + 102 capitalized variants of the same task). The architecture below has one job at this stage: **convert that log into governed dimensions and a clean fact grain so that square footage, standard times, and SLAs can be bolted on later without re-engineering.** Every modeling choice is made to keep effort-based metrics *impossible to compute accidentally today* and *trivial to compute correctly tomorrow*.

---

## 1. Conceptual Data Model

### Entities and why each exists

| Entity | Reason it exists | Lifecycle |
|---|---|---|
| **Vendor** | WhiteRose today; the model must survive a vendor change or multi-vendor portfolio. Schedules, standards, and rates are vendor-scoped. | Slowly changing |
| **Property** | The portfolio unit and the top benchmarking grain. Carries address, floor count, build characteristics, total SF (when available). | Slowly changing |
| **Floor / Zone** | Intermediate spatial grouping (Ground, P1–P3, 38th, 39th). Parker locations are already floor-prefixed ("39th Floor Corridor"), so this is latent in the data and worth materializing. | Static per property |
| **Area** | The atomic, *typed and (future) sized* space — the join key that makes two buildings comparable. "Main Lobby", "39th Storage Rm.", "Dog Spa". Locations are already split to rows; this entity governs them. | Static per property; revised on renovation |
| **Area Type** | The canonical classification of an Area (Lobby, Washroom, Amenity-Indoor…). The single most important benchmarking dimension — buildings differ, area *types* recur. | Reference data |
| **Task** | A single cleaning action. Whether this is atomic or bundled is the Phase-4 decision; the entity exists either way. | Reference + transactional |
| **Task Category** | Canonical grouping of tasks (General Clean, Floors-Hard, Glass, Chutes…) plus an effort-class axis. Enables roll-up without parsing free text. | Reference data |
| **Frequency** | The cadence policy (Daily, Weekly, Monthly, As-requested, Unknown). A governed dimension, not a string — it later converts to occurrences/week. | Reference data |
| **Employee** | The assigned worker; carries Role and shift context. Drives allocation/coverage views. | Slowly changing |
| **Employee Role** | Canonical role (Day-cleaner, Night-cleaner, Lead, Floater). Separates person from function for staffing analysis. | Reference data |
| **Schedule Assignment** | The transactional heart: *who is scheduled to do what task, in what area, on what day, in what time block, at what frequency.* The fact. | Transactional |
| **Cleaning Standard / SLA** | The contractual spec: required frequency and outcome per Area Type × Task Category. **Currently empty**, but modeled now so "required vs. scheduled" comparisons are a join, not a rebuild. | Reference (future) |
| **Square Footage** | An attribute of Area (and a roll-up to Floor/Property). **Currently empty**; modeled as a first-class measure so density metrics drop in later. | Reference (future) |
| **Standard Time** | Vendor/industry minutes per Task Category × surface. **Currently empty**; the gate to all effort metrics. Deliberately isolated so it cannot leak into today's calculations. | Reference (future) |
| **Work Order** | Ad-hoc / reactive work (not on the standing schedule). Distinct from Schedule Assignment because it is event-driven and feeds future actual-vs-planned analysis. | Transactional (future) |

### Relationships (cardinality)
```
Vendor 1───* Property
Property 1───* Floor 1───* Area
Area *───1 AreaType
Area 1───* ScheduleAssignment *───1 Task *───1 TaskCategory
ScheduleAssignment *───1 Frequency
ScheduleAssignment *───1 Employee *───1 EmployeeRole
ScheduleAssignment *───1 Date/Day (calendar)
AreaType *───* CleaningStandard *───1 TaskCategory     (SLA grid, future)
Area 1───1 SquareFootage                                (future attribute)
TaskCategory *───* StandardTime (by surface)            (future)
WorkOrder *───1 Area, *───1 Task, *───1 Employee        (future, reactive)
```
A Schedule Assignment is the many-to-many resolution of Area × Task × Employee × Day × Frequency. Cleaning Standard and Standard Time hang off the *type* dimensions (Area Type, Task Category), never off individual rows — that is what lets one SLA row govern thousands of assignments across the portfolio.

---

## 2. Logical Data Model (star schema for Power BI)

### Grain decision
**One fact row = one Task occurrence-rule for one Area, one Employee, one schedule block, one day-pattern.** This is the atomic-task grain (see Phase 4). It is additive on counts (assignments, scheduled occurrences) and *non-additive on effort by design* — there is no effort column yet.

### Fact tables

**`fact_schedule_assignment`** (primary fact, available today)
| Column | Type | Key |
|---|---|---|
| assignment_id | int | **PK** |
| property_key | int | FK → dim_property |
| area_key | int | FK → dim_area |
| task_key | int | FK → dim_task |
| employee_key | int | FK → dim_employee |
| frequency_key | int | FK → dim_frequency |
| day_key | int | FK → dim_calendar (or dim_day_pattern) |
| start_time_key | int | FK → dim_time |
| end_time_key | int | FK → dim_time |
| occurrences_per_week | decimal | *derived measure* from frequency (Daily=7 or 5 per coverage rule, Weekly=1…); Unknown → NULL |
| is_explicit_task | bool | flags the 59 "no explicit verb" facility-note rows |
| source_text | varchar | provenance, retained permanently |

**`fact_cleaning_standard`** (future — SLA grid)
sla_id PK · area_type_key FK · task_category_key FK · required_frequency_key FK · required_outcome · vendor_key FK.

**`fact_work_order`** (future — reactive work)
work_order_id PK · area_key · task_key · employee_key · requested_date · completed_date.

> Standard Time and Square Footage enter as **attributes/measures on dimensions** (`dim_area.area_sf`, `dim_standard_time.minutes`), not as facts, so that turning them on is a column populate, not a schema migration.

### Dimension tables

- **dim_property** (property_key PK, property_name, vendor_key FK, floors, year_built, total_sf*, region)
- **dim_floor** (floor_key PK, property_key FK, floor_label, floor_order)
- **dim_area** (area_key PK, property_key FK, floor_key FK, area_name_raw, area_name_canonical, **area_type_key FK**, surface_type, fixture_count, **area_sf*** ) — *raw kept for traceability, canonical for joins.*
- **dim_area_type** (area_type_key PK, area_type, traffic_tier, default_surface)
- **dim_task** (task_key PK, task_verb_canonical, **task_category_key FK**, effort_class, surface_applicability, task_text_raw)
- **dim_task_category** (task_category_key PK, task_category, functional_axis, **standard_minutes*** by surface via bridge)
- **dim_frequency** (frequency_key PK, frequency_label, occurrences_per_week, is_defined_flag)
- **dim_employee** (employee_key PK, property_key FK, employee_name, **role_key FK**, shift)
- **dim_employee_role** (role_key PK, role_canonical)
- **dim_calendar / dim_day_pattern** (day_key PK, day_name, day_order, is_weekend) — with a **pattern-expansion bridge** that maps "Mon-Fri" → 5 day rows so every daily metric is unambiguous.
- **dim_time** (time_key PK, clock_time, hour, shift_band AM/PM/Overnight)
- **dim_vendor** (vendor_key PK, vendor_name)

*Columns marked \* are modeled but NULL until the corresponding dataset arrives.*

### Star topology (Power BI)
`fact_schedule_assignment` at the center; all dimensions one hop out (single-direction filters). Area Type, Task Category, Frequency, Role are reached through their parent dimension (snowflake on the reference layer) — acceptable in Power BI because these are tiny conformed dimensions and keep the canonical vocabularies centrally governed. **Conformed dimensions** (dim_area_type, dim_task_category, dim_frequency, dim_calendar, dim_vendor) are shared across all properties and all future facts — this is what makes the portfolio benchmark a filter, not a re-model.

---

## 3. Canonical Taxonomies

### 3.1 Area Types (with real Parker mappings)
| Canonical area_type | traffic_tier | Example raw locations → |
|---|---|---|
| Lobby / Entrance | High | "lobby", "Main Enterphone area", "Front", "Back" |
| Vertical Transport | High | "4 Elevators", "39th Floor Garbage Chute" |
| Circulation | Medium | "39th Floor Corridor", "Loading Dock Corridor & Exit", "3rd Floor Tiled Exit to patio" |
| Washroom | High | "2 Washrooms", "39th Floor 3 washrooms" |
| Amenity – Indoor | Medium | "Cafe", "39th Floor Yoga Studio", "38th Floor Games room", "Entertainment Kitchen", "Dog Spa" |
| Amenity – Outdoor | Medium | "Summer - Gr. Floor Patio", "Barbeque", "3rd Floor Dog Run Area", "Pool" |
| Parking | Medium | "P1-P3 Parking Lobbies w/4 exits each", "P3 Exit (Cement)" |
| Back-of-House | Low | "39th Storage Rm.", "P3 Housekeeping Room", "Mail Room", "Mngt. Office w/Kitchenette" |
| Residential / Suites | Variable | "Model Suite #507", "Guest Suite #506" |
| Grounds / Exterior | Low | "Breezeway/driveway", "Trash Cans", "3rd Floor Dog Exit" |

### 3.2 Task Categories (two axes)
**Functional axis** — General Clean · Floors-Hard · Floors-Carpet · Glass/Windows · Chutes · Elevator-Tracks · Washroom-Service · Amenity-Service · Outdoors/Grounds · Suites/Units · Detail/Specials · Re-check/Re-clean · Facility-Note(no work).
**Effort-class axis** *(structural label only — not a time estimate)* — Light-touch · Routine · Heavy/Periodic · Project.

Real mappings: `"empty trash, replenish supplies, clean, dust, disinfect etc."` → General Clean / Routine · `"Clean Chutes (doors, frames…)"` → Chutes / Heavy · `"Squeegee Glass (in/out)…"` → Glass / Routine · `"Spot clean Carpet Stains"` → Floors-Carpet / Light · `"Elevator doors and frames & TRACKS"` → Elevator-Tracks / Project · `"(no explicit task stated)"` → Facility-Note / —.

### 3.3 Frequencies
| Canonical | occurrences_per_week | is_defined | Raw seen |
|---|---|---|---|
| Daily | 7 (or 5 per coverage rule) | yes | "Daily" |
| Weekly | 1 | yes | "Weekly" |
| 2×/week | 2 | yes | "2x/week" |
| Monthly | 0.25 | yes | "Monthly" |
| Seasonal | rule-based | yes | "Seasonal" |
| On-demand | NULL | yes | "As requested", "As required", "When cleaning" |
| **Unknown** | NULL | **no** | "Unknown" (63 rows) |

`is_defined` becomes a governance KPI (% defined). On-demand and Unknown are distinct: on-demand is a *known* reactive policy; Unknown is *missing* policy.

### 3.4 Employee Roles
Day-Cleaner (LD/standard day) · Night-Cleaner (LD evening) · Heavy-Duty (HD) · Lead/Supervisor · Floater/Relief · Weekend-Relief. (Parker source headers already encode "LD"/"HD" and shift windows — role is derivable, not invented.)

---

## 4. Schedule Data Modeling — bundled vs. atomic tasks

**Recommendation: split to atomic task records, with a `task_group_id` retained to reconstruct the original bundle.**

A row like `"empty trash, replenish supplies, clean, dust, disinfect etc."` is five verbs in one cell. The decision is whether the fact grain is the *bundle* or the *verb*.

**Advantages of atomic:**
- **Clean join to Standard Time and SLA.** Effort and standards attach to a single task type; a bundle would need an unstable many-to-one parse every time. This is the decisive argument — the whole future model keys off Task Category, and bundles blur the category.
- **Accurate category roll-ups.** A bundle spanning General-Clean + Floors can't be cleanly attributed; atomic rows can.
- **Comparability across vendors/buildings** whose bundling conventions differ — atomic normalizes wording differences.
- **Optimization-ready.** LP/MIP/constraint models operate on discrete task–area–frequency units; atomic *is* the decision-variable grain.

**Disadvantages / costs:**
- **Row explosion** (the 448 grows several-fold) and the need for a defensible, documented splitting rule — splitting is a modeling decision that must be auditable, not silent.
- **Risk of false precision**: splitting "clean, dust, disinfect" into three implies they are separately schedulable when they're one motion. Mitigation: split on *distinct* actions, keep genuinely inseparable verb-strings as one atomic task, and store the original in `source_text` + `task_group_id`.
- **Double-counting hazard** for any future effort metric if the same minutes get attached to each split verb. Mitigation: assign Standard Time at the *atomic task* level only, never re-summed from a bundle.

**Scalability / optimization implication:** atomic + `task_group_id` is the only grain that scales to many properties *and* feeds OR-Tools-style models, while still letting Power BI reconstruct the human-readable bundle for operational views. **Do the split now, before SF/standards arrive**, so the reference grain is fixed before anyone builds on it.

---

## 5. Missing Data Assessment (ranked)

| Rank | Dataset | Unlocks | Why this rank |
|---|---|---|---|
| 1 | **Canonical Area + Area-Type inventory with Square Footage** | Normalization; all density metrics; cross-building comparability | Without typed, sized areas there is no denominator and no join key — every later metric depends on it. Highest because it is also the prerequisite for the SLA grid. |
| 2 | **Standard Times (per Task Category × surface)** | All effort, hours, intensity metrics | The single gate between *descriptive* and *evaluative*. Deliberately ranked below area data because times are meaningless without a typed area to attach them to. |
| 3 | **Cleaning Specification / SLA** | "Required vs. scheduled"; over/under-service definitions | Gives "appropriate" a reference. Without it, any service-level judgment is unanchored. |
| 4 | **Operational history** (inspections, complaints, re-cleans, actual-vs-scheduled) | Validation of frequencies; plan-vs-reality | Confirms the schedule is the operation and that current cadences work; protects against optimizing into failures. |
| 5 | **Surface / finish per area** | Correct standard-time selection; method analysis | Modifies #2; carpet vs. tile changes the applicable standard. |
| 6 | **Traffic / soil indicators** | Explains *why* frequencies differ | Lowest now — explanatory, not foundational; valuable once 1–4 exist. |

Items 1–3 are the **validity gate**: no effort-based benchmarking is defensible until all three exist. The architecture models all six as empty-but-wired so each is a populate, not a build.

---

## 6. Metrics Framework (staged by data availability)

> Formulas use only counts and cadences in Tier A. Effort, hours, and rates appear **only** in C+, by the user's constraint and by data reality.

### A. Available today (schedule only)
| Metric | Formula | Inputs | Purpose |
|---|---|---|---|
| Assignment count | COUNT(assignments) by any dim | fact only | Allocation distribution |
| Scheduled occurrences / week | Σ occurrences_per_week | frequency | Coverage volume (defined-freq rows only) |
| Coverage breadth | COUNT(DISTINCT area_type with ≥1 assignment) | fact + area_type | Are all area types served? |
| Repeat-visit count | COUNT(assignments) per area per day | fact + calendar | Candidate duplication (descriptive only) |
| Frequency profile | share of assignments by frequency band | frequency | Cadence mix |
| **Scope-definition rate** | defined-freq rows ÷ all rows | frequency.is_defined | Governance KPI (Parker: 86%) |
| Block coverage span | merged unique [start,end] per employee per day | time, employee | Schedule footprint (NOT effort) |
| Balance index | max−min (or CV) of block span across staff | above | Allocation evenness |

### B. After Square Footage
| Metric | Formula | Inputs | Purpose |
|---|---|---|---|
| Coverage density | weekly occurrences ÷ (area_sf/1000) | + area_sf | Service per 1,000 SF — first normalized metric |
| Area-type SF distribution | Σ area_sf by area_type | area, area_type | Where space concentrates |
| Assignment density | assignments ÷ (area_sf/1000) | + area_sf | Attention per unit area |

### C. After Standard Times *(effort enters here, never before)*
| Metric | Formula | Inputs | Purpose |
|---|---|---|---|
| Weekly task-minutes | Σ (standard_minutes × occurrences_per_week) | + standard_time | True planned effort |
| Effort density | weekly task-minutes ÷ (area_sf/1000) | + SF + time | Cleaning intensity per 1,000 SF |
| Labour allocation by area type | effort share by area_type | as above | Where effort concentrates |
| Hours per 1,000 SF | weekly task-minutes/60 ÷ (total_sf/1000) | as above | Cross-building efficiency benchmark |

### D. After Operational History
| Metric | Formula | Inputs | Purpose |
|---|---|---|---|
| Schedule adherence | actual occurrences ÷ scheduled | + work/actuals log | Plan vs. reality |
| Frequency adequacy | complaints/fails per area-type vs. frequency | + outcomes | Is cadence sufficient? |
| Reactive ratio | work-order count ÷ scheduled count | + work orders | Stability of the standing plan |

---

## 7. Future Optimization Readiness (no rates assumed)

The model is built so optimization plugs into governed dimensions, not re-derived strings:

- **Staffing analysis** — `fact_schedule_assignment` × `dim_employee/role` × `dim_time` already supports allocation, balance, and shift-loading views today; adding Standard Time converts these to capacity models without touching the schema.
- **Scope rationalization** — once the SLA grid (`fact_cleaning_standard`) is populated, a deterministic join of *scheduled frequency vs. required frequency* per Area Type × Task Category surfaces over/under-scope as a calculated column — no estimation involved.
- **Frequency optimization** — `dim_frequency.occurrences_per_week` is a tunable parameter; constraint models can vary it per Area Type subject to SLA minimums, using occurrences (not hours) as the objective if rates are withheld.
- **Contract negotiation** — atomic Task × Area Type × Frequency, normalized by SF, gives a defensible scope inventory to negotiate against, independent of any labour rate.
- **Portfolio benchmarking** — conformed dimensions mean a new property is rows under the same Area Types and Task Categories; medians roll up automatically. Benchmarks can run on coverage density (Tier B) before any time data exists.

Because effort lives only in optional Tier-C columns, **every optimization above can be specified and even partially run on counts and cadences alone**, then sharpened when Standard Times arrive — exactly the staged readiness requested.

---

## 8. Critical Review

**Hidden assumptions in the current approach**
1. **Split-to-atomic introduces a modeling opinion.** Deciding where "clean, dust, disinfect" stops being one task is a judgment that, if undocumented, contaminates every downstream count. The `task_group_id` + a written splitting rule are mandatory, not optional.
2. **`occurrences_per_week` for "Daily" is a coverage assumption** (5 vs. 7) that silently scales every Tier-A volume metric. It must be a governed, visible parameter, not a hard-code.
3. **Day-pattern expansion ("Mon-Fri" → 5 rows) assumes uniform weekday work** — true for Parker, but a future schedule with weekday variation would be misrepresented unless the bridge preserves the original pattern.
4. **Area-type mapping assumes the name reveals the function.** "Dog Spa" and "Cafe" are clear; "Specials" and bare floor numbers are not. Mapping is a human-governed step with an error rate that should itself be tracked.

**Data-gap risks**
- **The validity gate (SF + Standard Time + SLA) is entirely external.** The model's usefulness is hostage to data Fitzrovia does not yet control; the architecture cannot manufacture it.
- **Schedule ≠ actuals.** The entire model describes *intended* work. Without operational history (Tier D), even perfectly normalized benchmarks describe the plan, not the operation.
- **Vendor wording drift.** Across vendors/properties, the same work is phrased differently; taxonomy mapping is the chokepoint and the most likely source of non-comparability at scale.

**What could invalidate future conclusions**
- Treating Tier-A counts as proxies for effort (a category error the schema *structurally prevents* by withholding an effort column — keep it that way).
- Benchmarking buildings of different finishes/traffic as like-for-like before Tier-B/C exist.
- Stale dimensions: renovations change SF and area type; monthly schedule reissues drift. Without an effective-dating strategy (SCD Type 2 on dim_area/dim_property), historical benchmarks silently corrupt.

**Where I challenge the framework**
- The instinct to split *every* verb is over-engineering. Split on **distinct actions and distinct surfaces**, not on every comma; inseparable motions stay as one atomic task. Over-splitting manufactures false precision and double-counting risk that no later data can undo.
- A pure star schema tempts teams to **flatten Area Type and Task Category into the fact** for speed. Resist it — the conformed reference dimensions are the entire basis of portfolio comparability; denormalizing them re-creates the free-text problem this project exists to solve.

**Recommendations to materially increase accuracy (ranked)**
1. **Adopt SCD Type-2** on `dim_property` and `dim_area` before the second property loads — renovations and re-scoping are inevitable and will otherwise corrupt trend analysis.
2. **Publish the splitting rule and the Daily-occurrences rule as governed metadata**, versioned, so every count is reproducible and auditable.
3. **Stand up the taxonomy as a managed reference dataset** (owner, change log, mapping-confidence flag) — it is the highest-leverage, lowest-cost accuracy investment and the one most likely to be skipped.
4. **Wire the empty Tier-B/C/D tables now** (SF, Standard Time, SLA, Work Order) so data acquisition is a populate, never a migration — and so the team can see exactly which joins light up which metrics.
5. **Keep effort structurally absent until Tier C** — no calculated "hours" column anywhere in the model until Standard Times exist, removing the temptation to estimate.

---

### Bottom line
The architecture's purpose at this stage is not to measure work but to **make work measurable later, correctly, and at portfolio scale**: governed Area Types and Task Categories as conformed dimensions, an atomic task grain with bundle traceability, frequency as a tunable parameter, and SF / Standard Time / SLA modeled as wired-but-empty so the validity gate is a data problem — not a redesign — the day Fitzrovia clears it.
