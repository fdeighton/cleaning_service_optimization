# Cleaning Operations Analysis & Modeling Framework
### Source of truth: extracted Parker schedule (448 task lines, 5 staff, 117 distinct locations)
*Prepared as an operations-analyst working document — methodology first, optimization later.*

---

## Executive orientation

The Parker dataset is **complete on the dimensions a schedule can carry, and silent on the dimensions workload analysis actually needs.** Every one of the 448 rows has a property, person, day, time block, location, task and frequency. None of them has a duration, an area size, a quality standard, or a reason. That single fact shapes everything below: with what we have we can describe and audit *allocation*; we cannot yet judge *appropriateness*. This report builds the bridge between the two.

---

## PHASE 1 — Data Audit

### 1.1 Operational dimensions available (and how clean they are)

| Dimension | Column | Coverage | Notes for analysis |
|---|---|---|---|
| Property | `property` | 100% | Single value here ("The Parker"); becomes a real dimension at portfolio scale. |
| Employee | `employee_name` | 100% | 5 staff. Volume skews: Karina 123 lines, Angie 117, Leonardo 113, Juan Carlos 61, Barbara 34. Line counts ≠ workload (see caveat). |
| Day / coverage pattern | `day_of_week` | 100% | Mixed grain: ranges (`Mon-Fri`, `Tue-Thu`) and single days. Must be **expanded** to per-day before any daily metric. |
| Schedule block | `start_time` + `end_time` | 100% | 33 distinct time blocks. This is the spine of any timeline/Gantt. |
| Area / location | `location` | 100% | 117 distinct strings — free text, inconsistent ("4 Elevators" vs "4 Elevator"). Needs a controlled vocabulary. |
| Task | `task` | 100% | Free text; compound phrases preserved verbatim. 59 rows carry **no explicit task verb** (facility/room notes). |
| Frequency | `frequency` | 100% populated, but **63 = "Unknown"** | Daily 143, Weekly 222, plus As-requested/Seasonal/Monthly tails. The "Unknown" block is concentrated in "Specials." |
| Provenance | `source_text`, `notes` | 100% / 73% | Excellent for traceability and re-derivation; not analytical variables themselves. |

**Derived dimensions already implied (not stored):** shift (AM/PM/overnight, inferable from start time), work category (chutes, glass, floors, etc. — derivable by keyword), and "task vs. re-check vs. facility-note" status.

### 1.2 What is missing for *true* workload analysis

The schedule answers **who / where / when / what**. Workload analysis needs **how much / how big / how good / why** — none of which are present:

1. **Task duration / standard time.** The single largest gap. A time block can hold 1 task or 12; without per-task minutes we cannot convert assignments into labour. (The dashboard's "shift hours" are *block coverage*, a ceiling, not effort.)
2. **Area size (square footage).** No way to normalize. "Clean the lobby" and "clean a washroom" are one row each but not one unit of effort.
3. **Cleaning standard / spec.** No definition of what "clean, dust, disinfect etc." must achieve, or to what frequency a surface *should* be done. Without this, "appropriate" has no reference point.
4. **Area type / function.** Lobby vs. amenity vs. back-of-house vs. residential corridor — currently only inferable from the name.
5. **Traffic / soil load.** The real driver of cleaning need (footfall, pets, weather exposure) is absent.
6. **Service-level agreement (SLA) / contract scope.** What WhiteRose is *contractually obligated* to clean and how often — the baseline that separates "over-serviced" from "doing the job."
7. **Headcount intent & paid hours.** Scheduled blocks ≠ paid hours ≠ FTE. No break/travel/setup time model.
8. **Outcome data.** No inspection scores, complaints, or re-clean triggers to validate that current frequencies are working.

### 1.3 Data to request, by owner

**From Development (building/asset data):**
- Floor plans with **square footage per area** and floor.
- Area inventory: every room/zone with a **function type** and floor.
- Building characteristics: floor count, elevator count, amenity list, flooring/finish type per area (carpet vs. tile drives method and time).
- Fixture counts (washroom stalls, chutes, BBQs) — already partially embedded in the schedule text.

**From Operations (how work actually happens):**
- **Standard task times** (or time-and-motion estimates) per task type per surface.
- Paid hours / shift definitions / break and travel allowances.
- Re-clean and complaint logs; inspection/QA scores.
- Actual vs. scheduled adherence (does the 6× lobby pass actually happen?).
- Traffic/soil indicators (foot-traffic counts, seasonal patterns, pet density).

**From WhiteRose (contract/standard data):**
- The **cleaning specification / scope of work** and contractual frequencies per area type.
- Quality standards / acceptable outcome definitions.
- Labour model and costing assumptions (loaded hourly rate, productivity targets such as SF/hour by area type).
- Equipment and consumable assumptions per task.

---

## PHASE 2 — Operational Model (normalized)

### Hierarchy
```
PROPERTY
  └── FLOOR / ZONE              (e.g., Ground, P1–P3, 38th, 39th)
        └── AREA                (atomic, typed, sized space: "Main Lobby", "Washroom #1")
              └── TASK          (a single verb on that area: "Dust mop", "Disinfect")
                    └── FREQUENCY ("Daily", "Weekly", "Monthly", "As-requested")
                          └── ASSIGNMENT (staff × day × time block)
```

### Normalized tables (target schema)
- **dim_property** (property_id, name, address, floors, total_sf, …)
- **dim_area** (area_id, property_id, floor, area_name, **area_type**, **area_sf**, surface_type, fixture_count)
- **dim_task** (task_id, **task_category**, task_verb, standard_minutes, method, surface_applicability)
- **dim_staff** (staff_id, property_id, name, role, shift, paid_hours)
- **fact_assignment** (assignment_id, property_id, area_id, task_id, staff_id, day, start_time, end_time, frequency, source_text)

The current 448-row export is effectively a denormalized **fact_assignment** with `dim_area` and `dim_task` embedded as free text. The modeling job is to lift those into governed dimensions.

### 2.1 The "unit of work"
Adopt a **two-tier** definition so we are honest about what we can measure now vs. later:

- **Schedule unit (available today):** `Area × Task × Frequency` — one normalized obligation, e.g. *"Main Lobby × dust-mop × daily."* This is countable from the schedule alone.
- **Effort unit (target, needs duration):** **Standard-minutes per occurrence × occurrences per week** = **weekly task-minutes**. This is the true currency of workload and the unit every benchmark below ultimately wants.

Until durations exist, use the schedule unit as the unit of work and label all "effort" figures as *proxy / planned-load*, never as labour hours.

### 2.2 Task categorization (proposed controlled taxonomy)
Two orthogonal axes:

**A. Functional category** (what kind of work): General Clean · Floors-Hard · Floors-Carpet · Glass/Windows · Chutes · Elevator Tracks · Washroom Service · Amenity (Indoor) · Amenity (Outdoor) · Outdoors/Grounds · Suites/Units · Detail/Specials · Re-check/Re-clean · Facility-note (no work).

**B. Effort class** (how heavy): Light-touch (re-check, empty trash) · Routine (dust/mop/disinfect) · Heavy/periodic (scrub, steam-clean, deep-clean) · Project/Special (baseboards, tracks, ventilation).

The combination lets us later ask "how many *heavy* tasks land on *amenity* areas weekly," which is the kind of question that drives rationalization.

### 2.3 Area categorization (proposed)
- **By function:** Lobby/Entrance · Circulation (corridors, stairs) · Vertical transport (elevators/chutes) · Washroom · Amenity-Indoor · Amenity-Outdoor · Parking · Back-of-house (storage, janitor, mechanical) · Residential (suites/units) · Grounds/Exterior.
- **By soil/traffic tier:** High (lobby, entrances, elevators) · Medium (corridors, amenities) · Low (storage, mechanical).
- **By surface:** Carpet · Hard floor · Glass · Mixed (drives method + standard time).

### 2.4 Most useful dimensions for future benchmarking
In priority order: **Area type** (the universal join key across buildings) → **Square footage** (the normalizer) → **Frequency** (the policy lever) → **Task category** (the method/effort lens) → **Floor/zone** and **Shift** (operational context). Area type + SF together are what make two different buildings comparable at all.

---

## PHASE 3 — Optimization Framework (deterministic, no ML)

### 3.1 What schedule data *alone* can evaluate
- **Allocation balance** — assignments and block-coverage per person/day; spot imbalance (Parker example: line counts range 34→123 across staff).
- **Coverage completeness** — which area types receive any service vs. none.
- **Frequency profile** — count of Daily/Weekly/Monthly/Unknown per area; surface the **63 "Unknown"-frequency** Parker rows as a governance gap.
- **Repeat-visit count** — same area cleaned N×/day (Parker: entrance touch-points hit up to 6×/day). Flags *candidate* duplication.
- **Temporal structure** — gaps, overlaps, clustering of heavy tasks, shift loading.

### 3.2 What *cannot* be evaluated without more data
- Whether a frequency is **correct** (needs SLA + traffic + outcomes).
- Whether effort is **proportionate** (needs duration + SF).
- Whether two passes are **redundant or both necessary** (needs standard + traffic).
- **Cost** of any area/task (needs hours + rate).
- True **understaffing/overstaffing** (needs effort vs. paid hours).

### 3.3 How square footage changes the analysis
SF turns *counting* into *rating*. Without it, every area is "1 row." With it:
- **Effort density** = task-minutes ÷ area_sf → comparable across rooms and buildings.
- **Coverage density** = cleans per week ÷ area_sf.
- Enables the portfolio KPI **hours per 1,000 SF**, the industry's lingua franca, and exposes areas that are large-but-light or small-but-heavy — invisible today.

### 3.4 How frequencies can be evaluated
Build a **frequency matrix: area_type × current frequency**, then compare each cell against (a) the **contract/SLA frequency**, (b) an **industry/peer norm**, and (c) **outcome data** (complaints, inspection fails). Three deterministic verdicts per cell:
- Current **> required** with clean outcomes → over-serviced (rationalization candidate).
- Current **< required** or current meets required but outcomes fail → under-serviced.
- Current **= required** with good outcomes → appropriate (leave alone).

### 3.5 How area-level workload can be benchmarked
For each area: **weekly task-minutes** (effort) and **weekly cleans** (coverage), both raw and per-1,000-SF. Rank within area type. Outliers above/below the type median are the investigation queue.

### 3.6 Proposed core framework — `Area × Task × Frequency × Square Footage`

Compute, per area:
```
Weekly Effort (min)   = Σ over tasks ( standard_minutes(task) × weekly_occurrences(frequency) )
Effort Density        = Weekly Effort ÷ (area_sf / 1000)        → minutes per 1,000 SF / week
Coverage Density      = Σ weekly_occurrences ÷ (area_sf / 1000) → cleans per 1,000 SF / week
Required Effort        = benchmark for that area_type (from SLA/peer)
Variance              = Effort Density − Required Effort        → signed gap
```

**How the four signals fall out of the variance + repeat-count:**
- **Over-serviced** — Effort/Coverage density well **above** the area-type benchmark *and* outcomes good. (Today, schedule-only proxy: high repeat-count on a low-traffic area.)
- **Under-serviced** — density **below** benchmark, or at/above benchmark but **outcomes failing**.
- **Duplicate work** — same area + same task + overlapping time across staff, or N daily passes beyond what the standard requires.
- **Scope rationalization** — area types serviced beyond SLA across the board, or "Unknown-frequency" specials that can be set to the minimum defensible cadence.

Until standard_minutes and area_sf arrive, run the framework in **proxy mode**: substitute `task_count` for effort and `repeat-count` for density, and clearly label outputs as directional.

---

## PHASE 4 — Dashboard Design (for management)

> Each dashboard states objective, metrics, visual, the insight it yields, and the decision it supports.

### 1. Executive Summary
- **Objective:** one-screen health read of the operation.
- **Metrics:** staff on shift, total planned-load hours, task lines, distinct areas, % frequencies defined, count of areas cleaned 3+×/day.
- **Visual:** KPI tiles + a single workload-balance bar.
- **Insight:** is the operation balanced and fully scoped? **Decision:** where to drill; whether scope/headcount review is warranted.
- **Why management cares:** fastest possible "is anything obviously off" signal.

### 2. Staffing Allocation
- **Objective:** see how labour is distributed across people and shifts.
- **Metrics:** block-coverage hours per person/day, assignment count, category mix per person, AM/PM/overnight split.
- **Visual:** horizontal bars (hours by person) + stacked category bars.
- **Insight:** imbalance and specialization (e.g., one person carries all heavy floor work). **Decision:** rebalance routes, justify or adjust headcount.

### 3. Area Coverage Matrix
- **Objective:** guarantee nothing is missed and nothing is gratuitously repeated.
- **Metrics:** cleans/week per `area_type × frequency`; flag zero-coverage and over-coverage cells.
- **Visual:** heatmap (rows = area types, cols = frequency bands; colour = count).
- **Insight:** coverage holes and concentration. **Decision:** add/trim service in specific area types.

### 4. Schedule Timeline / Gantt
- **Objective:** make the day legible.
- **Metrics:** start/end blocks per person, category-coloured; gaps and overlaps.
- **Visual:** per-employee Gantt with hover detail.
- **Insight:** idle windows, simultaneous coverage of the same zone. **Decision:** resequence, stagger, or merge passes.

### 5. Cleaning Intensity
- **Objective:** show effort concentration (the heart of the optimization case).
- **Metrics:** weekly task-minutes and minutes per 1,000 SF by area and area type; repeat-visit ranking.
- **Visual:** treemap (area sized by SF, coloured by intensity) + Pareto of repeat cleans.
- **Insight:** "where does effort pile up relative to size?" **Decision:** target over-/under-serviced areas. *(Requires duration + SF; runs in proxy mode until then.)*

### 6. Portfolio Benchmark *(future, multi-property)*
- **Objective:** compare buildings on a level field.
- **Metrics:** hours per 1,000 SF, cleaning intensity index, frequency-per-area-type, labour allocation by area type — all per property, vs. portfolio median.
- **Visual:** small-multiples / ranked bars with median reference line.
- **Insight:** which properties are outliers and why. **Decision:** propagate best practice, re-bid or re-scope outliers.

---

## PHASE 5 — Future State (scaling to more properties)

### 5.1 Scalable schema
The Phase-2 star schema (one `fact_assignment` + governed `dim_property/area/task/staff`) scales unchanged; each new building is rows in the fact table plus its area/staff dimension entries. **Two non-negotiables for scale:** a **controlled area-type vocabulary** and a **controlled task taxonomy**, both maintained centrally so buildings join cleanly. Keep `source_text` permanently for re-derivation/audit.

### 5.2 Benchmarking methodology
1. Normalize every property into the schema.
2. Compute per-area effort/coverage densities.
3. Roll up to **area-type medians across the portfolio** — these become the internal benchmark (more trustworthy than generic industry figures because they reflect your own buildings).
4. Score each area/property as variance from its type median.
5. Validate against SLA + outcomes before acting.

### 5.3 Repeatable workflow for a new property
**Extract** schedule → structured rows (proven on 6 buildings) → **Map** free-text locations/tasks to controlled `area_type`/`task_category` → **Enrich** with SF, standard times, SLA → **Compute** KPIs → **Benchmark** vs. portfolio → **Review** with Ops/WhiteRose → **Archive** with provenance. Steps 1–2 are automatable; step 3 is the data-collection dependency.

### 5.4 Recommended KPIs
- **Hours per 1,000 SF** (per property, per area type) — primary efficiency benchmark.
- **Cleaning intensity index** — task-minutes per 1,000 SF per week.
- **Frequency per area type** — vs. SLA and vs. portfolio norm.
- **Labour allocation by area type** — % of effort by zone; flags mis-weighting (e.g., lobbies dominating).
- **Coverage density** — cleans per 1,000 SF per week.
- **Scope-definition rate** — % of tasks with a defined (non-Unknown) frequency; a data-governance KPI.
- **Balance index** — spread of hours across staff (max−min, or coefficient of variation).

---

## PHASE 6 — Critical Review

### 6.1 Assumptions currently baked in
1. **The schedule reflects reality** — that planned passes actually occur as written. Unverified.
2. **One task line ≈ one comparable unit of effort** — false; a lobby clean and a trash-empty are not equal.
3. **Block coverage ≈ workload** — a ceiling, not effort; a block may be largely idle or overloaded.
4. **Repeat count = redundancy** — only a *candidate*; lobbies legitimately need multiple passes.
5. **Free-text locations map cleanly to area types** — requires manual governance; naming is inconsistent.
6. **Frequency labels are accurate** — but 14% of Parker rows are "Unknown," and range-days were expanded by rule.

### 6.2 Data gaps that create risk
- **No durations** → any "hours/effort/cost" figure is a proxy and can mislead if presented as fact.
- **No SF** → no normalization; cross-area and cross-building comparisons are unsafe.
- **No SLA/standard** → "over/under-serviced" has no reference; risk of cutting contractually required work.
- **No outcomes** → can't tell if current frequencies are sufficient; risk of optimizing into complaints.
- **Schedule ≠ actuals** → optimizing the plan while the floor does something else.

### 6.3 What could invalidate future conclusions
- Acting on **proxy effort** as if it were measured labour.
- Benchmarking buildings of **different finishes/traffic** as like-for-like.
- Treating a high repeat-count as waste when it is an SLA requirement.
- Stale dimension data (renovations change SF/area type; schedules drift monthly).
- Inconsistent taxonomy mapping across analysts → non-comparable buildings.

### 6.4 What would make this significantly more accurate (ranked)
1. **Standard task times** — unlocks real effort, hours, and cost. Highest leverage.
2. **Square footage + area-type inventory** — unlocks normalization and all benchmarks.
3. **Cleaning spec / SLA + frequencies** — gives "appropriate" a definition.
4. **Outcome data (inspections, complaints, re-cleans)** — validates frequency decisions.
5. **Actual-vs-scheduled adherence** — confirms the plan is the operation.
6. **Traffic/soil indicators** — explains *why* an area needs what it needs.

### 6.5 Specific recommendations
- **Now (schedule-only):** stand up dashboards 1–4 in *proxy mode*, clearly labelled "planned-load, not measured hours." Use them to surface candidates and drive the data request — not to cut scope.
- **Governance first:** lock a controlled **area-type vocabulary** and **task taxonomy** before adding properties; retro-map Parker as the reference build. Set a target to drive "Unknown" frequency to ~0%.
- **Data acquisition sprint:** prioritize standard times + SF + SLA (items 1–3) — these three convert the whole model from descriptive to evaluative.
- **Validate before action:** no over/under-service conclusion ships without SLA + outcome cross-checks.
- **Treat numbers honestly:** keep proxy and measured metrics visually distinct so management never mistakes one for the other.

---

### One-line summary
*We can fully describe and audit how Parker's cleaning work is allocated today; to judge whether it is allocated **correctly** we need three inputs — standard task times, square footage, and the cleaning spec/SLA — and the model above is built to absorb them the moment they arrive, then scale building-by-building on the same rails.*
