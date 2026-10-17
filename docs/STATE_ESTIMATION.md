# State estimation: the inputs contract

Status: proposal, Sat 2026-10-17. Written by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka), who now
owns the inputs: everything that goes into state estimation. Nothing here is decided until a WORKLOG `DEC-`
row says so. It fills ARCHITECTURE data contract 4 (the snapshot) for CON-21 and follows the design freeze:
inputs are confirmed, debounced plant signals, and unknown never means safe.

The contract is four files:

- `config/signals.yaml`: every signal, typed, with source, rate, stale limit, fallback and provenance; the
  activity registry per guest; the confirmation thresholds and derivation rules.
- `config/snapshot.schema.json`: the 1 Hz snapshot the core consumes (JSON Schema 2020-12).
- `tests/fixtures/snapshots/`: Scenario B under the survey file at minutes 0, 8, 12 and 19, and minute 10
  with the genset feed stale.
- `tests/test_snapshot_contract.py`: checks the three agree with each other, the cards and the oracles.

## What goes in, from whom

| Producer | What | Rate (ship time) |
|---|---|---|
| Siddharth's simulator, from the platform | raw plant signals: genset relay flags and kW, bus frequency, chilled-water pumps (running, alarm), flow, supply and return temperature | 1 Hz |
| Siddharth's simulator, from his A.6 state machine | course, speed in knots, noise, deck per zone, emission, ramp, deck machinery, own radar, alongside or at sea; each with any transition in progress and its expected end | 1 Hz |
| Siddharth's simulator, from the comms system | SATCOM and line-of-sight radio rates | 1 Hz |
| Siddharth's simulator, from the scenario or the public-data cache | seawater temperature, sea state, layering (hourly); wind speed and direction (1 Hz, the ship's anemometer) | hourly or 1 Hz |
| Siddharth's simulator, from each guest | mode in effect, metered draw and data rates (1 Hz); the guest's own reports: activity, G3's leg and hold acknowledgement (acoustic messages), G4's battery and range | 1 Hz or on report |
| The laptop, relayed every tick | crew aboard, people available, bridge confirmation, landing officer's deck report, standing plan; injected faults and feed drops | on change |
| The core itself | reservations it holds (for example G4's 35 kW under sar), fed back from the decision log | per tick |

Every raw value carries its reading time in ship seconds. A dropped feed is a missing value, never an
invented one.

## The boundary with Siddharth's simulator

**The simulator emits** what the ship's instruments would read, and nothing it would not. It owns the A.6
variables and their transition times, so it reports their values and any transition in progress. It emits
raw fault signals, not verdicts. It applies the core's commands and the timeline, and reports the result in
the next frames. It uses the signal names in `config/signals.yaml` (producer `simulator` or `laptop`), in the
shape `{value, source, t_s}`.

**The core derives** every signal whose producer is `estimator`: confirmed faults, gensets online, cooling
state, speed band, the acoustic link, heading freedom, deck machinery permitted, flight-deck use, the deck
latch, G4's land-by deadline, mode end times, and the capacity per class.

**Commands are Siddharth's to define** (contract 5). The estimator sends none. It sees their effect as a
changed mode, activity or transition in a later frame.

This moves two things out of the simulator. BUILD_PLAN T4 and the ARCHITECTURE component table put
"debounced faults" and "the acoustic link" in Siddharth's state machine. Here the simulator emits the raw
signals and the estimator confirms and derives. That needs a WORKLOG row and Siddharth's yes.

## The clock

- **Tick.** One snapshot. Tick n is at ship time n seconds, so 1 Hz means one tick per ship second.
- **Ship time** (`t_ship_s`). Seconds since minute 0 of the timeline. It is the only clock the estimator and
  the decisions read: ages, stale limits, debounce, restore hold, transition ends, A.6 times and deadlines.
  The timeline is written in `t_min`; an event at `t_min` m is applied at tick 60 m.
- **Wall time.** The host's monotonic clock and a UTC stamp. It appears only in the timing log: latency per
  decision and the pacing of ticks. It never appears in a snapshot or a decision record.
- **Demo pacing, x12.** Twelve ship seconds per wall second: a tick every 83 ms, a ship minute in 5 s. The
  pacing lives in the timing log header, not in the snapshot.
- **Hold and jump.** On hold no tick runs and ship time stops. A jump runs every tick unpaced up to the
  target; it never skips one. A laptop input is stamped with the tick that applies it, the next one, and
  written to the input log.
- **Unpaced replay.** Ticks run as fast as the host allows. Same snapshots, same records.
- **Events between ticks.** A decision runs on the snapshot that carries its trigger, not one tick later.
  A safety request (200 ms) is answered on arrival from the table built at the last tick, and its record
  names that tick.
- **A.8 checks.** Each record's latency is wall time. The 5 s first shed counts from the raw event:
  `(confirmed_t_s - raw_event_t_s)` in ship time, plus the D4 latency in wall time. With a 1 s debounce,
  4 s remain (`first_shed_budget_s`). At x12 the debounce passes in 83 ms of wall time, but it still counts
  as 1 s, what a real ship would wait (OPEN_QUESTIONS #47).

## Each tick, in order

1. **Read** the simulator's frame for tick n, the laptop inputs stamped n, and the core's held reservations.
2. **Validate.** A name that is not in `signals.yaml` is refused and logged. A value outside its type or
   range counts as missing; it is never clamped. A missing value keeps its last reading, and its age grows.
3. **Age.** `age_s` is ship time now minus the reading time. A field is stale when `age_s` is above its
   `stale_after_s`. Most 1 Hz signals go stale after 3 s, three ticks (`stale_feed.after_s`). Hourly data
   allows 3 h. G4's telemetry allows 10 s (R3). G3's acoustic reports allow 900 s, because the vehicle is out
   of contact by design while the ship manoeuvres.
4. **Fall back.** A stale field takes its fallback, the value that tightens limits. Its confidence becomes
   `substituted`, and a `substituted` block keeps the last value, its time and the rule. One rule binds
   everywhere: a fallback may tighten admission and arm the D4 ladder, but D4 sheds only on a confirmed
   fault. A stale genset feed counts as one genset down for D1 and the armed ladder, and sheds nothing. The
   decision sentence names the stale feed.
5. **Confirm faults.** A genset trip needs 2 of 3 votes: relay flag, kW below 22.5, bus below 58.8 Hz.
   Cooling needs the pump alarm plus low flow (below 70 %) or high delta-T (above 8 °C). Votes must hold 1 s
   from the raw event. A vote that drops sooner cancels the pending fault, and the cancellation is logged.
   Each fault keeps `raw_event_t_s`, `confirmed_t_s`, its votes and its budget left. A recovered genset or
   pump must read healthy 60 s before any guest is restored.
6. **Derive ship state.** Speed band from knots: a speed in an A.6 gap takes the faster band, whose reserve
   is lower. Acoustic link up only while the course is steady, the noise quiet, no deck machinery runs and
   the water is not layered. Heading free unless a running activity pins it (G3 on its cable route). Deck
   machinery permitted unless the ship is silent or a running activity excludes it. Flight deck in use while
   G4 launches or recovers. Deck latch per R3.
7. **Derive deadlines.** G4's land-by time is the earliest of two bounds. One is launch plus 90 min
   endurance. The other is the 20 % crossing plus 12 min, the crossing dated back from the last report below
   20 % at the slowest drain, 1.11 %/min. At minute 8 the report is 18 %, so the crossing is
   480 - (20 - 18) / 1.11 x 60 = 371.9 s (minute 6.2), and land-by is 1091.9 s, **minute 18.2**
   (EXPECTED_OUTCOMES). A deadline may move earlier, never later. Mode end times come from the card's
   `duration_s` (G4's fast charge ends at minute 37).
8. **Derive capacity per class.** For power, the guest reserve by speed band with two gensets, or 100 kW with
   one. For each mission line, 150 kW. For heat, 160 kW at 12 °C falling to 120 kW at 30 °C, times 0.6
   when degraded. For SATCOM and radio, the live rate, zero in silence. Committed is the declared kW of each
   guest's current mode plus held reservations. Free is capacity minus committed. `degraded_by` names each
   cause. The shed ceiling is min(power, heat) minus the 5 kW headroom.
9. **Emit** snapshot n. Every decision this snapshot triggers runs on it.

A derived field is as old as its oldest deciding input. It is stale only through a fallback, and its
confidence is the weakest of its inputs. The levels, weakest first: `substituted`, `assumed` (a scenario or
config value), `reported` (a person or a guest), `measured` (one fresh plant reading), `confirmed` (passed a
confirmation rule). The ARCHITECTURE working tree dropped confidence from contract 4. This contract keeps
it, as the task, SENSOR_CATALOG rule 5 and R-458 ask.

## What comes out

One JSON object per tick: `run` (contract, scenario, mission, seed, tick, `t_ship_s`, installed guests),
`held_by_core`, the groups `plant`, `ship_state`, `environment`, `links`, `crew`, `guests` (per installed
guest: mode, activity, `kw_actual`, `data_demand` and its own telemetry), `capacity`, then `faults` and the
`events` applied at this tick. Every field is `{value, source, age_s, confidence, stale}`, plus
`since_t_s`, `transition` (`to`, `started_t_s`, `expected_end_t_s`, `latest_end_t_s`) or `substituted`
where they apply. Unknown fields are refused.

## Who reads what

| Reader | Fields |
|---|---|
| Ledger, 1 Hz | `capacity.*`; each guest's mode, `kw_actual`, `data_demand`, `mode_ends_t_s`; emission |
| D1, D2 admission and placement, 30 s | envelope values from `assumptions.yaml`, not live readings (Scenario A); live only `situation`, `crew_aboard` (no override at 0) and, for A′, the A.11 window: `sea_state`, `wind_kn`, `speed_kn`, `course`, `deck_flight_deck`, `G3.activity`, `people_available`. Stale gensets or cooling tighten the one-genset-down line |
| D3 right of way, 2 s | `course`, `speed_kn`, `noise`, deck zones, `ramp`, `deck_machinery`, `deck_machinery_permitted`, `heading_free`, `flight_deck_ops`, `emission`, `wind_kn`, `wind_from_deg`, `sea_state`, each guest's activity, `G4.battery_pct`, `G4.land_by_t_s`, `G3.leg_*`, `G3.hold_ack`, `acoustic_link_up`, `crew_aboard`, `bridge_confirmation` |
| D4 shedding, 5 s | `faults` (confirmed only), `capacity.power`, `capacity.heat`, the lines, `shed_ceiling_kw`, modes, `mode_ends_t_s`, reservations |
| D5 crew policy | `crew_aboard`, `bridge_confirmation`, `hlo_deck_report`, `standing_plan`, `deck_latched_clear`, `deck_activity_since_sweep`, `G4.land_by_t_s` |
| Safety table, 200 ms | `G3.hold_ack`, `acoustic_link_up`, `G2.activity`, `G4.activity`, `hlo_deck_report`, `emission`, `deck_machinery_permitted` |
| Decision sentence | any `substituted` block, `tripped_genset`, `radar_transmitting` |

## Replay

A snapshot is a pure function of the timeline, the seed, `assumptions.yaml`, `signals.yaml`, the cards, the
priority file, the laptop input log and the public-data cache. It holds no wall-clock field. A replay gives
the same snapshots and the same decision log on every field, byte for byte. Only wall-clock timing differs,
and it goes to the timing log: per tick and per record, the UTC stamp, the monotonic time, the latency and
the pacing. The replay check compares snapshots and decision log, and reports the first field that differs.
`inputs_hash` (contract 7) should add the seed, `signals.yaml`, the public-data cache and the input log.
Mission compare is two runs on one timeline, so it is two snapshot streams: after minute 8 the files diverge
(sar reserves G4's 35 kW).

## Every signal

`*` marks a value new in this contract, assumed, with its reason in `signals.yaml` provenance. "3 s" is
`stale_feed.after_s`. "Ladder only" means admission and the armed ladder; D4 does not run on it.

| Signal | From | Type, units | Rate | Stale after | Fallback |
|---|---|---|---|---|---|
| `genset_1_relay_trip`, `genset_2_relay_trip` | plant | boolean | 1 Hz | 3 s | no vote |
| `genset_1_kw`, `genset_2_kw` | plant | 0 to 450 kW | 1 Hz | 3 s | no vote |
| `bus_frequency_hz` | plant | Hz (60 Hz bus*) | 1 Hz | 3 s | no vote |
| `gensets_online` | derived | 1 or 2 | tick | 3 s | 1, ladder only |
| `tripped_genset` | derived | none, genset_1, genset_2 | tick | 3 s | last confirmed |
| `chw_pump_1_running`, `chw_pump_2_running` | plant | boolean | 1 Hz | 3 s | false |
| `chw_pump_1_alarm`, `chw_pump_2_alarm` | plant | boolean | 1 Hz | 3 s | no vote |
| `chw_flow_pct` | plant | % of nominal | 1 Hz | 3 s | no vote |
| `chw_supply_c`, `chw_return_c` | plant | °C | 1 Hz | 3 s | no vote |
| `cooling_state` | derived | nominal, degraded | tick | 3 s | degraded, ladder only |
| `course` | ship state | free, steady | 1 Hz | 3 s | free |
| `speed_kn`* | ship state | 0 to 25 kn | 1 Hz | 3 s | unknown: speed conditions fail |
| `speed_band` | derived | stopped, slow, cruise, fast | tick | 3 s | fast (lowest reserve) |
| `noise` | ship state | quiet, normal, manoeuvring | 1 Hz | 3 s | manoeuvring* |
| `deck_flight_deck`, `deck_bays`* | ship state | clear, occupied | 1 Hz | 3 s | occupied |
| `emission` | ship state | normal, silent | 1 Hz | 3 s | normal for conflicts, silent for links |
| `ramp`* | ship state | free, in_use | 1 Hz | 3 s | in_use |
| `deck_machinery`* | ship state | boolean | 1 Hz | 3 s | true |
| `radar_transmitting`* | ship state | boolean | 1 Hz | 3 s | true |
| `situation` | scenario, laptop | alongside, at_sea | on change | 3 s | at_sea |
| `heading_free`* | derived | boolean | tick | 3 s | false |
| `deck_machinery_permitted`* | derived | boolean | tick | 3 s | false |
| `flight_deck_ops` | derived | free, in_use | tick | 3 s | in_use |
| `seawater_c` | scenario, public data | °C | hourly | 3 h* | worse of last and 30 °C |
| `sea_state` | scenario, public data | Douglas 0 to 9 | hourly | 3 h* | worse of last and 5 |
| `wind_kn` | plant (anemometer*) | kn | 1 Hz | 3 s | worse of last and 30 kn |
| `wind_from_deg`* | plant | degrees | 1 Hz | 3 s | no turn into wind planned |
| `layered_water` | scenario, public data | boolean | hourly | 3 h* | true |
| `satcom_mbps` | plant | 0 to 8 Mbit/s | 1 Hz | 3 s | 0 |
| `los_radio_mbps` | plant | 0 to 20 Mbit/s | 1 Hz | 3 s | 0 |
| `acoustic_link_up` | derived | boolean | tick | 3 s | false |
| `acoustic_kbps` | derived | 3 kbit/s when up*, else 0 | tick | 3 s | 0 |
| `crew_aboard` | laptop | 14, 6, 0 | on change | 3 s | next lower level |
| `people_available` | crew report | people | on change | 3 s | 0 |
| `bridge_confirmation` | crew report | none, pending, confirmed, denied | event | 3 s; answer expires 60 s, 180 s, 0 s by crew | denied |
| `hlo_deck_report` | crew report | none, clear, not_clear | event | 3 s; clear expires 300 s* | not_clear |
| `standing_plan` | crew report | none, approved | event | 3 s; expires 90 min* | none |
| `deck_activity_since_sweep` | plant | boolean | event | 3 s | true |
| `deck_latched_clear` | derived | boolean | tick | 3 s | false |
| `Gx.mode` (G1 to G6) | plant | the card's modes | 1 Hz | 3 s | highest-draw mode |
| `Gx.activity` (G1 to G6) | guest report | the registry, or none | 1 Hz; G3 by acoustic message | 3 s; G4 10 s; G3 900 s* | the most demanding: G2 winch, G3 surveying, G4 airborne |
| `Gx.kw_actual` (G1 to G6) | plant | kW | 1 Hz | 3 s | declared peak |
| `Gx.data_demand` (G1 to G6) | plant | Mbit/s per link (acoustic kbit/s) | 1 Hz | 3 s | card nominal |
| `Gx.mode_ends_t_s` (G2, G3, G4) | derived | ship s | tick | 3 s | last value |
| `G3.leg_state` | guest report | running, paused, aborted, done | acoustic message | 900 s* | running |
| `G3.leg_started_t_s`, `G3.leg_flown_s` | guest report | ship s; 0 to 2400 s | acoustic message | 900 s* | last value, said to be old |
| `G3.hold_ack` | guest report | boolean | acoustic message | 900 s* | false |
| `G4.battery_pct` | guest report | % | on report | 10 s | last report kept; its deadline stands |
| `G4.range_km` | guest report | km | 1 Hz | 10 s | beyond 20 km: radio at 1 Mbit/s |
| `G4.airborne_since_t_s` | derived | ship s | tick | 3 s | last value |
| `G4.battery_crossing_t_s` | derived | ship s | tick | 3 s | last value |
| `G4.land_by_t_s` | derived | ship s | tick | 3 s | never later |
| `capacity`: `power`, `port_line`, `stbd_line`, `heat`, `satcom`, `los_radio`, `acoustic` | derived | capacity, committed, free, degraded_by | tick | 3 s | from the inputs' fallbacks |
| `capacity.shed_ceiling_kw` | derived | kW | tick | 3 s | from the inputs' fallbacks |

Activities are named `Gx.activity` from one registry in `signals.yaml`: G1 listening; G2 probe, winch; G3
surveying, launch_recovery, holding_depth, holding_at_sea, on_cradle; G4 launch_recovery, airborne, landed;
G5 transmitting; G6 production, start. Each lists the modes it runs in and its effect on ship state (G2's
winch and G4's hangar doors are deck machinery; G3's ramp work uses the ramp). Today's cards say
`G4.recovering` and `stern_ramp_ops`. The test maps them to `G4.launch_recovery` and `G3.launch_recovery`
with a small table, which goes when F2 types the cards.

## Open, for a DEC row

1. The split above: the estimator confirms faults and derives the acoustic link (Siddharth to agree).
2. Keep `confidence` in contract 4 as the five-level enum.
3. G4's battery cadence. This contract follows the brief: one report at minute 8. A streamed battery would
   show the crossing at minute 6.2 and move the decision earlier.
4. Move the `*` values into `assumptions.yaml` with provenance, so they reach the Physical Account
   (`signals.yaml` `pending_moves`).
5. Scenario B gives no seed, sea state, wind series or structured starting state. The fixtures assume
   seed 0, sea state 4, wind 18 kn rising to 22 kn, and G4 launched at -3952 s (26.9 % at minute 0). The wind
   should be the ship's own feed, not part of G4's report.
6. Over-consumption: the estimator reports declared and metered draw; the tolerance is still open (R-082).
