# Team brief: where we are and what needs you

Status: Sat 00:51 PDT; branches, decisions, page limits and first hour updated Sat 11:43 PDT. Written by
Claude Opus 5.5 on behalf of Logan Walker (GhostWalka) for Logan and Siddharth. One page; details are
linked. No work split is proposed here (WORKLOG DEC-29).

## Where things stand

- **Branches.** `docs/game-plan-and-research` has the plan and research, in
  [PR #1](https://github.com/sidd91/softwareDefinedVessels/pull/1) to main.
  `feat/governor-core` sits on top of it with the data model and the drafts below, in
  [PR #2](https://github.com/sidd91/softwareDefinedVessels/pull/2), which includes PR #1's commits, so
  merging PR #2 alone is enough (DEC-34). At the Sat 11:24 check neither had a review and main held only
  the initial commit.
- **Built.** Platform assumptions with provenance, the guest manifest schema with six cards (five from
  the brief plus our desalination unit), four mission priority files, and 265 passing checks against
  the brief's own arithmetic. **No decision engine yet**, by Logan's direction (DEC-20, DEC-33).
- **Drafted for your review.** [Architecture and data contracts](ARCHITECTURE.md),
  [Scenario C memo](SCENARIO_C_MEMO.md), [camera equipment monitoring](../research/cv_equipment_monitoring.md),
  [demo storyboard](DEMO_SCRIPT.md), [README skeleton](../README.md),
  [Physical Account draft](PHYSICAL_ACCOUNT.md), [requirements matrix](REQUIREMENTS.md).
- **Research.** Sensors and data sets with 54 synthetic generator specs, camera placement, the
  Fincantieri fleet since 2000, shipboard procedures and accident lessons; see `research/`.
- **Schedule.** The plan's first milestone (Sat 01:30) assumed coding tonight, so it will slip
  (CON-10). Re-time after you have reviewed.

## Decisions waiting on you

Every open question from every document, with proposals: [docs/OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

| Ref | Question | Proposal | Where |
|---|---|---|---|
| DEC-29 | Who owns what? | Your call together | [architecture components](ARCHITECTURE.md) |
| Arch Q5 | Our own small UDP layer for the two-node bus, or existing middleware? | Own layer; deterministic replay is easier | [architecture](ARCHITECTURE.md) |
| Memo | At 6 aboard, who overrides if the bridge watch is also the landing officer? Declare fixed deck firefighting, or forbid drone launch at 0? | Team call | [memo](SCENARIO_C_MEMO.md) |
| CON-11 | Camera smoke: stop the drone's charge at once, or arm and wait for confirmation? Bring a second camera? | Team call | [camera design](../research/cv_equipment_monitoring.md) |
| OQ #42 | Emission silence with G4 airborne: A.6 forbids manoeuvre and deck machinery, but G4's recovery needs a turn into wind. Which wins? | Team call; options listed | [open questions](OPEN_QUESTIONS.md) |
| OQ #43 | Do the crew-rule compiler, the LLM paraphraser and the 3D view stay in scope under today's clock? | Logan's call (DEC-02, DEC-04) | [open questions](OPEN_QUESTIONS.md) |
| Organizers | Submission format and portal; whether slide 13's simulation exists; the authorized AI list; which memo; the minute-12 shed | Drafted as one message for Logan to send: [ORGANIZER_MESSAGE.md](ORGANIZER_MESSAGE.md). Open-Meteo is answered by the brief itself; the NPU runtime by DEC-31 | [software log](SOFTWARE_LOG.md) |

Decided since the first draft: Scenario B load-out (DEC-32), the envelope corner (DEC-35), port moves
(DEC-37), data links at minimum rates (DEC-38), node B hardware and local-only models (DEC-30, DEC-31),
merging PR #2 alone (DEC-34) and the Scenario B timeline (DEC-40).

## Requirement gaps

[The requirements matrix](REQUIREMENTS.md) traces 554 requirements from every page of the slides and
brief (509 called out): 11 done, 337 drafted, 197 planned, 9 not applicable, and **no open gaps**. Most
planned rows wait on the same thing, the ledger and the D1 to D4 engines. The last nine gaps were closed
overnight with honest answers; the ones that still need a team decision:

- **Shorter installation windows at 6 aboard** (R-088): model crew as a watch schedule or just a count?
- **G1's 30 % loss when our radar transmits** (R-362): add a degradation field to the schema, or treat
  it as a G1 special case?
- **Copernicus Marine** (R-514) needs a person to register; Argo data needs no account and may be enough.
- **First generators to build** (R-522): proposed genset trip, drone battery and seawater temperature.

## Tonight, for your review

- **Assumptions added**, each with its reason in `config/assumptions.yaml`: hull 60 m from the slides;
  guest reserve by speed (slow 250, cruise 200, fast 150 kW); what emission silence forbids; the Scenario
  C rule's nine parameters. Change any of them freely; the Physical Account regenerates.
- **Page limits:** README at most 3 pages, Scenario C memo at most 2, Physical Account 1; checked by
  `uv run python tools/build_pdfs.py`, which writes `docs/pdf/` and prints each page count.
- **New guide and checks:** how to add a guest card (`manifests/README.md`); priority files now have a
  schema and a test, for the jury's unseen file. 265 tests pass.

## Build plan

A proposal with tasks, pass checks and re-timed milestones: [docs/BUILD_PLAN.md](BUILD_PLAN.md). Hand-computed
expected outcomes for every Scenario A drill and Scenario B minutes 8 and 12, ready to become the first
tests: [docs/EXPECTED_OUTCOMES.md](EXPECTED_OUTCOMES.md).

## A possible first hour together

Review and merge PR #2 (DEC-34); agree owners; then start the ledger and D1 admission, the base for
both deep demos.
