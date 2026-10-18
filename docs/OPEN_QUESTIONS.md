# Open questions, in one place

Status: Sat 12:40 PDT, rewritten after the design freeze (WORKLOG DEC-44) and the work split (DEC-47) by
Claude Opus 5.5 on behalf of Logan Walker (GhostWalka). Each open question has a proposal and an owner. When
one is decided, add a WORKLOG Decisions row and update the source document. Numbers are stable: closed
questions keep theirs in the table at the end, and new questions take the next free number.

## Contracts and core

| # | Question | Proposal | Owner, source |
|---|---|---|---|
| 44 | The typed vocabulary (F2) has only speed bands, but G4 recovers at 5 to 12 kn and the A.11 window is 4 to 8 kn, which no A.6 band covers. Activity names also drift: G2 and G3 say `G4.recovering`, G4 defines `launch_recovery` | Add a numeric `speed_kn` signal beside `speed_band`; use `G4.launch_recovery` everywhere | Logan (T15); freeze delta 2 |
| 45 | `mission_critical` names guest ids (`sar.yaml`: G4), while the freeze says cards and priority files join by capability name. And what happens when a file does not weight a loaded card's capability? | Keep guest ids and have the loader check each one against the loaded cards; refuse a file that leaves a loaded capability unweighted, naming it | Logan (T17); freeze section 2 |
| 47 | Does A.8's 5 s first action count from the raw plant event or from its confirmation? | From the raw event. The record carries both times, so debounce and confirmation must fit inside the 5 s | Logan and Siddharth (T16, CON-21) |
| 48 | Which commands go in the 200 ms safety table? | R3's hold of landing clearance; G2's winch stop while G3 listens or G4 recovers; G3's hold depth before the ship manoeuvres; G4's return home in silence | Logan (T19); freeze delta 12 |
| 49 | DEC-02's live priority overrides (an override stack over the mission file): keep or defer? | Defer. The priority swap (T7) and Mission compare (T20) carry the "two ships" moment | Logan |
| 50 | Where does a rule's confirm policy come from when the priority file sets none? | Done in data: `rules.r3.confirm` {14: confirm, 6: standing_plan, 0: automatic}, which a priority file may override; Logan to confirm the defaults | Logan (T17); R-037 |

## Team and hardware

| # | Question | Proposal | Owner, source |
|---|---|---|---|
| 3 | Accept the re-timed milestones? | The proposal in the [build plan](BUILD_PLAN.md): contracts Sat 14:00, Scenario A 18:30, Scenario B 22:30, screen Sun 01:30, freeze 09:15 | Logan and Siddharth; CON-10, CON-17 |
| 46 | Who builds the board instrument (T24), and does it start before Scenario B passes? | Not before M2. Nothing in the demo depends on it | Logan and Siddharth; [NODE_B_BOARD.md](NODE_B_BOARD.md) |
| 51 | Who builds the final PDFs (T14)? | Open | Logan and Siddharth |
| 9 | Screen technology? | Plain HTML and JS served by FastAPI, uvicorn and websockets (install approved by DEC-39); no build step | Logan (UI, DEC-47) |
| 52 | The board still has its default login with SSH open on the venue Wi-Fi (CON-15) | Change the password (`adb shell -t passwd`), or turn Wi-Fi or SSH off on the board, since the instrument needs only USB | Logan; DEF-01 keeps the power arrangement |

## Demo

| # | Question | Proposal | Source |
|---|---|---|---|
| 12 | Where does the breadth strip go inside the brief's 90 s of Scenario B? | Nowhere inside: the breadth strip runs after Scenario A, next to the R3 segment | [storyboard](DEMO_SCRIPT.md) |
| 13 | Which breadth lines? | **Settled at the freeze alignment (Sat 12:30 PDT):** crew dial 14, 6, 0 with R3; landing zone not clear (from the landing officer's report); over-consuming guest; emission silence (waits on #42); mission sets; data feed drops (R-458). How many to show on the day is open | storyboard |
| 14 | Who drives the laptop and who talks? | Team call | storyboard |
| 53 | The camera foreshadow of the minute-19 pump fault is cut. What keeps the INJECTED fault from looking staged? | A labelled plant-signal trend on pump 1 (delta-T or pump current) before it fails, or let the jury trigger the fault from the laptop after minute 17 | DEC-40, storyboard |

## Rules

| # | Question | Proposal | Source |
|---|---|---|---|
| 42 | Emission silence with G4 airborne: brief A.6 says silence forbids manoeuvre and deck machinery (winches, hangar doors), while G4's card says that in silence it returns home and demands a clear deck, and its recovery needs a free turn into wind. Which wins, and does the record state the cost to the loser? | Open; team to decide one D3 rule. Options: G4's land-or-ditch hard limit outranks silence and the record states the emission cost; or silence holds and G4 holds off or ditches, and the record states that cost. The breadth line waits on this (T26) | brief A.6, `manifests/G4.yaml`, R-390, R-483 |
| 16 | Declare fixed deck firefighting, or forbid drone launch with nobody aboard? | Forbid launch at 0; simpler and honest | [Scenario C memo](SCENARIO_C_MEMO.md) |
| 54 | At 0 aboard, R3's latch sees only plant signals (hangar doors, winch, ramp, deck machinery; G4's own launch, which is exempt). Loose gear moving in wind cannot be sensed without a camera | State it as a limitation in the memo and the Physical Account | memo; freeze check |

## Modelling choices from the requirements matrix

| # | Question | Proposal | Source |
|---|---|---|---|
| 20 | Crew availability for installation windows: watch schedule or a simple count? | Count | [R-088](requirements/should-have-success-criteria.md) |
| 21 | G1's 30 % loss when our radar transmits: schema field or special case? | Schema field for state-dependent capability, added with T15 | R-362 |
| 22 | Copernicus Marine (needs a person to register) or Argo only? | Argo only | R-514 |
| 23 | First three generators to build? | Genset trip, drone battery, seawater temperature; Siddharth's call, since the simulator is his (DEC-47) | R-522 |

## Assumptions to confirm (all in `config/assumptions.yaml`, each with its reason)

| # | Question | Current value | Source |
|---|---|---|---|
| 24 | Hull length | 60 m, from the slides | [Physical Account](PHYSICAL_ACCOUNT.md) |
| 25 | Guest reserve by speed | slow 250, cruise 200, fast 150 kW | Physical Account |
| 26 | Rule R3 parameters | approach 4 min; drain 1.11 %/min; G4 telemetry stale after 10 s. The camera keys go with F5 | Physical Account |

## For the organizers

Logan sent the message in [ORGANIZER_MESSAGE.md](ORGANIZER_MESSAGE.md) (DEC-49). As he relayed it, the
organizers said the questions are fine and there is some flexibility, and there is no organizer simulator.
No specific answer is recorded for #37 or #39, so their fallbacks stand.

| # | Question | Where it stands | Source |
|---|---|---|---|
| 37 | What do we submit, where and by when (repository link, branch, tag or commit; PDFs; portal)? Public repo or jury access? | No specific answer. Fallback: main of the team repo with a `submission` tag, PDFs in `docs/pdf/`, jury access confirmed, per the checklist in the [build plan](BUILD_PLAN.md) | R-016 |
| 39 | Is Claude on the authorized AI list, and where is the list published? | No specific answer. Logan's word (DEC-05) stays the only record, and [SOFTWARE_LOG.md](SOFTWARE_LOG.md) says so | R-546, R-549 |
| 41 | In Scenario B, must the minute-12 shed execute steps, or may it show the armed ladder with 0 steps? | Siddharth's to decide as owner of the simulator and scenario timing (DEC-51). DEC-40 stands until he does: minute 12 holds under both files with the armed ladders shown, and the INJECTED minute-19 pump fault runs the sequence | DEC-40, DEC-51, R-067 |

## Closed

| # | Question | Closed by |
|---|---|---|
| 1 | Merge the plan and build into main? | DEC-34; PR #2 merged (DEC-48) |
| 2 | Who owns what? | DEC-47: Siddharth the simulator, ship-state machine and commands; Logan the rest. Board and PDFs open as #46 and #51 |
| 4 | Scenario B load-out (13.0 t against 10 t, Bay 2 twice)? | DEC-32: G3, G4, G5; superseded by DEC-63: the organisers' G1, G3, G4, G5 (9.56 t) |
| 5 | Which envelope corner decides admission? | DEC-35 |
| 6 | In port, may installed guests move between bays? | DEC-37 |
| 7 | Is the decision record the single source for screen and demo? | Yes (freeze section 2, DEC-44). Replay compares the decision log; wall-clock timing sits in a separate log |
| 8 | Two-node bus: own UDP layer or middleware? | Failover cut (DEC-44) |
| 10 | What demo hardware do we have? | The laptop only. The board is an instrument off the demo path (DEC-44) |
| 11 | Second camera for the leak line? | Cameras cut (DEC-44) |
| 15 | At 6 aboard, who overrides a camera detection? | Cameras cut. At 6 the standing plan approved at launch applies (R3) |
| 17 | Camera smoke: stop the charge or arm and wait? | Cameras cut (DEC-44) |
| 18 | Standard guest set for camera examples? | Cameras cut (DEC-44) |
| 19 | PyTorch for the PaDiM stretch? | Cameras cut (DEC-44) |
| 27 | Physical Account closing answer | A standby chilled-water pump (WORKLOG, Sat 12:25) |
| 28 | PDF route and page limits | `uv run python tools/build_pdfs.py` |
| 32 | At minute 12, is G3 charging? | DEC-40: on its own battery. Minute 12 holds; the organizer check is #41 |
| 33 | Data links at minimum or nominal rates? | DEC-38: minimum, nominal shown as degraded quality |
| 34 | Open-Meteo's free tier? | Answered by the brief, which names Open-Meteo Marine as a public source |
| 35 | Qualcomm's proprietary NPU runtime? | DEC-31, then NPU inference cut (DEC-44) |
| 36 | PaDiM's ResNet backbone and the China-derived rule? | Cameras cut (DEC-44) |
| 38 | Does an organizer simulator exist? | No (DEC-49). ArgOS runs its own seeded simulator, built by Siddharth |
| 40 | Scenario C memo or architecture memo? | DEC-50: treat them as different documents and write one 2-page memo that serves both |
| 43 | Crew-rule compiler, LLM paraphraser and 3D view in scope? | Cut (DEC-44) |
