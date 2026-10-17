# Build plan

Status: Sat 12:35 PDT, rewritten to the design freeze (WORKLOG DEC-44) and the work split (DEC-47) by Claude
Opus 5.5 on behalf of Logan Walker (GhostWalka). The task order follows the freeze's build order. The
milestone times are a proposal: Logan and Siddharth confirm them, which closes CON-10 and CON-17.

Every task has a pass check taken from the brief's numbers or from the oracles, so "done" is never a matter
of opinion. Expected verdicts, numbers and ladders for every Scenario A drill and the Scenario B moments are
in [EXPECTED_OUTCOMES.md](EXPECTED_OUTCOMES.md) and `tests/oracles/expected_outcomes.yaml`, already checked
against the cards. Components and contracts: [ARCHITECTURE.md](ARCHITECTURE.md).

## Milestones (proposed)

| Milestone | Target (PDT) | Pass check | If late |
|---|---|---|---|
| S1 Contracts | Sat 14:00 | T15, T16, T17 pass; the snapshot and command contract is agreed, which closes CON-21 | the ledger (T1) starts at 14:00 on the draft snapshot fields; it needs no typed conditions |
| S2 Ledger | Sat 16:00 | T1 and T18 pass | drop A′ installation windows |
| M1 Scenario A | Sat 18:30 | T2 and T3 pass: A1 to A7 from the engine within 30 s | Admission review falls back to the D1 record in Operations |
| M2 Scenario B | Sat 22:30 | T4 to T7 and T19 pass under both priority files | keep survey and rescue; drop patrol and disaster relief from the demo |
| M3 Screen | Sun 01:30 | T8, T20, T21 pass | Mission compare falls back to the priority swap on one run |
| M4 Replay and breadth | Sun 03:00 | T22 passes; T9, T11 and T25 work live or replayed and are labelled so | breadth lines replayed, not live |
| Rest | Sun 03:00-06:30 | | |
| M5 Docs | Sun 08:00 | T23 and T14 pass | |
| Freeze | Sun 09:15 | five rehearsals done; backup recording made; submission checklist below | |

**Done means:** a hostile priority file is refused with the expected errors; the two priority files give
the two Scenario B outcomes; A3 names mass as binding and lists cooling at 30 °C as also failing; N replays
give decision logs that match on every field except wall-clock latency and timestamps; every sentence is
filled from a template over record fields; Annex C is generated, not typed.

**Submission checklist** (freeze): (1) all work merged into main, including the simulator; (2) repo
visibility or jury access confirmed; (3) a `submission` tag on the submitted commit; (4) memo and Physical
Account PDFs committed at `docs/pdf/SCENARIO_C_MEMO.pdf` and `docs/pdf/PHYSICAL_ACCOUNT.pdf`; (5) the one
documented command smoke-tested from a fresh clone with the network off; (6) `uv run python
tools/build_pdfs.py` reports every page limit met.

## Tasks

Owners follow DEC-47: Siddharth builds the simulator, owns the ship-state machine and its transition times,
and defines the commands the core sends. Logan, with Claude, builds the rest. A blank owner is not yet
assigned. Task IDs are stable: T1 to T14 keep their numbers, T12 and T13 are cut, and T15 onward are new.

### Stage 1: typed conditions and the snapshot contract

| # | Task | Owner | Closes | Pass check | After |
|---|---|---|---|---|---|
| T15 | Typed conditions and hard limits (F2): the vocabulary in `manifests/schema.json`, values from `assumptions.yaml`; one canonical name per activity across the six cards. Time box 90 min | Logan | R-122, R-250, R-341 | a card with an unknown signal, value or activity name is refused with the field named; G2, G3 and G4 use one name for G4's recovery; the existing card tests still pass | |
| T16 | Snapshot and command contract (CON-21): 1 Hz snapshot fields in ship time, each input with source and age; the command set; the event types | Logan (snapshot), Siddharth (commands) | R-269, R-505, R-506 | a sample snapshot and a sample command list validate against the published schemas; both sides confirm in WORKLOG | |
| T17 | Loader: names checked across cards, priority files and the scenario; the optional `shed_order` and per-rule `confirm` fields (F3) validated | Logan | R-137, R-152, R-274 | a hostile priority file is refused with the failing field and the previous file keeps running; a file with `confirm` at 0 aboard is refused (A.6) | T15 |

### Stage 2: ledger with the ladder core

| # | Task | Owner | Closes | Pass check | After |
|---|---|---|---|---|---|
| T1 | Ledger and platform model: capacity, committed, free and degraded per class from `config/assumptions.yaml` and the cards, under conditions (seawater, gensets, cooling, speed, emission) | Logan | R-040, R-043, R-269, R-554 | reproduces the brief's checks already in `tests/`: 126.5 kW at cruise fits 200; 105 kW against 100 with one genset down; cooling 120 kW at 30 °C, 72 kW degraded; three of five sets of four over 10 t | T16 |
| T18 | Ladder core: price list and throttle-only prefix from the cards' modes and the priority file. Precedence: safety-critical never shed and hard limits first, throttle before shed, then `shed_order` if present, then the computed price | Logan | R-034, R-117, R-119 | reproduces the oracle's survey and rescue price lists; a test file with `shed_order` changes the order and the record says "declared" | T1 |

### Stage 3: Scenario A

| # | Task | Owner | Closes | Pass check | After |
|---|---|---|---|---|---|
| T2 | D1 admission with D2 placement, by enumeration, and the envelope sweep | Logan | R-064, R-065, R-069, R-100 to R-109 | A1 to A7 match the oracle; A3 names mass as binding (13.015 against 10 t) and lists cooling at 30 °C (125 of 120 kW) as also failing; the one-genset-down line uses T18's throttle prefix (DEC-35); yes-if lists are ranked by the active file; the seawater tipping point is reported. The D2 mast rule is written first (CON-18) | T1, T18 |
| T3 | Decision record, explainer and the `sdv` command | Logan | R-016, R-017, R-151, R-227 | `uv run sdv admit G4 --installed G1,G2,G3` prints the verdict and a template-filled sentence from the real engine; its latency goes to the timing log against the 30 s ceiling | T2 |

### Stage 4: D3 and D4 with the simulator

| # | Task | Owner | Closes | Pass check | After |
|---|---|---|---|---|---|
| T4 | Simulator and ship-state machine: seeded, 1 Hz tick in ship time, the event timeline as data, A.6 transition times; faults debounced and confirmed (genset trip on 2 of 3 signals; cooling on the plant alarm plus flow or delta-T); acoustic link up only while the course is steady, the noise quiet and no deck machinery runs, with an assumed drop delay; applies the core's commands | Siddharth | R-221, R-504, R-505, R-506, R-522 | the Scenario B timeline runs end to end and every snapshot validates against T16; each fault carries its raw-event and confirmation times; two runs with the same seed give the same snapshots | T16 |
| T5 | D3 right of way | Logan | R-066, R-110 to R-113 | minute 8 is decided within 2 s; the drone's 12-minute limit is named first; the sentence states the cost to the loser in minutes; the two files give different decisions; under rescue G3's leg is aborted, it holds at sea and is recovered over the ramp only after G4 has landed | T3, T4 |
| T6 | D4 shedding, precomputed every tick, run on a confirmed fault | Logan | R-067, R-114 to R-119 | minute 12 holds with 0 steps: survey 48 of 95 kW, rescue 81 of 95; the first armed step is G5 full to low power in both (frees 37 kW; 0.0038 per kW under survey, 0.0189 under rescue). Minute 19, INJECTED pump fault: first action within 5 s of the raw event, full sequence within 60 s; survey G4 35 to 10 kW (56 kW), rescue G5 45 to 8 kW (44 kW); every guest's loss stated | T4, T18 |
| T19 | Safety-command table (200 ms, A.8), rebuilt every tick next to the ladder | Logan | R-316 | R3's hold of landing clearance and G3's hold depth go out within 200 ms of the event, wall clock, as the timing log shows | T6 |
| T7 | Priority-file swap | Logan | R-136, R-152 | a swap mid-run re-decides the same event under the new file; two runs on one timeline give the two Scenario B outcomes | T5, T6, T17 |

### Stage 5: the screen

| # | Task | Owner | Closes | Pass check | After |
|---|---|---|---|---|---|
| T8 | Operations view: schematic, eight gauges, ship-state row, event log with decisions and rationales; the constraint ledger as its drill-down | Logan | R-146, R-218, R-507 | Scenario B runs end to end on screen within 90 s; every sentence on screen comes from a decision record; each decision shows its latency against its ceiling | T5 to T7 |
| T20 | Mission compare view: two runs on one timeline | Logan | R-136 | survey and rescue run side by side on one clock, with the differences marked | T8 |
| T21 | Admission review view: the jury's card and its one-number edit | Logan | R-152, R-064 | an edited number goes through the loader and D1 and gives a new verdict within 30 s | T3, T8 |

### Stage 6: replay, then breadth

| # | Task | Owner | Closes | Pass check | After |
|---|---|---|---|---|---|
| T22 | Replay and timing log | Logan | R-086, R-155, R-448 | N replays of Scenario B give decision logs identical on every field except wall-clock latency and timestamps, which are in the timing log; `inputs_hash` covers the timeline, assumptions, cards and priority file | T8 |
| T9 | Over-consuming guest | Logan (the simulator emits the draw) | R-082, R-083 | G5 drawing 15 % over its declaration is detected and throttled with a sentence | T6 |
| T10 | Public data for cooling and deck | Logan | R-080, R-081 | cached Sicily seawater and wind drive the cooling and flight-deck limits offline | T4 |
| T11 | Rule R3 at 14, 6 and 0 aboard, with the landing zone not clear | Logan | R-037, R-084, R-085, R-274 | at 14 the landing officer reports the deck and the bridge confirms; at 6 the standing plan approved at launch applies; at 0 recovery is allowed only if the deck was latched clear at the last crew sweep with no deck activity since, otherwise it is forbidden and the record states the cost under G4's hard limit; a "not clear" report holds recovery | T5, T19 |
| T25 | Data feed drops | Logan | R-458 | a feed older than its limit falls to its conservative value, the record says so in one sentence, and decisions continue | T6 |
| T26 | Emission silence line | Logan | R-390, R-477, R-483 | waits on [OPEN_QUESTIONS](OPEN_QUESTIONS.md) #42 | T5 |

### Stage 7: docs

| # | Task | Owner | Closes | Pass check | After |
|---|---|---|---|---|---|
| T23 | Docs pass against the built engine: README (with two sentences on prior art), memo, Physical Account, demo script | Logan | R-019, R-025, R-405 | every "planned" claim is built or removed; the Physical Account is regenerated | T22 |
| T14 | Final PDFs | | R-019 to R-024, R-025, R-552 | `uv run python tools/build_pdfs.py` builds all three into `docs/pdf/` on US Letter and A4 and reports README 3 pages or fewer, memo 2, Physical Account 1 | T23 |

### Optional

| # | Task | Owner | Closes | Pass check | After |
|---|---|---|---|---|---|
| T24 | Board instrument ([NODE_B_BOARD.md](NODE_B_BOARD.md)) | | R-313, R-314, R-405 | the VENTUNO Q runs the same container, replays Scenarios A and B, and reports watts, latency per decision class and CPU share against A.7 into the Physical Account; the demo runs unchanged with the board unplugged | T22 |

**Cut by DEC-44:** T12 (two nodes, wired and Wi-Fi, failover by replay) and T13 (camera leak line).

**Organizers:** Logan sent the message in [ORGANIZER_MESSAGE.md](ORGANIZER_MESSAGE.md) (DEC-49). There is
no organizer simulator, so T4 is ours. Minute 12 is Siddharth's call as owner of the scenario timing
(DEC-51); T6's pass check follows DEC-40 until he changes it.

Parallel tracks: Siddharth's T4 starts once T16 is agreed and runs beside Logan's T15, T17, T1, T18, T2 and
T3. The two tracks meet at T5 and T6. The cut order is in [GAMEPLAN](../GAMEPLAN.md#schedule-pacific-pdt).
