# Plant contract: what the simulator emits and what the governor may command

Status: proposal, Sat 12:50 PDT, by Claude Fable 5.1 on behalf of Siddharth Chawla (sidd91). Answers
CON-21 from the simulator side. Per DEC-47 the snapshot schema is Logan's to own; this is what the plant
emits today (`src/sdv/plant/sim.py`), offered as the starting point. The command set is Siddharth's.

## 1. Commands (governor → plant)

The governor never changes the ship directly; it asks, and the plant answers with the A.6 transition times.

| Call | Meaning | Returns |
|:--|:--|:--|
| `sim.request_state(var, value, source)` | Ask for a ship state: `course`, `speed_band`, `noise`, `deck`, `emission`, `genset`, `cooling`; values from `assumptions.yaml: ship_state.<var>.values` | `{result: immediate \| scheduled \| refused, ready_at_s?, why?}` |
| `sim.set_mode(guest, mode, source)` | Put a guest in a mode of its card (throttle, shed, restore) | raises on unknown mode |
| `sim.on_tick = fn(snapshot, sim)` | Hook called once per tick after the plant has updated; the governor decides inside it. `src/sdv/governor.py` is that governor today: it appends `decisions` (records), `governor` (active file, reserved kW, armed ladder) and `governor_log` (priority swaps) to the snapshot | — |

Rules the plant enforces, from A.6: deck clearing takes 3–5 min at 14 aboard, 8–12 at 6, is refused at 0
unless already clear; going quiet 2–4 min, leaving instant; speed 2–5 min per band crossed; silence instant;
genset restart 5–15 min; a degraded loop is never repaired at sea. Transition times come from the scenario's
pin when one exists (`seed_pins.deck_clear_min`, so Scenario B's 4-min clear and minute-17 landing hold on
every seed), otherwise one draw per request from the run's seed, so a replay repeats them exactly (DEC-52).
Faults are never requested: `request_state("genset", 1)` and `request_state("cooling", "degraded")` come back
`refused`; they enter only as confirmed scenario events (`genset_trip`, `cooling_degraded`). While silent, the
ship block carries `forbidden_actions` (A.6's list) for the core to honour.

Planned, not yet built: `sim.request_launch(guest)` / `request_recovery(guest)` (flight deck or ramp, with
the A.3 conditions checked and the deck set occupied/clear), `sim.start_cycle(guest, phase)` for G3's
40-min leg and 60-min charge, and an acoustic-link state for G3 (drops with manoeuvre, deck machinery,
layering).

## 2. Scenario events (data → plant)

`config/scenarios/*.yaml`, each with `t_min`. The plant applies these; anything else is passed to the
governor hook untouched. The governor answers `priority_swap {mission: <id> | <path> | <mapping>}` (validated,
refused files keep the old one) and reads `guest_report` as telemetry: hard limits are judged on what a guest
reported, never on the plant's internal battery model (DEC-56).

`baseline`, `guest_report {guest, battery_pct?, wind_kn?}`, `guest_state {guest, state}` (scripted while no
governor closes the loop: `landed_fast_charging`, `airborne`, `on_cradle`), `guest_mode {guest, mode}`,
`genset_trip {gensets_online, cooling?}`, `genset_restart`, `cooling_degraded {factor, confirmed_by}`,
`ship_state {var, value}`, `emission_change {value}`, `crew_change {crew}`,
`guest_overconsumption {guest, factor}`, `environment {seawater_c?, sea_state?, wind_kn?}`.

The scenario's `initial` block sets minute 0: crew, ship state, guest modes, placement, battery, airborne.

## 3. Snapshot (plant → governor and screen), once per second

```json
{
  "t_s": 720, "t_min": 12.0, "mission": "survey",
  "ship":   {"course": "steady", "speed_band": "slow", "noise": "quiet", "deck": "clear",
             "emission": "normal", "genset": 1, "cooling": "nominal",
             "age_s": {"course": 720, "speed_band": 720, "noise": 720, "deck": 0, "emission": 720, "genset": 0, "cooling": 720},
             "pending": [{"var": "deck", "value": "clear", "ready_at_s": 960, "eta_s": 240, "pick": "pinned"}],
             "forbidden_actions": [], "crew": 14},
  "env":    {"seawater_c": 24, "sea_state": 2, "wind_kn": 22},
  "guests": {"G4": {"mode": "standby", "declared_kw": 2, "actual_kw": 2, "capability_retained": 0.3,
                    "placement": {"drone": "flight_deck", "hangar": "flight_deck"},
                    "battery_pct": 13.56, "airborne": true}},
  "gauges": {"power": {"class": "power", "label": "guest power reserve", "unit": "kW",
                       "capacity": 100, "committed": 48, "free": 52,
                       "contributors": {"G3": 1, "G4": 2, "G5": 45}}, "heat": "...", "deck": "...",
             "mast": "...", "mass": "...", "data": "...", "compute": "...", "response_time": "..."},
  "lines":  {"power": "...", "power_line_port": "...", "power_line_stbd": "...", "heat": "...", "bays": "...",
             "flight_deck": "...", "stern_ramp": "...", "mast": "...", "mass": "...", "stability": "...",
             "satcom": "...", "los_radio": "...", "backbone": "...", "acoustic": "...", "compute": "...",
             "rt_admission": "...", "rt_arbitration": "...", "rt_shed_first_action": "..."},
  "events": [{"type": "genset_trip", "gensets_online": 1, "cooling": "nominal", "t_min": 12}]
}
```

Every line has the same shape (`class, label, unit, capacity, committed, free, contributors`) so a decision
can quote one verbatim: *"cooling loop at 30 °C has 12 kW free, guest needs 20 kW."* `gauges` is the
eight-per-class pick for the screen; `lines` is everything, including the two mission power lines.

## 4. Run file and replay

`sdv sim <scenario> --mission <id> --seed N` writes `runs/<scenario>_<mission>_sN.jsonl`: a header line
(`scenario, seed, mission, crew, inputs{assumptions, cards, missions, scenario} hashes`), one snapshot per
second, and a trailer (`run_hash`, events applied, FSM log). `sdv replay-check` runs twice and compares
hashes. Decision records will be appended to the same stream by the governor hook, so one file replays
the whole demo.

## 5. Open on this contract

- Field names above are proposals; Logan owns the schema (DEC-47). Rename freely, the plant follows.
- `response_time` committed is 0 until the governor writes its measured latency into the record.
- Scenario B minute 12 timing (DEC-51) is decided separately; the plant plays whatever the scenario file says.
