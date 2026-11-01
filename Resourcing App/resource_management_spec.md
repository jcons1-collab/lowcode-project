# Deliver Resource Management – PoC Specification

| | |
|---|---|
| **Document purpose** | Build brief for Claude Code to generate a working Proof of Concept |
| **Owner** | Deliver Operations |
| **Version** | 1.0 – 1 November 2026 |
| **Target** | Runs locally on a personal laptop: Python + Streamlit + SQLite |

---

## 1. Summary

Deliver Ops needs one place to plan and track how delivery people are allocated across client and internal work, and to compare **demand** (what we have sold or committed) with **supply** (who is actually available).

The app has six jobs:

1. **Import supply.** It loads people, their roles, cost rates, leave and public holidays from an HR Excel file.
2. **Import sold work.** It loads SOWs (Statements of Work) from a Salesforce-format Excel file. Each SOW automatically creates an Implementation project with phases, role demand lines and named resource assignments.
3. **Run the request workflow.** PMs raise resource requests for Confirm Plans, Ad Hoc Support, Client Investment and Internal Investment. Deliver Ops approves, changes or rejects them, and every change is audited.
4. **Expand allocations daily.** Every allocation, held as a % over any date range, is broken down into a **per-person, per-day** value that respects FTE, leave and public holidays. This makes demand, supply and utilisation answerable for any day, role, project, client or person.
5. **Show dashboards.** Demand vs supply, utilisation heatmaps, unfilled demand, over-allocation flags and KPIs, filterable by any dimension, viewed by day, week, month or quarter, in FTE.
6. **Report margins.** A margin module compares sold day rates with resource cost to give planned and final margin per SOW.

### 1.1 Success criteria for the PoC

The PoC succeeds if a stakeholder can watch the **whole end-to-end process, as automated as possible**:

1. Ops imports the People & Leave file and the SOW file. Projects, phases, demand lines and assignments are created automatically. Confirm Plans are auto-linked and won, and prospects flip to clients.
2. The dashboard immediately shows accurate daily-derived demand vs supply by role, client, project and person for the next 12 weeks, with unfilled demand and over-allocations flagged.
3. A PM raises a request, Ops approves it with changes, the change history is visible, and the dashboard updates. Tentative demand appears while the request is pending.
4. Ops imports new sick leave. The affected allocations are redistributed automatically and Ops sees a flag.
5. Leadership sees utilisation, billable utilisation against the 75% target, and the shortfall/surplus by role that drives hiring and redeployment decisions.
6. Ops and Leadership see planned margin per SOW.

The worked examples in §7.6 must pass as automated tests.

---

## 2. Scope

### 2.1 In scope (PoC)
- Mock login: a persona switcher with four app roles. There is no real authentication.
- Excel imports with a preview step: People & Leave, and SOWs in Salesforce format.
- A reference data seed: the role catalogue, standard phases, workstreams, countries, FX rates and settings.
- Implementation projects (from SOWs) and Confirm Plans (from PMs).
- Three standing workstreams: Ad Hoc Support, Client Investment and Internal Investment.
- The request → approval workflow with an audit trail, and change requests on existing allocations.
- The daily allocation engine, with leave and holiday redistribution, locked past and allocation splitting.
- Dashboards, filters, flags and Excel export.
- The margin module (planned, forecast-at-completion and final margin).
- A seed loader for the provided sample dataset.

### 2.2 Out of scope (future phases)

| Future item | Seam to leave in the PoC |
|---|---|
| Salesforce integration (SOWs, Opportunities, Accounts) | The import service takes a list of dicts. Excel is just one adapter. |
| HR system integration (people, leave) | Same as above. |
| Real SSO (e.g. Microsoft Entra ID) | `current_user()` is a single function behind the persona switcher. |
| Email, Slack or Teams notifications | Flags and the request inbox are stored as records that can be dispatched later. |
| **Timesheets / actuals for billing** (a separate module) | "Delivered" is currently the locked past plan. Actuals will replace it. |
| Pipeline forecasting from open opportunities | `project.kind` and `confirm_plan.status` allow later weighting. |
| Role matching enforcement | Not enforced. Any person can fill any role line. |
| Live FX rates | A static FX table, editable in Settings. |

---

## 3. Personas and permissions

| Capability | Resource | PM | Ops | Leadership |
|---|:-:|:-:|:-:|:-:|
| View own allocations (all clients and projects) | ✅ | ✅ | ✅ | ✅ |
| View all projects and allocations (read) | – | ✅ | ✅ | ✅ |
| View people's availability (supply) | – | ✅ | ✅ | ✅ |
| Create a Confirm Plan (header and phases) | – | ✅ | ✅ | – |
| Raise requests (new or change) | – | ✅ | ✅ | – |
| Approve, approve with changes, reject requests | – | – | ✅ | – |
| Create, edit, split or end allocations directly | – | – | ✅ | – |
| Run imports | – | – | ✅ | – |
| Dashboards | – | ✅ | ✅ | ✅ |
| Margin module and cost rates | – | – | ✅ | ✅ |
| Settings (thresholds, FX, roles, holidays) | – | – | ✅ | – |
| View change history | – | ✅ | ✅ | ✅ |

- **Persona switcher:** a sidebar selectbox lists all active people grouped by `app_role`. Choosing one sets `st.session_state.current_user`. Every page checks permissions through `core/auth.py::can(user, action)`.
- **Cost rates and margin figures** are never shown to Resource or PM personas. This applies to tables, exports and tooltips.

---

## 4. Domain model

### 4.1 Concepts

```
Client (Account) ──┬── Project: Implementation (from SOW) ── Phase ── DemandLine (role, %, dates, sold rate)
                   │                                                      └── Allocation (person, %, dates)
                   ├── Project: Confirm Plan (from PM) ── Phase ── Allocation (via approved requests)
                   └── Allocation in Workstream "Ad Hoc Support" / "Client Investment" (via requests)
Workstream "Internal Investment" ── Allocation (usually no client)
Person ── PersonRole (many; one primary; cost rate) ── Leave ── Country ── PublicHoliday
Request ──(approved)──► Allocation ──► AllocationDay (materialised daily days)
```

**Categories.** Every allocation has exactly one category. Its default billable flag can be overridden per allocation.

| Category | Container | Client | Phases | Default billable | Created by |
|---|---|---|---|---|---|
| SOW (Implementation) | Project (kind = Implementation) | Required | Pre-Mobilisation, Mobilisation, Solution Validation, Build, Deployment & Go Live, Hypercare | Yes | SOW import |
| Confirm Plan | Project (kind = Confirm Plan) | Required (Prospect or Client) | Discovery, Design, Plan | No (always non-billable) | PM request |
| Ad Hoc Support | Workstream | Required | None | Yes (overridable) | PM request |
| Client Investment | Workstream | Required | None | No | PM request |
| Internal Investment | Workstream | Optional (normally blank) | None | No | PM request |

- **Workstreams** are three fixed, seeded rows. They let ad hoc and investment allocations sit together without creating projects.
- **Reporting by client** works across all categories that carry a client.

### 4.2 Tables

Use SQLAlchemy 2.x ORM models in `core/models.py`. Dates are `date` and percentages are stored as fractions (0.2 = 20%). All IDs from external systems are kept as text.

**Reference**
- `country(code PK, name, currency)` – seeded with IE/Ireland/EUR, GB/United Kingdom/GBP, US/United States/USD and AU/Australia/AUD.
- `public_holiday(id, country_code FK, date, name)` – unique on (country_code, date).
- `role(id, name UNIQUE, role_group, active)` – `role_group` is `Implementation / Onboarding` or `Customer Support / Success` (catalogue in §4.3).
- `standard_phase(id, project_kind, name, sequence)`
- `workstream(id, name, category, default_billable, client_required)`
- `fx_rate(currency PK, rate_to_eur, as_of)`
- `setting(key PK, value)` – defaults in §9.

**People (supply)**
- `person(id PK text, full_name, email UNIQUE, resource_type [Employee|Contractor], country_code FK, fte, start_date, end_date NULL, app_role [Resource|PM|Ops|Leadership], active bool)`
- `person_role(person_id FK, role_id FK, is_primary bool, daily_cost_rate, cost_currency)` – PK is (person_id, role_id). Each person has exactly one primary role.
- `leave(id PK text, person_id FK, leave_type [Annual Leave|Sick Leave|Other Leave], start_date, end_date, day_fraction [1.0|0.5], notes)`
- `capacity_day(person_id, date, available_weight, capacity_days)` – materialised (§7.2). PK is (person_id, date).

**Clients and projects**
- `client(account_id PK text, name, status [Client|Prospect], region [EMEA|AMER|APAC], country_code NULL, source [import|app])`
- `project(id PK, kind [Implementation|Confirm Plan], name, client_id FK, start_date, end_date, status, pm_person_id NULL, currency NULL, sow_sf_id UNIQUE NULL, sow_number NULL, opportunity_id NULL, cp_status [Open|Won|Lost] NULL, linked_sow_project_id NULL)`
  - Implementation `status` is Active, On Hold, Completed or Cancelled.
- `phase(id PK, project_id FK, name, sequence, start_date, end_date)`
- `demand_line(id PK, external_id UNIQUE NULL, project_id FK, phase_id FK, role_id FK, start_date, end_date, pct, sold_day_rate NULL, currency NULL)` – a role demand line from a SOW.

**Allocations (approved demand)**
- `allocation(id PK, external_id UNIQUE NULL, person_id FK, role_id FK, category, project_id NULL, phase_id NULL, demand_line_id NULL, workstream_id NULL, client_id NULL, start_date, end_date, pct, billable bool, reason NULL, status [Active|Cancelled], parent_allocation_id NULL, source [sow_import|request|ops_manual], request_id NULL, unplaced_days float default 0, created_by, created_at, updated_by, updated_at)`
- `allocation_day(allocation_id FK, date, days, locked bool)` – materialised (§7.3). PK is (allocation_id, date).

**Workflow and audit**
- `request(id PK, request_type [New|Change], target_allocation_id NULL, category, project_id NULL, phase_id NULL, workstream_id NULL, client_id NULL, role_id, person_id, start_date, end_date, pct, billable, reason, status, requested_by, requested_at, decided_by NULL, decided_at NULL, decision_comment NULL, original_json NULL, resulting_allocation_ids_json NULL)`
  - `status` is Draft, Submitted, Approved, Approved with changes, Rejected or Cancelled.
  - `original_json` snapshots the PM's submitted values when Ops changes them.
- `audit_log(id, entity_type, entity_id, action, field NULL, old_value NULL, new_value NULL, actor_person_id, at, note NULL)` – append-only.
- `flag(id, flag_type, severity [info|warning|critical], person_id NULL, project_id NULL, allocation_id NULL, request_id NULL, week_start NULL, message, created_at, resolved_at NULL, resolved_by NULL)`

**Imports**
- `import_batch(id, kind [people_leave|sow], filename, uploaded_by, uploaded_at, status [previewed|committed|discarded], summary_json)`
- `import_snapshot(entity_type, external_id, values_json, values_hash, imported_at)` – the last imported values per record, used for re-import conflict detection (§6.4).

### 4.3 Seeded role catalogue

**Implementation / Onboarding:** Implementation Manager, Implementation Consultant, Project Manager, Solutions Architect, Technical Consultant, Integration Engineer, Data Migration Specialist, Business Analyst, Onboarding Specialist, QA / Test Analyst, Trainer / Customer Education Specialist, Change Management Consultant.

**Customer Support / Success:** Customer Support Representative, Technical Support Engineer, Support Manager, Customer Success Manager, Technical Account Manager, Escalation Manager, Knowledge Base / Technical Writer, Support Operations Analyst.

Ops can add, rename or deactivate roles in Settings.

---

## 5. Workflows

### 5.1 Request lifecycle

```
Draft ──submit──► Submitted ──approve──────────────► Approved
  │                  ├──approve with edits─────────► Approved with changes
  │                  ├──reject (comment required)──► Rejected
  └──cancel──►  Cancelled ◄──cancel (PM or Ops)──────┘ (while Submitted)
```

- **Draft:** PMs create and edit drafts. Drafts are not visible to Ops.
- **Submitted:** visible in the Ops **Request Inbox**. It counts as **tentative demand** on dashboards when the "Include tentative" toggle is on (the default).
- **Approve:** creates or updates allocation(s) with `source = request` and recomputes daily rows.
- **Approve with changes:** Ops edits the person, %, dates, role, billable or client inline before approving. Original values are stored in `original_json`. The inbox and history show a field-by-field diff, e.g. "40% → 30%, end 18 Dec → 4 Dec".
- **Reject:** a comment is mandatory.
- **Inbox ordering and checks:** the inbox sorts by start date and highlights requests submitted more than 2 working days ago. Before deciding, Ops sees the **capacity impact preview**: the person's weekly utilisation for the request window, with and without the request, coloured by band.
- **Over-allocation:** if approval would push the person above 100% on any day, a warning is shown, e.g. "Over 100% on 6 days; peak 140% on 12 Nov". Ops can still approve. This creates an `OVER_ALLOCATED` flag.

### 5.2 Request types and form fields

| Request | Required fields | Notes |
|---|---|---|
| New – Confirm Plan | Confirm Plan, phase, role, person, start, end, % | Billable is forced to No. Dates must sit within the phase. |
| New – Ad Hoc Support | Client, role, person, start, end, %, billable (default Yes) | Reason is optional. |
| New – Client Investment | Client, role, person, start, end, % | Billable defaults to No. Reason is optional. |
| New – Internal Investment | Role, person, start, end, % | Client is optional. Reason is optional. |
| Change | Target allocation and the new values (any of person, %, dates, end early, cancel) | Can target any active allocation, including SOW ones. On approval, the split rules (§7.4) apply. |

- **Person optional:** PMs normally name a person. If they leave it blank, Ops must pick one before approving.
- **Suggested people:** the request form and the Ops unfilled-demand view show a **"Suggested people"** list for the chosen role and window. People who hold the role (primary first) are ranked by lowest average utilisation in the window. The list shows each person's free FTE and country, and prefers the client's region.

### 5.3 Confirm Plan lifecycle

1. **Creation:** a PM creates the Confirm Plan header with a client (an existing Prospect or Client, or a new Prospect), an optional Salesforce Opportunity ID, and dates for the three phases (Discovery, Design, Plan). `cp_status = Open`. The header has no capacity impact, so it doesn't need approval.
2. **Staffing:** the PM raises Confirm Plan requests per phase, which Ops approves.
3. **Auto-win:** when a SOW import contains an `Opportunity ID` equal to an Open Confirm Plan's `opportunity_id`, the app:
   - sets `cp_status = Won`;
   - sets `linked_sow_project_id`;
   - flips the client to `Client`;
   - writes audit entries.
4. **Manual status:** Ops can set **Won** (choosing the SOW manually) or **Lost**. Lost cancels the plan's future allocations after confirmation.
5. **Locally created prospects:** a prospect created in the app gets `account_id = LOCAL-<n>` and `source = app`. When a SOW import brings a real Account ID, Ops can use **Merge prospect into client**, which re-points the prospect's projects and allocations.
6. **Reporting:** pre-sales effort (Confirm Plan FTE-days and cost) per Won and Lost plan, and Confirm Plan effort vs the linked SOW's sold days and value.

### 5.4 Direct Ops actions

Ops can create, edit, split, end early or cancel any allocation directly on the project or workstream screens, without a request. Each change is written to `audit_log`.

---

## 6. Imports

The templates are provided as `template_people_leave_import.xlsx` and `template_sow_import.xlsx`. Their **Instructions** sheets document every column. Sample filled versions are provided too (§12).

### 6.1 Common behaviour
1. **Upload:** Ops uploads the file on the **Imports** page.
2. **Parse and validate:** the app parses every sheet with pandas and validates it into a **preview**, shown as tabs:
   - **Add:** new records.
   - **Update:** field-level old → new values.
   - **Unchanged.**
   - **Conflicts:** SOW only (§6.4).
   - **Errors:** sheet, row and column, with a message.
3. **Commit:** blocked while errors exist, unless Ops ticks "Skip rows with errors". Commit runs in one DB transaction, writes `import_batch` and `import_snapshot`, recomputes the affected daily tables (§7) and raises flags.
4. **Upsert:** records are matched on their ID column. **Records missing from the file are left untouched.**
5. **Ignored columns:** columns marked "(calc)" are informational and ignored.
6. **Example rows:** the yellow example row must be deleted before import. The validator rejects rows whose IDs match the template examples (`EMP-1001` with name "Aoife Byrne"; `a0SQ00000XyZ123`).

### 6.2 People & Leave file

| Sheet | Key | Columns |
|---|---|---|
| People | Person ID | Full Name, Email, Resource Type, Country, FTE, Start Date, End Date, App Role, Active |
| PersonRoles | Person ID + Role | Is Primary, Daily Cost Rate, Cost Currency |
| Leave | Leave ID | Person ID, Leave Type, Start Date, End Date, Day Fraction (1 or 0.5), Notes |
| PublicHolidays | Country + Date | Holiday Name |

**Validation:**
- **Emails:** unique.
- **FTE:** between 0.1 and 1.0.
- **Country:** must exist.
- **Primary role:** exactly one per person in the file. When a person has no PersonRoles rows in the file, their existing roles are kept.
- **Roles:** must be in the catalogue.
- **Dates:** start ≤ end.
- **Leave overlaps:** overlaps for the same person are allowed. The day fraction is capped at 1.0 per day.

**After commit:**
1. Recompute `capacity_day` for affected people.
2. Recompute every allocation that overlaps changed leave, holidays, FTE or employment dates (§7.3).
3. Raise `LEAVE_REDISTRIBUTED` per affected allocation, e.g. "0.4 days moved to 9–13 Nov for Sinead Lynch on SOW-2026-008".

### 6.3 SOW file (Salesforce format)

| Sheet | Key | Columns |
|---|---|---|
| Clients | Account ID | Client Name, Status, Region, Country |
| SOWs | SOW ID | SOW Number, Opportunity ID, Account ID, SOW Name, Start Date, End Date, Currency, Status, Delivery PM (Person ID) |
| Phases | SOW ID + Phase | Start Date, End Date |
| RoleLines | Role Line ID | SOW ID, Phase, Role, Start Date, End Date, Allocation %, Sold Day Rate, Sold Days (calc) |
| Assignments | Assignment ID | Role Line ID, Person ID, Start Date, End Date, Allocation %, Assigned Days (calc) |

**On commit:**
1. Upsert clients.
2. Upsert the project (`kind = Implementation`).
3. Upsert phases, demand lines and allocations. Allocations get `category = SOW`, `billable = true`, `source = sow_import`, they are **Approved directly**, and they are expanded daily.
4. Run the Confirm Plan auto-win (§5.3).
5. Flip Prospect → Client for any client with a SOW.

**Validation:**
- **Phase dates:** within the SOW dates.
- **Line dates:** within the phase.
- **Assignment dates:** within the line.
- **Phase name:** one of the six standard phases.
- **People and roles:** Person ID and role must exist.
- **Values:** Allocation % between 0.01 and 2.0. A line over 100% means more than one person, e.g. 150%.
- **Warnings (not errors):**
  - Assignments for a line sum to more than the line %.
  - The person is outside their employment dates.

### 6.4 Re-import rule for SOW records

Each SOW record (SOW, phase, role line or assignment) is compared three ways:

| File vs last import snapshot | App edited since last import? | Result |
|---|---|---|
| Unchanged | No | Unchanged |
| Unchanged | **Yes** | **App edits are kept** (shown in preview as "kept app edit") |
| Changed | No | File value applied |
| Changed | Yes | **Conflict.** The preview shows file, app and last-import values. Ops picks *Use file* or *Keep app* per record (default *Keep app*). |

"App edited" means an `audit_log` entry exists for that entity after the snapshot's `imported_at`.

### 6.5 Seed loader
`python scripts/seed.py --reset` creates the DB and loads, in this order:
1. Reference data.
2. `sample_people_leave_import.xlsx`.
3. `sample_sow_import.xlsx`.
4. `sample_confirmplans_requests_seed.xlsx` (Confirm Plans, phases, requests including approved-with-changes originals, and FX rates).

The loader uses the same import services as the UI, without the preview step. Approved requests become allocations.

---

## 7. Calculation engine (core logic)

All functions live in `core/engine.py` as **pure functions** (no DB access) with unit tests, plus a thin persistence layer that materialises the results. A configurable `today()` (settings key `as_of_date`, default the real date) is used everywhere, so tests and demos are deterministic.

### 7.1 Definitions
- **Weekday:** Monday–Friday, for every country.
- **Standard day:** 1.0 day. Percentages are **% of a standard full day per weekday**, independent of FTE. For example, 20% over one week is 1.0 day, and 20% from Thursday to the following Friday (7 weekdays) is 1.4 days.
- **Available weight `w(p,d)`:**
  - `0` if d is a weekend, a public holiday in the person's country, before their start date or after their end date.
  - Otherwise `1 − leave_fraction(p,d)`, where leave_fraction is 0, 0.5 or 1.
- **Capacity `cap(p,d) = FTE(p) × w(p,d)`.** FTE is spread evenly over weekdays (0.8 FTE gives 0.8 days of capacity per working day).

### 7.2 Capacity materialisation
`capacity_day` stores `w` and `cap` for every person and every weekday from the global horizon start to the horizon end. The defaults are 1 Jan of last year to 31 Dec of next year. It is recomputed per person on any People, Leave or Holiday change.

### 7.3 Expanding an allocation into days

Inputs: person p, `start`, `end`, `pct`, the existing locked rows, and `today`.

```
W        = weekdays in [start, end]                     # holidays and leave NOT removed here
T        = pct × |W|                                    # total days committed; preserved on recalculation
locked   = existing allocation_day rows with date < today (only on recompute, never on first expansion)
           → for each locked row whose day now has w(p,d) = 0 (e.g. sick leave entered late),
             set days = 0 and log it (system adjustment, audited)
L        = Σ locked.days
F        = { d ∈ W : d ≥ today (or all of W on first expansion), w(p,d) > 0 }
R        = T − L
if Σ_{d∈F} w(p,d) > 0:   days(d) = R × w(p,d) / Σ_{d∈F} w(p,d)   for d ∈ F
else:                    unplaced_days = R ; raise flag UNPLACED_DAYS
```

- **Effect:** leave and public holidays don't reduce what was committed. The lost time is **redistributed** across the person's remaining available days in the window, weighted 0.5 for half days.
- **Over capacity:** if redistribution pushes a day above the person's capacity, the over-allocation rules (§8.4) flag it.
- **Locking:** manual edits never change past rows. Only the system adjustment above (late leave) touches them, and it always moves the time *forward*.
- **Re-triggers:** expansion re-runs for an allocation when its fields change, or when its person's capacity changes on any date in its window.
- **Tentative demand:** a Submitted request is expanded with the same function, held in memory (or cached), and never written to `allocation_day`.
- **Unfilled role demand** (per demand line, holiday-independent, because a line has no person):

```
for each weekday d in line window:
    covered(d)  = Σ pct of active allocations on that line whose window contains d
    unfilled(d) = max(0, line.pct − covered(d))      # in days
```

### 7.4 Editing and splitting allocations

When Ops edits an allocation (directly or through an approved Change request) with an **effective date** `e`:
- **Default `e`:** today, or the allocation start if it starts in the future.
- **Before `e` must be ≥ today:** past rows can't change.
- **If `e` > start:** the existing allocation is **split**.
  - Segment A keeps the original values with `end = e − 1 day`. Its days before today stay locked.
  - Segment B is created with the new values from `e` to the new end, and `parent_allocation_id` = A.
- **If `e` = start:** the allocation is updated in place.
- **End early:** set end = e − 1. Any remaining future rows are deleted.
- **Cancel:** removes all future rows. Past rows remain.
- **Display:** the **current view** shows the latest segments as one row per logical allocation, with the % shown per period, e.g. "40% to 14 Nov → 20%". The **History** tab shows all segments and audit entries.

Example: an allocation runs at 40% from 2 Nov to 18 Dec 2026, and it is changed to 20% from 16 Nov.
- Segment A: 40% from 2 Nov to 15 Nov.
- Segment B: 20% from 16 Nov to 18 Dec.

### 7.5 Aggregation for reporting

All dashboards read from `allocation_day`, `capacity_day`, tentative rows and unfilled rows, using pandas group-bys.

| Quantity | Formula |
|---|---|
| Supply (capacity) | Σ cap(p,d) |
| Approved demand | Σ allocation_day.days |
| Tentative demand | Σ expanded Submitted requests |
| Unfilled demand | Σ unfilled(d) of demand lines |
| Total demand | Approved + Unfilled + (Tentative if toggle on) |
| Utilisation % | (Approved [+ Tentative]) ÷ Supply |
| Billable utilisation % | Billable approved ÷ Supply. Target 75%. |
| Free capacity | Supply − Approved [− Tentative] (can be negative) |

- **FTE conversion per bucket:** `FTE = days ÷ number of weekdays in the bucket` (Mon–Fri, holiday-agnostic). For example, 3.0 days in a 5-weekday week is 0.6 FTE. A full-time person's supply therefore drops to 0.8 FTE in a week with a public holiday.
- **Buckets:** day, week (starting Monday), month and quarter (calendar).
- **Filter semantics:**
  - Supply filters only apply to **person attributes**: person, primary role, country, region, resource type, app role.
  - Demand filters apply to **allocation attributes** as well: project/SOW, client, category, billable, phase, allocation role, status.
  - When a demand-only filter is active (e.g. one client), the demand vs supply chart hides the supply line and shows a note ("Supply is not client-specific").
- **Role views:** supply by role always uses the **primary role**. Demand by role uses the **role on the allocation or demand line**.

### 7.6 Worked examples (must be implemented as pytest tests)

| # | Scenario | Expected |
|---|---|---|
| 1 | IE person, FTE 1.0, 20% from Thu 5 Nov to Fri 13 Nov 2026, no leave | 7 weekdays; total 1.4 days; 0.2 days on each weekday |
| 2 | GB person, 40% from Mon 2 Nov to Fri 13 Nov 2026, annual leave on Fri 6 Nov | Total 4.0; 0 on 6 Nov; 4.0 ÷ 9 = 0.4444 on each of the other 9 days |
| 3 | GB person, 50% from Mon 22 Mar to Fri 2 Apr 2027 (Good Friday 26 Mar, Easter Monday 29 Mar) | Total 5.0; 0 on the holidays; 0.625 on each of 8 days |
| 4 | IE person, 20% from Mon 7 Dec to Fri 11 Dec 2026, half-day leave on Wed 9 Dec | Total 1.0; weights 1,1,0.5,1,1; 0.2222 on full days and 0.1111 on Wed |
| 5 | Person at FTE 0.8 allocated 100% for one week | Capacity 0.8/day, allocated 1.0/day → 125% → over-allocated flag |
| 6 | GB person, 50% from Mon 26 Oct to Fri 6 Nov 2026, `today` = Mon 2 Nov; sick leave on Thu 29 Oct imported on 2 Nov | Past rows: 26, 27, 28 and 30 Oct = 0.5 each (2.0); 29 Oct set to 0. Remaining 3.0 over 2–6 Nov = 0.6 per day. `LEAVE_REDISTRIBUTED` flag raised |
| 7 | 20% for a single day that is a public holiday | No available day → `unplaced_days` = 0.2 and `UNPLACED_DAYS` flag |
| 8 | Demand line 80% from Mon 1 Mar to Fri 30 Apr 2027 (45 weekdays) with assignments of 50% and 30% over the same window | Line demand 36.0 days; unfilled 0. If only the 50% exists: unfilled 0.3/day = 13.5 days |
| 9 | Week bucket with 3.0 allocated days | 0.6 FTE |
| 10 | Split: 40% from 2 Nov to 18 Dec 2026, changed to 20% effective 16 Nov | Segment A: 40% from 2 to 13 Nov (ends 15 Nov, a Sunday); segment B: 20% from 16 Nov to 18 Dec; totals 4.0 + 5.0 days |

---

## 8. Dashboards and views

### 8.1 Global filter bar (sidebar, shared by dashboard pages)
- **Date range:** default today → +12 weeks.
- **Granularity:** Day, Week, Month or Quarter. Default Week.
- **Supply filters:** people (multi), primary role (multi), country (multi), region, resource type.
- **Demand filters:** client (multi), project/SOW (multi), category (multi), billable (All/Yes/No), phase, allocation role (multi).
- **Toggles:** Include tentative (default on), Include unfilled (default on).
- **Units:** FTE. Tooltips also show days.

Filter state persists in `st.session_state` across pages.

### 8.2 Main Dashboard (PM, Ops, Leadership)
1. **KPI tiles:**
   - Utilisation %
   - Billable utilisation % vs 75% target (green when at or above target)
   - Supply FTE
   - Approved demand FTE
   - Unfilled demand FTE
   - Tentative demand FTE
   - Over-allocated people count
   - At-risk (above 85%) people count
   - Bench (below 70%) people count
2. **Demand vs supply chart** (Plotly). Stacked bars per bucket show Approved billable, Approved non-billable, Tentative (hatched or lighter) and Unfilled (red outline). A line shows Supply.
3. **Role heatmap:** roles × buckets. The cell value is Supply − Demand in FTE, on a diverging colour scale (red shortfall, blue surplus). Hovering shows supply, approved, tentative and unfilled.
4. **Resource heatmap:** people × buckets. The cell value is utilisation %, coloured by band:
   - below 70% grey-blue (under)
   - 70–85% green (healthy)
   - above 85% and up to 100% amber (at risk)
   - above 100% red (over)
   Clicking a person opens their allocation detail.
5. **Flags list:** open flags sorted by severity. Over-allocations are shown by person-week. Unfilled demand starting within 4 weeks is included. Ops can resolve a flag.
6. **Demand by client / category:** a stacked bar of demand FTE by client (top 15 + Other) and by category.
7. **Detail table and Excel export:** the underlying aggregated rows (bucket, person, primary role, allocation role, client, project, category, billable, status, FTE, days), exported with `st.download_button` as `.xlsx`. Cost columns are only included for Ops and Leadership.

### 8.3 Other pages

| Page | Persona | Content |
|---|---|---|
| **My Allocations** | All | A Gantt timeline (Plotly `timeline`) of the user's allocations by client and project; a weekly FTE table; a daily breakdown expander; their leave and holidays. Read-only. |
| **Availability** | PM, Ops, Leadership | People × weeks free-capacity grid (FTE), filterable by any role held, country and type, with "Suggested people" for a role and window. |
| **Requests** | PM (own), Ops (all) | New request form (by type), my requests and their statuses, cancel. |
| **Request Inbox** | Ops | Submitted requests with capacity-impact preview, inline edit, and approve / approve with changes / reject. |
| **Projects** | All but Resource | List of Implementation and Confirm Plan projects. Detail view: phases, demand lines with assigned vs unfilled, allocations (Ops edit/split/assign), sold vs planned days per line (an overrun flag where planned > sold), history tab. Confirm Plan detail adds status and SOW linking. |
| **Workstreams** | All but Resource | Allocations in Ad Hoc Support, Client Investment and Internal Investment, filterable by client. Ops edits them. |
| **Imports** | Ops | Two upload panels with preview, conflict resolution and commit; import history. |
| **Margins** | Ops, Leadership | See §10. |
| **History** | PM, Ops, Leadership | Searchable audit log (entity, person, date range). |
| **Settings** | Ops | Thresholds, billable target, horizon, `as_of_date`, FX rates, role catalogue, public holidays, workstream billable defaults. |

### 8.4 Flags (automatically generated)

| Flag | Rule | Severity |
|---|---|---|
| `OVER_ALLOCATED` | A person-week's utilisation is above 100% (any day above 100% raises a warning on assignment) | critical |
| `AT_RISK` | A person-week's utilisation is above 85% and at most 100%. It leaves little room for BAU work. | warning |
| `LEAVE_REDISTRIBUTED` | Recalculation moved days because of new or changed leave or holidays | info |
| `UNPLACED_DAYS` | An allocation has committed days with no available day to place them | critical |
| `UNFILLED_DEMAND` | A demand line has unfilled days starting within the next 4 weeks | warning |
| `SOLD_DAYS_OVERRUN` | Planned days on a line are above its sold days | warning |
| `OUTSIDE_EMPLOYMENT` | An allocation falls outside the person's start or end dates | warning |
| `REQUEST_AGEING` | A request has been Submitted for more than 2 working days | info |
| `IMPORT_CONFLICT` | Unresolved re-import conflicts | warning |

Flags are recomputed after each import, approval or edit (idempotently: open flags with the same key are updated, not duplicated).

---

## 9. Settings (defaults)

| Key | Default |
|---|---|
| `band_under_max` | 0.70 |
| `band_healthy_max` | 0.85 |
| `band_at_risk_max` | 1.00 |
| `billable_target` | 0.75 |
| `default_horizon_weeks` | 12 |
| `reporting_currency` | EUR |
| `request_ageing_days` | 2 |
| `unfilled_lookahead_weeks` | 4 |
| `as_of_date` | blank (uses the real date); set it for demos and tests |
| Workstream defaults | Ad Hoc Support billable = Yes; Client Investment = No; Internal Investment = No; Confirm Plan = No (locked); SOW = Yes |

---

## 10. Margin module

All values are converted to EUR (`reporting_currency`) with `fx_rate`. Each person's cost comes from `person_role.daily_cost_rate` **for the role on the allocation**. If the person has no cost for that role, their primary role's rate is used.

| Measure (per SOW, also per phase, role line and person) | Formula |
|---|---|
| Sold days | Σ line.pct × weekdays(line) |
| Sold value (revenue) | Σ sold days × sold_day_rate (FX → EUR) |
| Planned days | Σ allocation_day.days on the SOW's allocations |
| Planned cost | Σ allocation_day.days × person-role cost (FX → EUR) |
| Unfilled cost estimate | Unfilled days × average cost of active people whose primary role is that role (toggle) |
| Overrun | Planned days above sold days on a line are costed but earn no revenue (non-billable over-servicing) |
| **Planned margin** | Sold value − (Planned cost [+ Unfilled cost]); margin % = margin ÷ sold value |
| Delivered to date | Days and cost where date < today (the locked plan; replaced by timesheet actuals in a future phase) |
| **Forecast at completion** | Delivered to date + remaining planned |
| **Final margin** | Shown once the SOW status is Completed: sold value earned (min(planned, sold) days per line × rate) − delivered cost |

The page shows:
- a SOW table with sold value, planned cost, margin and margin %, with a conditional colour against a configurable target margin (default 40%);
- a drill-down by role line showing sold vs planned days and overruns;
- Confirm Plan pre-sales cost per Won SOW and per Lost plan;
- an export to Excel.

---

## 11. Resourcing operating approach (how the app is used)

The app supports a simple, repeatable cadence:

| When | Who | Activity in the app |
|---|---|---|
| Weekly – Monday | Ops | Import the HR People & Leave file. Review `LEAVE_REDISTRIBUTED` and `OVER_ALLOCATED` flags. |
| On SOW signature (weekly batch for the PoC) | Ops | Import SOWs. Confirm Plans auto-win. Work the unfilled demand list using "Suggested people". |
| Continuous | PMs | Raise requests. They appear as tentative demand straight away. |
| Within 2 working days | Ops | Clear the Request Inbox using the capacity-impact preview. |
| Weekly resourcing review | Ops + PM leads | Role heatmap (next 12 weeks), flags list, bench list (below 70%), at-risk list (above 85%). |
| Monthly | Leadership | Utilisation and billable utilisation trend vs 75%, margin by SOW, and hiring/redeployment signals. |

**Decision signals**, shown as a "Signals" panel on the dashboard:
- **Hire / engage contractor:** a role shows a shortfall of more than 0.5 FTE for 4 or more consecutive weeks in the horizon (approved + unfilled + tentative).
- **Redeploy / invest:** a role shows a surplus of more than 1.0 FTE for 6 or more consecutive weeks. Suggest Internal or Client Investment allocations for its bench people.
- **Delivery risk:** a SOW has unfilled demand starting within 4 weeks, or a sold-days overrun.

---

## 12. Provided files

| File | Purpose |
|---|---|
| `template_people_leave_import.xlsx` | Blank HR import template: Instructions, People, PersonRoles, Leave, PublicHolidays. Dropdowns and header comments enforce the rules. Yellow example rows show the format. PublicHolidays is pre-filled for 2026–2027 (sample calendars; verify against official sources). |
| `template_sow_import.xlsx` | Blank Salesforce-format SOW template: Instructions, Clients, SOWs, Phases, RoleLines, Assignments. Includes calculated "Sold Days" and "Assigned Days" helper columns. |
| `sample_people_leave_import.xlsx` | 56 people (IE 17, GB 16, US 13, AU 10; 4 contractors; varied FTE; 2 future joiners); 96 person-role rows with cost rates in local currency; about 650 leave records (annual, sick, other, half days) for 2026–2027; public holidays. |
| `sample_sow_import.xlsx` | 50 clients and 10 prospects (EMEA, AMER and APAC); 15 SOWs (1 completed, 10 in flight, 4 starting in 2027), 90 phases, 435 role lines with sold rates, and 400 assignments. Gaps are left deliberately, so unfilled demand and over-allocations appear. |
| `sample_confirmplans_requests_seed.xlsx` | 7 Confirm Plans (3 Won and linked by Opportunity ID to SOWs, 2 Open, 2 Lost) with phases; about 116 requests across all statuses and categories (including an approved-with-changes example with original values); FX rates. |

**Seeded personas for the demo:** 2 Ops users, 6 PMs, 2 Leadership users and 46 Resources, as set in the `App Role` column.

The sample data gives roughly 68% average utilisation over the next 12 weeks, with a realistic spread: some people on the bench, some healthy, some at risk and some over-allocated.

---

## 13. Technical design

### 13.1 Stack
- Python 3.11 or later
- `streamlit` (multipage via `st.navigation`)
- `sqlalchemy` 2.x
- `pandas`
- `openpyxl`
- `plotly`
- `pytest`

There is no external service. SQLite is the database file `data/resource_mgmt.db`. It is free and built into Python, so nothing needs installing. Keep all SQL in the ORM, so moving to Postgres later is only a connection-string change.

### 13.2 Project structure
```
resource_app/
├── app.py                     # entry point: persona switcher, navigation filtered by permissions
├── pages/                     # dashboard.py, my_allocations.py, availability.py, requests.py,
│                              # inbox.py, projects.py, workstreams.py, imports.py, margins.py,
│                              # history.py, settings.py
├── core/
│   ├── db.py                  # engine, session factory, create_all
│   ├── models.py              # ORM models (§4.2)
│   ├── auth.py                # current_user(), can(user, action)
│   ├── calendar.py            # weekdays, availability weights, capacity materialisation
│   ├── engine.py              # pure allocation expansion, unfilled, split, aggregation helpers
│   ├── materialise.py         # writes capacity_day / allocation_day, recompute triggers
│   ├── workflow.py            # request state machine, approve/approve-with-changes/reject
│   ├── allocations.py         # create/edit/split/end/cancel + audit
│   ├── flags.py               # flag rules (§8.4), idempotent upsert
│   ├── metrics.py             # dashboards' data frames, FTE conversion, filters
│   ├── margin.py              # §10
│   ├── suggestions.py         # "Suggested people" ranking
│   ├── audit.py               # audit_log helpers
│   └── imports/
│       ├── common.py          # preview model, error collection, snapshot/conflict logic
│       ├── people_leave.py
│       └── sow.py
├── scripts/seed.py            # --reset; loads reference + sample files (§6.5)
├── data/                      # sqlite db + sample xlsx files
├── tests/                     # test_engine.py (§7.6), test_imports.py, test_workflow.py, test_metrics.py
├── requirements.txt
└── README.md                  # setup: python -m venv, pip install -r, seed, streamlit run app.py
```

### 13.3 Implementation notes
- **Performance:** at about 60 people over 3 years there are under 50k capacity rows and about 100k allocation rows. Bulk-insert with `session.execute(insert(...), rows)`. Cache dashboard frames with `st.cache_data`, keyed on a `data_version` setting that is incremented after every write.
- **Recompute scope:** only recompute affected people and allocations, never the whole database, except on seed.
- **Audit:** use one helper so every write path (UI, import, workflow) writes `audit_log` consistently.
- **Visual language:** use the same four band colours everywhere (§8.2). Show percentages as whole numbers ("20%") and FTE to 1 decimal place.
- **Validation messages:** must be human-readable and name the sheet, row and column, e.g. "RoleLines row 14: Phase 'Build' not defined for SOW a0S…".
- **Demo time:** setting `as_of_date` in Settings lets the demo freeze "today" at 2 Nov 2026 to match the sample data.

---

## 14. Build plan for Claude Code (milestones and acceptance)

| # | Milestone | Done when |
|---|---|---|
| 1 | Skeleton, models, reference seed, persona switcher, permissions | The app starts. Switching persona changes the visible pages. |
| 2 | Calendar and allocation engine | All §7.6 tests pass. |
| 3 | People & Leave import (preview → commit, recompute, flags) | The sample file imports with 0 errors. Re-importing the same file shows everything Unchanged. Editing a leave row and re-importing raises `LEAVE_REDISTRIBUTED`. |
| 4 | SOW import (projects, phases, lines, assignments, auto-win, conflict rules) | The sample imports. 3 Confirm Plans become Won once the seed file is loaded. The §6.4 table is covered by tests. |
| 5 | Allocation management (Ops edit/split/end/cancel, history) | Example 10 works through the UI. History shows the segments and audit entries. |
| 6 | Requests, inbox and Confirm Plans | The full flow works: PM submit → tentative on dashboard → Ops approve with changes → diff in history → allocation live. |
| 7 | Dashboards, filters, flags, signals, export | All views in §8.2 render from the seeded data. Filters work. The export opens in Excel. |
| 8 | Margin module | The SOW margin table reconciles with a hand calculation for one SOW (include a test). |
| 9 | Seed script, README, demo script | A clean clone runs in under 5 minutes using README steps. The demo script below works end to end. |

### 14.1 Demo script (end-to-end story)
1. **Ops:** run `seed.py --reset`, then open Imports and re-upload the sample SOW file to show the preview (all Unchanged).
2. **Leadership:** open the Dashboard (next 12 weeks). Point out the KPIs, the role heatmap shortfalls and the Signals panel.
3. **PM:** raise an Ad Hoc Support request for a client, choosing a person from "Suggested people". The dashboard shows the tentative demand.
4. **Ops:** in the Inbox, reduce the % and shorten the dates, then approve with changes. Show the diff in History.
5. **Ops:** upload the People & Leave file with a new sick-leave row for an allocated person. Show the redistribution flag and the updated daily breakdown.
6. **Ops:** split an allocation mid-way (40% → 20%) and show the history.
7. **Resource:** switch to a resource and show My Allocations across clients.
8. **Leadership:** open Margins and show planned margin by SOW and Confirm Plan pre-sales cost per won deal.

---

## 15. Assumptions and open points

These are assumptions to confirm with Deliver Ops. Each has a sensible default for the PoC.

1. **Working week:** every country works Monday–Friday. Local working-week differences are out of scope.
2. **Region-level holidays:** the sample uses one calendar per country (GB = England & Wales, US = federal, AU = New South Wales). Region-level calendars, such as Scotland or other Australian states, would need a `region` on person and holiday.
3. **Hours:** no hours are tracked. Everything is in days and FTE.
4. **Over 100% lines:** a role line above 100% means it needs more than one person. Assignments can exceed the line (with a warning) but never block.
5. **Locked past:** recalculation for late leave zeroes past days and moves the time forward. Manual edits can't change the past.
6. **Cost-rate visibility:** cost rates are confidential to Ops and Leadership.
7. **Prospects created in the app:** these are merged manually into imported Salesforce accounts.
8. **FX:** rates are static for the PoC.
