# Architecture and data contracts

Status: frozen design, Sat 12:32 PDT. Rewritten by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka) to
match the design freeze ([DESIGN_FREEZE.md](DESIGN_FREEZE.md), approved as WORKLOG DEC-44) and the work split
(DEC-47). Built so far: the data model (`config/assumptions.yaml`, `manifests/schema.json`, six cards, four
priority files, `config/scenarios/scenario_b.yaml`), the test oracles and `tools/physical_account.py`. No
engine code yet. Tasks and owners: [BUILD_PLAN.md](BUILD_PLAN.md).

## Principles

1. **One ledger, one manifest language** (DEC-15). Everything that uses or supplies a resource is described
   the same way and counted in one ledger of margins.
2. **Deterministic core.** The engines are pure functions of their inputs. Same inputs give the same
   decision and the same sentence. A replay matches on every field except wall-clock latency and wall-clock
   timestamps, which go to a separate timing log.
3. **Explain from the binding constraint.** Every decision carries the ledger line that bound it. The
   sentence is a template filled from that line's numbers, never a canned string.
4. **Confirmed inputs only.** Faults enter as debounced, confirmed plant signals. Nothing on the 200 ms,
   2 s or 5 s paths runs a solver or a model (freeze section 5).
5. **Unknown never means safe.** A stale or missing feed falls to its conservative value, and the record
   says so in one sentence (R-458).
6. **Numbers live in data.** Code reads `config/assumptions.yaml`. Every assumed number has a reason, and
   the Physical Account is generated from it.
7. **Names are checked at load.** A card, priority file or scenario that uses a state, position, capability
   or guest the ship profile and the loaded cards do not define is refused with the failing field. The
   previous file keeps running.

## The frozen design, in one picture

```
 config/assumptions.yaml      manifests/G1..G6.yaml       config/missions/*.yaml (the jury swaps this)
        └──────────────────────────┼──────────────────────────────┘
                                   ▼
            LOADER: names checked; a bad file is refused, the old one kept          [Logan]
                                   ▼
   LEDGER (1 Hz) [Logan] ◄──── 1 Hz SNAPSHOT ◄──── SIMULATOR + SHIP STATE (A.6) [Siddharth]
   capacity / committed / free / degraded           seeded, event timeline as data; course, speed,
   per class; power to heat 1:1; cooling(T);        noise, deck, emission, gensets, cooling; transition
   reserve(speed, gensets); lines; mass x k         times; debounced faults; acoustic link
                                   ▼                         ▲
   D1/D2 ADMIT+PLACE   D3 RIGHT OF WAY   D4 SHED LADDER   D5 CREW POLICY   SAFETY TABLE
   enumeration, at     hard limits       precomputed      rule x crew →    200 ms lookups
   the envelope (30 s) first (2 s)       every tick (5 s) policy           (stop, hold, secure)
                                   ▼                         │ COMMANDS [Siddharth defines]
          DECISION RECORD → EXPLAINER (templates over record fields) → DECISION LOG + TIMING LOG
                                   ▼
          ONE SCREEN: Operations (constraint ledger drill-down), Mission compare, Admission review
          CLOCK + REPLAY: hold, jump, identical logs                                [Logan]
          tools/physical_account.py → Annex C;  BOARD INSTRUMENT → measured rows   [board: not assigned]
```

## Components

| Component | Does | Reads | Writes | Owner (DEC-47) |
|---|---|---|---|---|
| Data model | assumptions, cards, priority files, Scenario B timeline, schemas | brief | YAML and JSON files | Logan; built |
| Typed conditions (F2) | a small vocabulary of signals and values for card conditions and hard limits | `assumptions.yaml` `ship_state` | `manifests/schema.json` | Logan |
| Loader | checks every name; refuses a bad file with the failing field and keeps the old one | cards, priority files, scenario | loaded model, or a refusal record | Logan |
| Ship-state machine | A.6 variables with transition times; debounced, confirmed faults; acoustic link state | commands, event timeline | 1 Hz snapshot | Siddharth |
| Simulator | seeded plant and guests on a 1 Hz tick; the event timeline as data; applies the core's commands | scenario, cards | snapshots | Siddharth |
| Command set | the requests the core may send: guest modes, ship-state requests, safety commands | | contract (CON-21) | Siddharth defines |
| Snapshot schema | what the simulator emits each tick | | contract (CON-21) | Logan |
| Ledger | capacity, committed, free and degraded capacity per class, at 1 Hz | snapshot, cards, placement | ledger lines | Logan |
| Ladder core | price list and throttle-only prefix from the cards' modes and the priority file | ledger, priority file | ordered steps | Logan |
| D1 admission, D2 placement | verdict and placement by enumeration, judged at the envelope | ledger, ladder core, positions | decision record | Logan |
| D3 right of way | hard limits first, then mission-weighted value | snapshot, typed conditions, priority file | decision record with cost to the loser | Logan |
| D4 shedding | the ladder precomputed every tick; runs on a confirmed fault | ledger, ladder core | ordered commands, loss per guest | Logan |
| D5 crew policy | per rule and crew level: confirm, standing plan, automatic or forbidden | rules, crew level, priority file | policy per action | Logan |
| Safety-command table | 200 ms answers (A.8), rebuilt every tick next to the D4 ladder | ledger, snapshot, rules | commands | Logan |
| Decision record, explainer | one record per decision; the sentence is a template over its fields | engine outputs | decision log (JSONL), timing log | Logan |
| Clock and replay | ship-time clock that can hold and jump; replay compares logs | event timeline, decision log | match, or the first differing field | Logan |
| Screen | one screen with three views (below) | snapshots, decision log | demo inputs | Logan |
| Physical Account | Annex C from `assumptions.yaml` and the cards | data model, board rows | `docs/PHYSICAL_ACCOUNT.md` | Logan; generator built |
| Board instrument | the same container on the VENTUNO Q, off the demo path ([NODE_B_BOARD.md](NODE_B_BOARD.md)) | replayed timelines | measured Physical Account rows | not assigned |

The design freeze cut three earlier components (DEC-44): the two-node bus with failover, camera virtual
sensors, and the crew rule compiler.

**The screen.** One screen, as the brief asks, with three views. **Operations**: ship schematic, eight
gauges, ship-state row, event log with decisions and rationales; the constraint ledger is its drill-down.
**Mission compare**: two runs on one timeline, one per priority file, so the jury sees the same code run two
ships. **Admission review**: the D1 record for the jury's card, with the one-number edit. The laptop
provides every demo input: the card and its edit, the priority swap, the crew level and injected faults.

## Data contracts

**1. Guest manifest** (`manifests/schema.json`, validated in tests). Per guest: capability name; cooling
type; parts with mass, area, preferred and allowed positions; consumption per class as min, nominal and
peak with duration; a mode ladder from full to off with the share of capability kept; conditions on ship
state per activity; part-of, requires and excludes relations; installation work in port and at sea; a
safety-critical flag; hard limits such as the drone's 20 % battery rule. Adding a guest is adding one YAML
file. Conditions and hard limits use only the typed vocabulary (F2): `course`, `speed_band`, `noise`,
`deck`, `emission`, `ramp`, `deck_machinery`, `wind_kn_max` and `sea_state_max`, with values from
`assumptions.yaml`. A hard limit has the shape `{signal, op, value, then: {action, within_min}}`. Two gaps
to close in T15 ([OPEN_QUESTIONS](OPEN_QUESTIONS.md) #44): the cards need a numeric `speed_kn` beside the
band (G4 recovers at 5 to 12 kn and the A.11 window is 4 to 8 kn, which no A.6 band covers), and one
canonical name per activity (G2 and G3 say `G4.recovering`, G4 defines `launch_recovery`).

**2. Platform assumptions** (`config/assumptions.yaml`). Capacities per class, positions, envelope,
ship-state transition times, crew confirmation times, installation windows, rule parameters. It also holds
fault entry (`fault_entry`: 2 of 3 trip signals, alarm plus flow or delta-T, 1 s debounce, raw-event and
confirmed times), the acoustic link rule (`data.acoustic_link`, drop delay 0 s, 60 s judged latency), the
stale-feed fallback (`stale_feed`), the safety-command table (`safety_commands`) and R3's default confirm
policy (`rules.r3.confirm`), which a priority file may override. A `provenance` map tags each key as brief,
assumed (with a reason) or measured (with a status); tests fail if an assumed number has no reason.

**3. Priority file** (`config/missions/*.yaml`, `config/missions/schema.json`). Capability weights 0 to 1,
keyed by capability name, and the mission-critical guests. Two optional fields (F3):

- `shed_order`: keyed by capability name, like the weights.
- `confirm`: per rule, one value for each crew level 14, 6 and 0, each one of `confirm`, `standing_plan`,
  `automatic` or `forbidden`. `confirm` is refused at 0 aboard, because A.6 makes confirmation impossible
  uncrewed.

No shipped priority file sets `shed_order`; disaster relief already keeps G5 last through
`mission_critical`. Swapping this file is the jury's "different ship" test. The schema and the loader both
check it, and a hostile file is a test: refused with the failing field, the previous file kept.

**4. Snapshot** (1 Hz in ship time; schema owned by Logan, emitted by Siddharth's simulator; CON-21).
Ship time `t_s` and `seq`; ship state (course, speed band and speed in knots, noise, deck, emission, ramp,
deck machinery); gensets online and cooling state, each fault with its raw-event and confirmation times;
seawater temperature, sea state and wind (the water column is a per-scenario statement, `location.layered`,
not a live field); crew aboard; the deck state latched at the last crew
sweep and any deck activity since; acoustic link up or down; each guest's mode, activity and actual draw per
class (for example G3 at depth, G4 airborne with its battery percentage). Every input field carries
`source` (plant, crew report, public data or assumed) and `age_s`. A field older than its limit in
`assumptions.yaml` is replaced by its conservative value.

**5. Commands** (core to simulator; set defined by Siddharth; CON-21). Guest mode changes, ship-state
requests (course, speed, noise) that the simulator carries out with the A.6 transition times, and the
safety commands: stop, hold, secure. Every command carries the `seq` of the decision that sent it.

**6. Event timeline** (`config/scenarios/*.yaml`, read by the simulator). One event per entry: time,
type, payload. Types: `baseline`, `card_presented`, `card_edited`, `priority_swap`, `genset_trip`, `genset_restart`,
`cooling_degraded`, `guest_report` (the drone's battery), `guest_state`, `guest_overconsumption`,
`crew_change`, `deck_report`, `emission_change`, `feed_drop`. An injected fault carries a flag, and the
screen labels it INJECTED.

**7. Decision record** (JSONL, the core output). Fields: `seq, t_s, kind (D1 to D5, safety), trigger
{event seq, raw_event_t_s, confirmed_t_s}, subject, verdict, binding {class, label, capacity, demand,
free, unit}, also_failing [lines], sentence, losses {guest: loss}, cost_to_loser, options [ranked],
placement, order_source (computed or declared), crew_policy, inputs_hash, ceiling_ms`. The `inputs_hash`
covers the timeline, the assumptions, the cards and the priority file. The **timing log** holds, per
`seq`, the wall-clock timestamp and `latency_ms`. The screen, the replay check and the demo all read these
two logs. Replay compares the decision log only.

**8. Ledger line.** `class, label, unit, capacity, demand, contributors {guest: amount}`. Classes: power
total, port line, starboard line, heat, bay units, high slots, flight deck, mass, stability, SATCOM,
backbone, line-of-sight radio, acoustic, compute cores, response time.

## Decision engines: inputs, objective, ceiling

| Engine | Objective | Ceiling | Sentence pattern |
|---|---|---|---|
| D1 admission | verdict at both gensets, the 200 kW reserve and cooling at 30 °C; must survive one genset down by throttling to the 95 kW gate, otherwise yes-if; the raw one-genset-down line always shown (DEC-35); port moves with crane time (DEC-37); links at minimum rates (DEC-38); the seawater tipping point; for yes-if, least mission value lost | 30 s | "Refused: {line} has {free} {unit} free, {guest} needs {need} {unit}." |
| D2 placement | maximise the smallest remaining margin; preferred slots first; leave the most future cards admissible | 30 s | "{part} to {slot}: rejected {slot2}, {line} has {free} {unit} free." |
| D3 right of way | hard limits first, then mission-weighted value | 2 s | "{winner} proceeds: {hard limit or weight}, {loser} loses {cost}." |
| D4 shedding | the precedence below; power and heat rechecked after each step | 5 s first action, 60 s full sequence | "{guest} to {mode}: frees {kW} kW, loses {capability}." |
| D5 crew policy | what a human still confirms at 14, 6 and 0, approved ahead of time | n/a | "At {crew} aboard, {rule} is {policy}." |
| Safety commands | answered from the precomputed table, no solver on the path | 200 ms | "{command} {guest}: {reason}." |

**Binding line.** The binding line is the one with the smallest normalised margin (free minus demand, over
capacity). Every other line over its limit is listed as also failing. A3 is the check: mass binds at
13.015 against 10 t, and cooling at 125 of 120 kW at 30 °C is listed as also failing
([EXPECTED_OUTCOMES.md](EXPECTED_OUTCOMES.md)).

**D4 precedence.** Safety-critical guests are never shed, and hard limits come first. Throttles come
before sheds. Then the priority file's `shed_order`, if it has one. Otherwise the computed price: mission
weight times capability lost per kW freed, non-critical before mission-critical, ties broken by guest id.
The record's `order_source` says which applied. The armed ladder covers current draws and reservations.

**Scenario B checks** (DEC-40, [EXPECTED_OUTCOMES.md](EXPECTED_OUTCOMES.md)). Siddharth decides minute 12
as owner of the scenario timing (DEC-51), and DEC-40 stands until he does.

- Minute 8, rescue: G3's leg is aborted and it holds at sea. It is recovered over the ramp only after G4
  has landed, because the flight deck and the ramp are mutually exclusive.
- Minute 12: the trip holds under both files against the 95 kW power limit, with 0 steps. Survey loads
  49.5 kW (48 on the chilled-water loop; G1's 1.5 kW is air-cooled, DEC-63): G4 is airborne at 2 kW with no
  charge to throttle, so the first armed step is G5 full to low power (frees 37 kW, 0.0038 per kW). Rescue
  loads 82.5 kW (81 on the loop) with G4's 35 kW reserved, and the first armed step is also G5 full to low
  power (0.0189 per kW).
- Minute 19, INJECTED pump fault (loop limit 75 kW against the loop's 81 kW: cooling binds while the bus is
  at 82.5 of 95): survey slows G4's charge from 35 to 10 kW (loop 56 kW); rescue takes G5 from 45 to 8 kW
  (loop 44 kW).

**Time base.** The ledger ticks at 1 Hz in ship time. Decisions and safety commands run when an event
arrives, not at the next tick. Latency is measured in wall-clock time. The demo clock can hold and jump.
Proposal for CON-21: A.8's 5 s first action counts from the raw plant event, so debounce and confirmation
must fit inside it.

**Fault entry.** A genset trip counts when 2 of 3 signals agree (relay flag, kW near zero, frequency dip).
A cooling fault needs the plant alarm plus flow or delta-T.

**Acoustic link.** Up only while the course is steady, the noise is quiet and no deck machinery runs. It
drops after an assumed delay, so a hold-depth command must reach G3 before a manoeuvre starts.

**Admission override** (DEC-32). A captain may force a refused admission for extreme situations. It needs
a human, so it is not available at 0 aboard. The record keeps the binding line, is marked overridden, and
names who overrode and why.

## Open decisions for the team

All open questions, with proposals, are in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md). The ones that shape
these contracts:

1. The snapshot fields and the command set must agree before either side builds on them (CON-21).
2. Numeric `speed_kn` and canonical activity names in the typed vocabulary (#44).
3. Whether `mission_critical` stays keyed by guest id or moves to capability names (#45).
4. Emission silence with G4 airborne: which wins, and what the record states as the cost (#42).
5. Who builds the board instrument (#46).
