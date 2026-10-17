# Open questions, in one place

Status: Sat 01:28 PDT. Gathered by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka) from every planning
document, so the team can decide in one sitting. Each has a proposal; the decision is the team's. When one
is decided, add a WORKLOG Decisions row and update the source document.

## Before anyone builds (morning review)

| # | Question | Proposal | Source |
|---|---|---|---|
| 1 | Merge PR #1 (plan, research, worklog) into main? | Yes; Siddharth merges as repo owner | WORKLOG CON-06 |
| 2 | Who owns what? | Team call; no split proposed | CON-07, DEC-29, [architecture](ARCHITECTURE.md) |
| 3 | Accept the re-timed milestones? | Review 08:30, Scenario A 12:30, Scenario B 17:30, screen 21:30 | [build plan](BUILD_PLAN.md), CON-10 |
| 4 | Scenario B load-out (13.0 t against 10 t, Bay 2 twice)? | Run as given and flag it on screen | [storyboard](DEMO_SCRIPT.md), CON-12 |
| 5 | Which envelope corner decides admission? | Both gensets at 30 °C; report one-genset-down separately | [architecture](ARCHITECTURE.md) Q3 |
| 6 | In port, may installed guests move between bays to admit a card? | Yes, and report the moves | architecture Q4 |
| 7 | Is the decision record the single source for screen and demo? | Yes | architecture Q2 |

## Technology and hardware

| # | Question | Proposal | Source |
|---|---|---|---|
| 8 | Two-node bus: our own UDP layer or existing middleware? | Own layer; replay stays simple | architecture Q5 |
| 9 | Screen technology? | Plain HTML and JS, no build step | architecture Q6 |
| 10 | What demo hardware do we have (second machine, cable, router)? | Bring a travel router or hotspot; never venue Wi-Fi | architecture Q7 |
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
| 27 | Physical Account closing answer | a 50 kW, 12.5 kWh battery bridge lifting the one-genset-down reserve to 150 kW | Physical Account |
| 28 | PDF route for the memo, README and Physical Account, and confirming page limits | pick one tool and check all three | R-552, [README](../README.md) |

## For the organizers

| # | Question | Fallback | Source |
|---|---|---|---|
| 29 | Is Open-Meteo's free tier acceptable for the hackathon? | NOAA OISST and Argo | CON-05 |
| 30 | Is Qualcomm's proprietary NPU runtime allowed (box arrives Sat 10:00)? | Run on its CPU | CON-04 |
| 31 | If we used PaDiM, would a ResNet backbone from a Microsoft lab in China fall under the China-derived rule? | Do not use PaDiM | camera design Q3 |
