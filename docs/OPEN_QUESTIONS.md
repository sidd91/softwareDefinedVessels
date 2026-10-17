# Open questions, in one place

Status: Sat 01:28 PDT; rows 1, 27, 28, 32 and 34 to 43 updated Sat 11:43 PDT after the whole-plan review
(docs/PLAN_REVIEW_FINDINGS.md). Gathered by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka) from every planning
document, so the team can decide in one sitting. Each has a proposal; the decision is the team's. When one
is decided, add a WORKLOG Decisions row and update the source document.

## Before anyone builds (morning review)

| # | Question | Proposal | Source |
|---|---|---|---|
| 1 | Merge the plan and build into main? | **Decided (DEC-34):** merge PR #2, which includes PR #1's commits; Siddharth merges as repo owner. Not merged yet; the freeze checklist in the [build plan](BUILD_PLAN.md) covers it | WORKLOG CON-06 |
| 2 | Who owns what? | Team call; no split proposed | CON-07, DEC-29, [architecture](ARCHITECTURE.md) |
| 3 | Accept the re-timed milestones? | Review 08:30, Scenario A 12:30, Scenario B 17:30, screen 21:30 | [build plan](BUILD_PLAN.md), CON-10 |
| 4 | Scenario B load-out (13.0 t against 10 t, Bay 2 twice)? | **Decided (DEC-32):** run G3, G4, G5; refuse the full load-out at the pier, recommend this subset, logged override available | [storyboard](DEMO_SCRIPT.md), CON-12 |
| 5 | Which envelope corner decides admission? | **Decided (DEC-35):** both gensets at 30 °C, and the set must survive one genset down by throttling alone against a 95 kW gate, or it becomes yes-if | [architecture](ARCHITECTURE.md) Q3 |
| 6 | In port, may installed guests move between bays to admit a card? | **Decided (DEC-37):** yes, and report the moves | architecture Q4 |
| 7 | Is the decision record the single source for screen and demo? | Yes | architecture Q2 |

## Technology and hardware

| # | Question | Proposal | Source |
|---|---|---|---|
| 8 | Two-node bus: our own UDP layer or existing middleware? | Own layer; replay stays simple | architecture Q5 |
| 9 | Screen technology? | Plain HTML and JS, no build step | architecture Q6 |
| 10 | What demo hardware do we have (second machine, cable, router)? | **Partly decided (DEC-30, DEC-41):** node B is an Arduino VENTUNO Q, up over USB-C ([NODE_B_BOARD.md](NODE_B_BOARD.md)); still need a travel router or hotspot for a private Wi-Fi path, and the team's call on a wired path (DEF-01) | architecture Q7 |
| 11 | Second USB or phone camera for the leak line? | Only if cheap; the line works replayed | [camera design](../research/cv_equipment_monitoring.md) Q4 |

## Demo

| # | Question | Proposal | Source |
|---|---|---|---|
| 12 | Where does the breadth strip go inside the brief's 90 s of Scenario B? | Only lines that happen inside B (cable pull, crew dial); the rest after Scenario A | [storyboard](DEMO_SCRIPT.md) Q4 |
| 13 | Which four breadth lines? | Camera leak (replayed), crew dial, cable pull, over-consuming guest | storyboard Q2 |
| 14 | Who drives the laptop and who talks? | Team call | storyboard Q3 |

## Rules and cameras

| # | Question | Proposal | Source |
|---|---|---|---|
| 15 | At 6 aboard, who overrides a camera detection if the bridge watch is also the landing officer? | The bridge watch, logged | [Scenario C memo](SCENARIO_C_MEMO.md) |
| 16 | Declare fixed deck firefighting, or forbid drone launch with nobody aboard? | Forbid launch at 0; simpler and honest | memo |
| 17 | Camera smoke at the drone charger: stop the charge at once, or arm and wait for confirmation? | Arm and wait, like other plant faults | camera design Q1, CON-11 |
| 18 | Is G1, G3, G4, G5 our standard guest set for camera and admission examples? | Yes (9.56 t, fits) | camera design Q2 |
| 19 | Pull PyTorch for the PaDiM anomaly stretch? | No; classical checks first | camera design Q3 |

## Modelling choices from the requirements matrix

| # | Question | Proposal | Source |
|---|---|---|---|
| 20 | Crew availability for installation windows: watch schedule or a simple count? | Count | [R-088](requirements/should-have-success-criteria.md) |
| 21 | G1's 30 % loss when our radar transmits: schema field or special case? | Schema field for state-dependent capability | R-362 |
| 22 | Copernicus Marine (needs a person to register) or Argo only? | Argo only | R-514 |
| 23 | First three generators to build? | Genset trip, drone battery, seawater temperature | R-522 |

## Assumptions to confirm (all in `config/assumptions.yaml`, each with its reason)

| # | Question | Current value | Source |
|---|---|---|---|
| 24 | Hull length | 60 m, from the slides | [Physical Account](PHYSICAL_ACCOUNT.md) |
| 25 | Guest reserve by speed | slow 250, cruise 200, fast 150 kW | Physical Account |
| 26 | Rule R3 parameters | approach 4 min; drain 1.11 %/min; staleness 3 s and 10 s | Physical Account |
| 27 | Physical Account closing answer | being re-derived to include cooling, from the decided Scenario B (DEC-32, DEC-40); the earlier draft, a 50 kW, 12.5 kWh battery bridge, counted power only (review finding math-1) | Physical Account |
| 28 | PDF route for the memo, README and Physical Account, and confirming page limits | **Decided:** `uv run python tools/build_pdfs.py` builds all three into `docs/pdf/` (pandoc and headless Chromium; LibreOffice fallback), checks US Letter and A4, and prints each page count against its limit | R-552, [README](../README.md) |

## From the expected outcomes

| # | Question | Proposal | Source |
|---|---|---|---|
| 32 | At minute 12 of Scenario B, is the survey vehicle charging (the brief's 105 kW) or on its own battery? Only with it charging does the trip force any shedding | **Decided (DEC-40):** on its own battery; the minute-12 trip holds with both ladders armed, and the shed happens at the labelled minute-19 pump fault. Organizer check in #41 | [expected outcomes](EXPECTED_OUTCOMES.md) |
| 33 | Judge data links at guests' minimum rates or nominal? At nominal, G5 alone exceeds the 2 Mbit/s SATCOM envelope | **Decided (DEC-38):** minimum for admission, nominal reported as degraded quality | expected outcomes, assumption 8 |

## For the organizers

Questions 37 to 41 are drafted as one message in [ORGANIZER_MESSAGE.md](ORGANIZER_MESSAGE.md), not yet sent.
Nothing in the build waits on an answer: each row has a fallback.

| # | Question | Fallback | Source |
|---|---|---|---|
| 34 | Is Open-Meteo's free tier acceptable for the hackathon? | **Answered by the brief:** its Stack, data and tools section names Open-Meteo Marine ("no key") as a tier-2 public source, so CON-05 can close on that line; CC BY 4.0 attribution in the README when the data is cached | CON-05 |
| 36 | If we used PaDiM, would a ResNet backbone from a Microsoft lab in China fall under the China-derived rule? | Do not use PaDiM | camera design Q3 |
| 37 | What do we submit, where and by when (repository link, branch, tag or commit; PDFs; portal)? Public repo or jury access? | Main of the team repo with a `submission` tag, PDFs in `docs/pdf/`, jury access confirmed: the freeze checklist in the [build plan](BUILD_PLAN.md) | review deliverables-2, R-016 |
| 38 | Slide 13 says "Deterministic simulation provided": does an organizer simulator exist, and where? | Our own seeded simulator, as the brief describes | R-492 |
| 39 | Is Claude on the authorized AI list, and where is the list published? | Logan's word (DEC-05) stays the only record, and [SOFTWARE_LOG.md](SOFTWARE_LOG.md) says so | R-546, R-549 |
| 40 | Is the 2-page memo the Scenario C rule memo (brief) or an architecture memo (slide 14)? | The Scenario C memo, as the brief's deliverables list says; architecture stays in the README | R-004, R-435 |
| 41 | In Scenario B, must the minute-12 shed execute steps, or may it show the armed ladder with 0 steps (DEC-40)? | DEC-40 as decided, with the labelled minute-19 event executing the sequence | DEC-40, R-067 |

#35 (Qualcomm's proprietary NPU runtime) is no longer asked: DEC-31 settles it, with models on ONNX Runtime
on node B's CPU.

## From the plan review

| # | Question | Options | Source |
|---|---|---|---|
| 42 | Emission silence with G4 airborne: brief A.6 says silence forbids manoeuvre and deck machinery (winches, hangar doors), while G4's card says that in silence it returns home and demands a clear deck, and its recovery needs a free turn into wind. Which wins, and does the decision record state the cost to the loser? | Open; team to decide one D3 rule. Options from the review: G4's land-or-ditch hard limit outranks silence and the record states the emission cost; or silence holds and G4 holds off or ditches, and the record states that cost. Until decided, the "Emission silence" breadth line in the [storyboard](DEMO_SCRIPT.md) would show a manoeuvre the ship state forbids | brief A.6, `manifests/G4.yaml`, R-390, R-483, review critic-4 |
| 43 | Do the crew-rule compiler (DEC-02), the LLM paraphraser and the 3D view (DEC-04) stay in scope under today's clock? | Logan's call. Today the [build plan](BUILD_PLAN.md) has no task for any of them, GAMEPLAN's cut order drops the LLM paraphraser and the 3D view second and third, and [SOFTWARE_LOG.md](SOFTWARE_LOG.md) lists the LLM as considered, not approved | brief Out of scope ("voice or natural-language interfaces"), R-536, review deliverables-9 |
