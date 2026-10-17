# Build plan (proposal for team review)

Status: Sat 00:52 PDT. Drafted by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka). A proposal only:
owners are blank on purpose (WORKLOG DEC-29) and nothing starts until the team has reviewed (DEC-24).
It turns the plan into ordered tasks, each with the requirements it closes and a pass check taken from
the brief's own numbers, so "done" is never a matter of opinion. The exact expected verdicts, numbers and ladders for every
Scenario A drill and Scenario B minute 8 and 12 are in [EXPECTED_OUTCOMES.md](EXPECTED_OUTCOMES.md); the same results
are in `tests/oracles/expected_outcomes.yaml`, already checked against the cards by
`tests/test_expected_outcomes_data.py`, so the first engine test only has to load it and compare.

## Proposed re-timed milestones (replaces GAMEPLAN's slipped schedule if accepted, CON-10)

| Milestone | Target (PDT) | Pass check |
|---|---|---|
| Review | Sat 08:30 | PR #1 merged; CON-12 (Scenario B load-out) and the envelope corner decided; owners agreed |
| M1 Scenario A | Sat 12:30 | the three Scenario A drills pass as tests, each verdict within 30 s with its one-sentence reason |
| M2 Scenario B | Sat 17:30 | minute-8 decision within 2 s and minute-12 ladder (first action 5 s, sequence 60 s) under both priority files; replay identical |
| M3 Screen | Sat 21:30 | Scenario B watchable end to end: schematic, 8 gauges, decision log, priority swap, crew dial |
| M4 Breadth | Sun 01:30 | each breadth line works live or replayed and is labelled so |
| Freeze | Sun 09:15 | five rehearsals done; PDFs exported; backup recording made |

The Qualcomm box lands about Sat 10:00; until then node B is a second process on the laptop.

## Tasks

| # | Task | Closes | Pass check | After |
|---|---|---|---|---|
| T1 | Ledger and platform model: capacity and demand per class from `config/assumptions.yaml` and the cards, under conditions (seawater, gensets, cooling, speed, emission) | R-040, R-043, R-554 | reproduces the brief's checks already in `tests/`: 126.5 kW at cruise fits 200; 105 kW against 100 with one genset down; cooling 120 kW at 30 °C, 72 kW degraded; three of five sets of four over 10 t | review |
| T2 | D1 admission with placement (D2) and the envelope sweep | R-064, R-065, R-069, R-100 to R-109 | the 35 kg drill refuses by 35 kg and names mass; the bay drill names Bay 1 and mass; yes-if lists are ranked by the active priority file; the seawater tipping point is reported | T1 |
| T3 | `sdv` command and decision record | R-016, R-017 | `uv run sdv admit G4 --installed G1,G2,G3` prints the verdict and sentence from the real engine, with latency against its ceiling | T2 |
| T4 | Event timeline, seeded simulator, three generators (genset trip, drone battery, seawater) | R-086, R-155, R-522 | two runs with the same seed and timeline produce byte-identical decision logs | T1 |
| T5 | D3 right of way | R-066, R-110 to R-113 | minute 8: decided within 2 s; the drone's 12-minute limit is named first; the sentence states the cost to the loser in minutes; the two priority files give different decisions | T4 |
| T6 | D4 shedding ladder, precomputed each tick | R-067, R-114 to R-119 | minute 12: first action within 5 s and full sequence within 60 s; throttle before shed; safety-critical never shed; every guest's loss stated | T4 |
| T7 | Priority-file swap and validation | R-152, R-137 | a swapped file re-decides the same event differently; a malformed file is refused with the failing field while the old file keeps running | T5, T6 |
| T8 | Screen: schematic, 8 gauges, decision log, mission and crew controls | R-146, R-218 | Scenario B runs end to end on screen within the storyboard's 90 s | T5 to T7 |
| T9 | Over-consuming guest | R-082, R-083 | a guest drawing 15 % over its declaration is detected and throttled with a sentence | T6 |
| T10 | Public data for cooling and deck | R-080, R-081 | cached Sicily seawater and wind drive the cooling and flight-deck limits offline | T4 |
| T11 | Rule R3 at two crew levels | R-084, R-085 | the same recovery is confirmed at 14, held from launch at 6, and refused at 0 when the deck cannot be proven clear | T5 |
| T12 | Two nodes, wired and Wi-Fi, failover by replay | R-458 | pull the cable: no decision lost; kill the primary: the standby continues with the same sequence numbers | T4 |
| T13 | Camera leak line (C1), replayed first | DEC-27 | the replayed leak marks cooling degraded with source camera and sheds nothing until a fault is confirmed | T6 |
| T14 | Deliverable PDFs and README pass | R-019 to R-024, R-025, R-552 | README at most 3 pages; memo at most 2; Physical Account one page; page counts checked in the final route | anytime |

Build order if people work in parallel: T1 first; then T2 and T3 on one track, T4 on another; T5, T6
and T7 together; then T8 to T13 split freely. Cut order stays as in GAMEPLAN; T13, T12 and T10 are the
first to fall back to replayed or cached versions.
