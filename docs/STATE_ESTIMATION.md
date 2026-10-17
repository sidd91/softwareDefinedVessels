# State estimation: the inputs contract

Status: proposal, Sat 2026-10-17. Written by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka), who now
owns the inputs: everything that goes into state estimation. Nothing here is decided until a WORKLOG `DEC-`
row says so. It fills ARCHITECTURE data contract 4 (the snapshot) for CON-21 and follows the design freeze:
inputs are confirmed, debounced plant signals, and unknown never means safe.

**`config/signals.yaml` is the only authority** for signal names, types, feeds, fallbacks, derivations,
activities and event payloads. This document explains the rules; it does not repeat the table. The other files
are derived from it or checked against it:

| File | What it is |
|---|---|
| `config/frame.schema.json` | what the simulator hands the estimator each tick (`argos-frame/1`); generated |
| `config/snapshot.schema.json` | what the estimator hands the core each tick (`argos-snapshot/2`); generated |
| `tools/gen_snapshot_schema.py` | `signals.yaml` to both schemas; `--check` fails if either is out of date |
| `tools/build_snapshot_fixtures.py` | builds the Scenario B fixtures from compact specs |
| `tests/fixtures/frames/`, `tests/fixtures/snapshots/` | one frame and the snapshot it produces, per fixture |
| `tests/test_snapshot_contract.py` | the schemas and fixtures equal the generators' output; every derived value recomputed from config and checked against the oracles |

## The boundary with Siddharth's simulator

**The simulator emits** what the ship's instruments would read, and nothing they would not. It owns the A.6
variables and their transition times, so it reports their values and any change under way. It emits raw fault
signals, not verdicts, following `fault_signatures` in `signals.yaml`: a genset trip at tick t sets the relay
flag, drops that genset to 0 kW and holds the bus at 59.6 Hz, so the estimator confirms at t + 1 on two votes;
a pump fault sets the alarm, stops the pump, drops flow to 50 % and opens delta-T to 9 °C. It applies the
core's commands and the laptop inputs, and reports the result in later frames. The deck fields it reports
(`ramp`, `deck_machinery`, the deck zones) are the truth: it must set `deck_machinery` while G2 winches or G4
launches or recovers, and `ramp` while G3 launches or recovers.

**The estimator derives** every signal whose producer is `estimator`: confirmed faults, gensets online,
cooling state, the acoustic link, heading freedom, deck machinery permitted, flight-deck use, the deck latch,
G4's land-by deadline, over-draw, mode end times and the capacity of each live class. It checks the
simulator's deck fields against the running activities' `effects` and logs a mismatch; where they disagree it
takes the worse of the two.

**Commands are Siddharth's to define** (contract 5). The estimator sends none.

This moves two things from his side to Logan's: BUILD_PLAN T4 and the ARCHITECTURE component table put
"debounced faults" and "the acoustic link" in his state machine. It also asks him to emit values A.6 does not
list. Both need his yes in a WORKLOG row before either side codes faults (open item 1).

## The frame

The interface is an in-process Python call, with no thread and no socket:

```python
frame = sim.step(tick: int, commands: list, inputs: list) -> dict   # one argos-frame/1 object
```

- **Presence.** A 1 Hz signal is in every frame with `t_s` = tick. An event-rate signal (G3's acoustic
  messages, G4's battery report and launch time) is in the frame only on the tick its report arrives, with
  `t_s` = the report time. An hourly signal is present on the tick of its reading. A dropped feed's signals
  are **left out**, never sent as null. A null value means the instrument reads "nothing" (no crew report).
- **Shape.** `signals` holds every non-guest reading by name; `guests.Gx` holds that guest's readings by key.
  Each reading is `{value, source, t_s}`, plus `transition` while a change is under way and `reported_t_s` for
  a crew answer (the time it was given; `t_s` is the relay time).
- **Transitions.** During a change the simulator reports the instantaneous value each tick, linear from the
  start value to `transition.to` over `[started_t_s, expected_end_t_s]`. An enum keeps its old value until the
  end tick. `latest_end_t_s` is the slow end of the A.6 range. A genset restart puts a transition on
  `gensets_online` from the restart event (5 to 15 min).
- **Laptop inputs take one path.** The core logs each laptop input at tick n in the input log and passes it to
  `sim.step(n, …)`. The simulator applies it: a crew answer becomes a laptop-feed signal, an injected fault
  becomes its fault signature, and a `feed_drop {feed, until_t_s}` leaves that feed's signals out of the frames.
  The estimator never fakes a drop. Laptop signals are state: the simulator re-emits them every tick.
- **Events.** The frame's `events` are the timeline and laptop events the simulator applied at this tick, with
  payloads typed per `signals.yaml` `events`. An event at `t_min` m is applied at tick `ceil(60 × m)`; a
  triggered event (Scenario B's pump fault, 2 min after G4 lands) fires on the first tick its trigger plus
  delay is met.
- **Scenario constants.** The water column (`layered_water`) is a run constant, `run.constants`, confidence
  `assumed`, never stale (assumptions `data.acoustic_link.layered_water`). Seawater temperature and sea state
  are hourly readings with their real age: in Scenario B the scenario value is read at tick 0, so it is 1141 s
  old at minute 19.

## The clock and the loop

The core owns the loop:

```
for n = 0, 1, 2, …:
    frame      = sim.step(n, commands_from_tick(n - 1), inputs_stamped(n))
    snapshot_n = estimate(frame)                 # reads only the frame log and the previous estimate
    run every decision snapshot_n triggers, each to a record
    # only then does tick n + 1 start
```

- **Tick and ship time.** One tick is one snapshot. Tick n is at `t_ship_s` = n, so 1 Hz means one tick per
  ship second. Ship time is the only clock the estimator and the decisions read: ages, stale limits, debounce,
  restore hold, transition ends and deadlines.
- **Commands land on the next tick.** Commands from any decision on snapshot n are applied by the simulator in
  frame n + 1, whatever the wall-clock latency. A safety request arriving between ticks is answered from the
  table built at the last completed tick n, logged with n, and its command is applied at n + 1. In ship time a
  decision's latency is therefore always 0 ticks and its actuation lands one tick later. Each decision record
  carries the tick its commands are applied at.
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
2. **Age.** A raw field's `age_s` is ship time now minus its reading time. A signal with no reading yet has
   value null and `age_s` null, confidence `assumed` (G4's battery before minute 8).
3. **Feed health.** A 1 Hz or hourly signal is stale when its own age is above its feed's `stale_after_s`
   (3 s for most feeds, 10 s for G4's telemetry, 3 h for public data). An event-rate signal keeps its report
   age but is stale only when its feed is, so G4's minute-8 battery report is 241 s old at minute 12 and still
   fresh: the telemetry heartbeat (`G4.activity`, 1 Hz) is. G3's acoustic feed goes stale only while
   `acoustic_link_up` is true, after 120 s of link-up silence; while the link is down by design G3 is out of
   contact, not stale. The snapshot's `feeds` block shows each feed's health and any injected drop.
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
   - **Lifting.** A fallback lifts after 3 consecutive fresh frames of its feed, so a flapping feed cannot flip
     D1 limits every tick.
   - **Keep, don't invent.** G3's activity keeps its last report (`surveying` only if that was the last
     report). G4's activity keeps its last value (`airborne` only if it was airborne or recovering). A
     `by_use` fallback keeps the last good value and each consumer applies its own entry.
5. **Confirm faults.** `raw_event_t_s` is the first tick any vote for that subject is true. `confirmed_t_s` is
   the first tick t on which the vote count meets the rule on every tick of `[t − 1, t]`. A genset trip needs 2
   of 3 votes; cooling needs the pump alarm or a stopped pump, plus low flow or high delta-T. A vote that drops
   sooner cancels the pending fault (logged). A pending fault whose votes go stale is **held**, state
   `held_stale`, and confirms if the feed returns showing it still true; meanwhile the ladder stays armed and the
   record says the fault is unconfirmed because the feed is stale. A recovered genset or pump must read healthy
   60 s before any guest is restored.
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
   drops"). A deadline may move earlier, never later. The launch time is an input (`G4.launched_t_s`, sent at
   tick 0 and on each launch), since Scenario B's sortie began before tick 0. Mode end times come from the
   card's `duration_s`.
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

One JSON object per tick: `run` (contract, scenario, mission, seed, `tick`, `t_ship_s`, installed guests, run
constants), the groups `plant`, `ship_state`, `environment`, `links`, `crew`, `guests`, `capacity`, then `feeds`,
`faults` and the `events` applied at this tick. Every field is `{value, source, age_s, confidence, stale}`, plus
`since_t_s`, `reported_t_s`, `transition`, `substituted` or `by` where they apply. Unknown fields are refused.
Who reads each field is its `read_by` in `signals.yaml`.

**Not in the snapshot:**

- **Committed, free and reservations.** These are ledger lines (contract 8). The ledger takes, per guest, the
  larger of its mode's declared kW, the kW the core reserves for it (from the decision log:
  `{Gx: {mode, kw, since_t_s}}`) and its fresh `kw_actual`. Under sar at minute 12 that is G4 at max(2, 35):
  1 + 35 + 45 = 81 kW against 95, 14 spare, as the oracle says. Demand on a link that is 0 by rule is
  buffered, with free 0 and no margin computed. Over-consumption shows as `Gx.overdraw_pct`; above 5 % for 10 s
  (assumed) it raises `guest_overconsumption`.
- **Static classes**: backbone, compute cores, mass, bay units, high slots, flight deck and stability come from
  `assumptions.yaml`, the cards and the placement, in the ledger.
- **The peak budget and heat inertia** (+250 kW for 60 s, +30 kW for 60 s every 10 min): no decision credits
  them (`admission.peak_credit_kw` 0; D4 sheds to the steady ceiling). Crediting them would add
  `capacity.power_peak` and `capacity.heat_inertia` with their last-used times.

## Replay

1. Every frame is written to a **frame log** (JSONL). Estimator and core replay read the frame log, so a replay
   never needs the simulator. Re-running the simulator with the same seed and checking it reproduces the frame
   log is a separate check, Siddharth's.
2. Snapshots and records are serialized with sorted keys, no whitespace, and floats rounded to 0.1 (kW, s, kn,
   °C, Hz, %). The fixtures hold rounded values (371.9, 1091.9) and the tests compare them exactly.
3. A timed-out decision replays its logged outcome. A safety request replays after the decisions of the tick it
   was logged with.
4. A replay therefore reproduces every snapshot and every record byte for byte; only the timing log differs. The
   replay check compares snapshots and the decision log and reports the first field that differs.
   `inputs_hash` (contract 7) should add the seed, `signals.yaml`, the frame log and the input log.

Mission compare is two runs on one timeline: two frame logs that diverge after minute 8, and two decision logs.

## Names against ARCHITECTURE

The snapshot has `tick` (an integer) and `t_ship_s` (= tick); contract 4 calls the latter `t_s`. A decision
record's `t_s` is the `t_ship_s` of the snapshot it ran on, and `seq` is only the decision and record counter
that commands carry. For a later ARCHITECTURE edit, once the agents editing it now are done: contract 4 to
these names, contract 7's replay line to "snapshots and decision log", committed and free to the ledger only,
and `feed_drop`'s payload to `{feed, until_t_s}`.

## Fixtures (Scenario B, seed 0)

| Fixture | Shows |
|---|---|
| `survey_m00` | the start; no battery report yet, land-by 1448 s from endurance, `assumed` |
| `survey_m08` | G4 reports 18 %: crossing 371.9 s, land-by 1091.9 s (minute 18.2) |
| `survey_m08_crew0` | the same with 0 aboard: deck latched clear at the last sweep, R3 automatic |
| `survey_m09_stale_g4_telemetry` | injected drop: telemetry 15 s old, battery stale with its feed, land-by kept and named |
| `survey_m10_stale_genset_feed` | injected drop: power management feed 4 s old, one genset down for D1 only, nothing shed; G4's 120 s old report still fresh |
| `survey_m12`, `sar_m12` | trip at 720 s confirmed at 721 s; the ledger gives 48 of 95 kW (survey) and 81 of 95 kW (sar, with the reservation) |
| `survey_m19`, `sar_m19` | injected pump fault: heat 80 kW, ceiling 75 kW against 81 kW; G3 631 s silent but not stale |

After the minute-8 decision: G3 is told to hold and acknowledges at 510 s (a 30 s round trip); the bridge
confirms at 540 s (request seq 1); the manoeuvre lands at 541 s; the ship goes from 3 to 5 kn over 2 min,
inside the slow band, so there is no A.6 band change (EXPECTED_OUTCOMES minute-8 cost); the deck clears by
781 s; G4 lands at 1020 s.

## Open, for a DEC row

1. **The split with Siddharth.** The estimator confirms faults and derives the acoustic link, and the simulator
   owns the fault signatures and the transitions. He would also emit values A.6 does not list: `ramp`,
   `deck_machinery`, `deck_activity_since_sweep`, `radar_transmitting`, per-zone deck, numeric `speed_kn`,
   `wind_from_deg`, `G4.launched_t_s`, transitions with expected and latest ends, frames that leave out a
   dropped feed, and the deck fields set while the activities run.
2. Keep `confidence` in contract 4 as the five-level scale.
3. G4's battery cadence: one report at minute 8, as in the brief. A streamed battery would show the crossing
   at minute 6.2 and move the decision earlier.
4. Move the assumed values in `signals.yaml` `pending_moves` into `assumptions.yaml` with provenance, so they
   reach the Physical Account, once the agents editing it are done.
5. Scenario B gives no seed, sea state, wind series or structured starting state. The fixtures assume seed 0,
   sea state 4, the ship's wind 18 kn rising to 22 kn, SATCOM 6 Mbit/s and G4 launched at −3952 s, all listed in
   the minute-0 baseline payload.
6. The over-consumption tolerance (R-082): proposed 5 % for 10 s.
