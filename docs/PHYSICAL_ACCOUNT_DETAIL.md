# Physical Account, detail

Full reasons and every file:line that reads each assumed key. One-page version: [PHYSICAL_ACCOUNT.md](PHYSICAL_ACCOUNT.md).
A key counts as read where a line names its full dotted key, or reads it through a subscript chain on a variable
loaded from its YAML file; "not yet" means nothing reads it yet.

| Key | Value | Why | Where used |
|---|---|---|---|
| `power.guest_reserve_kw_by_speed` | {slow: 250, cruise: 200, fast: 150} | Propulsion is out of model scope: we take the guest reserve as the brief gives it, with propulsion and hotel load already netted out, and model no propulsion load. A.1 quotes 200 kW at cruise within 150-250 kW; we read that range as the speed dependence, since a slower ship leaves more of the bus for guests: slow takes the top (250 kW), fast the bottom (150 kW). | not yet |
| `power.envelope_reserve_kw` | 200 | The mission envelope covers the slow and cruise bands (A.10: use the lower reserve), so admission uses the lower of the two: 200 kW. | tests/test_expected_outcomes_data.py:177 |
| `admission.peak_credit_kw` | 0 | DEC-35, our reading of CON-08: admission never credits the brief's +250 kW (+100 kW with one set down) for up to 60 s. Any draw longer than 60 s is sustained, not a peak (A.1), and a 60 s allowance cannot carry it. | tests/test_scenario_b_timeline_data.py:21 |
| `admission.one_genset_down_gate` | {kw: 95, rule: 'min(one-genset-down reserve, cooling at 30 C) minus shed headroom', over_gate: throttle-only prefix of the D4 ladder; else yes-if; else no} | DEC-35: each admitted set is also judged with one genset down against min(100 kW reserve, 120 kW of cooling at 30 C) minus the 5 kW headroom = 95 kW. Over 95 kW only the throttle-only prefix of the D4 ladder counts (interruptible modes that keep capability above 0, non-critical guests first); reaching 95 kW keeps the verdict as 'holds by throttling', otherwise it becomes yes-if or no. | tests/test_scenario_b_timeline_data.py:72 |
| `power.shed_headroom_kw` | 5 | Kept free after shedding so a normal load swing does not re-trigger the sequence. | tests/test_envelope_gate_data.py:29, tests/test_expected_outcomes_data.py:32, tests/test_scenario_b_timeline_data.py:23 |
| `power.trip_confirm` | {signals: [relay_flag, kw_near_zero, frequency_dip], needed: 2} | A single sensor must not trigger a shed; 2 of 3 independent signals confirm a trip (Viking Sky lesson). | not yet |
| `positions.bay1.power_line` | port | One connection per bay (A.1); Bay 1 on the port line. | tests/test_expected_outcomes_data.py:108 |
| `positions.bay2.power_line` | stbd | Bay 2 on the starboard line, so the two bays never share a line. | tests/test_expected_outcomes_data.py:108 |
| `positions.flight_deck.power_line` | stbd | Flight deck on starboard; drone charging and a Bay 2 guest together stay under 150 kW. | tests/test_expected_outcomes_data.py:108 |
| `positions.mast_free.power_line` | port | Mast on port, the lighter-loaded line. | tests/test_expected_outcomes_data.py:108 |
| `power.line_lost_on_trip` | none | A.9 lets us choose. Both mission lines survive a genset trip, so the reduced total reserve, not a single line, binds. | not yet |
| `power.gensets.load_limit` | 0.9 | Plant check only, read by tests/test_brief_arithmetic.py and by no decision. Common practice loads gensets to about 90 % of rating, so each 450 kW set gives 405 kW. | tests/test_brief_arithmetic.py:146 |
| `power.hotel_kw.committed` | 400 | Plant check only. The top of A.1's 250-400 kW committed hotel load, the conservative choice. | tests/test_brief_arithmetic.py:147, tests/test_brief_arithmetic.py:149 |
| `power.ship_aux_kw` | 55 | Plant check only. Ship auxiliaries outside the hotel load, chillers and chilled-water pumps among them. With it, one 405 kW set less the 250 kW of hotel kept after the shed leaves exactly the brief's 100 kW (A.9), and two sets leave at least the 200 kW reserve at cruise. The check has no propulsion term, because propulsion is out of model scope (see power.guest_reserve_kw_by_speed), so it shows the brief's reserves are reachable, not a full electrical balance. | tests/test_brief_arithmetic.py:147, tests/test_brief_arithmetic.py:149 |
| `power.hotel_shed_on_trip_kw` | 150 | Plant check only. Non-essential hotel load the power management system drops on a trip, so one set leaves the brief's 100 kW for guests. | tests/test_brief_arithmetic.py:149 |
| `heat.degraded_means` | one chilled-water pump of two | The brief's -40 % degraded loop (A.2, pump or exchanger down) is read as one of two chilled-water pumps lost. | not yet |
| `heat.degraded_confirm` | plant alarm plus flow or delta-T, automatic | Scenario B (DEC-40): a cooling fault counts as confirmed only on the plant alarm plus flow or delta-T, automatically; camera evidence alone only precomputes the plan. | not yet |
| `heat.camera_unknown` | plant sensors decide; camera evidence alone never confirms a fault | research/cv_equipment_monitoring.md C1. Camera evidence alone never confirms a cooling fault (heat.degraded_confirm). When the leak camera is unknown, plant sensors decide, where pump status unknown already counts as degraded, and only the early warning is lost. This is the one exception to 'camera unknown counts as changed', because cameras are not guaranteed (DEC-27). | not yet |
| `heat.chillers_on_essential_board` | True | Chillers and chilled-water pumps sit on the essential board inside the 55 kW ship auxiliaries, so the 150 kW non-essential hotel shed on a genset trip does not take cooling with it. | not yet |
| `admission.seawater_scan_step_c` | 0.1 | Resolution for reporting the seawater temperature at which a verdict flips. | tests/test_expected_outcomes_data.py:555 |
| `admission.seawater_scan_max_c` | 35 | Scan a little past the 30 C design point (A.10) to show the stress case off Florida (30.4 C). | tests/test_expected_outcomes_data.py:554 |
| `hull.loa_m` | 60 | The slides show a 60 m vessel (reference drawing and demo baseline); the brief allows 60-70 m. We use 60 m. The roll model in research/sensors/navigation_environment.md, built at 65 m, was re-checked at 60 m: roll period 9.75 s against 9.70 s, no material change. | not yet |
| `positions.hangar_roof` | {kind: roof, max_kg: 60, power_line: stbd, cooling: air, zone: hangar_roof} | The brief allows G5's antenna on the hangar roof (x1.2, check drone clearance); we assume a 0.3 m2 antenna clears drone operations, limit the roof to 60 kg like the mast and feed it from the starboard line with the flight deck. | manifests/G5.yaml:13 |
| `scenario_b.guests` | [G3, G4, G5] | DEC-32: the brief's Scenario B load-out G2, G3, G4, G5 is 13.015 t against the 10 t mass margin (A.4) and needs Bay 2 twice, so it is refused at the pier and G3, G4, G5 (9.515 t) runs, with a logged override for extreme situations. | tests/test_scenario_b_timeline_data.py:45, tests/test_scenario_b_timeline_data.py:46, tests/test_scenario_b_timeline_data.py:145 |
| `admission.data_rates_judged_at` | guest_minimum | DEC-38: admission judges data links at guests' minimum rates and reports the nominal shortfall as degraded quality. At nominal rates G5's 6 Mbit/s alone exceeds the 2 Mbit/s SATCOM floor and would change verdicts. | not yet |
| `data.satcom_envelope_mbps` | 2 | Admission judges SATCOM at the low end of the brief's 2-8 Mbit/s: it is shared by everyone aboard and only 70-95 % available (A.5), and nothing aboard controls its rate. | tests/test_expected_outcomes_data.py:574 |
| `data.los_radio_operating_mbps` | 20 | Within 20 km (data.los_radio_drone_range_km_max) we assume the radio gives its top rate, 20 Mbit/s; the brief does not say how the rate falls with range. This is the opposite end from SATCOM, judged at its floor, because the drone's range is set by how we fly it and SATCOM's rate is not. At the 1 Mbit/s floor, G4's 5 Mbit/s minimum would fail every set with G4 (A1, A2, A3, A5, A6, Scenario B). Range loss in flight is handled at run time, not at admission. | not yet |
| `data.los_radio_drone_range_km_max` | 20 | We assume G4 flies within 20 km of the ship, the near end of A.5's 20-40 km radio reach. Unverified: neither the brief nor our research gives the drone's range. | not yet |
| `transition_picks.r3_worst_case` | {confirm_min: {14: 1, 6: 3}, clear_deck_min: {14: 5, 6: 12}} | Rule R3's lead time takes the slow end of each A.6 range so the rule holds in the worst case: confirm 1 min at 14 aboard (15-60 s) and 3 min at 6 (1-3 min); clear the deck in 5 min at 14 (3-5 min) and 12 min at 6 (8-12 min). | tests/test_scenario_b_timeline_data.py:56, tests/test_scenario_b_timeline_data.py:57 |
| `scenario_b.seed_pins.confirm_min` | 1 | A.6: crew confirmation takes 15-60 s with 14 aboard; the demo seed pins the slow end, 1 min, as R3's worst case does. | tests/test_scenario_b_timeline_data.py:67 |
| `scenario_b.seed_pins.deck_clear_min` | 4 | A.6: 3-5 min to clear the deck with full crew; the demo seed pins 4 min. R3's worst-case pick stays 5 min (transition_picks.r3_worst_case); with it G4 would land at minute 18, still inside its minute-18.2 deadline. | tests/test_scenario_b_timeline_data.py:67 |
| `scenario_b.seed_pins.approach_min` | 4 | The same 4 min final approach as rules.r3.approach_min. | tests/test_scenario_b_timeline_data.py:59, tests/test_scenario_b_timeline_data.py:67 |
| `scenario_b.seed_pins.g4_lands_at_min` | 17 | Decision at minute 8, then confirm 1 + clear deck 4 + approach 4 = minute 17 (DEC-40). A fixed seed keeps the demo replayable. | tests/test_scenario_b_timeline_data.py:58, tests/test_scenario_b_timeline_data.py:67 |
| `decision_watchdog` | {budget: response_time_s ceiling of each decision, on_miss: {admission: 'no, timed out', placement: keep current, arbitration: keep current ship state, shedding: last precomputed ladder}} | Annex C asks for solver budget and timeout behaviour. Each decision's budget is its A.8 ceiling (admission and placement 30 s, arbitration 2 s, first shed 5 s). On a miss a watchdog emits the safe default with a sentence naming the ceiling (GAMEPLAN, watchdogs and safe defaults): admission answers no, placement keeps the current plan, arbitration keeps the current ship state and retries, and shedding runs the ladder precomputed on the last tick (DEC-16), so a slow solver never delays the first shed. | not yet |
| `rules.r3.camera` | fixed flight-deck camera, inference in the 20 % ship-systems compute reserve, never shed | R3: the deck camera is ship supply, so its inference sits in the ship-systems compute reserve (brief A.7) and is never shed. | not yet |
| `rules.r3.zone` | marked landing area, flying-stations positions masked, drone secured with no deck hand | R3 guards the marked landing area; the fire party and landing officer stand near but clear of it, which assumes the drone is secured with no deck hand (research E3 puts deck crew on deck for helicopters). | not yet |
| `rules.r3.change_threshold` | to_calibrate | R3: how much of a deck marker or zone must change to count as not clear. A false alarm costs a hold, a miss a damaged drone. To be calibrated on the demo webcam. | not yet |
| `rules.r3.unchanged` | all deck markers visible and the frame matches the last crew sweep | R3 at 0 aboard: the evidence that the deck is still clear since the last crew sweep. | not yet |
| `rules.r3.override` | landing officer only, at 14 and 6 aboard, logged, valid for one landing, cancelled by a new detection | R3: an override is an authority act, not a sensor reading; impossible at 0 aboard (brief A.6). | not yet |
| `rules.r3.uncrewed_launch` | needs automatic landing and securing, fixed deck firefighting and a lit or low-light deck view for the 90 min sortie | R3 at 0 aboard: nobody can clear the deck (brief A.6), so a launch is refused unless recovery stays possible for the whole sortie. Fixed deck firefighting availability is unconfirmed. | not yet |
| `rules.r3.approach_min` | 4 | Scenario C rule R3: final approach and landing from the loiter point; G4's own estimate is used if longer. Transit from range runs alongside deck clearing. | tests/test_expected_outcomes_data.py:761, tests/test_scenario_b_timeline_data.py:57, tests/test_scenario_b_timeline_data.py:59 |
| `rules.r3.drain_pct_min` | 1.11 | R3: 100 % over the 90 min endurance (brief B, G4); we assume G4 never drains slower, which dates the 20 % crossing conservatively. Unverified. | tests/test_expected_outcomes_data.py:760, tests/test_scenario_b_timeline_data.py:55 |
| `rules.r3.stale_s` | {camera: 3, g4_telemetry: 10} | R3: a camera frame older than 3 s or drone telemetry older than 10 s counts as unknown. | not yet |
| `scenario_b.events.cooling_degraded` | {t_min: 19, type: cooling_degraded, factor: 0.6, confirmed: true, added_event: true, trigger: {after: {guest: G4, state: landed_fast_charging}, delay_min: 2}, load_modes: {G3: standby, G4: fast_charge, G5: full}} | Invented, labelled event (DEC-40): a chilled-water pump fails 2 min after G4 lands, so it always falls inside G4's 20-min fast charge. The -40 % is brief A.2 and no repair at sea is A.6. At 24 C the loop drops from 133.3 to 80 kW, a 75 kW ceiling against the 81 kW of load_modes, so cooling binds: survey slows G4's charge to 10 kW (56 kW), sar takes G5 to 8 kW (44 kW). | tests/test_scenario_b_timeline_data.py:31, tests/test_scenario_b_timeline_data.py:95, tests/test_scenario_b_timeline_data.py:124 |

## Guest-card values we assumed

Card lines marked `assumed: true`: at least one number on the line is ours, not Annex B's. G6 is wholly our invention.

| Card line | Where |
|---|---|
| `compute_cores: {nominal: 2, assumed: true}` | manifests/G1.yaml:17 |
| `compute_cores: {nominal: 2, assumed: true}` | manifests/G2.yaml:18 |
| `- {name: sampling, power_kw: 6, capability_retained: 0.8, assumed: true, note: "logging without the winch"}` | manifests/G2.yaml:21 |
| `- {name: standby, power_kw: 1, capability_retained: 0.0, assumed: true}` | manifests/G2.yaml:22 |
| `- {name: cradle, mass_t: 3.5, assumed: true, preferred: [bay1], allowed: [bay1], note: "whole Bay 1, port only` | manifests/G3.yaml:13 |
| `- {name: vehicle, mass_t: 2.0, length_m: 5.5, assumed: true, part_of: cradle, preferred: [bay1], allowed: [bay` | manifests/G3.yaml:14 |
| `data_acoustic_kbps: {min: 1, nominal: 3, assumed: true, note: "acoustic link while submerged"}` | manifests/G3.yaml:18 |
| `compute_cores: {nominal: 4, assumed: true}` | manifests/G3.yaml:19 |
| `- {name: standby, power_kw: 1, capability_retained: 0.3, assumed: true, note: "vehicle holds or waits on its o` | manifests/G3.yaml:22 |
| `compute_cores: {nominal: 4, assumed: true}` | manifests/G4.yaml:17 |
| `- {name: charge, power_kw: 10, capability_retained: 0.7, assumed: true, note: "slower recharge delays the next` | manifests/G4.yaml:20 |
| `- {name: standby, power_kw: 2, capability_retained: 0.3, assumed: true}` | manifests/G4.yaml:21 |
| `data_satcom_mbps: {min: 1, nominal: 6, assumed: true, note: "up to 6 of 8 Mbit/s; 1 Mbit/s minimum is our assu` | manifests/G5.yaml:17 |
| `power_kw: {min: 4, nominal: 18, assumed: true}` | manifests/G6.yaml:14 |
| `data_backbone_mbps: {nominal: 2, assumed: true}` | manifests/G6.yaml:15 |
| `compute_cores: {nominal: 1, assumed: true}` | manifests/G6.yaml:16 |
| `- {name: production, power_kw: 18, capability_retained: 1.0, assumed: true}` | manifests/G6.yaml:18 |
| `- {name: recirculate, power_kw: 4, capability_retained: 0.1, assumed: true, note: "keeps membranes wet, produc` | manifests/G6.yaml:19 |

Taken from the brief, then narrowed by the rows above: `power.guest_reserve_kw`: used at the nominal 200 and 100 kW of the 150-250 and 90-120 kW ranges; `power.peak_extra_kw`: never credited at admission (admission.peak_credit_kw, DEC-35); `positions.stern_ramp`: a craft is judged against the 7 m low end of 7-9 m, per the G3 card; `data`: SATCOM judged at 2 Mbit/s, the line-of-sight radio at 20 Mbit/s and guests at their minimum rates; `ship_state`: single picks in transition_picks.r3_worst_case and the Scenario B seed pins; `crew`: single picks in transition_picks.r3_worst_case and the Scenario B seed pins.

Taken from the brief without change: `compute`, `envelope`, `heat`, `hull.allowed_loa_m`, `installation`, `mass`, `positions.bay1`, `positions.bay2`, `positions.flight_deck`, `positions.mast_free`, `power.mission_line_kw`, `power.peak_max_s`, `response_time_s`, `scenario_b.location`, `ship_state.emission`.

The closing answer's numbers are derived from these files by tools/physical_account.py, which stops if any of its
claims no longer holds; tests/test_scenario_b_timeline_data.py checks them again.
