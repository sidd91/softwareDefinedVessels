# Deployment: the governor's computers and the Reference Kit

Status: design, Sat 2026-10-17, from Logan's DEC-56 to DEC-58; written by Claude Opus 5.5 on behalf of Logan
Walker (GhostWalka). Numbers are in `config/assumptions.yaml` (`governor`) and the Physical Account. The demo
runs on one laptop. This page says how ArgOS would sit aboard a real hull. Built and tested today: the board
count, the standby in lockstep and the kit (build, verify, install, rollback). Every part marked **Design** is
not built.

## In one paragraph

ArgOS runs on small, identical computers spread across the ship, never on one box. The Qualcomm board we have
(VENTUNO Q, 8 cores, 55 GB) is the primary. A second, identical board stands by in another fire zone, and
larger hulls get one more board for each 25 m. Because every tick is deterministic, the standby runs on the
same inputs and reaches the same decisions. Today it runs beside the primary in one process
(`Loop(standby=True)`). **Design:** a heartbeat between the boards, and a takeover after 3 s
with nothing to catch up on. **Design:** Pi-class nodes at the important sites watch their own equipment and
keep the latest shed plan, so a site still knows what to switch off even if every board is lost. Every device
that has room carries the Deployment Reference Kit: the vessel's profile and design documents, and a datasheet,
troubleshooting and FAQ for every guest card in `manifests/`. Vendor manuals are listed as required documents
and come with each guest.

## The computers (60 m hull)

| Device | Where | Does |
|---|---|---|
| Board 1, primary | bridge | **Design:** runs the governor: estimator, decisions, screen. Today the governor runs on the laptop |
| Board 2, standby | engine control room | runs the same governor on the same inputs in lockstep. **Design:** takes over after 3 s without heartbeat |
| Boards 3 and 4, zone | forward equipment room, hangar | **Design:** collect their zone's edge nodes, and either can become primary |
| Edge nodes (6) | engine control room, chilled-water plant, bridge, hangar and flight deck, stern ramp, mission bays | **Design:** local monitoring, and the latest shed table, pushed every tick |
| SSD copies (2) | bridge, engine control room | **Design:** offline backup of the kit and the run logs |
| Printed binder | bridge | the kit on paper |

Board count: 2 on any hull, plus one for each started 25 m beyond the first 25 m. That is 2 at 25 m, 4 at
60 m and 4 at 70 m (`sdv kit plan` prints it for the configured hull). The extra boards are
dual use: zone aggregators in normal service, spare governors when needed.

**In step or not.** The standby feeds the primary's frames and inputs through its own estimator and decisions
and compares every snapshot, record and command byte for byte (`Loop(standby=True)`). The screen shows STANDBY
IN STEP. If the two ever differ on the same inputs, the screen shows STANDBY OUT OF STEP as an alarm, and the
tick output names the first field that differs. The standby state is in the tick output and on the screen, not
in the five run logs.

## The Deployment Reference Kit

What it holds, all generated from the repository so it matches what the governor runs (`sdv kit build`):

- **Vessel:** the ship profile, every signal, the mission profiles, the cards and the design documents.
- **Governor runbook:** for each event (genset trip, pump fault, stale feed, unanswered bridge request,
  board lost, standby out of step, profile refused), what ArgOS does and what the crew does.
- **One page per guest card in `manifests/`**, aboard or not: technical data (modes, power, parts and
  positions), operating conditions and hard limits, its weight and response class under each mission profile,
  troubleshooting for each signal it reports, an FAQ, and the vendor documents it must bring (operator and
  maintenance manuals, safety data, interface specification). These are listed as required, and the operator
  brings them with the card.
- **Manifest:** every file's size and SHA-256 checksum, the commit it was built from, and what each device holds.

Where it goes: every device gives the kit at most a set share of its storage (20 GB of a board, 8 GB of an
edge node). If the whole kit fits, the device keeps all of it; if not, it keeps the shared files and the
pages for its own site. The SSDs and the printed binder always hold the whole kit.

## Updating at port

1. **Build ashore** from the commit that will sail. The build covers every card in `manifests/`. It is not
   filtered by the port's admission decisions (D1 and D2) yet. New guests bring their vendor documents with
   their card.
2. **Load over the port network**, not SATCOM. Each device copies the kit into its idle slot
   (`sdv kit install`), checks every checksum there, and only then switches to it. The previous kit stays in the
   other slot, so one command rolls back.
3. **Refresh the copies:** plug in each SSD and run the same install. Reprint the binder pages whose checksums
   changed.
4. **Confirm before sailing:** every device reports the same commit; a device that fails verification keeps
   its previous kit and is named.

## Changes at sea

- **Mission profiles change at sea.** The bridge swaps the active profile, or applies one edited in the
  builder. The governor checks it first and refuses a bad one with the field named, keeping the previous
  profile. Every change is a logged input, so a replay reproduces it.
- **A guest swapped at sea** (the drone, for example) brings its documents on its own media. **Design:** its
  kit page is regenerated from its card on the boards, and the full rebuild waits for the next port. Today a
  page comes only from `sdv kit build`.
- No kit download over SATCOM by default: the kit is for when the link is down.
