# Team brief: where we are and what needs you

Status: Sat 00:42 PDT. Written by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka) for Logan and
Siddharth. One page; details are linked. No work split is proposed here (WORKLOG DEC-29).

## Where things stand

- **Branches.** `docs/game-plan-and-research` has the plan and research, in
  [PR #1](https://github.com/sidd91/softwareDefinedVessels/pull/1) to main, unreviewed.
  `feat/governor-core` sits on top of it with the data model and the drafts below.
- **Built.** Platform assumptions with provenance, the guest manifest schema with six cards (five from
  the brief plus our desalination unit), four mission priority files, and 12 passing checks against
  the brief's own arithmetic. **No decision engine yet**, by Logan's direction (DEC-24).
- **Drafted for your review.** [Architecture and data contracts](ARCHITECTURE.md),
  [Scenario C memo](SCENARIO_C_MEMO.md), [camera equipment monitoring](../research/cv_equipment_monitoring.md),
  [demo storyboard](DEMO_SCRIPT.md), [README skeleton](../README.md),
  [Physical Account draft](PHYSICAL_ACCOUNT.md), [requirements matrix](REQUIREMENTS.md).
- **Research.** Sensors and data sets with 54 synthetic generator specs, camera placement, the
  Fincantieri fleet since 2000, shipboard procedures and accident lessons; see `research/`.
- **Schedule.** The plan's first milestone (Sat 01:30) assumed coding tonight, so it will slip
  (CON-10). Re-time after you have reviewed.

## Decisions waiting on you

| Ref | Question | Proposal | Where |
|---|---|---|---|
| CON-12 | The brief's Scenario B load-out (G2, G3, G4, G5) is 13.0 t against a 10 t margin and needs Bay 2 twice. Run as given or use a feasible subset? | Run as given and flag it on screen: an honest physical model is scored | [storyboard](DEMO_SCRIPT.md) |
| DEC-29 | Who owns what? | Your call together | [architecture components](ARCHITECTURE.md) |
| Arch Q3 | Which envelope corner decides admission? | Both gensets at 30 °C; report one-genset-down separately | [architecture](ARCHITECTURE.md) |
| Arch Q4 | In port, may installed guests move between bays to admit a new card? | Yes, report the moves | [architecture](ARCHITECTURE.md) |
| Arch Q5 | Our own small UDP layer for the two-node bus, or existing middleware? | Own layer; deterministic replay is easier | [architecture](ARCHITECTURE.md) |
| Memo | At 6 aboard, who overrides if the bridge watch is also the landing officer? Declare fixed deck firefighting, or forbid drone launch at 0? | Team call | [memo](SCENARIO_C_MEMO.md) |
| CON-11 | Camera smoke: stop the drone's charge at once, or arm and wait for confirmation? Bring a second camera? | Team call | [camera design](../research/cv_equipment_monitoring.md) |
| Organizers | Is Open-Meteo's free tier acceptable here? Is Qualcomm's proprietary NPU runtime allowed (box arrives Sat 10:00)? | Ask on Saturday morning | [software log](SOFTWARE_LOG.md) |

## Requirement gaps

[The requirements matrix](REQUIREMENTS.md) traces 554 requirements from every page of the slides and
brief (509 called out): 11 done, 332 drafted, 193 planned, 9 gaps, 9 not applicable. Most planned rows
wait on the same thing, the ledger and the D1 to D4 engines. The nine gaps:

- **Brief call-outs to decide:** shorter installation windows at 6 aboard (R-088); the exact rationale
  fields, verdict, bound resource, condition, free amount and need with units (R-148); G1's 30 % loss when
  our own radar transmits unless "quiet radio" is declared (R-362); propulsion pods as a power consumer
  (R-239); the slide's ambiguous 6 m "LOB" dimension (R-238).
- **Light items:** the slide chart's spike times versus its callouts (R-207); designing from what a
  Kubernetes request cannot express (R-500); registering for Copernicus Marine early, which needs a
  person to create the account (R-514); starting the synthetic generators in hour 1 (R-522).

## Tonight, for your review

- **Assumptions added**, each with its reason in `config/assumptions.yaml`: hull 60 m from the slides;
  guest reserve by speed (slow 250, cruise 200, fast 150 kW); what emission silence forbids; the Scenario
  C rule's nine parameters. Change any of them freely; the Physical Account regenerates.
- **Page limits:** the Scenario C memo fits 2 A4 pages at 11 pt; the Physical Account is now grouped for
  one page but a rough render still gives about 2, so confirm it in whatever PDF route we pick.
- **New guide and checks:** how to add a guest card (`manifests/README.md`); priority files now have a
  schema and a test, for the jury's unseen file. 12 tests pass.

## A possible first hour together

Review and merge PR #1; settle CON-12 and the envelope corner; agree owners; then start the ledger
and D1 admission, the base for both deep demos.
