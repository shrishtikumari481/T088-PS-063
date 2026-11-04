# PS-063 – Blood Bank Inventory and Cross-Match Allocation Engine — Sample Data Pack

Prepared by 10 SECONDS for Team T088.

## Files

| File | What it holds | Row count |
|---|---|---|
| `donors.csv` | 80 donors with group, Rh, date of birth, prior donation and deferral | 80 data rows |
| `donations.csv` | 150 donation attempts (history from 2026-05-15 and the current period) with weight and haemoglobin | 150 data rows |
| `components.csv` | Component units (PRBC / FFP / PLATELET) separated from each accepted donation | 433 data rows |
| `screening_results.csv` | TTI screening results (5 markers per donation) | 725 data rows |
| `hospitals.csv` | 5 hospitals (government / private) | 5 data rows |
| `hospital_quotas.csv` | Daily issue caps per hospital per component | 15 data rows |
| `requests.csv` | Hospital requests across the request period | 90 data rows |
| `commands.txt` | Single timeline: donations, screening releases, requests, issues, returns, cross-match results, cancellations, daily runs and prints | 637 command lines (excluding comments) |

Row numbers quoted below are 1-based data-row numbers (the header is row 0). Line numbers for `commands.txt` are physical line numbers including comment lines.

## Column reference

Conventions: dates `YYYY-MM-DD`; timestamps `YYYY-MM-DD HH:MM:SS` (24h, IST, no timezone suffix); money in Rs as plain decimals with 2 places (no commas, no symbol); percentages as plain numbers (12.5 means 12.5%); booleans `true`/`false`; IDs uppercase with a fixed prefix. An empty cell means "not applicable / not supplied" and only occurs in columns whose notes say so.

### `donors.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| donor_id | string | DNR-nnn | — | numbered in first-donation order |
| donor_name | string | — | — | — |
| gender | enum | — | M, F | — |
| date_of_birth | date | — | — | age = completed years on the donation date |
| blood_group | enum | — | O, A, B, AB | — |
| rh | enum | — | POS, NEG | — |
| first_time_donor | bool | — | — | — |
| last_donation_date | date | — | — | previous whole-blood donation; empty for first-time donors |
| deferred_until | date | — | — | empty = not deferred |
| mobile | string | 10 digits | — | — |

### `donations.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| donation_id | string | DON-nnnn | — | — |
| donor_id | string | — | donors.csv | — |
| collection_ts | timestamp | — | — | — |
| weight_kg | decimal | kg, 1 dp | — | — |
| haemoglobin_g_dl | decimal | g/dL, 1 dp | — | — |
| additive_solution | bool | — | — | PRBC 42 days if true |
| mobilised_by_hospital_id | string | — | hospitals.csv | replacement donation credited to the hospital; empty = voluntary |

### `components.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| unit_id | string | U-nnnn-X | — | X = P (PRBC), F (FFP), L (PLATELET) |
| donation_id | string | — | donations.csv | deferred attempts have no units |
| component | enum | — | PRBC, FFP, PLATELET | — |
| volume_ml | int | ml | — | — |
| separated_ts | timestamp | — | — | — |
| frozen_ts | timestamp | — | — | FFP only |

### `screening_results.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| donation_id | string | — | donations.csv | — |
| marker | enum | — | HIV, HBV, HCV, SYPHILIS, MALARIA | — |
| result | enum | — | REACTIVE, NON_REACTIVE | — |
| result_ts | timestamp | — | — | all 5 results of a donation arrive together |

### `hospitals.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| hospital_id | string | HSP-nn | — | — |
| hospital_name | string | — | — | — |
| hospital_type | enum | — | GOVERNMENT, PRIVATE | government pays 50% |
| city | string | — | — | — |

### `hospital_quotas.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| hospital_id | string | — | hospitals.csv | — |
| component | enum | — | PRBC, FFP, PLATELET | — |
| daily_cap_units | int | units/day | — | — |

### `requests.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| request_id | string | REQ-nnn | — | numbered by request_ts |
| hospital_id | string | — | hospitals.csv | — |
| patient_name | string | — | — | — |
| patient_gender | enum | — | M, F | — |
| patient_age | int | years | — | — |
| patient_group | enum | — | O, A, B, AB | — |
| patient_rh | enum | — | POS, NEG | — |
| component | enum | — | PRBC, FFP, PLATELET | — |
| units | int | — | — | — |
| urgency | enum | — | ROUTINE, URGENT, EMERGENCY | — |
| request_ts | timestamp | — | — | the REQUEST command carries the same time |
| needed_by_ts | timestamp | — | — | — |

## Command file format

`commands.txt` holds one command per line in the form `COMMAND_NAME|arg1|arg2|...`. Commands must be processed strictly in file order. Lines starting with `#` are comments and blank lines are ignored. An empty argument (two adjacent `|`) means "not supplied". Every command used in this pack:

| Command | Arguments (in order) | Meaning |
|---|---|---|
| `DONATION` | `donation_id|ts` | donation attempt (eligibility check; accepted → components enter QUARANTINE) |
| `SCREENING` | `donation_id|ts` | all 5 screening results of the donation become known (screening_results.csv) |
| `REQUEST` | `request_id|ts` | hospital request arrives (details in requests.csv) — allocate now |
| `ISSUE` | `request_id|ts` | hospital collects the cross-matched / allocated units |
| `RETURN` | `request_id|ts|units|cold_chain` | hospital returns units of that request's issue |
| `CROSSMATCH_RESULT` | `request_id|ts|result` | retrospective cross-match for an EMERGENCY issue (COMPATIBLE / INCOMPATIBLE) |
| `CANCEL_REQUEST` | `request_id|ts` | hospital cancels the request (release reservations, drop from queue) |
| `DAILY_RUN` | `date` | end-of-day expiry, quarantine and alert run (23:59:59) |
| `PRINT_STOCK` | `date` | stock position by group and component at end of that date |
| `PRINT_INVOICE` | `hospital_id|from_date|to_date` | processing-charge invoice for issues in the range |

## Planted scenarios

Every edge case in the brief, mapped to the exact record where it occurs, followed by extra traps.

- **EC-01 Donor exactly 65 years old; first-time donor exactly 60**
  - DNR-072 turns 65 on the donation date (eligible, 18–65); DNR-073 is a first-time donor turning 60 that day (eligible, <= 60) — `donors.csv row 72 and row 73`
- **EC-02 Exactly 90 days since the last donation for a male donor**
  - DNR-075 (male) last donated 2026-07-09, exactly 90 days before 2026-10-07 — eligible — `donors.csv row 75`
- **EC-03 FFP frozen at exactly 8 hours after collection**
  - FFP frozen at exactly collection + 8 h 00 min (valid 365 days if 'within 8 hours' is inclusive) and a second FFP frozen at + 8 h 01 min (shelf life 0 → DISCARDED) — `components.csv rows 326, 327, 328 and rows 329, 330, 331`
- **EC-04 Unit expiring today at 23:59 requested at 23:30**
  - REQ-066: platelet request at 2026-10-15 23:30; the A+ platelet collected 2026-10-10 07:30 expires 2026-10-15 23:59 (collection date + 5 days) — still issuable — `components.csv rows 341, 342, 343; requests.csv row 66`
- **EC-05 Rh- female patient aged exactly 50 in an EMERGENCY with zero Rh- stock**
  - REQ-002: B− female aged exactly 50, EMERGENCY, while no Rh-negative PRBC is in date (May–Aug Rh− PRBC have expired; the next Rh− collection is 2026-10-06) — 'females over 50' does not include 50: no Rh+ unit may be issued → shortfall queued. Contrast REQ-003: B− male EMERGENCY at 10:05 may receive Rh+ PRBC — `requests.csv row 2 and row 3`
- **EC-06 Two groups with equal available count when choosing the compatible fallback**
  - REQ-001: AB+ patient, no AB+ PRBC exists; compatible stock at 2026-10-02 11:00 is O+ 9 and A+ 9 (equal, largest) and B+ 7 — the 'largest available count' preference ties between O+ and A+; state and apply your tie-break (then FEFO inside the chosen group) — `requests.csv row 1; donations.csv rows 71, 72, 73, 74, 75, 76 … 95 (25 rows)`
- **EC-07 Cross-match reservation reaching 72 hours during an EMERGENCY pre-emption**
  - REQ-016 (ROUTINE, O−) cross-matches the only two O− PRBC units at 2026-10-09 10:00:00 and never issues them; REQ-040 (EMERGENCY, O−) arrives at 2026-10-12 10:00:00 — exactly 72 h later: is the reservation already auto-released (EMERGENCY simply takes a free unit) or must it be pre-empted (ROUTINE back to the queue)? — `requests.csv row 16 and row 40; donations.csv rows 104, 105`
- **EC-08 Unit returned at exactly 30 minutes after issue**
  - REQ-035: 2 units issued 15:10, 1 returned in cold chain at 15:40 = exactly 30 minutes → restocked and not billed (if 'within 30 minutes' is inclusive); REQ-048: returned 31 minutes after issue → discarded and billed — `commands.txt line 451, lines 450, 453, line 490, lines 486, 493`
- **Extra traps (not in the brief, but realistic):**
  - DNR-074 is 66 — DEFERRED (age) and the attempt yields no components — `donations.csv row 101`
  - DNR-076 (female) donated 119 days ago — needs 120 → DEFERRED — `donations.csv row 111`
  - DON-0116: HBV REACTIVE — every component of the donation is DISCARDED and the donor is permanently deferred — `screening_results.csv rows 566, 567, 568, 569, 570`
  - Screening results arrive 80 h after collection — the units stay QUARANTINE past 72 h and the platelet (older than 72 h without results) is DISCARDED — `components.csv rows 368, 369, 370`
  - Haemoglobin 12.4 g/dL (< 12.5) — DEFERRED, no components — `donations.csv row 135`
  - Weight 44.5 kg (< 45) — DEFERRED — `donations.csv row 136`
  - DNR-080 carries a deferral until 2026-11-30 — blocked (DEFERRED) — `donations.csv row 142`
  - REQ-075: 4 A+ platelets requested; the pool may only combine same-group units whose expiries lie within 24 h of each other — the pooled product expires at the earliest member — `components.csv rows 380, 381, 382, 383, 384, 385 … 409 (12 rows)`
  - HSP-04 (government) has a PRBC daily cap of 2: REQ-050 (ROUTINE, 3 units) is capped — PARTIAL with 1 queued; REQ-052 (EMERGENCY) the same day ignores the cap; billing at 50% plus the Rs 500 EMERGENCY surcharge — `requests.csv row 50 and row 52`
  - REQ-079: EMERGENCY issue with no CROSSMATCH_RESULT within 24 h — flag the issue — `requests.csv row 79`
  - REQ-016 is cancelled on 2026-10-16 while (after EC-07) it may still be queued — remove it from the queue — `commands.txt line 546`

## What is NOT in this pack

Expected outputs are not provided for this set. Validate your engine with your own test suite against the rules in your brief (BR-01 … BR-nn). A separate hidden input set with the same schema will be used at final evaluation; outputs are compared field-for-field, so follow the column formats above exactly in your own output.

## Output format expected at evaluation

Produce these CSV files (header row, same conventions as above, rows sorted as stated). Where the brief is silent on a format detail the choice below is binding for evaluation.

### `unit_status.csv`

One row per unit status change.

Columns, in order: `unit_id`, `ts`, `status`, `reason`

### `donation_eligibility.csv`

One row per donation attempt.

Columns, in order: `donation_id`, `donor_id`, `decision`, `failed_rule`

### `allocations.csv`

One row per allocated unit (and one row per shortfall).

Columns, in order: `request_id`, `unit_id`, `unit_group`, `unit_rh`, `compatibility_path`, `reservation_state`, `allocated_ts`, `sla_met`, `note`

### `stock_positions.csv`

One row per group/Rh/component per PRINT_STOCK.

Columns, in order: `date`, `blood_group`, `rh`, `component`, `available`, `quarantine`, `crossmatched`, `alert`

### `invoices.csv`

One row per billed unit per PRINT_INVOICE.

Columns, in order: `hospital_id`, `request_id`, `unit_id`, `component`, `base_charge`, `government_discount`, `emergency_surcharge`, `amount`

Binding choices: a component's last valid day = collection date + shelf-life days (PRBC 35/42, FFP 365, PLATELET 5) and it expires at 23:59 that day. Unit `status` is QUARANTINE, AVAILABLE, CROSSMATCHED, ISSUED, RETURNED, DISCARDED or EXPIRED. `decision` is ACCEPTED or DEFERRED. `compatibility_path` is IDENTICAL, COMPATIBLE_<group><rh>, O_NEG_RESERVE or EMERGENCY_RH_POS. `alert` is SHORTAGE, CRITICAL or empty.
