# CleanLens — Fitzrovia Cleaning Schedule Visual Analytics Specification
### Pilot: The Parker · Portfolio-ready · Schedule-data-only (no effort, no durations, no estimates)
*Implementation-ready spec. Every measure below uses only the 10 standardized fields. Anything labelled **[PROXY]** is a schedule-derived approximation, never a workload claim.*

---

## 1. Tool Concept

**Name: CleanLens** — a reusable, property-agnostic lens on any Fitzrovia cleaning schedule.

**Architecture recommendation: Power BI on a SQL-backed star semantic model (hybrid).**

| Option | Verdict | Why |
|---|---|---|
| **Power BI + SQL semantic model** | ✅ **Build this** | Native matrix/heatmap/small-multiples; one published dataset, many properties via slicer; RLS per property; refreshes when new buildings load. The standardized 10-field schema is tailor-made for a conformed star model. |
| Python/Streamlit | Secondary | Good for the *ingestion + Sankey/network* pieces Power BI does poorly; use as a pre-processor and for the two exotic visuals, not the management surface. |
| Excel | ❌ | Won't scale to portfolio, no governed model, manual per-property rebuild. |
| Pure SQL+BI | Partial | The SQL layer is the *foundation*, not the deliverable; pair with Power BI. |

**Net:** SQL view layer (cleansing + conformed keys) → Power BI semantic model (star, measures in DAX) → CleanLens report (10 pages). Streamlit only for Sankey/network and the schedule-ingestion utility.

---

## 2. Dashboard Pages

> Conventions: every page carries global slicers **Property · Day · Employee · Area Type · Frequency**. "Interpretation guide" tells the user what good/bad looks like.

### Page 1 — Executive Overview
- **Purpose:** 60-second health read of one property's schedule.
- **User:** Property manager, regional director.
- **Slicers:** Property, Day.
- **Visuals:**
  - **KPI cards** (8): Scheduled Assignments, Distinct Employees, Distinct Areas, Distinct Tasks, Schedule Blocks, Defined-Frequency Rate %, Bundled-Task Rate % **[PROXY]**, Location-Standardization Issues.
  - **Donut** — assignment share by Frequency band.
  - **Horizontal bar** — assignments by Employee.
  - **Treemap** — assignments by Area Type.
- **Measures:** `Assignment Count`, `Distinct Employees/Areas/Tasks`, `Schedule Block Count`, `Defined Frequency Rate`, `Bundled Task Rate`, `Loc Std Issue Count`.
- **Tooltip:** count, % of property total, rank.
- **Interpretation:** balanced employee bars + high defined-frequency rate (Parker: 86%) = healthy; one giant treemap tile or low defined-rate = drill deeper.

### Page 2 — Property Schedule Summary
- **Purpose:** the full shape of one property's standing schedule.
- **User:** Operations analyst.
- **Slicers:** Property, Day, Shift band.
- **Visuals:** Stacked bar (assignments by Day × Frequency); column (assignments by Shift band AM/PM/Overnight); table (Area → assignment count, distinct tasks, frequency mix).
- **Measures:** `Assignment Count`, `Task Count by Area`, `Frequency Count`.
- **Tooltip:** day, shift, frequency breakdown.
- **Interpretation:** even day distribution is expected for residential; spikes flag weekend-only or special-day load.

### Page 3 — Employee Allocation
- **Purpose:** who is assigned how much and where.
- **User:** Manager, scheduler.
- **Slicers:** Property, Day, Employee, Area Type.
- **Visuals:**
  - **Horizontal bar** — assignment count by Employee.
  - **Stacked bar** — Employee × Area Type (assignment count).
  - **Stacked bar** — Employee × Task Category.
  - **Matrix** — Employee (rows) × Day (cols), value = Schedule Block Count.
- **Measures:** `Assignment Count`, `Employee-Location Coverage`, `Task Count by Employee`, `Schedule Block Count`.
- **Tooltip:** employee, area type, task category, blocks.
- **Interpretation:** wildly unequal bars = allocation question (NOT a fairness verdict — counts ≠ effort); one employee owning a whole task category = specialization/risk concentration.

### Page 4 — Area Coverage
- **Purpose:** which areas/area-types get the most scheduled attention.
- **User:** Operations analyst.
- **Slicers:** Property, Area Type, Day, Frequency.
- **Visuals:**
  - **Treemap** — Area Type → Area, sized by assignment count.
  - **Bar** — top 20 Areas by assignment count.
  - **Heatmap** — Area Type (rows) × Day (cols), value = assignment count.
  - **Bar** — assignments per Area Type, split defined vs. unknown frequency.
- **Measures:** `Assignment Count`, `Area-Task Coverage`, `Coverage Density Proxy` **[PROXY]**.
- **Tooltip:** area, area type, tasks, frequencies.
- **Interpretation:** high-count entrance/lobby areas are normal; a back-of-house area with high counts is worth a look. **Density here is assignment-based [PROXY] — not effort.**

### Page 5 — Task & Frequency Analysis
- **Purpose:** what work dominates and at what cadence.
- **User:** Analyst, WhiteRose liaison.
- **Slicers:** Property, Task Category, Frequency.
- **Visuals:** Bar (assignments by Task Category); 100% stacked bar (Task Category × Frequency); donut (Frequency mix); bar (top tasks by raw text, with Bundled flag).
- **Measures:** `Assignment Count`, `Frequency Count`, `Bundled Task Rate` **[structural]**.
- **Tooltip:** category, frequency, bundled Y/N.
- **Interpretation:** a Task Category sitting mostly in "Unknown" frequency = governance gap; high bundled rate (Parker: 59%) = atomic-split backlog.

### Page 6 — Weekly Schedule Timeline (Gantt)
- **Purpose:** make the operating day legible.
- **User:** Manager, scheduler.
- **Slicers:** Property, Day, Employee.
- **Visuals:**
  - **Gantt** (custom visual / matrix-as-Gantt) — rows = Employee, x = time-of-day, bars = schedule blocks coloured by Task Category.
  - **Calendar strip** — Day-of-week × Shift band density.
- **Measures:** `Schedule Block Count`, block start/end from `dim_time_block`.
- **Tooltip:** start–end, task category, areas in block, tasks in block.
- **Interpretation:** visible idle windows or two employees covering the same zone simultaneously = sequencing observations (not optimization claims).

### Page 7 — Area × Task Matrix
- **Purpose:** which task types touch which area types.
- **User:** Analyst, WhiteRose.
- **Slicers:** Property, Frequency.
- **Visuals:** **Matrix heatmap** — rows = Area Type, cols = Task Category, value = assignment count, conditional-formatted.
- **Measures:** `Area-Task Coverage`, `Assignment Count`.
- **Tooltip:** area type, task category, count, frequency mix.
- **Interpretation:** empty cells = an area type never receiving a task type (coverage gap or correctly N/A); dense rows = high-attention area types.

### Page 8 — Employee × Area Matrix
- **Purpose:** coverage map of people to places.
- **User:** Manager.
- **Slicers:** Property, Day.
- **Visuals:** **Matrix** — rows = Employee, cols = Area Type, value = assignment count; secondary **bar** = distinct area types per employee.
- **Measures:** `Employee-Location Coverage`, `Assignment Count`.
- **Tooltip:** employee, area type, distinct areas.
- **Interpretation:** single-employee area types = key-person dependency; very wide coverage per person = generalist routing.

### Page 9 — Data Quality Audit
- **Purpose:** trust the data before trusting the charts.
- **User:** Data steward, analyst.
- **Slicers:** Property.
- **Visuals:**
  - **Scorecard** (gauge/cards): Defined-Frequency Rate, Location-Standardization Issue Count, Bundled-Task Rate, No-Explicit-Task Count, % rows with notes.
  - **Table** — location standardization clusters (raw variants of same normalized name, e.g. *Mail Room / Mail room*; *PARKER PLAQUE / PARKER Plaque*).
  - **Bar** — Unknown-frequency assignments by Area Type.
- **Measures:** `Unknown Frequency Rate`, `Loc Std Issue Count`, `Bundled Task Rate`, `No-Explicit-Task Count`.
- **Tooltip:** raw variants, counts.
- **Interpretation:** these are the **gating metrics** — every other page inherits their reliability. Parker baseline: 86% defined freq, 59% bundled, 3 standardization clusters, 59 no-task rows.

### Page 10 — Portfolio Benchmarking
- **Purpose:** compare properties on schedule-only metrics (valid today).
- **User:** Regional director, portfolio lead.
- **Slicers:** Property (multi-select), Area Type, Frequency.
- **Visuals:**
  - **Small multiples** — frequency-mix donut per property.
  - **Clustered bar** — Assignment Count / Distinct Locations / Distinct Tasks by Property.
  - **100% stacked bar** — Task Category mix by Property.
  - **Bar** — Data-Quality score by Property.
- **Measures:** all Tier-A measures, grouped by Property.
- **Tooltip:** property, metric, portfolio median.
- **Interpretation:** differences in *mix and data quality* are valid; **do not read count differences as efficiency** — buildings differ in size and scope (see §7).

---

## 3. Visualization Catalog (30)

> Format: name · question · fields · measures · encoding · interpretation · red flag.

1. **Assignment KPI cards** · How much scheduled work? · all · `Assignment Count` · number tiles · scale baseline · *red flag:* count swings vs. last refresh with no schedule change.
2. **Frequency donut** · What cadence dominates? · frequency · `Frequency Count` · angle=share · cadence profile · *red flag:* large "Unknown" slice.
3. **Assignments by Employee (bar)** · Who has most assignments? · employee · `Assignment Count` · length=count · allocation spread · *red flag:* one bar ≫ others (investigate, not judge).
4. **Employee × Area Type (stacked bar)** · Where is each person assigned? · employee, area_type · `Assignment Count` · stack=area type · routing mix · *red flag:* a person with a single area type only.
5. **Employee × Task Category (stacked bar)** · What work does each do? · employee, task_category · `Task Count by Employee` · stack=category · specialization · *red flag:* full category owned by one person.
6. **Area Type treemap** · Which area types get attention? · area_type · `Assignment Count` · tile size=count · attention map · *red flag:* low-traffic type with outsized tile.
7. **Top-20 Areas (bar)** · Which specific areas dominate? · location · `Assignment Count` · length=count · hotspot list · *red flag:* back-of-house area near top.
8. **Area Type × Day heatmap** · When are areas served? · area_type, day · `Assignment Count` · colour=count · weekly rhythm · *red flag:* an area type blank on weekdays.
9. **Task Category bar** · What work dominates? · task_category · `Assignment Count` · length=count · effort-type mix [structural] · *red flag:* "Other"/"Facility-note" large = taxonomy gaps.
10. **Task Category × Frequency (100% stacked)** · Are categories on sensible cadences? · task_category, frequency · `Assignment Count` · stack=frequency · cadence consistency · *red flag:* category mostly Unknown.
11. **Frequency mix donut** · Cadence profile · frequency · `Frequency Count` · angle · profile · *red flag:* Unknown > 15%.
12. **Top tasks (raw) bar w/ bundled flag** · Which task strings recur? · task · `Assignment Count`, `Bundled Flag` · length+icon · normalization need · *red flag:* high bundled rate.
13. **Employee Gantt** · What does the day look like? · employee, time_block, task_category · `Schedule Block Count` · x=time, colour=category · day legibility · *red flag:* overlapping same-zone coverage.
14. **Calendar density strip** · Which days/shifts are heavy? · day, shift · `Assignment Count` · colour=count · load rhythm · *red flag:* unexplained single-day spike.
15. **Area × Task matrix heatmap** · Which tasks touch which areas? · area_type, task_category · `Area-Task Coverage` · colour=count · coverage map · *red flag:* expected cell empty.
16. **Employee × Area matrix** · Who covers where? · employee, area_type · `Employee-Location Coverage` · colour=count · coverage map · *red flag:* single-person area type (key-person risk).
17. **Distinct-area-types per employee (bar)** · Generalist vs specialist? · employee · `DISTINCTCOUNT area_type` · length · breadth · *red flag:* one person covering everything.
18. **Defined-Frequency gauge** · Is cadence governed? · frequency · `Defined Frequency Rate` · gauge · governance · *red flag:* < 85%.
19. **Location standardization table** · Are names clean? · location · `Loc Std Issue Count` · text clusters · data hygiene · *red flag:* >0 clusters (Parker: Mail Room/Mail room).
20. **Bundled-task scorecard** · Atomic-split backlog? · task · `Bundled Task Rate` · card · modeling debt · *red flag:* >50% (Parker: 59%).
21. **No-explicit-task bar** · How many facility-note rows? · task, area_type · `No-Explicit-Task Count` · length · scope clarity · *red flag:* concentrated in serviceable areas.
22. **Unknown-frequency by Area Type (bar)** · Where is cadence undefined? · area_type, frequency · `Unknown Frequency Rate` · length · gap location · *red flag:* core area type with high unknown.
23. **Property comparison clustered bar** · How do buildings differ (counts)? · property · Tier-A measures · grouped bars · scope contrast · *red flag:* misread as efficiency.
24. **Task-category mix by property (100% stacked)** · Different work profiles? · property, task_category · `Assignment Count` · stack · profile compare · *red flag:* none — descriptive only.
25. **Frequency mix small multiples** · Cadence per building · property, frequency · `Frequency Count` · donut grid · pattern compare · *red flag:* one building all-Unknown.
26. **Data-quality score by property (bar)** · Which data to trust? · property · composite DQ score · length · trust ranking · *red flag:* a building far below peers.
27. **Schedule blocks by employee×day (matrix)** · Shift structure · employee, day · `Schedule Block Count` · colour · structure · *red flag:* a person with zero blocks on a working day.
28. **Sankey: Employee → Area Type → Task Category** *(Streamlit)* · How does work flow? · employee, area_type, task_category · `Assignment Count` · flow width=count · routing structure · *red flag:* one dominant channel hiding others.
29. **Network: Employee–Area co-assignment** *(Streamlit)* · Who shares areas? · employee, location · edge=shared area · node/edge graph · backup coverage · *red flag:* isolated node (no backup).
30. **Coverage-density-proxy bar by Area Type** **[PROXY]** · Relative attention per area type · area_type · `Coverage Density Proxy` · length · attention proxy · *red flag:* reading as workload — it is assignment count per distinct area, not effort.

---

## 4. Measures & Calculated Fields (DAX, schedule-only)

```DAX
Assignment Count        = COUNTROWS(fact_schedule_assignment)
Distinct Employees      = DISTINCTCOUNT(fact[employee_key])
Distinct Locations      = DISTINCTCOUNT(fact[location_raw])
Distinct Tasks          = DISTINCTCOUNT(fact[task_key])
Distinct Areas          = DISTINCTCOUNT(dim_location[area_key])
Task Count by Area      = CALCULATE([Assignment Count], ALLEXCEPT(fact, dim_location[area_key]))
Task Count by Employee  = CALCULATE([Assignment Count], ALLEXCEPT(fact, dim_employee[employee_key]))
Frequency Count         = CALCULATE([Assignment Count], ALLEXCEPT(fact, dim_frequency[frequency_key]))

-- governance / quality
Unknown Frequency Rate  = DIVIDE(
                            CALCULATE([Assignment Count], dim_frequency[is_defined_flag]=FALSE),
                            [Assignment Count])                       -- Parker: 14%
Defined Frequency Rate  = 1 - [Unknown Frequency Rate]               -- Parker: 86%
Loc Std Issue Count     = COUNTROWS(FILTER(
                            SUMMARIZE(dim_location, dim_location[area_name_canonical],
                              "variants", DISTINCTCOUNT(dim_location[area_name_raw])),
                            [variants] > 1))                          -- Parker: 3 clusters
Bundled Task Rate       = DIVIDE(
                            CALCULATE([Assignment Count], dim_task[is_bundled]=TRUE),
                            [Assignment Count])   -- [structural] flag = task text has ',' '&' or 'etc' ; Parker: 59%
No-Explicit-Task Count  = CALCULATE([Assignment Count], fact[is_explicit_task]=FALSE)  -- Parker: 59

-- structure
Schedule Block Count    = DISTINCTCOUNT(fact[block_key])
                          -- block_key = hash(employee_key, day_key, start_time, end_time); Parker: 73
Employee-Location Coverage = DISTINCTCOUNT(fact[employee_key] & "|" & dim_location[area_key])
Area-Task Coverage      = DISTINCTCOUNT(dim_location[area_key] & "|" & dim_task_category[task_category_key])

-- [PROXY] — assignment-based, NOT effort/workload
Coverage Density Proxy  = DIVIDE([Assignment Count], [Distinct Areas])  -- assignments per distinct area
Property Coverage Density Proxy = DIVIDE([Assignment Count], DISTINCTCOUNT(dim_location[area_key]))
```
**Proxy labelling rule:** any measure whose name ends `Proxy` is rendered with a ⚠ icon and a fixed tooltip: *"Schedule-derived approximation. Not labour, effort, or productivity."*

---

## 5. Visual Storytelling Layer — 5-minute read

- **Step 1 — Total scheduled work** *(Page 1 cards):* read Assignment Count, Employees, Areas, Blocks. This is the size of the standing schedule.
- **Step 2 — Where work concentrates** *(Page 4 treemap + Page 6 Area heatmap):* biggest tiles = most-assigned area types; expect entrances/lobbies high.
- **Step 3 — Employee allocation** *(Page 3 bars + matrix):* is assignment volume spread or lopsided? Note specialization. *Do not call it fairness — counts aren't effort.*
- **Step 4 — Area coverage** *(Page 7 Area×Task matrix):* scan for empty cells (gaps) and dense rows (high-attention types).
- **Step 5 — Task & frequency consistency** *(Page 5):* is each task category on a sensible, defined cadence? Watch the Unknown slice.
- **Step 6 — Data quality** *(Page 9 scorecard):* check Defined-Frequency Rate, standardization clusters, bundled rate. **If these are poor, treat every earlier page as provisional.**
- **Step 7 — Portfolio compare** *(Page 10, when ≥2 properties):* compare mix and data-quality, never raw efficiency.

---

## 6. Global Tool Design

| Layer | Global (shared) | Property-specific |
|---|---|---|
| Semantic model | conformed dims: Area Type, Task Category, Frequency, Day, Time Block, Role | dim_location rows, dim_employee rows |
| Measures | all DAX above (write once) | none — measures are universal |
| Report pages | all 10 page templates | rendered per Property via slicer |
| Taxonomy mapping | central, version-controlled | the raw→canonical mapping table per building |

- **Cross-property slicers:** Property (multi-select), Area Type, Task Category, Frequency, Day — all conformed, so they filter every building identically.
- **Valid benchmark metrics today:** assignment counts, distinct locations/tasks/areas, task-category mix, frequency mix, schedule-block counts, **data-quality scores**.
- **Invalid until SF + Standard Times:** anything per-SF, any "hours," intensity, labour allocation, staffing adequacy, cost. These columns exist in the model but stay NULL and their visuals are hidden until populated.

---

## 7. Portfolio Benchmarking Readiness

**Valid today (schedule-only, count-based):**
- Assignment count by property — *scope volume.*
- Distinct locations / tasks / areas by property — *scope breadth.*
- Task-category mix by property — *work profile.*
- Frequency mix by property — *cadence policy.*
- Data-quality score by property — *data trustworthiness.*

**NOT valid today (and why):**
- **Labour efficiency / productivity** — requires durations and actuals; none exist.
- **Workload fairness** — assignment count ≠ effort; a 5-task lobby block ≠ a 5-task storage-room block.
- **Cost efficiency** — needs hours × rate; explicitly out of scope.
- **Staffing adequacy** — needs effort vs. paid capacity; unmeasurable from a schedule.

Why: every invalid metric divides by or multiplies an effort/size quantity the dataset does not contain. Counts describe *what is scheduled*, not *what it costs or takes*.

---

## 8. Data Model for the Visual Tool

**Star, single fact, conformed dims.**

```
                 dim_property ──┐
dim_employee ─┐                 │
dim_location ─┼──< fact_schedule_assignment >──┬── dim_frequency
dim_task ─────┘     (grain: 1 atomic task ×    ├── dim_day
                     area × employee × block)   └── dim_time_block
dim_location >── dim_area_type     dim_task >── dim_task_category   (snowflake refs)
```

| Table | PK | Key FKs | Notes |
|---|---|---|---|
| **fact_schedule_assignment** | assignment_id | property_key, location_key→area, employee_key, task_key, frequency_key, day_key, time_block_key | + occurrences_per_week, is_explicit_task, block_key, source_text |
| dim_property | property_key | — | name, region, (sf NULL) |
| dim_employee | employee_key | property_key, role_key | name, shift |
| dim_location | location_key | property_key, area_type_key | area_name_raw, area_name_canonical, (area_sf NULL) |
| dim_area_type | area_type_key | — | area_type, traffic_tier |
| dim_task | task_key | task_category_key | task_text_raw, task_verb_canonical, is_bundled, (std_minutes NULL) |
| dim_frequency | frequency_key | — | frequency_label, occurrences_per_week, is_defined_flag |
| dim_day | day_key | — | day_name, day_order, is_weekend (+ pattern-expansion bridge) |
| dim_time_block | time_block_key | — | start_time, end_time, shift_band |

**Relationships:** all 1→many from dim to fact, single-direction filter. Area Type and Task Category reached via their parent dim (small conformed reference snowflake — keeps the vocabulary centrally governed). `dim_day` includes a bridge expanding "Mon-Fri"→5 days so daily metrics are unambiguous.

---

## 9. Implementation Plan

| Phase | Inputs | Outputs | Dashboards enabled | Limitations |
|---|---|---|---|---|
| **1 — Parker prototype** | Parker CSV (10 fields) | SQL cleansing views + Power BI star + measures; Pages 1–9 for Parker | Everything except Portfolio (P10) | Single property; bundled tasks not yet split; no benchmarking |
| **2 — Global semantic model** | Phase-1 model + conformed dims | Published dataset, taxonomy mapping table, RLS, parameterized pages | All pages as templates; P10 ready (1 property) | Still 1 building; comparisons trivial |
| **3 — Add properties** | More schedules in same 10-field format | Multi-property fact; mapping per building | **P10 Portfolio Benchmarking live** (count/mix/DQ only) | Only count-based comparisons valid |
| **4 — Add square footage** | dim_location.area_sf populated | Density (Tier-B) measures un-hidden | Coverage-density per 1,000 SF, area-type SF distribution | Still no effort/hours |
| **5 — Add standard times** | dim_task.std_minutes populated | Effort (Tier-C) measures un-hidden | Intensity, labour allocation, hours/1,000 SF | Planned effort, not actuals |
| **6 — Benchmark + optimization readiness** | + operational history/SLA | Adherence, frequency-adequacy; OR-ready extract | Full benchmarking; feeds LP/MIP later | Optimization itself out of this tool's scope |

---

## 10. Final Recommendation — build this first

**Build Phase 1 + the conformed shell of Phase 2 in one pass:**

1. **SQL cleansing views** that (a) canonicalize location names (fold *Mail Room/Mail room*, *PARKER PLAQUE/PARKER Plaque* — 3 clusters today), (b) lowercase-normalize task text to kill casing duplicates, (c) flag `is_bundled` and `is_explicit_task`, (d) map raw locations/tasks to **Area Type** and **Task Category** via a version-controlled mapping table, (e) derive `block_key`, `occurrences_per_week`, `is_defined_flag`.
2. **Power BI star model** exactly as §8, with SF/std-minutes columns present but NULL and their visuals hidden behind a "data available" flag.
3. **Ship Pages 1, 9, and 3 first** — Executive Overview, **Data Quality Audit**, Employee Allocation. Quality first is deliberate: it tells managers how far to trust the rest, and it produces the immediate, defensible wins (86% defined frequency, 59% bundled, 3 standardization clusters, 59 facility-note rows) that justify the build.
4. Then fill in Pages 2,4,5,6,7,8; leave Page 10 as a template that activates on the second property.

**Why this order:** the conformed dimensions and the cleansing layer are the reusable asset — build them once on Parker and every future building is a data-load, not a project. Lead with Data Quality because it is the only page whose conclusions are fully valid today and it gates the credibility of everything else. Defer every per-SF and per-hour visual into hidden, wired columns so the tool never tempts anyone to read effort that the data cannot support.

*First concrete artifact to produce: the SQL cleansing view + the raw→canonical Area Type / Task Category mapping table for Parker. Everything else hangs off it.*
