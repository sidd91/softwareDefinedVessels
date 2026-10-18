# ArgOS pitch facts

**ArgOS: Reliability through Automation**

- The single source for every number and claim a slide may use.
- Rule: a number that is not in this file does not go on a slide.
- Team: Logan Walker (GhostWalka) and Siddharth Chawla.
- Written by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka), Sat 2026-10-17, 22:28 to 23:05 PDT.
- Every row names the command or test that produced it (IDs in "Commands run"), and when.
- All times are PDT on Sat 2026-10-17.
- Two commits were checked:
  - `5f09b6c`: this branch's base (main `918478a` plus the deployment map).
  - `1148d11`: `origin/main` at 22:30 (fix pack 1), run from a `git archive` copy with no `.git`.
- Where the two differ, the row says so. The demo runs from main, so use the main value.
- "ms" is wall-clock time on Logan's laptop, with other agents running at the same time.

## Terms, defined once

| Term | Plain English |
|---|---|
| ArgOS | our resource governor: software between the ship's automation and its payloads |
| Guest | a payload that comes aboard: G1 to G5 from the brief, G6 ours |
| Card | a guest's manifest: what it draws, what it needs, where it fits |
| Priority file, profile | the mission's weights and rules, swapped by the jury |
| Ledger | one table of capacity, demand and free space per resource |
| Line | one row of the ledger, for example mass or cooling |
| Binding line | the line that decides: the most over, or the tightest |
| D1 to D6 | the brief's six decision classes |
| A.8 | the brief's time limit for each kind of decision |
| Yes-if | yes, if something gives way, ranked by mission value lost |
| Gate | the one-genset-down test: min(100 kW, cooling) minus 5 kW |
| Tick | one ship second; the loop runs at 1 Hz |
| Snapshot | the estimated ship state at one tick |
| Record | one decision: its numbers and one sentence |
| Replay | the logs re-run without the simulator, compared byte for byte |
| Test double | a labelled stand-in for the simulator |
| Standby | a second governor on the same inputs, compared every tick |
| Response class | the time limit a guest answers to: 200 MS, 5 S or 60 S |
| Physical Account | every assumed number, its reason, where code uses it (Annex C) |
| Envelope | the conditions the ship will sail in (A.10); cooling judged at 30 °C |
| Scenario A | the brief's admission test: ship in port, the jury's card |
| Scenario B | the brief's contention run: right of way at minute 8, genset trip at minute 12; ours runs 20 ship minutes |
| R3 | our crew rule: nobody on the flight deck during the drone's recovery |
| t-eq | tonnes-equivalent: mass weighted by where it sits (mast x3, deck x1), for stability |
| SATCOM, LOS radio | satellite link; line-of-sight radio |
| P90 | 90th percentile: 9 samples in 10 are at or below it |

## Commands run

| ID | Command | Commit | When |
|---|---|---|---|
| C1 | `uv run sdv admit G4 --installed G1,G2,G3` | 5f09b6c | 22:30 |
| C2 | C1 with `--set G4.hangar.mass_t=0.8` | 5f09b6c | 22:30 |
| C3 | Scenario A batch: `uv run sdv admit <card> --installed <set> --mission <file>`, cases in section 4 | 5f09b6c | 22:31 |
| C4 | C3 again | 1148d11 | 22:32 |
| C5 | `uv run sdv run --mission survey --log-dir <dir>` | 5f09b6c | 22:32 |
| C6 | `uv run sdv run --mission sar --log-dir <dir>` | 5f09b6c | 22:32 |
| C7 | `uv run sdv replay <dir> --mission sar`, then `--mission survey` | 5f09b6c | 22:32 |
| C8 | C5 to C7 again | 1148d11 | 22:43 |
| C9 | `python3` over each run's `timing.jsonl`: min and max per decision, worst tick | both | 22:49, 22:50 |
| C10 | safety one-liner: `Loop(..., standby=True)`, `loop.safety('g3_hold_depth')` at tick 300, read `core.timing` | both | 22:49, 22:50 |
| C11 | `uv run pytest -q` | 5f09b6c | 22:34 to 22:38 |
| C12 | `uv run pytest -q tests/test_ui_server.py::test_ws_streams_the_live_loop_and_takes_laptop_inputs` | 5f09b6c | 22:38 |
| C13 | `uv run pytest -q` | 1148d11 | 22:39 to 22:43 |
| C14 | `uv run pytest -q tests/test_loader.py tests/test_mission_schema.py tests/test_decisions_b.py tests/test_loop.py tests/test_kit.py tests/test_response.py tests/test_ui_live.py` | 5f09b6c | 22:39 to 22:42 |
| C15 | `uv run sdv kit plan` | both | 22:34, 22:39 |
| C16 | `uv run sdv kit build <dir>`, then `uv run sdv kit verify <dir>` | 5f09b6c | 22:48 |
| C17 | `uv run python tools/deploy_map/deploy.py --out <dir>` | 5f09b6c | 22:34 |
| C18 | `uv run sdv run --mission survey --variant crew0 --no-script`; the same without `--no-script`; `uv run sdv run --mission survey --no-script` | both | 22:36, 22:44 |
| C19 | config batch: response classes per profile, boards per hull, package licences, `grep` for network and randomness in `src/sdv` | 5f09b6c | 22:46 |
| C20 | `uv run python tools/physical_account.py` (it rewrites the account: reverted here, nothing committed) | both | 22:35, 22:39 |
| C21 | a bad priority file `config/missions/jury.yaml` (`sar_air: 1.5`), then C1 | main copy | 22:45 |
| C22 | `pdftotext` of the brief, `~/Downloads/[n3 DMM] Software-Defined-Vessel_SHORT..pdf` | none | 22:29 |
| C23 | `timeout 10 adb devices` (is the board connected?) | none | 22:41 |
| C24 | standby one-liner: `Loop(..., standby=True)` to tick 1200, the set of `out.standby` | both | 22:49, 22:50 |
| C25 | snapshot log of C5, `capacity` block at ticks 0, 721 and 1141 | 5f09b6c | 22:37 |
| C26 | scratch script: a `crew_change` to 6 and to 0 at tick 100, with and without the scripted bridge answer, `Loop(...).ticks(until=1200)` | both | 22:57 |

## 1. The pitch in four lines

| Beat | Line | Backed by |
|---|---|---|
| Product | ArgOS: a resource governor for a 60 m re-configurable vessel | F-01 |
| Problem | a fixed budget in 8 classes, and payloads nobody aboard has seen | F-02 |
| Unique | one ledger; one sentence from the number that bound; same code, two missions | F-11, F-43 to F-50 |
| Demo | Scenario B on both files, then Scenario A with the jury's card | F-43 to F-54, F-22 to F-41 |

| ID | Fact | Value | Verified by | When |
|---|---|---|---|---|
| F-01 | Hull in the ship profile | 60 m (brief Annex A: 60 to 70 m) | C15 "HULL 60 m"; C22 | 22:53 |

## 2. The brief's eight resource classes

| ID | Class (brief) | ArgOS ledger lines | Verified by | When |
|---|---|---|---|---|
| F-02 | The 8 classes | power, heat rejection, deck, mast, mass and stability, data links, compute, response time | C22, "What you're building" | 22:29 |
| F-03 | Electrical power | `power` 200 kW, `line_port` 150, `line_stbd` 150 | C1 | 22:30 |
| F-04 | Heat rejection | `heat` 120 kW at 30 °C; `mast_air_cooling` 2 kW | C1 | 22:30 |
| F-05 | Deck positions | placement (Bay 1, Bay 2, flight deck); `flight_deck_drone` 150 kg | C1 | 22:30 |
| F-06 | Mast positions | `mast_mass` 60 kg, `mast_area` 0.6 m² | C1 | 22:30 |
| F-07 | Mass and stability | `mass` 10 t, `stability` 12 t-eq | C1 | 22:30 |
| F-08 | Data links in D1 | 5f09b6c: none · main: `satcom` 2, `los_radio` 20, `backbone` 10000 Mbit/s | C3, C4 | 22:31, 22:32 |
| F-09 | Compute in D1 | 5f09b6c: none · main: `compute` 102.4 cores (4 x 32 x 0.8) | C4, C19 | 22:32, 22:46 |
| F-10 | Response time | a ceiling on every decision in the timing log | C9 | 22:49 |
| F-11 | Ledger lines in the A1 verdict | 5f09b6c: 10 · main: 14 | C1, C4 | 22:30, 22:32 |
| F-12 | Links at 1 Hz in every snapshot | acoustic 3 kbit/s, SATCOM 6, LOS radio 20 Mbit/s | C25, tick 0 | 22:37 |

## 3. Decision classes: A.8 limit against measured

| ID | Class | A.8 limit | Measured | Verified by | When |
|---|---|---|---|---|---|
| F-13 | D1 Admission (with D2) | 30 s | 0.5 to 5.8 ms (5f09b6c) · 0.9 to 5.2 ms (main), 15 runs each | C3, C4, `TIME` line | 22:31, 22:32 |
| F-14 | D2 Placement | 30 s | inside the D1 time (one call) | C3 | 22:31 |
| F-15 | D3 Right of way | 2 s | 0.3 to 0.9 ms | C9 | 22:49, 22:50 |
| F-16 | D4 first action | 5 s | compute 0.3 to 1.1 ms; applied 2 s after the raw fault, due by 5 s | C9; C5, C6 records | 22:49 |
| F-17 | D4 full sequence | 60 s | 1 step needed at minute 19, applied tick 1142, due by 1200 | C5, C6 records | 22:32 |
| F-18 | D5 Crew as a setting | none in A.8 (ours: 2 s) | 0.2 to 0.7 ms | C9 | 22:49, 22:50 |
| F-19 | D6 Physical Account | none | 21 rows, 61 assumed and 2 measured keys, 6 cards | C20 | 22:35 |
| F-20 | Safety command (stop, hold, secure) | 200 ms | 0.072 to 0.109 ms | C10 | 22:49, 22:50 |
| F-21 | Whole tick (estimator and every decision) | none (a tick is 1 s) | worst 1.2 to 10.2 ms over 1201 ticks | C9 | 22:49, 22:50 |

## 4. Scenario A: admission in port

Same verdicts on both commits. Times are 5f09b6c's.

| ID | Case: card onto | File | Verdict | Binding line | Top yes-if | One genset down | Time | Check |
|---|---|---|---|---|---|---|---|---|
| F-22 | A1: G4 onto G1, G2, G3 | survey | YES-IF | mass 10.035 / 10 t, 35 kg over | G1 off, value lost 0.2 | 81.5 / 100 kW, fits | 1.8 ms | C3, C4 · 22:31 |
| F-23 | A1 | sar | YES-IF | same | G3 off, 0.2 | fits | 2.0 ms | C3, C4 · 22:31 |
| F-24 | A2: G1 onto G2, G3, G4 | survey | YES-IF | mass 10.035 / 10 t | G4 off, 0.2 | fits | 1.8 ms | C3, C4 · 22:31 |
| F-25 | A2 | sar | YES-IF | same | G3 off, 0.2 | fits | 1.9 ms | C3, C4 · 22:31 |
| F-26 | A3: G5 onto G2, G3, G4 | survey | YES-IF | mass 13.015 / 10 t; also over: stability 13.263 / 12, cooling 125 / 120 kW | G2 off, 1.0 | 125 / 100, holds by throttling | 5.8 ms | C3, C4 · 22:31 |
| F-27 | A3 | sar | YES-IF | same | G3 off, 0.2 | holds by throttling | 5.6 ms | C3, C4 · 22:31 |
| F-28 | A4: G3 onto G1, G2, G5 | survey | YES-IF | mass 12.07 / 10 t; also over: stability 12.165 / 12 | G5 off, 0.2 | fits | 3.0 ms | C3, C4 · 22:31 |
| F-29 | A4 | sar | YES-IF | same | G2 off and G5's node to Bay 2, 0.5 | fits | 2.8 ms | C3, C4 · 22:31 |
| F-30 | A5: G4 onto G1, G2, G5 | survey | YES | cooling 100 / 120 kW, 20 spare | none | 101.5 over the 95 gate; holds with G4 fast charge to charge (25 kW) | 1.8 ms | C3, C4 · 22:31 |
| F-31 | A5 | sar | YES | same | none | holds with G2 winch to sampling (14 kW) | 1.9 ms | C3, C4 · 22:31 |
| F-32 | A6: A1 with G4's hangar at 0.8 t | both | YES | mass 9.985 / 10 t, 15 kg spare | none | fits | 1.0 ms | C3, C4 · 22:31 |
| F-33 | A7: G6 (ours) onto G4, G5 | disaster relief | YES | cooling 98 / 120 kW, 22 spare | none | 98 over the gate; holds with G4 fast charge to charge | 1.4 ms | C3, C4 · 22:31 |
| F-34 | A7 | sar | YES | same | none | holds with G6 production to recirculate (14 kW) | 1.2 ms | C3, C4 · 22:31 |

| ID | Fact | Value | Verified by | When |
|---|---|---|---|---|
| F-35 | Seawater tipping point | A3 flips at 27.75 °C; A1, A2, A6 at 48 °C; A5 at 39 °C | C3 `SEAWATER TIP` | 22:31 |
| F-36 | How the binding line is picked | the most over, as a share of capacity; the others listed as also over | C3 (A3, A4); `src/sdv/admission.py` | 22:31 |

The jury's one-number edit:

| ID | Edit (`--set`) | Result | Verified by | When |
|---|---|---|---|---|
| F-37 | `G4.hangar.mass_t=0.8` | card re-validated; YES-IF becomes YES | C2, C3, C4 | 22:30 |
| F-38 | `G4.hangar.mass_t=heavy` | refused, field named, "Previous card kept" | C3, C4 | 22:31 |
| F-39 | `G4.hangar.colour=red` | refused, "'colour' was unexpected", card kept | C3, C4 | 22:31 |
| F-40 | `G4.hangar.mass_t=10` | NO: mass 19.185 / 10 t, "No removal set fits" | C3, C4 | 22:31 |
| F-41 | `G5.consumes.data_satcom_mbps.min=50`, onto G1, G2 | 5f09b6c: YES (not judged) · main: NO, "SATCOM binds: 50.2 Mbit/s against 2 Mbit/s" | C3, C4 | 22:31, 22:32 |
| F-42 | `G5.consumes.power_kw.nominal=60`, onto G2, G3, G4 | crashes (`StopIteration`) on both: see Do not claim | C3, C4 | 22:31, 22:32 |

## 5. Scenario B: minutes 8, 12 and 19, both files

Load-out G3, G4, G5. Same outcomes on both commits.

| ID | Moment | Survey file | Rescue file (sar) | Verified by | When |
|---|---|---|---|---|---|
| F-43 | Min 8, D3 | G4 recovers first: below 20 % it must land within 12 min, by minute 18.2 | same | C5, C6, C8 | 22:32, 22:43 |
| F-44 | Min 8, cost to the loser | G3 holds depth, loses 25 to 27 survey minutes | G3's leg aborted, at least 25 to 27 minutes, no resume time; G4's 35 kW reserved | C5, C6, C8 | 22:32, 22:43 |
| F-45 | Min 8, D5 at 14 aboard | bridge asked to confirm; cleared at minute 9 | same | C5, C6, C8 | 22:32, 22:43 |
| F-46 | G4 lands | tick 1020, minute 17.0, 1.2 min inside 18.2 | same | C5, C6 snapshots | 22:48 |
| F-47 | Min 12, genset trip (raw 720 s, confirmed 721 s) | holds: 48 of 95 kW, 0 steps | holds: 81 of 95 kW, 0 steps | C5, C6, C8 | 22:32, 22:43 |
| F-48 | Min 12, first armed step | G5 full to low power, frees 37 kW | same | C5, C6, C8 | 22:32, 22:43 |
| F-49 | Min 12 sentence, main only | adds the full armed order, and "the envelope case does not arise": 105 kW against 95 | same | C8 | 22:43 |
| F-50 | Min 19, injected pump fault | cooling binds, 81 kW against 75; G4 fast charge to charge, 56 kW; G4 loses 30 % | cooling binds, 81 against 75; G5 to low power, 44 kW; G5 loses 70 % | C5, C6, C8 | 22:32, 22:43 |
| F-51 | Min 19 timing | raw 1140 s, confirmed 1141, applied 1142; due 1145 (5 s) and 1200 (60 s) | same | C5, C6 records | 22:32 |
| F-52 | Min 19, two limits at once | power 100 kW (genset still down), cooling 80 kW (pump down); limit 80 - 5 = 75 | same | C25, tick 1141 | 22:37 |
| F-53 | Min 19 with no pump loss | limit stays 95 kW against 81 kW: nothing shed | same | F-47, F-50 | 22:37 |
| F-54 | Decisions per run | 6 records: D3, D5 x 2, D4 x 3 | same | C7 | 22:32 |

## 6. Replay, determinism and the standby

| ID | Fact | Value | Verified by | When |
|---|---|---|---|---|
| F-55 | Replay of a logged run | "REPLAY EQUAL 1201 snapshots, 6 records, byte for byte", survey and sar | C7, C8 | 22:32, 22:43 |
| F-56 | Standby governor in lockstep | 1201 of 1201 ticks "in step", survey and sar | C24 | 22:49, 22:50 |
| F-57 | Logs per run | frames, inputs, snapshots, decisions, timing | C5 | 22:32 |
| F-58 | Wall clock in records | none: latency goes only to `timing.jsonl` | C7 (byte-equal replay), C9 | 22:32, 22:49 |
| F-59 | Network calls or randomness in `src/sdv` | none found | C19 | 22:46 |

## 7. Tests

| ID | Fact | Value | Verified by | When |
|---|---|---|---|---|
| F-60 | Test suite, main `1148d11` | 1314 passed in 271.61 s | C13 | 22:39 to 22:43 |
| F-61 | Test suite, `5f09b6c` | 1293 passed, 1 failed, in 226.95 s | C11 | 22:34 to 22:38 |
| F-62 | The 1 failure | a websocket UI test; fails in its file, passes alone in 13 s | C12 | 22:38 |
| F-63 | Edge-case files: loader, profiles, Scenario B, loop, kit, response, live screen | 120 passed | C14 | 22:39 to 22:42 |
| F-64 | Hostile inputs in `tests/test_loader.py` | 15 cards, 8 priority files, each refused with the field named | C14; C19 count | 22:46 |

## 8. Response classes (docs/RESPONSE_TIME.md)

| ID | Fact | Value | Verified by | When |
|---|---|---|---|---|
| F-65 | The brief's limits in config | admission 30 s, placement 30, arbitration 2, first shed 5, full sequence 60, safety 0.2 | C19 | 22:46 |
| F-66 | Tags | 200 MS, 5 S, 60 S, 30 S, 2 S, formatted from those numbers | C19; `test_the_tags_come_from_the_brief_numbers` in C14 | 22:46 |
| F-67 | Who is 60 S (gives power last) | survey: G3 · sar: G4 · patrol: G1 · disaster relief: G5, G6 | C19 | 22:46 |
| F-68 | Everyone else | 5 S (gives power first) | C19 | 22:46 |
| F-69 | 200 MS guests by default | none: no card is safety-critical, as the brief says | C19 | 22:46 |
| F-70 | Order | every 5 S step before any 60 S step; slow down before switching off | `test_d4_takes_every_5_s_step_before_any_60_s_step` in C14; both minute-19 steps slow a guest down (F-50) | 22:42 |

## 9. Governor hardware plan (docs/DEPLOYMENT.md)

| ID | Fact | Value | Verified by | When |
|---|---|---|---|---|
| F-71 | Boards on the 60 m hull | 4: primary (bridge), standby (engine control room), 2 zone boards | C15 | 22:34 |
| F-72 | Board rule | 2, plus 1 per started 25 m beyond 25 m: 25 m 2, 40 m 3, 60 m 4, 70 m 4, 100 m 5 | C19 | 22:46 |
| F-73 | Board in config | VENTUNO Q, 8 cores, 14 GB RAM, 55 GB | C19 | 22:46 |
| F-74 | Edge nodes | 6, Pi 5 class, 64 GB each, each holds the latest shed table | C15 | 22:34 |
| F-75 | Offline copies | 2 SSDs of 1000 GB, 1 printed binder | C15 | 22:34 |
| F-76 | Heartbeat, takeover | 1 s, 3 s (in config; design, not run on two boards) | C19 | 22:46 |
| F-77 | Reference Kit | 30 files, 0.27 MB, stamped with its commit; every device holds all of it; checksums verified | C16 | 22:48 |
| F-78 | Kit share per device | 20 GB of a board, 8 GB of an edge node | C19 | 22:46 |

## 10. Deployment map (tools/deploy_map, this branch only)

| ID | Fact | Value | Verified by | When |
|---|---|---|---|---|
| F-79 | Route | Strait of Sicily cable corridor, Mazara del Vallo to Kelibia and back: 4 waypoints, 191.4 km | C17 `deployment.json` | 22:34 |
| F-80 | Period | 01 to 15 Oct 2026, 14 days (A.10) | C17 | 22:34 |
| F-81 | Samples | 400 points, seed 0, ±10 km either side of the route | C17 | 22:34 |
| F-82 | Seawater | P10 24.22, P50 25.14, P90 25.95, max 27.0 °C | C17 | 22:34 |
| F-83 | Wind and gusts | wind max 23.93 kn; gust P90 24.97, max 31.83 kn | C17 | 22:34 |
| F-84 | Sea state | P90 3, max 3; waves max 2.45 m | C17 | 22:34 |
| F-85 | Windows open | G2 probe 100 %, G3 launch and recovery 100 %, G4 launch and recovery 90 % | C17 | 22:34 |
| F-86 | Cooling on the route | 129.0 kW at P90, 126.7 at max; 76.0 kW with a pump down, against 105 kW of guest heat | C17 | 22:34 |
| F-87 | Verdict per profile | all 4 YES, at the envelope and at the route maximum; mass binds, 9.515 / 10 t | C17 | 22:34 |
| F-88 | Weather source | Open-Meteo (CC BY 4.0), fetched 2026-10-17T22:49Z, 360 hourly rows per waypoint | C17 cache file | 22:36 |

## 11. Physical Account (docs/PHYSICAL_ACCOUNT.md)

| ID | Fact | Value | Verified by | When |
|---|---|---|---|---|
| F-89 | Size | 1 page, 21 rows; 61 assumed and 2 measured keys; 6 cards | C20 | 22:35 |
| F-90 | How it is made | generated from `config/assumptions.yaml` and the cards: each key's source, reason, and where code reads it | C20 | 22:35 |
| F-91 | Keys no code reads yet | 5f09b6c: 23 "not yet" · main: 12 "documented only" | `grep` of each commit's detail page | 22:41 |
| F-92 | Closing answer | one standby chilled-water pump; then minute 19 sheds nothing (F-53) | `docs/PHYSICAL_ACCOUNT.md`, F-53 | 22:37 |

## 12. Data, licences, AI

| ID | Fact | Value | Verified by | When |
|---|---|---|---|---|
| F-93 | Python packages | 27, all MIT, BSD, Apache-2.0 or PSF: 26 third-party plus ours | C19 | 22:46 |
| F-94 | Our code | MIT; `LICENSE` names Siddharth only (audit gap 28) | `head LICENSE`, both commits | 22:53 |
| F-95 | Ship and guest numbers | the brief's Annex A and B, plus our labelled assumptions | C20 | 22:35 |
| F-96 | Public data | Open-Meteo, in the deployment map only; Natural Earth coastlines, public domain | C17 | 22:34 |
| F-97 | AI used | Claude (Anthropic) only, declared in `docs/SOFTWARE_LOG.md` | file | 22:37 |

## 13. Crew levels: D5, rule R3, Scenario B minute 8 (docs/SCENARIO_C_MEMO.md)

Same sentences on both commits.

| ID | Crew aboard | What the record says | Verified by | When |
|---|---|---|---|---|
| F-98 | 14, bridge answers | "Bridge asked to confirm" at 08:00; "Recovery cleared" at 09:00 | C5, C8 | 22:32, 22:43 |
| F-99 | 14, nobody answers | "Recovery held at 14 aboard: no answer from the bridge", 09:01 | C18 `--no-script` | 22:36 |
| F-100 | 0 from launch, deck swept clear | "Recovery automatic at 0 aboard", 08:00; no bridge request sent | C18 `--variant crew0 --no-script` | 22:36, 22:44 |
| F-101 | 6 from tick 100, no standing plan | "Recovery held at 6 aboard: no standing plan approved" | C26 | 22:57 |
| F-102 | 0 from tick 100, no new sweep | "Recovery forbidden at 0 aboard: ... voided the latch. G4 ditches by minute 18.2" | C26 | 22:57 |
| F-103 | 6 or 0 with the scripted bridge answer | crashes at tick 539 (`TypeError`): see X-23 | C26 | 22:57 |

## Do not claim

Planned or partial, not built. Source: Siddharth's audit, `git show origin/audit/main-gaps:docs/AUDIT_MAIN.md`,
end of section 4, "Declare as limitations". Rows marked "tonight" come from the commands above.

| ID | Do not say | Say instead | Source |
|---|---|---|---|
| X-01 | "not now, and when" (A′), installation windows (A.11) | D1 answers for a ship alongside | audit |
| X-02 | absolute excludes and `requires` in admission | schema and D3 data, not D1 logic | audit |
| X-03 | over-consumption detected and handled | metered in the ledger, not detected or named | audit |
| X-04 | D2 maximises remaining margin, shows rejected alternatives | D2 is a fixed order of rules; no D2 record | audit |
| X-05 | D3 settles any two guests | one contention, G4 recovery against G3 survey, triggered by a hard limit | audit |
| X-06 | the -40 % loop at 30 °C is in the verdict | an information line on the Admission screen (DEC-36) | audit |
| X-07 | minute 12 sheds | holds by design, armed ladder shown (DEC-40, DEC-61); minute 19 sheds | audit, F-47 |
| X-08 | a ship-physics simulator | a scripted, labelled test double; `SDV_SIM` swaps it | audit, C5 header |
| X-09 | the jury can change any number | masses and other fields yes; a kW edit crashes (F-42) | audit; tonight |
| X-10 | drop any priority file in | loaded by id; a bad file on disk stops start-up (C21); a bad profile at sea is refused | audit; C21 tonight |
| X-11 | Scenario B runs on real weather | the brief's 24 °C; Open-Meteo only in the standalone map | audit, C17 |
| X-12 | every Physical Account number is read by code | 12 (main) to 23 (5f09b6c) keys documented only (F-91) | audit; tonight |
| X-13 | the authorised-AI list is cited | its source is still pending | audit, `docs/SOFTWARE_LOG.md` |
| X-14 | data links and compute in D1, on 5f09b6c | on main only (F-08, F-41) | tonight |
| X-15 | `sdv run --variant crew0` as is | crashes (`TypeError`) on the scripted bridge answer, both commits; add `--no-script` | C18 tonight |
| X-16 | board measurements: watts, latency per class | planned; the board was not connected tonight | `docs/NODE_B_BOARD.md`, C23 |
| X-17 | 3 s failover between two boards | design only; the standby check runs in one process (F-56) | `docs/DEPLOYMENT.md`, F-76 |
| X-18 | MET, MISSED, DUE shown on screen | in the records, not on screen yet | `docs/RESPONSE_TIME.md` |
| X-19 | the run the jury watched can be replayed | replay is from `sdv run --log-dir` | audit gap 12 |
| X-20 | the deployment map is part of the ArgOS screen | standalone tool, this branch only | `tools/deploy_map/deploy.py` |
| X-21 | every test passes on 5f09b6c | 1 UI test fails in the full run (F-61) | C11, C12 |
| X-22 | certified, or cyber-secure | out of scope by the brief | C22 |
| X-23 | change the crew level to 6 or 0 live, before minute 9 | the loop crashes at tick 539 on the scripted bridge answer, which the screen also plays (`src/sdv/ui/live.py`); show crew 14 and 0 from the CLI (F-99, F-100) | C26 tonight, audit gap 5 |
