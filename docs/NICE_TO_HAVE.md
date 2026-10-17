# ArgOS: nice to have

Status: Sat 13:16 PDT. Written by Claude on behalf of Logan Walker (GhostWalka). Ideas for after the initial demo
works. Nothing here is on the build path: an item starts only once the core demo passes its done check in
[BUILD_PLAN.md](BUILD_PLAN.md), and each pick gets a WORKLOG DEC row. The first section doubles as the demo's
"next steps" slide.

## Next steps

1. **Equipment watch.** Cameras flag leaks, smoke and loose deck gear where no sensor exists. Information only
   until a plant signal confirms.
2. **Standby governor on an edge node.** A second ArgOS on the VENTUNO Q takes over by replaying the decision
   log, over wired and Wi-Fi paths.
3. **Rule builder.** Crew write a new rule in a form over typed signals, dry-run it against recorded scenarios,
   approve it and see its version in every decision.
4. **Worst single failure, every second.** An N-1 strip recomputed at 1 Hz, the way dynamic-positioning
   consequence analysis already works on ships.
5. **Same code, new hull.** ArgOS on a second vessel class with only a new ship profile and signal list, and a
   shore operations view for uncrewed runs.

## Ideas

| Idea | What it adds | Builds on | Effort | Origin |
|---|---|---|---|---|
| **Sensing** | | | | |
| Camera equipment watch: leak at the chilled-water loop (C1), smoke (C2), deck gear out of place (C3) | Evidence where sensors are missing or weak; plans cooling as degraded before the pump alarm, sheds only on a confirmed fault | the snapshot's source, age and confidence fields | a day | cut by DEC-44; [research](../research/cv_equipment_monitoring.md), [placement](../research/camera_placement.md) |
| Camera proof of a clear landing zone at 0 aboard | Lets R3 allow a recovery the latched deck state cannot prove | the item above | hours | cut by DEC-44 (F5) |
| Person detection | Counts people on deck as a second source to the landing officer | the camera pipeline | a day | cut by DEC-44; last in priority since DEC-23 |
| Live public data | Seawater and wind from Open-Meteo Marine instead of the cached run | the environment signals | hours | T10; CON-05 |
| Calibrated acoustic link model | Drop and recovery timing from the vehicle's real modem data | the acoustic rule in the contract | a day | freeze delta 13 |
| **Resilience** | | | | |
| Two-node failover by replay | A standby governor on the board takes over with the same sequence numbers when the laptop dies | the deterministic decision log | a day | cut by DEC-44; [board notes](NODE_B_BOARD.md) |
| Duplicate wired and Wi-Fi paths | A cable pull flips the path and no decision is missed | failover | hours | cut by DEC-44; CON-16 has the Wi-Fi timing |
| Safety commands on the board's real-time MCU | Stop, hold and secure answered within 200 ms even if Linux stalls | the precomputed safety table | a day | DEC-30 |
| Board instrument, full set | Watts, latency per decision class and CPU share measured on the board, feeding the Physical Account | T24 | hours | freeze delta 10 |
| **Rules and crew** | | | | |
| Form-based rule builder | Signal, operator, value, action and crew policy chosen from lists; dry-run diff of decisions; named approval; version hash in every record | typed conditions (F2), the loader | a day | DEC-02; the freeze cut the text grammar, not a form |
| R3 confirm countdown and escalation | Unanswered means no; "recovery held" escalates; deck work refused until G4 is secured | D5, R3 | hours | UI critique |
| Captain override of a refused load-out | Logged override with reason, kept on the record as overridden | D1 | hours | DEC-32 |
| Emission silence with the drone airborne | One D3 rule: land-or-ditch outranks silence, the cost of breaking silence stated | D3 | hours | OPEN_QUESTIONS #42 |
| **Decisions** | | | | |
| N-1 strip at 1 Hz | Worst single failure (genset, pump) recomputed every tick with its armed ladder | the ladder core | hours | UI critique |
| Restore after a genset restart | Gives capacity back in reverse order without re-tripping | D4 | hours | DEMO_SCRIPT minute 24 |
| Card and priority-file fuzzing | Every numeric field moved by 20 % and hostile files refused with the field named | the loader, the oracles | hours | review demo-2, freeze delta 3 |
| Seawater tipping point for every card | Where each verdict flips across 12 to 30 °C, shown as a band | D1 | hours | Scenario A |
| Replay proof on screen | A REPLAY MATCH chip with the log hash after a rerun | replay | hours | UI critique |
| **Screens** | | | | |
| Mission compare, live | Two runs on one timeline, side by side, the jury's file on the left | the simulator, the screen | a day | design canvas view B |
| Shore operations view | Crew-0 rendering: automatic and forbidden rows only, read over SATCOM | the screen | hours | UI critique |
| Day, dusk and night palettes | Bridge-display palettes for each light level | the screen | hours | UI critique |
| 3D ship view | A toggle beside the scored 2D screen, bound to the same 1 Hz state | the state stream | a day | cut by DEC-44; "3D earns nothing" |
| **Deployment planning** | | | | |
| Deployment globe (Cesium-like) | The planned route or operations area on a 3D globe: the ship's track, the guests' working areas, and each decision pinned where and when it was made | the screen, the run logs | a day | Logan, Sat 15:43. CesiumJS (Apache-2.0) or MapLibre GL (BSD-3) with offline tiles; no Cesium ion or other hosted tiles (local-only rule) |
| Weather-sampled deployment envelope | Picks points at random along the route or inside the area, samples the predicted weather at each (wind, sea state, seawater temperature) and turns the spread into expected deployment parameters, for example the worst-decile seawater for cooling and the wind and sea state behind the flight-deck and ramp windows. Every mission profile build is then run against them before sailing, with the verdicts and the binding lines it would give | the globe, the profile builder, D1's seawater tipping point, the weather API Siddharth is bringing into the simulator | a day | Logan, Sat 15:43 |
| **Platform and physics** | | | | |
| Standby chilled-water pump | The Physical Account's closing change, modelled: the minute-19 fault then sheds nothing | the ledger | hours | Physical Account |
| Second hull class | A new ship profile and signal list, no code change, run through Scenario A | the loader | a day | brief: re-configurable vessel |
| Edge inference on the NPU | Vision models on the board's accelerator, only with an open or cleared runtime | the camera pipeline | more | cut by DEC-44; CON-04, DEC-31 |
