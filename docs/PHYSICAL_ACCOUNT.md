# Physical Account (draft)

Generated from `config/assumptions.yaml` by `tools/physical_account.py`. Every number the
software relies on that is not in Annex A or B, or that narrows a range given there.

| Key | Value | Why | Where used |
|---|---|---|---|
| `power.line_lost_on_trip` | none | The brief lets us choose. Both lines survive a trip, so the reduced total reserve, not a single line, binds. | not yet used in code |
| `power.shed_headroom_kw` | 5 | Kept free after shedding so a normal load swing does not re-trigger the sequence. | not yet used in code |
| `power.gensets.load_limit` | 0.9 | Common practice is to load gensets to about 90 % of rating; with it, two 450 kW sets close against the brief's 200 kW guest reserve. | tests/test_brief_arithmetic.py:95 |
| `power.hotel_kw.committed` | 400 | Upper end of the brief's 250-400 kW hotel range, the conservative choice. | tests/test_brief_arithmetic.py:96, tests/test_brief_arithmetic.py:98 |
| `power.ship_aux_kw` | 55 | Ship auxiliaries outside hotel load; chosen so 810 kW minus 400 hotel minus 55 leaves the brief's 200 kW guest reserve with 155 kW spare. | tests/test_brief_arithmetic.py:96, tests/test_brief_arithmetic.py:98 |
| `power.hotel_shed_on_trip_kw` | 150 | Non-essential hotel load the PMS drops on a trip, so one 405 kW set leaves the brief's 100 kW for guests. | tests/test_brief_arithmetic.py:98 |
| `power.trip_confirm` | {needed: 2, signals: [relay_flag, kw_near_zero, frequency_dip]} | A single sensor must not trigger a shed; 2 of 3 independent signals confirm a trip (Viking Sky lesson). | not yet used in code |
| `data.satcom_envelope_mbps` | 2 | Admission is judged at the low end of the brief's 2-8 Mbit/s SATCOM range. | not yet used in code |
| `data.los_radio_operating_mbps` | 20 | Within the drone's 5-20 km operating range the line-of-sight radio delivers its top rate; range loss is handled at run time, not at admission. | not yet used in code |
| `positions.bay1.power_line` | port | One connection per bay; Bay 1 on the port line. | not yet used in code |
| `positions.bay2.power_line` | stbd | Bay 2 on the starboard line, so the two bays never share a line. | not yet used in code |
| `positions.flight_deck.power_line` | stbd | Flight deck on starboard; drone charging and a Bay 2 guest together stay under 150 kW. | not yet used in code |
| `positions.mast_free.power_line` | port | Mast on port, the lighter-loaded line. | not yet used in code |
| `positions.hangar_roof` | {cooling: air, kind: roof, max_kg: 60, power_line: stbd, zone: hangar_roof} | The brief allows G5's antenna on the hangar roof (x1.2, check drone clearance); we assume a 0.3 m2 antenna clears drone operations and limit the roof to 60 kg like the mast. | manifests/G5.yaml:13, manifests/schema.json:82 |
| `admission.seawater_scan_step_c` | 0.1 | Resolution for reporting the seawater temperature at which a verdict flips. | not yet used in code |
| `admission.seawater_scan_max_c` | 35 | Scan a little past the 30 °C design point to show the stress case off Florida (30.4 °C). | not yet used in code |

Taken from the brief without change: `compute`, `crew`, `data`, `envelope`, `heat`, `installation`, `mass`, `positions.bay1`, `positions.bay2`, `positions.flight_deck`, `positions.mast_free`, `positions.stern_ramp`, `power.guest_reserve_kw`, `power.mission_line_kw`, `power.peak_extra_kw`, `power.peak_max_s`, `response_time_s`, `ship_state`.

Guest-card assumptions are marked `assumed: true` in `manifests/G*.yaml`; G6 is wholly ours.

Closing question (draft): more generation. Real 88-95 m patrol ships carry 1.8-2.7 MW;
the reference platform's 900 kW is what makes one genset trip a crisis. To be finalized.
