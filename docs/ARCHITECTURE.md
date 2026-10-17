# Architecture and data contracts (draft for team review)

Status: **draft, Fri 21:55 PDT.** Written by Claude on behalf of Logan Walker (GhostWalka) so the
team can split work and react before anyone builds deep. Only the data model exists so far:
`config/assumptions.yaml`, `manifests/schema.json`, six cards, four priority files, and tests that
check them against the brief. Everything below is a proposal; change it in review, not in code.

## Principles

1. **One ledger, one manifest language.** Everything that uses or supplies a resource is described
   the same way and counted in one ledger of margins. Roles: host commitment, guest, supply, crew.
2. **Deterministic core.** The decision engines are pure functions of their inputs. Same inputs,
   same decision, same sentence. Replay is the redundancy mechanism.
3. **Explain from the binding constraint.** Every decision carries the ledger line that bound it;
   the sentence is built from that line's numbers, never from a canned string.
4. **Unknown never means safe.** Missing or stale inputs tighten limits; they never loosen them.
5. **Numbers live in data.** Code reads `config/assumptions.yaml`; nothing physical is hard-coded.

## Components

| Component | Does | Reads | Writes | Owner |
|---|---|---|---|---|
| Data model | assumptions, guest cards, priority files, schema | brief | YAML / JSON files | proposed: Claude for Logan; drafted |
| Ledger | per-class capacity and demand for a configuration under conditions | assumptions, cards, placement, conditions | ledger lines | open |
| D1 admission | yes / no / yes-if / not-now for a new card | ledger, envelope, priority file | decision record | open |
| D2 placement | which slot for each part, maximising remaining margin | positions, cards | placement + rejected alternatives | open |
| D3 right of way | who proceeds when guests' conditions on ship state collide | ship state, conditions, priority file | decision record with cost to loser | open |
| D4 shedding | precomputed ladder; executes on a confirmed trip | ledger, modes, priority file | ordered actions + per-guest loss | open |
| D5 crew policy | per-rule confirm / automatic / forbidden by crew level | rules, crew level | policy per action | open |
| Simulator | seeded 1 Hz clock, event timeline in, decisions out | everything above | decision log (JSONL) | open |
| Edge / bus | two nodes, wired + Wi-Fi paths, heartbeats, failover by replay | decision log | node health, path state | open |
| Virtual sensors | camera detections to ship state with source, age, confidence | camera or synthetic stream | sensor readings | open |
| Rule compiler | controlled grammar to approved, testable rules | crew text | rule records | open |
| Screen | schematic, 8 gauges, decision log, mission and crew controls | state stream | none | open |

## Data contracts

**1. Guest manifest** (`manifests/schema.json`, validated in tests). Per guest: capability name;
cooling type; parts with mass, area, preferred and allowed positions; consumption per class as
min / nominal / peak with duration; a mode ladder from full to off with the share of capability
kept; ship-state conditions per activity; part-of / requires / excludes relations; installation
work in port and at sea; safety-critical flag; mission criticality resolved by the priority file;
hard limits such as the drone's 20 % battery rule. Adding a guest is adding one YAML file.

**2. Platform assumptions** (`config/assumptions.yaml`). Capacities per class, positions, envelope,
ship-state transition times, crew confirmation times, installation windows. A `provenance` map tags
each key as brief or assumed with a reason; tests fail if an assumed number has no reason.

**3. Priority file** (`config/missions/*.yaml`). Capability weights 0–1, mission-critical guests.
To add: shed policy overrides (for example "comms node last in disaster relief") and the crew
confirmation policy per rule. Swapping this file is the jury's "different ship" test.

**4. Conditions snapshot** (proposed, 1 Hz). Seawater temperature, gensets online, cooling state,
emission state, course, speed band, noise, deck state, sea state, wind, crew level. Every field
carries `source` (measured / camera / crew / assumed), `age_s` and `confidence`.

**5. Event timeline** (proposed, JSONL). One event per line: `t_s`, `type`, `payload`, `seq`.
Types: `card_presented`, `card_edited`, `priority_swap`, `override_push`, `genset_trip`,
`genset_restart`, `cooling_degraded`, `drone_battery`, `guest_overconsumption`, `crew_change`,
`emission_change`, `sensor_reading`, `sensor_drop`, `link_down`, `node_down`.

**6. Decision record** (proposed, JSONL, the core output). Fields:
`seq, t_s, kind (D1–D5), subject, verdict, binding {class, label, capacity, demand, free, unit},
sentence, cost_to_loser, options [ranked], placement, inputs_hash, latency_ms, ceiling_ms`.
The screen, the replay check, the worklog of decisions and the demo all read this one record.

**7. Ledger line** (proposed). `class, label, unit, capacity, demand, contributors {guest: amount}`.
Classes: power total, port line, starboard line, heat, bay units, high slots, flight deck, mass,
stability, SATCOM, backbone, line-of-sight radio, acoustic, compute cores, response time.

## Decision engines: inputs, objective, ceiling

| Engine | Objective | Ceiling | Output sentence pattern |
|---|---|---|---|
| D1 admission | verdict at both gensets, the 200 kW reserve and cooling at 30 °C; must survive one genset down by throttling to the 95 kW gate, otherwise yes-if; the raw one-genset-down line is always shown (DEC-35); port moves reported with crane time (DEC-37); links judged at minimum rates (DEC-38); report the seawater tipping point; for yes-if, least mission value lost | 30 s | "Refused: {line} has {free} {unit} free; {guest} needs {need} {unit}." |
| D2 placement | maximise the smallest remaining margin; prefer preferred slots; leave the most future cards admissible | 30 s | "{part} to {slot}; rejected {slot2} because {line}." |
| D3 right of way | hard limits first, then mission-weighted value | 2 s | "{winner} proceeds: {hard limit or weight}; {loser} loses {cost}." |
| D4 shedding | throttle before shed, cheapest loss per kW first, recheck power and heat each step | 5 s first, 60 s all | "{guest} to {mode}: frees {kW}; loses {capability}." |
| D5 crew policy | what a human still confirms at 14 / 6 / 0, approved ahead of time | n/a | "At {crew} aboard {rule} is {confirm / automatic / forbidden}." |

## Proposed additions since the first draft (for review)

- **Camera readings** (`research/cv_equipment_monitoring.md`, WORKLOG CON-11). A camera check logs a
  `sensor_reading` event, never a frame, with `camera`, `region`, `check`, `state`, `score`,
  `threshold`, `confidence_index`, `calibrated: false`, `age_s`, `reference_age_s`, `latched` and
  `health {blur_ok, frozen, view_ok}`. The conditions snapshot gains `zone_hazard` per zone. Hazard
  findings latch until crew or plant confirm; only deck-occupancy findings withdraw themselves. A leak
  maps to the existing cooling state `degraded` with `source: camera, confirmed: false`.
- **Priority file schema** (`config/missions/schema.json`, tested). The governor validates a swapped
  file before use and refuses a bad one with the failing field, keeping the previous file meanwhile.
- **Rule parameters live in data.** Scenario C rule R3's parameters are `rules.r3.*` in
  `config/assumptions.yaml`, so every rule's numbers reach the Physical Account like any other
  assumption.
- **Admission envelope rule** (DEC-35). Judge the verdict at both gensets, the lower speed-band reserve (200 kW) and cooling at 30 °C. For each admitted set (each removal option for yes-if), report the raw one-genset-down line first: stacked envelope draws against 100 kW. Gate = min(100, cooling at 30 °C) minus 5 kW headroom = 95 kW. If the load is over 95 kW, walk the D4 ladder's throttle-only prefix: a step counts only if its mode is interruptible and keeps capability above 0; non-critical steps first, mission-critical last and named. Reaching 95 kW or less keeps the verdict, worded "holds by throttling". Otherwise the verdict becomes yes-if, adding the cheapest removal sets that pass the same check; no set passes means no. The 60 s peak allowance is never credited; cooling at -40 % is an information line, not part of the verdict.
  Sentence template: "{Verdict}. Binding: {class}, {demand} of {capacity} {unit} at 30 °C. One genset down:
  {class} {load} of 100 kW, {fits | N kW short} as loaded; {nothing needed | holds by {action} ({kW} freed,
  {capability lost}), automatic within 5 s, no guest switched off | does not hold by throttling, so {guest} must leave}."
- **Admission override** (Logan, DEC-32). A refused admission can be forced by an explicit captain override
  for extreme situations. It needs a human, so it is not available at 0 aboard; the decision record keeps
  the binding line, marks the decision overridden, and names who overrode and why.
- **Requirements trace.** Every component above maps to rows in `docs/requirements.yaml`; edit the YAML
  and re-render (`tools/render_requirements.py`).

## Open decisions for the team

1. Owners for each component above.
2. Is the decision record the single source of truth for the screen and the demo?
3. Which envelope corner decides admission: both gensets at 30 °C (proposed), or one genset down?
4. How strict is placement in port: may installed guests move between bays to admit a new card?
5. Bus: our own small UDP layer (proposed by research) or an existing open-source middleware?
6. Screen technology: plain HTML and JS (proposed) or what the team prefers.
7. Which demo hardware we actually have: second machine, cable, router, Qualcomm box Sat 10:00.
