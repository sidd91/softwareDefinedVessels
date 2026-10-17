# Team brief: where we are and what needs you

Status: Sat 12:40 PDT. Written by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka) for Logan and
Siddharth. One page; details are linked.

## Where things stand

- **Main.** PR #2 is merged (DEC-48): the data model, the requirements trace, the plans and the deliverable
  drafts. Branch `feat/argos-core` is cut from main for the freeze alignment and then the core.
- **Design frozen.** Logan approved Siddharth's design freeze (DEC-44, [DESIGN_FREEZE.md](DESIGN_FREEZE.md)).
  Our data model is the base. Cut: cameras and computer vision, the 3D view, the crew rule compiler, the LLM
  paraphraser, person detection, NPU inference and two-node failover. The VENTUNO Q board becomes an
  instrument for the Physical Account ([NODE_B_BOARD.md](NODE_B_BOARD.md)). The project is called ArgOS
  (DEC-45).
- **Built.** Platform assumptions with provenance, the guest manifest schema with six cards (five from the
  brief plus our desalination unit), four priority files, the Scenario B timeline, hand-computed oracles,
  the Physical Account generator and the PDF route, all checked by tests. **No engine code yet.**
- **Organizers.** Logan sent the message (DEC-49): the questions are fine, there is some flexibility, and
  there is no organizer simulator. One 2-page memo serves both the Scenario C and the architecture reading
  (DEC-50). Minute 12 of Scenario B is Siddharth's call (DEC-51); DEC-40 stands until he decides.

## Who builds what (DEC-47)

| Who | Builds |
|---|---|
| Siddharth | the simulator; the ship-state machine with its transition times, debounced faults and the acoustic link; the command set the core sends |
| Logan, with Claude | typed conditions, the loader, the ledger and ladder core, D1 to D5, the safety-command table, decision records and the explainer; the snapshot schema, the clock and replay; the screen; the docs |
| Not assigned | the board instrument (T24) and the final PDFs (T14) |

## Build order

Typed conditions and the snapshot contract, then the ledger with the ladder core, then Scenario A (D1 and
D2 by enumeration), then D3 and D4 with the simulator, then the screen, replay and docs. Tasks, pass
checks and proposed milestones (contracts Sat 14:00, Scenario A 18:30, Scenario B 22:30, screen Sun 01:30,
freeze 09:15) are in [BUILD_PLAN.md](BUILD_PLAN.md). The done check for Scenario A: A3 names mass as binding
and lists cooling at 30 °C as also failing.

## Decisions waiting on you

Every open question, with proposals: [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

| Ref | Question | Proposal | Who |
|---|---|---|---|
| CON-21 | Snapshot fields and command set | Agree them first (T16); both confirm in WORKLOG | Logan and Siddharth |
| DEC-51, OQ #41 | Must minute 12 execute steps? | DEC-40 stands: it holds, with both armed ladders shown | Siddharth |
| OQ #3 | Re-timed milestones | The build plan's proposal; closes CON-10 and CON-17 | Logan and Siddharth |
| OQ #46, #51 | Owners for the board instrument and the final PDFs | Board only after Scenario B passes | Logan and Siddharth |
| OQ #42 | Emission silence with G4 airborne: which wins? | Team call; options listed | Logan and Siddharth |
| OQ #44, #45 | Numeric speed in the typed vocabulary; how `mission_critical` names guests | Proposals listed | Logan |
| CON-15, OQ #52 | The board's default login is open on the venue Wi-Fi | Change the password, or turn Wi-Fi or SSH off on the board | Logan |
| WORKLOG | Siddharth's DEC-42 and CON-17 on `design/freeze` became DEC-43 and CON-19 at the merge | Confirm, or correct with a new row; pull before the next WORKLOG write | Siddharth |

## Requirement gaps

[The requirements matrix](REQUIREMENTS.md) traces 554 requirements from every page of the slides and
brief (509 called out): 11 done, 337 drafted, 197 planned, 9 not applicable, and no open gaps. Most planned
rows wait on the ledger and the D1 to D4 engines. The freeze changes how some rows are met: cameras and
failover are gone, R3 at 0 aboard uses the deck state latched at the last crew sweep, and "keeps working
when a data feed drops" (R-458) gets its own breadth line.

## A possible first hour together

Agree the snapshot and command contract (T16). Then Logan starts typed conditions (T15) and Siddharth the
simulator (T4).
