# ArgOS pitch facts

**ArgOS: Reliability through Automation**

- The single source for every number and claim a slide may use.
- Rule: a number that is not in this file does not go on a slide.
- Team: Logan Walker (GhostWalka) and Siddharth Chawla.
- Written by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka). First pass Sat 2026-10-17, 22:28 to 23:05 PDT. Refreshed Sat 23:38 to Sun 00:20 PDT.
- Baseline: `origin/main` at `4c4f93c` (fix packs 1, 2, 3a and 3b), merged into this branch as `1fae181`.
- This branch has the same engine and tests as that main, plus these docs and the older map tool from `5f09b6c`.
- Every row names the command that produced it (C-ids below) and when. Times are PDT, Sat 2026-10-17, unless marked Sun.
- "ms" is wall-clock time on Logan's laptop. "Alone" means no test suite ran at the same time.

Labels:

| Label | Means |
|---|---|
| (on branch fix/review-ours, not on main yet) | Logan's estimator, kit and safety hardening, `58aa013` |
| (on branch feat/deployment-map, not on main yet) | Logan's offline weather map, `b1926e3` |
| (on branch docs/review-fixes, not on main yet) | Logan's doc corrections, `893914a` |
| (now, since the load-out reached main at 7b9a804: X) | Siddharth's organisers' load-out, G1, G3, G4, G5, measured on `c5c7f1d`. Main moved to `7b9a804` at 23:53, after this check. That commit carries the branch with the same code, so from `7b9a804` on, X is the value on main |

## 0. Headline numbers for the deck

| Number | Fact |
|---|---|
| 8 | resource classes in one ledger, 14 ledger lines in a verdict (F-02, F-11) |
| 6 | decision classes, D1 to D6, each timed against the brief's limit where A.8 sets one (F-13 to F-20) |
| 0.9 to 7.4 ms | admission verdict, against 30 s (F-13) |
| 0.3 ms | right of way, against 2 s (F-15) |
| 0.3 to 0.4 ms | first shed computed, against 5 s (F-16) |
| under 0.05 ms | safety command answered, against 200 ms (F-20) |
| 1.8 ms | worst whole tick of 1201, against a 1 s tick (F-21) |
| 1201 of 1201 | ticks replayed byte for byte, and standby in step, both files (F-55, F-56) |
| 1476 | tests on main, all pass (F-60) |
| 15 and 8 | hostile cards and priority files, each refused with the field named (F-64) |
| 35 kg | over the 10 t margin in Scenario A, A1: YES-IF, then YES at 0.8 t (F-22, F-37) |
| 105 kW | the brief's minute-12 set against 95 kW, does not arise (F-49) (now, since the load-out reached main at 7b9a804: 106.5 kW) |
| 81 against 75 kW | minute 19, cooling binds, one step sheds (F-50, F-52) |
| 4 | governor boards on 60 m: 2 + ceil((60 - 25) / 25) (F-71, F-72) |
| 30 files, 0.27 MB | Reference Kit on every device, checksums verified (F-77) |
| 21 rows | Physical Account, 61 assumed and 2 measured keys (F-89) |
| 25.8 °C, 27.2 °C | route P90 and area max seawater, Sicily, 1 to 15 Oct 2026 (F-82, feat/deployment-map) |
| 89 % | G4 launch and recovery window open on that route (F-85, feat/deployment-map) |

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
| Gate | the one-genset-down test in D1: min(100 kW, cooling at 30 °C) minus 5 kW, so 95 kW |
| Tick | one ship second. The loop runs at 1 Hz |
| Snapshot | the estimated ship state at one tick |
| Record | one decision: its numbers and one sentence |
| Replay | the logs re-run without the simulator, compared byte for byte |
| Test double | a labelled stand-in for the simulator |
| Standby | a second governor on the same inputs, compared every tick. Today in the same process |
| Response class | the time limit a guest answers to: 200 MS, 5 S or 60 S |
| NORMAL, LATE | the screen's word for a decision's time against its own limit |
| Physical Account | every assumed number, its reason, where code uses it (Annex C) |
| Envelope | the conditions the ship will sail in (A.10). Cooling judged at 30 °C |
| Scenario A | the brief's admission test: ship in port, the jury's card |
| Scenario B | the brief's contention run: right of way at minute 8, genset trip at minute 12. Ours adds an injected pump fault at minute 19 and runs 20 ship minutes |
| R3 | our crew rule: nobody on the flight deck during the drone's recovery |
| t-eq | tonnes-equivalent: mass weighted by where it sits (mast x3, deck x1), for stability |
| SATCOM, LOS radio | satellite link, line-of-sight radio |
| P90 | 90th percentile: 9 samples in 10 are at or below it |

## Commands run

| ID | Command | Where | When |
|---|---|---|---|
| C1 | `git fetch origin && git merge origin/main` | main `4c4f93c` into this branch, clean, `1fae181` | 23:38 |
| C2 | `uv run sdv --help`, then `--help` of admit, run, replay, demo, kit | `1fae181` | 23:41 |
| C3 | Scenario A batch: `uv run sdv admit <card> --installed <set> --mission <file> [--set ...]`, 14 cases and 10 edits (section 4) | `1fae181` | 23:42 with the suite running, 23:53 alone |
| C4 | C3 again, plus `admit G1 --installed G3,G4,G5` | copy of `c5c7f1d` (fix/scenario-b-loadout-g1) | 23:45 |
| C5 | `uv run sdv run --mission survey --log-dir <dir>`, then `--mission sar` | `1fae181` | 23:42, 23:53 alone |
| C6 | `uv run sdv replay <dir> --mission <file>`, both files | `1fae181` | 23:42, 23:53 |
| C7 | C5 and C6 again | copy of `c5c7f1d` | 23:44 |
| C8 | `python3` over each run's logs: time per decision, worst tick, D4 ticks and steps, G4's landing tick, capacity at ticks 0, 721, 1141 | C5, C7 logs | 23:43, 23:53 |
| C9 | standby and safety script: `Loop(..., standby=True)` to tick 1200, both files, the 4 safety requests at ticks 300, 600, 900 with `loop.safety()` | `1fae181` | 23:48, 23:54 alone |
| C10 | crew script: `crew_change` to 6 and to 0 at tick 100, with and without the scripted bridge answer, standby on | `1fae181` | 23:48 |
| C11 | `uv run sdv run --mission survey --variant crew0`, the same with `--no-script`, and `uv run sdv run --mission survey --no-script` | `1fae181` | 23:53 |
| C12 | input script: `feed_drop guest_meter` 1130 to 1150, `feed_drop pms` 1135 to 1175, `profile_applied` at 1100 (sar with `sar_air` 0.45, `coastal_connectivity` 0.35), standby on | `1fae181`, then a copy of `58aa013` (fix/review-ours) | 23:54, 23:55 |
| C13 | `uv run pytest -q` | `1fae181` | 23:39 to 23:47 |
| C14 | `uv run pytest --collect-only -q` (all, tests/test_deploy_map.py, tests/test_loader.py, the three fix files), `git diff origin/main HEAD -- tests` | `1fae181`, copy of `c5c7f1d` | 23:49 to 23:58 |
| C15 | `uv run sdv kit plan`, `kit build <dir>`, `kit verify <dir>`, then `kit install <dir> --root <dev>` twice and `kit rollback --root <dev>` | `1fae181` | 23:46, 00:07 Sun |
| C16 | `sdv kit build` into a folder that holds one other file, and `pytest tests/test_review_fixes.py` | copies of main and of `58aa013` | 23:56 |
| C17 | `python tools/deploy_map/deploy.py --out <dir>` | copy of `b1926e3` (feat/deployment-map) | 23:40 |
| C18 | `python tools/physical_account.py`, then `python tools/build_pdfs.py account`, and `pdfinfo docs/pdf/*.pdf` | copy of main `4c4f93c` | 23:51 |
| C19 | code and config reads: response class per guest (`ledger.response_of`), boards per hull (`kit.governor_boards`), package licences, `grep` for network, randomness, takeover, heartbeat, shed table, MET, MISSED, LATE | `1fae181` | 23:50 to 00:02 Sun |
| C20 | `uv run sdv admit --card <G6 copied as G7>`, a broken card file, a stray G7.yaml in manifests/ | copy of main | 23:54 |
| C21 | a bad priority file `config/missions/jury.yaml` (`sar_air: 1.5`), then `sdv admit` | copy of main | 23:55 |
| C22 | `pdftotext` of the brief, `[n3 DMM] Software-Defined-Vessel_SHORT..pdf` | first pass | 22:29 |
| C23 | `timeout 10 adb devices` (is the board connected?) | none | 23:55 |
| C24 | `git merge-base --is-ancestor` for each branch against `origin/main`, `git ls-remote --tags origin` | refs | 23:57 |
| C25 | `uv run sdv demo --port 8461 --log-dir <dir>` for 25 s, `/api/meta`, 30 frames on `/ws`, then `sdv replay` of the logged run | `1fae181` | 00:00 Sun |

## 1. The pitch in four lines

| Beat | Line | Backed by |
|---|---|---|
| Product | ArgOS: a resource governor for a 60 m re-configurable vessel | F-01 |
| Problem | a fixed budget in 8 classes, and payloads nobody aboard has seen | F-02 |
| Unique | one ledger, one sentence from the number that bound, same code with two missions | F-11, F-43 to F-50 |
| Demo | Scenario B under the jury's file, Mission compare for both files, then Scenario A with the jury's card | F-43 to F-54, F-22 to F-42, F-105 |

| ID | Fact | Value | Verified by | When |
|---|---|---|---|---|
| F-01 | Hull in the ship profile | 60 m (brief Annex A: 60 to 70 m) | C15 "HULL 60 m", C22 | 23:46 |

## 2. The brief's eight resource classes

| ID | Class (brief) | ArgOS ledger lines | Verified by | When |
|---|---|---|---|---|
| F-02 | The 8 classes | power, heat rejection, deck, mast, mass and stability, data links, compute, response time | C22, "What you're building" | 22:29 |
| F-03 | Electrical power | `power` 200 kW, `line_port` 150, `line_stbd` 150 | C3, A1 | 23:42 |
| F-04 | Heat rejection | `heat` 120 kW at 30 °C, `mast_air_cooling` 2 kW | C3, A1 | 23:42 |
| F-05 | Deck positions | placement (Bay 1, Bay 2, flight deck), `flight_deck_drone` 150 kg | C3, A1 | 23:42 |
| F-06 | Mast positions | `mast_mass` 60 kg, `mast_area` 0.6 m² | C3, A1 | 23:42 |
| F-07 | Mass and stability | `mass` 10 t, `stability` 12 t-eq | C3, A1 | 23:42 |
| F-08 | Data links in D1 | `satcom` 2, `los_radio` 20, `backbone` 10000 Mbit/s | C3, A1 | 23:42 |
| F-09 | Compute in D1 | `compute` 102.4 cores (4 nodes x 32 cores x 0.8 guest share) | C3, A1, `config/assumptions.yaml:59-65` | 23:42 |
| F-10 | Response time | a limit on every decision in the timing log (`ceiling_ms`) | C8 | 23:43 |
| F-11 | Ledger lines in the A1 verdict | 14 | C3 | 23:42 |
| F-12 | Links in every snapshot, tick 0 | acoustic 3 kbit/s, SATCOM 6, LOS radio 20 Mbit/s | C8 | 23:43 |

## 3. Decision classes: A.8 limit against measured

| ID | Class | A.8 limit | Measured | Verified by | When |
|---|---|---|---|---|---|
| F-13 | D1 Admission (with D2) | 30 s | 0.9 to 7.4 ms over the 14 cases, alone. 2.7 to 16.7 ms with the suite running | C3, `TIME` line | 23:53, 23:42 |
| F-14 | D2 Placement | 30 s | inside the D1 time (one call) | C3 | 23:53 |
| F-15 | D3 Right of way | 2 s | 0.3 ms alone (0.9 to 1.0 ms with the suite) | C8 | 23:53 |
| F-16 | D4 first action | 5 s | compute 0.3 to 0.4 ms alone (1.0 to 1.2 with the suite). Applied at tick 1142, 2 s after the raw fault, due by 1145 | C8, C5 records | 23:53 |
| F-17 | D4 full sequence | 60 s | 1 step needed at minute 19, applied tick 1142, due by 1200 | C5 records | 23:42 |
| F-18 | D5 Crew as a setting | none in A.8 (ours: 2 s) | 0.2 to 0.3 ms alone | C8 | 23:53 |
| F-19 | D6 Physical Account | none | 21 rows, 61 assumed and 2 measured keys, 6 cards | C18 | 23:51 |
| F-20 | Safety command (stop, hold, secure) | 200 ms | 0.006 to 0.049 ms over 24 answers, alone (0.012 to 0.099 with the suite). Verdicts: sent, not needed, cannot | C9 | 23:54 |
| F-21 | Whole tick (estimator and every decision) | none (a tick is 1 s) | worst 1.6 to 1.8 ms over 1201 ticks, alone (5.9 to 12.5 with the suite) | C8 | 23:53 |
| F-104 | Time on screen | each decision's time against its own limit, NORMAL or LATE | the RESPONSE tile and each record's RESPONSE row, `src/sdv/ui/view.py:364-376`, `:438-439`, `:489-490` | C19 | 23:58 |

## 4. Scenario A: admission in port

Same verdicts with the suite running and alone, and on fix/scenario-b-loadout-g1 (C4). Times are the alone run, 23:53.

| ID | Case: card onto | File | Verdict | Binding line | Top yes-if | One genset down | Time | Check |
|---|---|---|---|---|---|---|---|---|
| F-22 | A1: G4 onto G1, G2, G3 | survey | YES-IF | mass 10.035 / 10 t, 35 kg over | G1 off, value lost 0.2 | 81.5 / 100 kW, fits | 2.8 ms | C3 |
| F-23 | A1 | sar | YES-IF | same | G3 off, 0.2 | fits | 1.7 ms | C3 |
| F-24 | A2: G1 onto G2, G3, G4 | survey | YES-IF | mass 10.035 / 10 t | G4 off, 0.2 | fits | 2.5 ms | C3 |
| F-25 | A2 | sar | YES-IF | same | G3 off, 0.2 | fits | 2.4 ms | C3 |
| F-26 | A3: G5 onto G2, G3, G4 | survey | YES-IF | mass 13.015 / 10 t. Also over: stability 13.263 / 12, cooling 125 / 120 kW | G2 off, 1.0 | 125 / 100, holds by throttling | 7.4 ms | C3 |
| F-27 | A3 | sar | YES-IF | same | G3 off, 0.2 | holds by throttling | 6.8 ms | C3 |
| F-28 | A4: G3 onto G1, G2, G5 | survey | YES-IF | mass 12.07 / 10 t. Also over: stability 12.165 / 12 | G5 off, 0.2 | 91.5 / 100, fits | 3.7 ms | C3 |
| F-29 | A4 | sar | YES-IF | same | G2 off and G5's node to Bay 2, 0.5 | fits | 4.1 ms | C3 |
| F-30 | A5: G4 onto G1, G2, G5 | survey | YES | cooling 100 / 120 kW, 20 spare | none | 101.5 over the 95 gate, holds with G4 fast charge to charge (25 kW) | 2.7 ms | C3 |
| F-31 | A5 | sar | YES | same | none | holds with G2 winch to sampling (14 kW) | 1.9 ms | C3 |
| F-32 | A6: A1 with G4's hangar at 0.8 t | both | YES | mass 9.985 / 10 t, 15 kg spare | none | fits | 0.9 ms | C3 |
| F-33 | A7: G6 (ours) onto G4, G5 | disaster relief | YES | cooling 98 / 120 kW, 22 spare | none | 98 over the gate, holds with G4 fast charge to charge | 1.6 ms | C3 |
| F-34 | A7 | sar | YES | same | none | holds with G6 production to recirculate (14 kW) | 1.1 ms | C3 |

| ID | Fact | Value | Verified by | When |
|---|---|---|---|---|
| F-35 | Seawater tipping point | A3 flips at 27.75 °C. A1, A2, A6 at 48 °C. A4 at 43.5 °C. A5 at 39 °C. A7 at 39.9 °C | C3 `SEAWATER TIP` | 23:53 |
| F-36 | How the binding line is picked | the most over, as a share of capacity. The others are listed as also over | C3 (A3, A4), `src/sdv/admission.py` | 23:53 |

The jury's one-number edit (all A1's set unless named):

| ID | Edit (`--set`) | Result | Verified by | When |
|---|---|---|---|---|
| F-37 | `G4.hangar.mass_t=0.8` | "card re-validated", YES-IF becomes YES, 0.9 ms | C3 | 23:53 |
| F-38 | `G4.hangar.mass_t=heavy` | refused, "'heavy' is not a number. Previous card kept.", exit 2 | C3 | 23:53 |
| F-39 | `G4.hangar.colour=red`, `G4.hangar.foo=1` | refused, "'red' is not a number", and "no field hangar.foo on the card. Previous card kept.", exit 2 | C3 | 23:53, 23:58 |
| F-40 | `G4.hangar.mass_t=10` | NO: mass 19.185 / 10 t, "No removal set fits", 2.0 ms | C3 | 23:53 |
| F-41 | `G5.consumes.data_satcom_mbps.min=50`, onto G1, G2 | NO, "SATCOM binds: 50.2 Mbit/s against 2 Mbit/s, 48.2 Mbit/s over", 1.2 ms | C3 | 23:53 |
| F-42 | a kW edit: `G5.consumes.power_kw.nominal=60` onto G2, G3, G4, and `G4.consumes.power_kw.peak=50` | decides, no crash. G5 at 60 kW: YES-IF on mass, one genset down 140 / 100 kW holds by throttling (G4 frees 25, G5 52), tip 21 °C, 5.1 ms. G4 peak 50: YES-IF, 96.5 / 100 kW holds by throttling, 1.6 ms | C3 | 23:53 |
| F-105 | a new card as a file: `sdv admit --card G7.yaml --installed G4,G5 --mission disaster_relief` (G6 copied as G7) | "card validated", "G7 activities not registered: conditions not judged (2 on the card)", YES, cooling 98 / 120 kW, 1.2 ms. A broken file: refused with the field named, exit 2. A stray G7.yaml in manifests/: "refused manifests/G7.yaml ...", and admission still runs | C20 | 23:54 |
| F-106 | Edits on screen | each part's mass_t, and NOMINAL and PEAK kW (`src/sdv/ui/static/js/admit.js:114-122`). Any other field on the CLI with `--set` | C19 | 23:58 |
| F-107 | Mistyped field path | `G4.nope.x=1`: refused, "no field nope.x on the card. Previous card kept.", exit 2 | C3 | 23:53 |

## 5. Scenario B: minutes 8, 12 and 19, both files

| ID | Moment | Survey file | Rescue file (sar) | Verified by | When |
|---|---|---|---|---|---|
| F-108 | Load-out | G3, G4, G5: 9.515 t, stability 9.763 t-eq (now, since the load-out reached main at 7b9a804: G1, G3, G4, G5, 9.56 t, stability 9.853 t-eq, G1 air-cooled on the mast). The brief's G2 to G5 is 13.015 t (F-26) | same | C8 `run.installed`, `sdv admit G3 --installed G4,G5`, C4 | 23:43, 23:58 |
| F-43 | Min 8, D3 | G4 recovers first: below 20 % it must land within 12 min, by minute 18.2 | same | C5, C7 | 23:42, 23:44 |
| F-44 | Min 8, cost to the loser | G3 holds depth, loses 25 to 27 survey minutes | G3's leg aborted, at least 25 to 27 minutes, no resume time. G4's 35 kW charge reserved | C5, C7 | 23:42, 23:44 |
| F-45 | Min 8, D5 at 14 aboard | bridge asked to confirm, cleared at minute 9 | same | C5, C7 | 23:42, 23:44 |
| F-46 | G4 lands | tick 1020, minute 17.0, 1.2 min inside 18.2 | same | C8, also on C7 | 23:43 |
| F-47 | Min 12, genset trip (raw 720 s, confirmed 721 s) | holds: 48 of 95 kW, 0 steps (now, since the load-out reached main at 7b9a804: 49.5 of 95 on the bus, 48 on the loop) | holds: 81 of 95 kW, 0 steps (now, since the load-out reached main at 7b9a804: 82.5 of 95, 81 on the loop) | C5, C7 | 23:42, 23:44 |
| F-48 | Min 12, first armed step | G5 full to low power, frees 37 kW | same | C5, C7 | 23:42, 23:44 |
| F-49 | Min 12 sentence | the full armed order, and "the envelope case does not arise": 105 kW against 95 (now, since the load-out reached main at 7b9a804: 106.5 kW with G1 full 1.5 kW, and the ladder adds G1 full to off, frees 1.5 kW, 100 % lost) | same | C5, C7 | 23:42, 23:44 |
| F-50 | Min 19, injected pump fault | cooling binds, 81 kW against 75. G4 fast charge to charge, 56 kW. G4 loses 30 % | cooling binds, 81 against 75. G5 to low power, 44 kW. G5 loses 70 % | C5, C7 (same steps and results on the branch, plus "G1 ... nothing") | 23:42, 23:44 |
| F-51 | Min 19 timing | raw 1140 s, confirmed 1141, applied 1142. Due 1145 (5 s) and 1200 (60 s) | same | C8 | 23:43 |
| F-52 | Min 19, two limits at once | power 100 kW (genset still down), cooling 80 kW (pump down). One limit: min(100, 80) minus 5 = 75 kW, against 81 kW (now, since the load-out reached main at 7b9a804: each line on its own, power limit 95 against the bus at 82.5, cooling limit 75 against the loop at 81, so cooling binds) | same | C8, tick 1141 | 23:43 |
| F-53 | Min 19 with no pump loss | limit stays 95 kW against 81 kW: nothing shed (now, since the load-out reached main at 7b9a804: bus 82.5 of 95, loop 81 of 128.3, nothing shed) | same | from F-47, F-50, C8 capacity at tick 721 | 23:43 |
| F-54 | Decisions per run | 6 records: D3, D5 x 2, D4 x 3 (hold 12:01, shed 19:01, hold 19:02) | same | C6, C7 | 23:42, 23:44 |

## 6. Replay, determinism and the standby

| ID | Fact | Value | Verified by | When |
|---|---|---|---|---|
| F-55 | Replay of a logged run | "REPLAY EQUAL 1201 snapshots, 6 records, byte for byte", survey and sar, also on fix/scenario-b-loadout-g1 | C6, C7 | 23:42, 23:44, 23:53 |
| F-56 | Standby in lockstep | 1201 of 1201 ticks "in step", survey and sar. Still in step after an edited profile at tick 1100 (weights 0.45 and 0.35). Built as a second estimator and core in the same process (`Loop(standby=True)`, `src/sdv/loop.py:88-90`) | C9, C12 | 23:54 |
| F-57 | Logs per run | frames, inputs, snapshots, decisions, timing | C5 | 23:42 |
| F-58 | Wall clock in records | none: latency goes only to `timing.jsonl` | C6 (byte-equal replay), C8 | 23:42 |
| F-59 | Network calls or randomness in `src/sdv` | none found | C19 | 23:58 |
| F-109 | The screen's runs are logged | `sdv demo` prints "RUN 1 under survey.yaml logs to .../live-survey-1" and its replay command. That run replayed EQUAL (30 ticks). Full length: `test_a_live_run_is_logged_and_sdv_replay_reports_equal`, in C13. A RESTART or a JUMP back starts a new numbered run | C25, C13 | 00:00 Sun |
| F-110 | Standby after a dropped guest-meter feed | "out of step at tick 1133" (`G4.kw_actual.since_t_s`). In step (on branch fix/review-ours, not on main yet) | C12 | 23:54, 23:55 |

## 7. Tests

| ID | Fact | Value | Verified by | When |
|---|---|---|---|---|
| F-60 | Test suite on main `4c4f93c` | 1476 tests, all pass. This branch: 1492 passed in 510.96 s, which is main's 1476 plus the 16 map tests from `5f09b6c`. The other test files equal main's | C13, C14 | 23:39 to 23:49 |
| F-61 | Test suite on fix/scenario-b-loadout-g1 | 1485 collected, main's 1476 plus 9 (now, since the load-out reached main at 7b9a804: 1485 on main). Siddharth's review logs 1485 green | C14, its WORKLOG | 23:58 |
| F-62 | Known flaky test | `tests/test_ui_server.py::test_ws_streams_the_live_loop_and_takes_laptop_inputs` fails in some full runs and passes alone (docs/HANDOFF_SIDDHARTH.md, on branch fix/review-ours, not on main yet). It passed in C13 | C13 | 23:47 |
| F-63 | Tests for tonight's fixes: jury edits, jury card file, crew levels | 150, all in the 1476 | C14 | 23:58 |
| F-64 | Hostile inputs in `tests/test_loader.py` | 15 cards, 8 priority files, each refused with the field named | C14 | 23:58 |
| F-111 | Logan's hardening tests | 10 in `tests/test_review_fixes.py`, all pass (on branch fix/review-ours, not on main yet) | C16 | 23:56 |

## 8. Response classes (docs/RESPONSE_TIME.md)

| ID | Fact | Value | Verified by | When |
|---|---|---|---|---|
| F-65 | The brief's limits in config | admission 30 s, placement 30, arbitration 2, first shed 5, full sequence 60, safety 0.2 | C19, `config/assumptions.yaml:67-73` | 23:58 |
| F-66 | Tags | 200 MS, 5 S, 60 S, 30 S, 2 S, formatted from those numbers | C19, `test_the_tags_come_from_the_brief_numbers` in C13 | 23:58 |
| F-67 | Who is 60 S (gives power last) | survey: G3. sar: G4. patrol: G1. disaster relief: G5, G6 | C19 | 23:58 |
| F-68 | Everyone else | 5 S (gives power first) | C19 | 23:58 |
| F-69 | 200 MS guests by default | none: no card is safety-critical, as the brief says. A 200 MS guest is never on a ladder (`test_a_200_ms_guest_is_never_on_either_ladder`) | C19, C13 | 23:58 |
| F-70 | Order | every 5 S step before any 60 S step. Slow down before switching off | `test_d4_takes_every_5_s_step_before_any_60_s_step` in C13, both minute-19 steps slow a guest down (F-50) | 23:47 |
| F-112 | MET and MISSED words | not computed anywhere. Records carry due ticks, the screen shows NORMAL or LATE (F-104). docs/RESPONSE_TIME.md on main still lists MET and MISSED as record words. Corrected (on branch docs/review-fixes, not on main yet) | C19 | 23:58 |

## 9. Governor hardware plan (docs/DEPLOYMENT.md)

| ID | Fact | Value | Verified by | When |
|---|---|---|---|---|
| F-71 | Boards on the 60 m hull | 4: primary (bridge), standby (engine control room), 2 zone boards (forward equipment room, hangar) | C15 | 23:46 |
| F-72 | Board rule | 2 + ceil((LOA - 25) / 25): 25 m 2, 40 m 3, 50 m 3, 51 m 4, 60 m 4, 70 m 4, 76 m 5, 100 m 5 | C19, `src/sdv/kit.py:37-41` | 23:58 |
| F-73 | Board in config | VENTUNO Q, 8 cores, 14 GB RAM, 55 GB | C19, `config/assumptions.yaml:116` | 23:58 |
| F-74 | Edge nodes | 6, Pi 5 class, 8 GB RAM, 64 GB each: engine control room, chilled-water plant, bridge, hangar and flight deck, stern ramp, mission bays. Design only: local monitoring and the latest shed table. No code holds or pushes a shed table | C15, C19 | 23:46, 23:58 |
| F-75 | Offline copies | 2 SSDs of 1000 GB (bridge, engine control room), 1 printed binder | C15 | 23:46 |
| F-76 | Heartbeat, takeover | 1 s, 3 s, in config only (`config/assumptions.yaml:120-121`). No code takes over. docs/DEPLOYMENT.md on main states the takeover with no design label. Marked Design (on branch docs/review-fixes, not on main yet) | C19 | 23:58 |
| F-77 | Reference Kit | 30 files, 0.27 MB, stamped with its commit. Every device holds all of it. "VERIFIED every file against the manifest". Install goes to the idle slot (slot_a, then slot_b), rollback returns to slot_a | C15 | 23:46, 00:07 Sun |
| F-78 | Kit share per device | 20 GB of a board, 8 GB of an edge node | C19, `config/assumptions.yaml:130` | 23:58 |
| F-113 | Kit build into a used folder | on main it replaces the folder (a file in it was deleted). "REFUSED ... holds files and is not a kit", exit 1, and install checks a staging copy before it touches a slot (on branch fix/review-ours, not on main yet) | C16 | 23:56 |
| F-114 | The board tonight | not connected: `adb devices` lists none | C23 | 23:55 |

## 10. Deployment map (on branch feat/deployment-map, not on main yet)

Every row in this section is from feat/deployment-map `b1926e3` (C17). This branch still carries the older `5f09b6c` copy of the tool: do not use its numbers.

| ID | Fact | Value | Verified by | When |
|---|---|---|---|---|
| F-79 | Route | Strait of Sicily cable-survey plan (Siddharth's), Mazara del Vallo to Kelibia and back: 4 waypoints, 191.4 km | C17 `deployment.json` | 23:40 |
| F-80 | Period | 1 to 15 Oct 2026, 14 days (A.10) | C17 | 23:40 |
| F-81 | Data | 337 route hours, 1080 area hours at 3 grid points. 400 seeded samples (seed 0, 10 km either side) draw the dots and count the windows | C17 | 23:40 |
| F-82 | Seawater | route P90 25.8 °C, route max 26.0 °C, area max 27.2 °C | C17 | 23:40 |
| F-83 | Gust | route P90 24.5 kn, max 32.3 kn (area, route max 32.2) | C17 | 23:40 |
| F-84 | Sea state (Douglas, corrected scale) | route P90 4, route max 4, area max 5 | C17 | 23:40 |
| F-85 | Weather windows open | G2 probe 100 %, G3 launch and recovery 100 %, G4 launch and recovery 89 % | C17 | 23:40 |
| F-86 | Cooling | load-out heat 105 kW. Loop 129.3 kW at route P90, 128.9 kW at route max, 77.4 kW with one pump down, 120 kW at the 30 °C brief envelope | C17 | 23:40 |
| F-87 | Verdict per profile | D1 admits all four profiles at 30 °C and at route seawater. Mass binds, 9.515 / 10 t. The map's load-out is its own setting, G3, G4, G5 (`tools/deploy_map/config.yaml`) | C17 | 23:40 |
| F-88 | Weather source | Open-Meteo Marine API (sea temperature, waves) and Archive API (wind, gusts), CC BY 4.0, fetched 2026-10-17T22:49Z | C17 cache file | 23:40 |

## 11. Physical Account (docs/PHYSICAL_ACCOUNT.md)

| ID | Fact | Value | Verified by | When |
|---|---|---|---|---|
| F-89 | Size | 21 rows. 61 assumed and 2 measured keys. 6 cards | C18 | 23:51 |
| F-90 | How it is made | generated from `config/assumptions.yaml` and the cards: each key's source, reason, and where code reads it | C18 | 23:51 |
| F-91 | Keys no code reads yet | 12 "documented only" | C18 detail page | 23:51 |
| F-92 | Closing answer | one standby chilled-water pump. Then minute 19 sheds nothing (F-53) | C18 one-page | 23:51 |
| F-115 | Page count | the committed PDF is 1 page, built Sat 14:59 PDT from an older page. A rebuild from main gives 2 pages on Letter and on A4 (limit 1). The committed one-page is 3 "Used in" cells behind a fresh run | C18 | 23:51 |

## 12. Data, licences, AI

| ID | Fact | Value | Verified by | When |
|---|---|---|---|---|
| F-93 | Python packages | 27 installed, all MIT, BSD, Apache-2.0 or PSF: 26 third-party plus ours | C19, package metadata | 23:58 |
| F-94 | Our code | MIT. `LICENSE` names Siddharth only (audit gap 28) | `head LICENSE` | 23:58 |
| F-95 | Ship and guest numbers | the brief's Annex A and B, plus our labelled assumptions | C18 | 23:51 |
| F-96 | Public data | Open-Meteo, in the deployment map only. Natural Earth coastlines, public domain (on branch feat/deployment-map, not on main yet) | C17 | 23:40 |
| F-97 | AI used | Claude (Anthropic) only, declared in `docs/SOFTWARE_LOG.md:26-27` | file | 23:58 |

## 13. Crew levels: D5, rule R3, Scenario B minute 8 (docs/SCENARIO_C_MEMO.md)

| ID | Crew aboard | What the record says | Verified by | When |
|---|---|---|---|---|
| F-98 | 14, bridge answers | "Bridge asked to confirm G4's recovery at 14 aboard" at 08:00. "Recovery cleared at 14 aboard: the bridge confirmed at minute 9" at 09:00 | C5 | 23:42 |
| F-99 | 14, nobody answers | "Recovery held at 14 aboard: no answer from the bridge", 09:01 | C11 `--no-script` | 23:53 |
| F-100 | 0 from launch, deck swept clear | "Recovery automatic at 0 aboard: platform deck state latched at the last crew sweep", 08:00. Same with and without the scripted answer | C11 `--variant crew0` | 23:53 |
| F-101 | 6 from tick 100, no standing plan | "Recovery held at 6 aboard: no standing plan approved. G4 must land by minute 18.2." | C10 | 23:48 |
| F-102 | 0 from tick 100, no sweep | "Recovery forbidden at 0 aboard: no crew sweep is known, the deck is not latched clear. G4 ditches by minute 18.2." | C10 | 23:48 |
| F-103 | 6 or 0 with the scripted bridge answer | no crash: both run to tick 1200, standby in step. The screen's crew chip sends this same input (`src/sdv/ui/static/js/app.js:106`) | C10 | 23:48 |

## 14. Demo commands checked (docs/DEMO_SCRIPT.md, docs/DEMO_READINESS.md)

| Command or line | Result on main `4c4f93c` | Verified by |
|---|---|---|
| `uv run sdv demo` | "ArgOS screen on http://127.0.0.1:8461/ (live)", a LOGS and a RUN line, `/api/meta` 200 within 1 s, `/ws` streams | C25 |
| `--port`, `--source fixtures`, `--log-dir` | in `sdv demo --help` | C2 |
| `uv run sdv replay runs/live/live-<file>-<n> --mission <file>` | EQUAL on a logged screen run | C25 |
| `uv run sdv run --mission sar --pace 12` | flags exist, the run checked unpaced (F-54) | C2, C5 |
| `uv run sdv admit --card path.yaml --installed G4,G5 --mission disaster_relief` | works (F-105) | C20 |
| T-30 step 3, "1278 passed or more" | 1476 on main | C13 |
| Status table in DEMO_READINESS (23:10, `6a91f5d`) | stale: fix/jury-card-file and fix/simbar-clicks are both on main `4c4f93c` | C24 |
| T-30 step 1 in DEMO_READINESS | names `918478a`. No tag on origin (0 tags) | C24 |
| Presenter rules "until fix/simbar-clicks ..." and "until fix/jury-card-file ..." | these fall away on `4c4f93c` | C24 |

## Do not claim

Not built, or partial. Sources: Siddharth's audit (`docs/AUDIT_MAIN.md`, section 4, "Declare as limitations"), docs/HANDOFF_SIDDHARTH.md (on branch fix/review-ours, not on main yet), and the commands above.

| ID | Do not say | Say instead | Source |
|---|---|---|---|
| X-01 | "not now, and when" (A′), installation windows (A.11) | D1 answers for a ship alongside: yes, yes-if or no | audit, C19 (no not-now in `admission.py`, no `card_presented` laptop input) |
| X-02 | absolute excludes and `requires` in admission | schema and D3 data, not D1 logic | audit, C19 |
| X-03 | over-consumption detected and handled | the estimator derives `overdraw_pct`. No decision module reads it | audit, C19 |
| X-04 | D2 maximises remaining margin, shows rejected alternatives | D2 is a fixed order of rules. No D2 record | audit, C19 |
| X-05 | D3 settles any two guests | one contention, G4 recovery against G3 survey, triggered by a hard limit | audit, `src/sdv/arbitration.py:99-103` |
| X-06 | the -40 % loop at 30 °C is in the verdict | an information line on the Admission screen (DEC-36) | audit |
| X-07 | minute 12 sheds | holds by design, armed ladder shown (DEC-40, DEC-61). Minute 19 sheds | audit, F-47 |
| X-08 | a ship-physics simulator | a scripted, labelled test double. `SDV_SIM` swaps one in. feat/ship-state-fsm is not on main | audit, C24 |
| X-10 | drop any priority file in | loaded by id. A bad file on disk stops `sdv admit` with a traceback that names the field (exit 1). A bad profile at sea is refused | C21 |
| X-11 | Scenario B runs on real weather | the brief's 24 °C. Open-Meteo only in the standalone map (on branch feat/deployment-map, not on main yet) | audit, C17 |
| X-12 | every Physical Account number is read by code | 12 keys documented only (F-91) | C18 |
| X-13 | the authorised-AI list is cited | its source is still pending (`docs/SOFTWARE_LOG.md:18-19`) | file |
| X-16 | board measurements: watts, latency per class | planned. The board was not connected tonight (F-114) | `docs/NODE_B_BOARD.md`, C23 |
| X-17 | automatic takeover by the standby board, 3 s failover | design only. The standby runs in the same process and is compared every tick (F-56) | C19, F-76 |
| X-18 | MET, MISSED or DUE verdicts per step | not computed. Records carry due ticks. The screen shows NORMAL or LATE against each decision's limit (F-104) | C19, F-112 |
| X-20 | the deployment map is part of the ArgOS screen | standalone tool (on branch feat/deployment-map, not on main yet) | C17 |
| X-22 | certified, or cyber-secure | out of scope by the brief | C22 |
| X-24 | edge nodes hold the shed table | design only. Nothing builds, pushes or reads a shed table | C19, F-74 |
| X-25 | D4 never sheds on a stale feed | a stale plant feed blocks the shed: "Not shed ... not confirmed". But a dropped guest-meter feed makes D4 shed on the fallback draw, 17 times, ticks 1133 to 1149. And a dropped PMS feed holds the shed to tick 1175, past its 1145 due tick | C12, handoff #1 and #2 (Siddharth's) |
| X-26 | the standby stays in step on any input | in step on both runs and on an edited profile (F-56). Out of step on main after a dropped guest-meter feed (F-110) | C12 |
| X-27 | a 200 ms safety request from the screen | the engine answers it in under 0.05 ms (F-20). No screen control sends one | `src/sdv/ui/live.py:20`, handoff #15 |
| X-28 | the landing officer's report, the deck sweep or a standing plan from the screen | the crew chip (14, 6, 0) is the only crew control on screen. The engine takes the others as laptop inputs, no button sends them | `src/sdv/ui/live.py:20`, C19 |
| X-29 | the Physical Account fits one page | the committed PDF is 1 page from an older build. A rebuild gives 2 (F-115) | C18 |
| X-30 | a tagged submission | no tag on origin tonight | C24 |
| X-31 | the kit is filtered by the port's admission decisions, or rebuilt aboard for a guest swapped at sea | the kit covers every card in `manifests/`, built ashore by `sdv kit build` | docs/review-fixes `docs/DEPLOYMENT.md` (on branch docs/review-fixes, not on main yet) |

Fixed on main since the first pass. These may now be claimed, with the fact named:

| Old ID | Was | Now | Fact |
|---|---|---|---|
| X-09 | a kW edit crashes D1 | any card number decides or is refused with the field named | F-42, F-107 |
| X-14 | data links and compute missing from D1 on `5f09b6c` | 14 lines on main, SATCOM binds when over | F-08, F-41 |
| X-15 | `sdv run --variant crew0` crashes on the scripted answer | runs, "Recovery automatic at 0 aboard" | F-100 |
| X-19 | the run the jury watched cannot be replayed | every screen run is logged and replays | F-109 |
| X-21 | 1 UI test fails on `5f09b6c` | 1476 pass on main, one known flaky test passed | F-60, F-62 |
| X-23 | crew to 6 or 0 live crashes the loop | held or forbidden with its reason, no crash | F-101 to F-103 |
