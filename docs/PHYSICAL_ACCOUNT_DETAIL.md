# Physical Account, detail

Full reasons and where each assumed number is used. One-page version:
[PHYSICAL_ACCOUNT.md](PHYSICAL_ACCOUNT.md).

| Key | Value | Why | Where used |
|---|---|---|---|
| `rules.r3.approach_min` | 4 | Scenario C rule R3: final approach and landing from the loiter point; G4's own estimate is used if longer. Transit from range runs alongside deck clearing. | not yet in code |
| `rules.r3.drain_pct_min` | 1.11 | R3: 100 % over the 90 min endurance (brief B, G4); we assume G4 never drains slower, which dates the 20 % crossing conservatively. Unverified. | not yet in code |
| `rules.r3.stale_s` | {camera: 3, g4_telemetry: 10} | R3: a camera frame older than 3 s or drone telemetry older than 10 s counts as unknown. | not yet in code |
| `rules.r3.change_threshold` | to_calibrate | R3: how much of a deck marker or zone must change to count as not clear. A false alarm costs a hold, a miss a damaged drone. To be calibrated on the demo webcam. | not yet in code |
| `rules.r3.zone` | marked landing area, flying-stations positions masked, drone secured with no deck hand | R3 guards the marked landing area; the fire party and landing officer stand near but clear of it, which assumes the drone is secured with no deck hand (research E3 puts deck crew on deck for helicopters). | not yet in code |
| `rules.r3.override` | landing officer only, at 14 and 6 aboard, logged, valid for one landing, cancelled by a new detection | R3: an override is an authority act, not a sensor reading; impossible at 0 aboard (brief A.6). | not yet in code |
| `rules.r3.camera` | fixed flight-deck camera, inference in the 20 % ship-systems compute reserve, never shed | R3: the deck camera is ship supply, so its inference sits in the ship-systems compute reserve (brief A.7) and is never shed. | not yet in code |
| `rules.r3.uncrewed_launch` | needs automatic landing and securing, fixed deck firefighting and a lit or low-light deck view for the 90 min sortie | R3 at 0 aboard: nobody can clear the deck (brief A.6), so a launch is refused unless recovery stays possible for the whole sortie. Fixed deck firefighting availability is unconfirmed. | not yet in code |
| `rules.r3.unchanged` | all deck markers visible and the frame matches the last crew sweep | R3 at 0 aboard: the evidence that the deck is still clear since the last crew sweep. | not yet in code |
| `hull.loa_m` | 60 | The slides show a 60 m vessel (reference drawing and demo baseline); the brief allows 60-70 m. We use 60 m; research/sensors/navigation_environment.md assumed 65 m for its roll model and should be re-run at 60 m. | not yet in code |
| `power.guest_reserve_kw_by_speed` | {cruise: 200, fast: 150, slow: 250} | The brief says the reserve is a function of speed and gives 200 kW nominal at cruise within 150-250 kW. Less propulsion load at slow speed leaves more for guests, so slow takes the top of the range and fast the bottom. | not yet in code |
| `power.envelope_reserve_kw` | 200 | The envelope covers the slow and cruise bands, so admission uses the lower of their reserves: 200 kW. | not yet in code |
| `power.line_lost_on_trip` | none | The brief lets us choose. Both lines survive a trip, so the reduced total reserve, not a single line, binds. | not yet in code |
| `power.shed_headroom_kw` | 5 | Kept free after shedding so a normal load swing does not re-trigger the sequence. | not yet in code |
| `power.gensets.load_limit` | 0.9 | Common practice is to load gensets to about 90 % of rating; with it, two 450 kW sets close against the brief's 200 kW guest reserve. | tests/test_brief_arithmetic.py |
| `power.hotel_kw.committed` | 400 | Upper end of the brief's 250-400 kW hotel range, the conservative choice. | tests/test_brief_arithmetic.py |
| `power.ship_aux_kw` | 55 | Ship auxiliaries outside hotel load; chosen so 810 kW minus 400 hotel minus 55 leaves the brief's 200 kW guest reserve with 155 kW spare. | tests/test_brief_arithmetic.py |
| `power.hotel_shed_on_trip_kw` | 150 | Non-essential hotel load the PMS drops on a trip, so one 405 kW set leaves the brief's 100 kW for guests. | tests/test_brief_arithmetic.py |
| `power.trip_confirm` | {needed: 2, signals: [relay_flag, kw_near_zero, frequency_dip]} | A single sensor must not trigger a shed; 2 of 3 independent signals confirm a trip (Viking Sky lesson). | not yet in code |
| `data.satcom_envelope_mbps` | 2 | Admission is judged at the low end of the brief's 2-8 Mbit/s SATCOM range. | not yet in code |
| `data.los_radio_operating_mbps` | 20 | Within the drone's 5-20 km operating range the line-of-sight radio delivers its top rate; range loss is handled at run time, not at admission. | not yet in code |
| `positions.bay1.power_line` | port | One connection per bay; Bay 1 on the port line. | not yet in code |
| `positions.bay2.power_line` | stbd | Bay 2 on the starboard line, so the two bays never share a line. | not yet in code |
| `positions.flight_deck.power_line` | stbd | Flight deck on starboard; drone charging and a Bay 2 guest together stay under 150 kW. | not yet in code |
| `positions.mast_free.power_line` | port | Mast on port, the lighter-loaded line. | not yet in code |
| `positions.hangar_roof` | {cooling: air, kind: roof, max_kg: 60, power_line: stbd, zone: hangar_roof} | The brief allows G5's antenna on the hangar roof (x1.2, check drone clearance); we assume a 0.3 m2 antenna clears drone operations and limit the roof to 60 kg like the mast. | manifests/G5.yaml, manifests/README.md |
| `admission.seawater_scan_step_c` | 0.1 | Resolution for reporting the seawater temperature at which a verdict flips. | not yet in code |
| `admission.seawater_scan_max_c` | 35 | Scan a little past the 30 °C design point to show the stress case off Florida (30.4 °C). | not yet in code |

Taken from the brief without change: `compute`, `crew`, `data`, `envelope`, `heat`, `hull.allowed_loa_m`, `installation`, `mass`, `positions.bay1`, `positions.bay2`, `positions.flight_deck`, `positions.mast_free`, `positions.stern_ramp`, `power.guest_reserve_kw`, `power.mission_line_kw`, `power.peak_extra_kw`, `power.peak_max_s`, `response_time_s`, `ship_state`, `ship_state.emission`.
