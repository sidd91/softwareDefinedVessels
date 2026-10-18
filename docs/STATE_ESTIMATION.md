# State estimation: the inputs contract

Status: proposal, Sat 2026-10-17. Written by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka), who now
owns the inputs: everything that goes into state estimation. Nothing here is decided until a WORKLOG `DEC-`
row says so. It fills ARCHITECTURE data contract 4 (the snapshot) for CON-21 and follows the design freeze:
inputs are confirmed, debounced plant signals, and unknown never means safe.

**Built** (Sat 14:45): `src/sdv/estimator.py`, `Estimator(scenario, mission, variant).step(frame)`, the nine
steps below. `tests/test_estimator.py` steps a labelled test double of the simulator (`tests/support/sim_stub.py`,
built from this contract only) through Scenario B with the scripted core and reproduces every snapshot fixture;
D3 and D4 give the same records on its snapshots as on the fixtures. `since_t_s` is the tick the value last
changed (a number in transition changes every tick and settles on the end tick); the fixtures' hand annotations
miss a few changes, listed in the test.

**`config/signals.yaml` is the only authority** for signal names, types, feeds, fallbacks, derivations,
activities, event payloads, the `sim.step` arguments, the drafted fault signatures and transition times, the
Scenario B starting state and script, and the timeline mapping. This document explains the rules; it does not
repeat the tables. The other files are derived from it or checked against it:

| File | What it is |
|---|---|
| `config/frame.schema.json` | what the simulator hands the estimator each tick (`argos-frame/1`), plus `$defs.command` and `$defs.input`, the two `sim.step` argument lists; generated |
| `config/snapshot.schema.json` | what the estimator hands the core each tick (`argos-snapshot/2`); generated |
| `tools/gen_snapshot_schema.py` | `signals.yaml` to both schemas; `--check` fails if either is out of date |
| `tools/build_snapshot_fixtures.py` | builds the Scenario B fixtures from `baselines.scenario_b` and compact specs; holds `canonical()`, the log serializer |
| `tests/fixtures/frames/`, `tests/fixtures/snapshots/` | one frame and the snapshot it produces, per fixture |
| `tests/test_snapshot_contract.py` | the schemas and fixtures equal the generators' output; every derived value recomputed from config and checked against the oracles |

## The boundary with Siddharth's simulator

**The simulator emits** what the ship's instruments would read, and nothing they would not. It owns the A.6
variables and their transition times (`transition_drafts`), so it reports their values and any change under
way. It emits raw fault signals, not verdicts, following `fault_signatures`: a genset trip at tick t sets the
relay flag, drops that genset to 0 kW, holds the bus at 59.6 Hz and puts the other genset at its share of the
bus load, capped at its rating (`fault_signatures.bus_load`: hotel 400 kW less the 150 kW trip shed, plus 55 kW
auxiliaries, plus the guests' metered kW; 354.5 kW at minute 12, 387.5 kW at minute 19, never above 450). The
estimator confirms at t + 1 on two votes. A pump fault sets the alarm, stops the pump, drops flow to 50 %,
warms the supply to 8.5 °C and opens delta-T to 9 °C. It applies the core's commands and the laptop inputs,
and reports the result in later frames. It must set `deck_machinery` while G2 winches or G4 launches or
recovers, and `ramp` while G3 launches or recovers.

**The estimator derives** every signal whose producer is `estimator`: confirmed faults, gensets online,
cooling state, the acoustic link, heading freedom, deck machinery permitted, flight-deck use, the deck latch,
G4's land-by deadline, over-draw, mode end times and the capacity of each live class. For `ramp` and
`deck_machinery` it reads the simulator's value and the running activities' `effects`, takes the worse of the
two and logs a mismatch, so a simulator value that forgets an activity can only make the field more cautious.

**Commands are Siddharth's to define** (contract 5). `signals.yaml` `commands` holds the drafts the core and
the fixtures use until he settles them. The estimator sends none.

This moves two things from his side to Logan's: BUILD_PLAN T4 and the ARCHITECTURE component table put
"debounced faults" and "the acoustic link" in his state machine (CON-22). It also asks him to emit values A.6
does not list. Both need his yes before either side codes faults (the checklist under Open).

## The frame and `sim.step`

The interface is an in-process Python call, with no thread and no socket:

```python
sim = Simulator(scenario, mission, seed, variant)              # variant: "default" or a baselines variant
frame = sim.step(tick: int, commands: list, inputs: list) -> dict   # one argos-frame/1 object
```

- **Presence.** A 1 Hz signal is in every frame. An event-rate signal (G3's acoustic messages, G4's battery
  report and launch time) is in the frame only on the tick its report arrives. An hourly signal is present on
  the tick of its reading. A dropped feed's signals are **left out**, never sent as null. A null value means
  the instrument reads "nothing" (no crew report).
- **Reading time is arrival time.** Every reading's `t_s` is the frame's tick, so a report is age 0 on
  arrival. A message's latency (G3's acoustic 10 to 60 s) is inside the simulator, which decides on which
  tick it arrives; the estimator never back-dates a reading. A crew answer also carries `reported_t_s`, the
  `t_s` of the input that gave it, kept while the simulator re-emits the answer every tick.
- **Shape.** `signals` holds every non-guest reading by name; `guests.Gx` holds that guest's readings by key.
  Each reading is `{value, source, t_s}`, plus `transition` while a change is under way and `reported_t_s`.
- **Transitions.** During a change the simulator reports the instantaneous value each tick, linear from the
  start value to `transition.to` over `[started_t_s, expected_end_t_s]`. An enum keeps its old value until the
  end tick. `latest_end_t_s` is the slow end of the A.6 range. A genset restart puts a transition on
  `gensets_online` from the restart event.
- **Commands** (`step.commands`, typed by `$defs.command`). Every command from every decision run on snapshot
  n − 1, in record order, each `{seq, kind, args}` with `seq` the decision record that sent it. The drafted
  kinds: `set_mode`, `ship_state` (course, speed, noise, carried out with the transition times),
  `clear_deck`, `guest_command` (G3's hold or abort, relayed acoustically), `bridge_request` and
  `bridge_close`.
- **Inputs** (`step.inputs`, typed by `$defs.input`). Every laptop input stamped n whose event has
  `to: simulator`, in input-log order, each `{t_s: n, type, injected, payload}`. These go to the simulator:
  injected faults and over-consumption, feed drops, crew changes, deck reports and sweeps, bridge answers,
  standing plans, emission changes, guest requests. These go **only to the core**, which handles and logs them
  at tick n and never passes them on: card presented, card edited, priority swap, an edited profile applied at sea and safety requests (the
  answer is a command applied at n + 1). The simulator applies an input on its own tick: a crew answer becomes
  a laptop-feed signal, an injected fault becomes its fault signature, a `feed_drop {feed, until_t_s}` leaves
  that feed's signals out. The estimator never fakes a drop. Laptop signals are state: the simulator
  re-emits them every tick.
- **Events and order.** Within tick n the simulator applies the commands, then the timeline events due at n,
  then the inputs, and then emits the readings. `frame.events` lists every timeline event and input it
  applied at n, `{t_s: n, type, origin, injected, payload}`, the input's payload unchanged and `origin:
  laptop`.
- **Bridge requests.** A decision that needs the bridge sends `bridge_request {request_seq, rule,
  asked_t_s}`, with `asked_t_s` the tick of the snapshot it ran on (480), not the tick the command lands (481).
  From frame 481 `bridge_requests` holds `{request_seq, rule, state: pending, asked_t_s, answered_t_s: null}`.
  The answer is the laptop input `bridge_answer {request_seq, answer}`: the simulator sets `state` and
  `answered_t_s` to the input's tick. In a scripted run the input script sends it at `asked_t_s +
  seed_pins.confirm_min` (540). The core sends `bridge_close {request_seq}` once the decision has closed (R3:
  G4 landed, snapshot 1020), and the entry leaves the list at 1021. A pending request older than its crew
  level's `wait_s` counts as no.
- **Scenario constants.** The water column (`layered_water`) is a run constant, `run.constants`, confidence
  `assumed`, never stale. Seawater temperature and sea state are hourly readings with their real age: in
  Scenario B the scenario value is read at tick 0, so it is 1141 s old at minute 19.

### The run baseline

The starting state is data, not code: `baselines.scenario_b` gives the seed, the value at tick 0 of every raw
signal the tick-0 frame carries (`start`, including state from before tick 0: `G4.launched_t_s` −3952,
`last_sweep`), the series a value follows (the ship's wind, 18 kn rising to 22 kn by minute 8; G4's range,
12 km to 11 km by minute 8, then closing to 0 at the landing) and named variants. The simulator echoes the
run's start in the tick-0 `baseline` event, `{note, variant, start}`, typed by `$defs.start`, and the snapshot's
`run.variant` names it. The `crew0` variant starts with 0 aboard, the deck swept clear at −4200 s and no deck
activity since: the starting state a `deck_sweep` input cannot express, because an input's `t_s` is its tick.

### Timeline to frame

Scenario events and seed pins are **absolute ship times the simulator honours**: an event at `t_min` m is
applied at tick `ceil(60 × m)`, and a triggered event (the pump fault, 2 min after G4 lands) on the first tick
its trigger plus delay is met. DEC-40's 8 + 1 + 4 + 4 = 17 counts from the decision at 480, so the one-tick lag
of the minute-8 commands (applied at 481 and 541) comes out of G4's final approach: the deck clears at 781 and
G4 lands at 1020, 239 s later. If the run's decisions have not cleared the recovery by a pinned landing, the
simulator skips the event and logs it.

`timeline_mapping` says how each scenario event becomes a frame event, and the test builds every one and
validates it. Copied as they stand the scenario keys do not validate, so the mapping is required:

| Scenario event | Frame event payload | Not in the payload |
|---|---|---|
| `baseline` | `note`, the run's `variant` and `start` | |
| `guest_report` G4 | `{guest, fields: {battery_pct: 18}}` | `wind_kn`: the anemometer carries wind |
| `genset_trip` | `{genset: 2, confirmed: true}` | `gensets_online`, `cooling`: the estimator's outputs, checked against the snapshot |
| `guest_state` G4 | `{guest, activity: landed, mode: fast_charge}` | `state` is split |
| `cooling_degraded` | `{pump: 1, factor: 0.6, confirmed: true}`, event `injected` | `trigger` (when it fires), `load_modes` (checked by the ledger test) |
| `genset_restart` | `{genset: 2, expected_end_t_s: tick + 600}` | `gensets_online`, `optional` |

## The clock and the loop

The core owns the loop:

```
for n = 0, 1, 2, …:
    frame      = sim.step(n, commands_from_snapshot(n - 1), simulator_inputs_stamped(n))
    snapshot_n = estimate(frame)                 # reads only the frame log and the previous estimate
    handle the core-only inputs stamped n; run every decision snapshot_n triggers, each to a record
    # only then does tick n + 1 start
```

- **Tick and ship time.** One tick is one snapshot. Tick n is at `t_ship_s` = n, so 1 Hz means one tick per
  ship second. Ship time is the only clock the estimator and the decisions read: ages, stale limits, debounce,
  restore hold, transition ends and deadlines.
- **Commands land on the next tick.** Commands from any decision on snapshot n are applied by the simulator in
  frame n + 1, whatever the wall-clock latency. A safety request arriving between ticks is answered from the
  table built at the last completed tick n, logged with n, and its command is applied at n + 1. In ship time a
  decision's latency is therefore always 0 ticks and its actuation lands one tick later. Each decision record
  names that tick in `applies_at_tick`.
- **Wall time** appears only in the timing log: per record `latency_ms` against `ceiling_ms`, and per tick the
  pacing. It never appears in a frame, a snapshot or a record.
- **Pacing.** Demo pacing is x12: the loop sleeps until each tick's wall deadline, 83 ms apart, a ship minute in
  5 s. If compute overruns a deadline, ship time slows and the overrun goes to the timing log. A tick is never
  skipped. Hold stops the loop; a jump runs every tick unpaced up to the target. Unpaced replay runs as fast as
  the host allows.
- **A.8 checks.** In ship time: the tick the first shed command is applied must be no later than
  `raw_event_t_s + 5` (`first_shed_due_t_s`). With synchronous ticks that is `confirmed_t_s + 1`: the trip at
  720 s confirms at 721 s and the first shed lands at 722 s, inside 725 s. The 60 s full sequence counts the
  same way. Separately, in wall time, each decision's compute is checked against its ceiling (200 ms, 2 s, 5 s,
  30 s) and against one tick period when paced. The two are never added together.
- **Watchdog.** When `decision_watchdog` cuts a decision off at its wall ceiling, the record says
  `timed_out: true` and the input log keeps the outcome, so a replay applies it instead of re-timing.

## Each tick, in order

1. **Read** frame n. A name that is not in `signals.yaml` is refused and logged. A value outside its type or
   range counts as missing; it is never clamped. The `kw_actual` ranges run to twice the card's top mode, so an
   over-draw stays a reading.
2. **Age.** A raw field's `age_s` is ship time now minus its reading's `t_s`. A signal with no reading yet has
   value null and `age_s` null, confidence `assumed` (G4's battery before minute 8).
3. **Feed health.** A 1 Hz or hourly signal is stale when its own age is above its feed's `stale_after_s`
   (3 s for most feeds, 10 s for G4's telemetry, 3 h for public data). An event-rate signal keeps its report
   age but is stale only when its feed is, so G4's minute-8 battery report is 241 s old at minute 12 and still
   fresh: the telemetry heartbeat (`G4.activity`, 1 Hz) is. **G3** sends a status message every 60 s while the
   acoustic link is up (`cadence_s`, counted from its previous message or from the link coming up), and a reply
   to a command when it is ready: 0, 60, …, 480, the hold acknowledgement at 510; the next, due at 570, is lost
   because the link drops at 541. Its feed is stale only while `acoustic_link_up` is true, after 120 s (two
   missed messages) of link-up silence; while the link is down by design G3 is out of contact, not stale. The
   snapshot's `feeds` block shows each feed's health and any injected drop.
4. **Fall back.** A stale field takes its `fallback`, marked `substituted` with the last value, its time, the
   rule and the stage. The rules that bind everywhere (`fallback_policy`):
   - **D4 never acts on a substituted value.** It acts on confirmed faults and on over-commitment the ledger
     computes only from fresh inputs. A fallback may tighten admission and arm the ladder: a stale genset feed
     counts as one genset down for D1 and the armed ladder, and sheds nothing.
   - **Two stages** for `speed_kn`, `wind_kn` and `wind_from_deg`: the last value, substituted, for a 30 s
     grace, then the fallback value. A null `speed_kn` or `wind_from_deg` fails every numeric condition.
   - **Unknown never means safe, even against a hard limit.** While G4 is below 20 %, D5 asks the landing
     officer for wind and deck; a fresh report (`hlo_wind_kn`, `hlo_deck_report`) replaces the stale value,
     stage `crew_report`, and the record names it. At 0 aboard the closure stands and the record states the
     cost to G4.
   - **Lifting.** A fallback lifts on the first fresh frame of its feed: the field's `stale` and `substituted`
     end on the same tick, and the feed's `stale` with them. There is no lift window. A flapping feed can flip
     D1's limits tick by tick, but it sheds nothing, because D4 never acts on a substituted value.
   - **Keep, don't invent.** G3's activity keeps its last report (`surveying` only if that was the last
     report). G4's activity keeps its last value (`airborne` only if it was airborne or recovering). A
     `by_use` fallback keeps the last good value and each consumer applies its own entry.
5. **Confirm faults, per subject** (`genset_1`, `genset_2`, `chw_pump_1`, `chw_pump_2`). A vote listed in
   `shared` reads a plant-wide signal (the bus frequency, the loop's flow and delta-T) and counts for a
   subject only while that subject has one of its own votes, so the healthy pump at minute 19 holds no fault.
   `raw_event_t_s` is the first tick one of the subject's own votes is true. `confirmed_t_s` is the first tick
   t on which the vote count meets the rule on every tick of `[t − 1, t]`. A genset trip needs 2 of 3 votes;
   cooling needs the pump alarm or a stopped pump, plus low flow or high delta-T. A vote that drops sooner
   cancels the pending fault (logged). A pending fault whose votes go stale is **held**, state `held_stale`,
   and confirms if the feed returns showing it still true; meanwhile the ladder stays armed and the record
   says the fault is unconfirmed because the feed is stale. A recovered genset or pump must read healthy 60 s
   before any guest is restored.
6. **Derive ship state.** The guest reserve comes from `speed_kn`: inside an A.6 band, that band's reserve; in
   a gap, the lower of its two neighbours (200 kW for 0.5 to 3 kn, 200 for 5 to 10, 150 for 14 to 18), so a gap
   never loosens the budget. `speed_band` is a display label. The acoustic link is up only while every
   `up_when` condition holds and the water column is not layered. The four effect fields (`ramp`,
   `deck_machinery`, `heading_free`, `flight_deck_ops`) carry `by`, the guests whose running activity sets them.
   **A guest's own conditions are evaluated against the state less its own effects**, so G4's recovery does not
   block its own turn into the wind and G3's ramp work does not block its own recovery.
   `deck_machinery_permitted` is emission normal and no running activity listing `deck_machinery` in its
   `excludes`. `deck_latched_clear` is the last crew sweep clear with no deck activity since (G4's own launch
   excepted).
7. **Derive deadlines.** G4's land-by is the earlier of launch plus 90 min and the 20 % crossing plus 12 min.
   A report below 20 % dates the crossing back at the slowest drain, 1.11 %/min: at minute 8, 18 % gives
   480 − 2 / 1.11 × 60 = 371.9 s and a land-by of 1091.9 s, **minute 18.2** (EXPECTED_OUTCOMES). While the
   telemetry feed is stale and the last report is at or above 20 %, the crossing is projected forward at the
   fastest drain (1.5 %/min, assumed): the earliest crossing the report allows (R-458, DEMO_SCRIPT "Data feed
   drops"). A deadline may move earlier, never later. Mode end times come from the card's `duration_s`.
8. **Derive capacity** of the live classes only: power, the two lines, heat, SATCOM, radio and acoustic, plus
   `shed_ceiling_kw` = min(power, heat) − 5 kW. A link that is 0 by rule (acoustic down, silence) says so in
   `zero_by_rule`. `degraded_by` names each cause.
9. **Emit** snapshot n.

**Confidence and age of a derived field.** It is computed this tick: `age_s` 0. Its confidence is
`substituted` if any of its `inputs` is, `confirmed` if it is a confirm-rule output while a fault of that rule
is confirmed, and otherwise the weakest of its inputs; with only config behind it, `assumed`. A raw field's
confidence comes from its source: plant `measured`; guest, crew, laptop and public data `reported`; scenario
`assumed`. The levels, weakest first: `substituted`, `assumed`, `reported`, `measured`, `confirmed`. The
ARCHITECTURE working tree dropped confidence from contract 4; this contract keeps it (open item 2).

## What comes out, and what does not

One JSON object per tick: `run` (contract, scenario, variant, mission, seed, `tick`, `t_ship_s`, installed
guests, run constants), the groups `plant`, `ship_state`, `environment`, `links`, `crew`, `guests`, `capacity`,
then `feeds`, `faults` and the `events` applied at this tick. Every field is `{value, source, age_s,
confidence, stale}`, plus `since_t_s`, `reported_t_s`, `transition`, `substituted` or `by` where they apply.
Unknown fields are refused. Who reads each field is its `read_by` in `signals.yaml`.

**Not in the snapshot:**

- **Committed, free and reservations.** These are ledger lines (contract 8). The ledger takes, per guest, the
  larger of its mode's declared kW, the kW the core reserves for it (from the decision log:
  `{Gx: {mode, kw, since_t_s}}`) and its fresh `kw_actual`. Under sar at minute 12 that is G4 at max(2, 35):
  1.5 + 1 + 35 + 45 = 82.5 kW against 95, 12.5 spare, as the oracle says; the chilled-water loop carries 81 of it
  (G1 is air-cooled), judged on its own line. Demand on a link that is 0 by rule is
  buffered, with free 0 and no margin computed. Over-consumption shows as `Gx.overdraw_pct`; above 5 % for 10 s
  (assumed) it raises `guest_overconsumption`.
- **Static classes**: backbone, compute cores, mass, bay units, high slots, flight deck and stability come from
  `assumptions.yaml`, the cards and the placement, in the ledger.
- **The peak budget and heat inertia** (+250 kW for 60 s, +30 kW for 60 s every 10 min): no decision credits
  them (`admission.peak_credit_kw` 0; D4 sheds to the steady ceiling). Crediting them would add
  `capacity.power_peak` and `capacity.heat_inertia` with their last-used times.

## Replay

1. Every frame is written to a **frame log** (JSONL), and every laptop input to the **input log**. Estimator
   and core replay read those two logs, so a replay never needs the simulator. Re-running the simulator with
   the same seed and checking it reproduces the frame log is a separate check, Siddharth's.
2. Every log line is written with `canonical()` (`tools/build_snapshot_fixtures.py`): numbers rounded to 0.1
   (kW, s, kn, °C, Hz, %), a whole number written as an integer so 18 and 18.0 give the same bytes, sorted
   keys, no whitespace. The fixture files are pretty-printed for review instead; the tests compare parsed
   objects and check that `canonical()` is stable on every fixture. The fixtures hold rounded values (371.9,
   1091.9) and the tests compare them exactly.
3. A timed-out decision replays its logged outcome. A safety request replays after the decisions of the tick it
   was logged with.
4. A replay therefore reproduces every snapshot and every record byte for byte; only the timing log differs. The
   replay check compares the canonical snapshots and decision log and reports the first field that differs.
   `inputs_hash` (contract 7) should add the seed, `signals.yaml`, the frame log and the input log.

Mission compare is two runs on one timeline: two frame logs that diverge after minute 8, and two decision logs.

## Names against ARCHITECTURE

The snapshot has `tick` (an integer) and `t_ship_s` (= tick); contract 4 calls the latter `t_s`. A decision
record's `t_s` is the `t_ship_s` of the snapshot it ran on, and `seq` is only the decision and record counter
that commands carry. For a later ARCHITECTURE edit, once the agents editing it now are done: contract 4 to
these names; contract 5 to the command envelope `{seq, kind, args}` once Siddharth settles it; contract 7 to
add `applies_at_tick` and `timed_out` to the record and to replay "snapshots and decision log"; committed and
free to the ledger only; and `feed_drop`'s payload to `{feed, until_t_s}`.

## Fixtures (Scenario B, seed 0)

| Fixture | Shows |
|---|---|
| `survey_m00` | the start, every reading the baseline's `start` (G1 listening on the mast at 1.5 kW, DEC-63); no battery report yet, land-by 1448 s from endurance, `assumed` |
| `survey_m08` | G4 reports 18 %: crossing 371.9 s, land-by 1091.9 s (minute 18.2) |
| `survey_m08_crew0` | the `crew0` variant: deck latched clear at the last sweep, R3 automatic |
| `survey_m09_stale_g4_telemetry` | injected drop: telemetry 15 s old, battery stale with its feed, land-by kept and named |
| `survey_m10_stale_genset_feed` | injected drop: power management feed 4 s old, one genset down for D1 only, nothing shed; G4's 120 s old report still fresh |
| `survey_m12`, `sar_m12` | trip at 720 s confirmed at 721 s; the ledger gives 49.5 of 95 kW (survey) and 82.5 of 95 kW (sar, with the reservation), 48 and 81 of it on the loop |
| `survey_m19`, `sar_m19` | injected pump fault: heat 80 kW, a 75 kW loop limit against the loop's 81 kW (82.5 kW on the bus, G1's 1.5 air-cooled); G3 631 s silent but not stale |

**The script after minute 8** is `baselines.scenario_b.script`: the commands by the snapshot they are decided
on, the inputs by tick, and the outcomes. The decisions are the core's; the times are pins, drafts or
assumptions, and each says which. D3's decision at 480 tells G3 to hold depth (survey) or abort its leg (sar)
and asks the bridge (request 1); G3 acknowledges at 510 (a 30 s round trip, assumed); the bridge confirms at
540 (the seed's 1 min); the turn into the wind and the deck clear land at 541; the ship goes from 3 to 5 kn
over 2 min (latest 3), inside the slow band, so there is no A.6 band change (EXPECTED_OUTCOMES minute-8 cost;
A.6 gives no time for a change inside a band, so 2 and 3 min are assumed); the deck clears by 781 (seed
4 min); G4 is in launch and recovery from 781 and lands at 1020 (the pin); the core closes request 1 at 1021.
Under survey only, the survey resumes on snapshot 1080 (assumed: 60 s to secure G4): noise normal at once,
course steady and 3 kn by 1201. The pump fails at 1140 and D4's mode change lands at 1142.

## Open, for a DEC row

**Agree with Siddharth.** He owns the simulator, the ship-state machine, its transition times and the
commands (DEC-47). Before either side codes against this contract he needs to say yes, in a WORKLOG `DEC-`
row, to exactly these:

- [ ] **CON-22, the split.** The estimator confirms faults (per subject, with shared votes) and derives the
      acoustic link; the simulator emits raw signals only.
- [ ] **The extra signals.** He emits values A.6 does not list: `ramp`, `deck_machinery`,
      `deck_activity_since_sweep`, `radar_transmitting`, per-zone deck, numeric `speed_kn`, `wind_from_deg`,
      `G4.launched_t_s`, transitions with expected and latest ends, frames that leave out a dropped feed, and
      the deck fields set while the activities run.
- [ ] **The `sim.step` call and the frame**: `Simulator(scenario, mission, seed, variant)`, `step(tick,
      commands, inputs)`, the order inside a tick, reading time = arrival tick, G3's 60 s cadence, the echo of
      inputs in `frame.events`.
- [ ] **The input shape** `{t_s, type, injected, payload}` and the routing: which laptop inputs reach him
      (`to: simulator`) and which stay in the core.
- [ ] **The command drafts** (`commands`): the envelope `{seq, kind, args}` and the six kinds, including
      `bridge_request` with the core's `asked_t_s` and `bridge_close`; he may rename or replace them.
- [ ] **The fault signatures** (`fault_signatures`): the trip at 59.6 Hz with the other genset on the capped
      bus load, the pump fault at 50 % flow, 8.5 °C supply and +9 °C, the false alarm, the restart.
- [ ] **The transition durations** (`transition_drafts`): in-band speed change 120 s (latest 180), course
      settle 120 s (180), deck clear 240 s (300), the noise rule, genset restart 600 s (900), G3's 30 s round
      trip.
- [ ] **The timeline rules**: pins are absolute ticks he honours (G4 lands at 1020, the approach absorbs the
      lag), and `timeline_mapping` with its choices (genset 2, pump 1).
- [ ] **The baseline**: `baselines.scenario_b` start, series and the `crew0` variant as his initial state.

Then, for Logan and the team:

1. Keep `confidence` in contract 4 as the five-level scale.
2. G4's battery cadence: one report at minute 8, as in the brief. A streamed battery would show the crossing
   at minute 6.2 and move the decision earlier.
3. Move the assumed values in `signals.yaml` `pending_moves` into `assumptions.yaml` and the Scenario B ones
   (`baselines.scenario_b`, the mapping's choices) into `config/scenarios/scenario_b.yaml`, with provenance, so
   they reach the Physical Account, once the agents editing those files are done.
4. The over-consumption tolerance (R-082): proposed 5 % for 10 s.
5. The fallback lift is now the first fresh frame. If the demo shows a feed flapping, add a hold as a new
   substituted stage and a fixture, not a counter outside the fields.
