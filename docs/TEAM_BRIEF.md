# Team brief: where we are and what needs you

Status: Fri 23:56 PDT. Written by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka) for Logan and
Siddharth. One page; details are linked. No work split is proposed here (WORKLOG DEC-29).

## Where things stand

- **Branches.** `docs/game-plan-and-research` has the plan and research, in
  [PR #1](https://github.com/sidd91/softwareDefinedVessels/pull/1) to main, unreviewed.
  `feat/governor-core` sits on top of it with the data model and the drafts below.
- **Built.** Platform assumptions with provenance, the guest manifest schema with six cards (five from
  the brief plus our desalination unit), four mission priority files, and 11 passing checks against
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

Filled in when [the requirements matrix](REQUIREMENTS.md) lands.

## A possible first hour together

Review and merge PR #1; settle CON-12 and the envelope corner; agree owners; then start the ledger
and D1 admission, the base for both deep demos.
