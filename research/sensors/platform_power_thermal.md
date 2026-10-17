# Platform sensors: power, thermal, machinery, mass/stability, safety

Scope: what a resource governor on a fictional 60–70 m multi-role vessel would read from platform systems, which public data can calibrate it, and synthetic specs for everything else. Research cut-off 2026-10-16.
Legend: `*` = value confirmed in a cited source [n]; `est.` = engineering estimate; `assumed` = modelling assumption for our simulator; `unconfirmed` = could not verify.

**Protocols in this domain.** Genset controllers, multifunction meters, chillers and the integrated automation system (IAS) usually talk **Modbus RTU/TCP**; for example, a DEIF AGC 150 exposes kW, kVAr, V, I, f and PF over Modbus TCP [22]. Engine ECUs use **SAE J1939** (CAN, 250 kbit/s): SPN 190 engine speed is in PGN 61444, SPN 100 oil pressure in PGN 65263, SPN 175 oil temperature in PGN 65262, and SPN 183 fuel rate in PGN 65266 [21]. ET1 (PGN 65262) is sent every 1 s* [20]. The authoritative list is SAE J1939-DA, which is paywalled. Small-craft engines also publish **NMEA 2000**: PGN 127488 Engine Rapid at 10 Hz* and PGN 127489 Engine Dynamic at 1 Hz* (oil pressure and temperature, coolant temperature, fuel rate, alarm flags) [19]. Field definitions come from canboat, which reverse-engineered them because the NMEA database is copyrighted [18]. **CANopen** is common in BMS and crane load cells (vendor-specific, unconfirmed). **IEC 61850** (MMS/GOOSE) is for protection IEDs; evidence of shipboard use is only indirect, as IEEE 45.3-2025 references it [34]. **OPC UA** is the usual northbound IAS interface (vendor-specific). **IEC 61162-450** multicasts IEC 61162-1 sentences and 61162-3 PGNs over UDP on a single layer-1/2 Ethernet network. It is navigation-centric (ed. 3.0, 2024) [27] and is where the inclinometer and the seawater-temperature (MTW) sentences live.

## 1. Sensor table

| Sensor | Measures | Data type & units | Typical rate | Interface/protocol | Feeds (resource / ship-state / guest) | Fitted 60–100 m? |
|---|---|---|---|---|---|---|
| Genset AC meter (in controller) | P, Q, PF, f, V, I per phase, kWh | float kW, kVAr, –, Hz, V, A | 2–10 Hz poll (est.) | Modbus TCP/RTU [22]; J1939 generator PGNs (unconfirmed) | power supply; genset status | yes |
| Engine speed pickup | rpm | float rpm | 10 Hz* (PGN 127488) | J1939 SPN 190 / NMEA 2000 | genset status; **overspeed trip precursor** | yes |
| Lube-oil pressure | pressure | float bar | 1 Hz* (PGN 127489) | J1939 SPN 100; 4–20 mA | **trip precursor**: low alarm then shutdown, often hard-wired [25] | yes |
| Lube-oil temperature | temperature | float °C | 1 Hz* (ET1) | J1939 SPN 175 | slow precursor | yes |
| Jacket/coolant water temperature | temperature | float °C | 1 Hz* | J1939 SPN 110; PGN 127489 | **trip precursor**: high alarm then shutdown [25] | yes |
| Exhaust gas temperatures (per cylinder, turbo in/out) | temperature | float °C (thermocouple) | 1 Hz (est.) | thermocouple module to IAS (Modbus/Profibus) | derate/alarm precursor; load plausibility | yes (per-cylinder sometimes on small high-speed sets) |
| Charge-air pressure and temperature | pressure, temperature | float bar, °C | 1 Hz | J1939; 4–20 mA | derate precursor (air-cooler fouling) | yes |
| Fuel rate / fuel rack / flowmeter | flow, rack position | float L/h or kg/h; % | 1 Hz | J1939 SPN 183; Coriolis meter over Modbus | emission state; specific fuel consumption check | yes (ECU); sometimes (flowmeter) |
| Crankcase oil-mist detector | mist concentration | float + alarm | 1 Hz | Modbus / digital input | trip precursor | rarely at ~450 kW (class threshold unconfirmed) |
| Generator winding and bearing PT100s | temperature | float °C | 1 Hz | RTD / 4–20 mA to IAS | slow precursor | sometimes |
| Generator protection relay | trips: ANSI 32 reverse power, 50/51 overcurrent, 27/59 under/over-voltage, 81 under/over-frequency, 40 loss of excitation | bool events + fault record | event (ms-class) | hard-wired to breaker; status over Modbus or IEC 61850 | **genset trip = instant capacity loss** | yes (IEC 61850 rarely) |
| Breaker positions (gen ACB, bus-tie, feeders, MPL-1/2, shore) | position | enum: open / closed / tripped / withdrawn | event + 1 Hz poll | digital input to PLC, then Modbus/Profinet | power topology; admission | yes |
| Busbar voltage and frequency | V, f | float V, Hz | 10 Hz (est.) | PMS | blackout and overload detection; a frequency dip is the earliest overload cue | yes |
| PMS status | sets online, available kW, load-dependent start/stop, heavy-consumer request/grant, preferential-trip stage | int / enum / kW | 1 Hz + events | Modbus TCP / OPC UA | power admission, right of way, shedding | yes (with ≥2 sets) |
| Preferential-trip relays | stage 1/2 tripped | bool | event; example delays 5 s and 10 s, main breaker at 15 s* [23] | hard-wired | baseline load shedding. Class rules: shed below 100 % rated current; loss of one paralleled set immediately trips non-important loads [24] | yes |
| Mission power line meters (2 × 150 kW) | kW, A, kWh, THD | float | 5–10 Hz (est.) | multifunction meter, Modbus | per-guest draw; heat input | sometimes (guest-level metering) |
| Shore connection panel | kW, V, f, phase sequence, earth fault, interlocks | float / bool | 1 Hz | Modbus. IEC/IEEE 80005-3:2025 governs LV shore connections (400–1000 V, ≥250 A, ≤1 MVA) [28] | harbour power | sometimes |
| UPS / battery bank | SoC %, V, A, temperature, runtime, alarms | float / enum | 1 Hz | Modbus / SNMP; NMEA 2000 PGN 127508/127506 (rates unconfirmed); CAN BMS | compute and response-time holdup; peak buffer | yes (UPS); sometimes (ESS) |
| Insulation monitor (IT network) | insulation resistance, earth-fault alarm | float kΩ / bool | 1 Hz | Modbus / digital input | electrical safety; guest isolation | yes |
| Chilled-water supply/return temperature | temperature | float °C (PT100) | 1 Hz (BMS often 10–60 s) | Modbus RTU/TCP | heat rejection used | yes |
| Chilled-water flow | flow | float m³/h | 1 Hz | magnetic/ultrasonic meter, Modbus | Q = ṁ·cp·ΔT | sometimes (often inferred from pump state) |
| Chiller unit | run/trip, capacity %, compressor kW, alarms | enum / float | 1 Hz | chiller controller, Modbus | cooling capacity | yes |
| Chilled-water and seawater pumps | run/trip, ΔP | bool / bar | 1 Hz | digital input / Modbus | degraded mode (−40 %) | yes |
| Seawater inlet temperature | temperature | float °C | 0.1–1 Hz | 4–20 mA to IAS; NMEA 0183/61162-1 MTW sentence | chiller derating (env) | yes |
| Heat-exchanger fouling indicators | seawater ΔP across exchanger, approach temperature (derived) | float | 0.1 Hz | IAS | slow capacity drift | sometimes |
| Compartment temperature/RH | temperature, humidity | float °C, %RH | 0.1 Hz | HVAC Modbus | thermal margin per zone | yes |
| Rack inlet/outlet temperature, PDU power | temperature, power | float °C, kW | 0.2–1 Hz | SNMP / Redfish / Modbus | compute class; heat | sometimes |
| Vibration condition monitoring | overall velocity RMS (ISO 10816-6 for reciprocating machines >100 kW [29]); raw acceleration 10–50 kHz | float / waveform | overall per minute; raw on trigger | CMS gateway, OPC UA / Modbus | prognostic headroom; noise-state proxy | sometimes online; handheld surveys are common |
| Shaft-line/gearbox bearing PT100s | temperature | float °C | 1 Hz | IAS | precursor | yes |
| Tank levels (fuel, fresh water, ballast, sewage) | level, volume | float m, m³, % | 0.1–1 Hz | radar or pressure, 4–20 mA/HART; PGN 127505 on small craft | mass margin; free surface | yes |
| Draft gauges fwd/aft (pressure) | draft | float m | 1 Hz | 4–20 mA to loading computer | displacement, trim | sometimes |
| Electronic inclinometer | heel, roll amplitude, roll period | float °, s | ≥5 Hz output over IEC 61162; ±90° range [31] | IEC 61162-1/-450; IMO MSC.363(92), ISO 19697 [30] | stability cross-check; sea state | sometimes |
| Loading computer | displacement, KG, GM, trim, heel, % of limit | float t, m, ° | on demand / 0.01–0.1 Hz | proprietary; export over Modbus/OPC UA (vendor-specific). Software approved under IACS UR L5 [32] | mass/stability budget | sometimes (common on OSVs) |
| Crane/winch load cell | load | float t | 10 Hz | CANopen / Modbus (unconfirmed) | deck positions; dynamic mass | sometimes |
| Fire detection (addressable) | per address: normal / pre-alarm / alarm / fault / disabled | enum | loop poll ~1–5 s (est.); alarms as events | proprietary loop, serial/Modbus gateway; FSS Code Ch. 9 | deck state; fan/damper trips cut zone cooling | yes |
| Bilge / flood level | high and high-high switches; some analog | bool / float | event | digital input to IAS | stability; emergency right of way | yes |
| Gas detection | %LEL (H₂ in battery rooms, fuel vapour), ppm CO, %O₂ | float + alarm | 1 Hz | 4–20 mA / Modbus | battery-guest admission; ventilation | sometimes |
| Watertight door status | open / closed / locked; local or remote | enum | event + 1 Hz | digital input to door panel; SOLAS II-1 (clause unconfirmed) | deck state; damage-stability posture | yes (where fitted) |
| Underwater/structure-borne noise | dB, spectra | float | 1 Hz summary | hydrophone or accelerometer to CMS | noise-level state | rarely (naval/research only) |

## 2. Public datasets and APIs

| Name | Content | Format & size | Licence | Origin (org, country) | URL | What we would use it for | Caveats |
|---|---|---|---|---|---|---|---|
| UCI Condition Based Maintenance of Naval Propulsion Plants | 11,934 simulated steady states of a CODLAG frigate gas turbine: speed, GT torque/rpm, T48, P1/P2, fuel flow kg/s, plus compressor and turbine decay coefficients | text; zip 554 kB (data.txt 3.3 MB) [1] | CC BY 4.0 [1] | Coraddu, Oneto, Anguita, Figari et al., Univ. of Genoa, Italy [2] | [1] | fuel-flow-vs-load shape; slow decay-drift scenarios; Italian naval storyline | gas turbine, not a diesel genset; steady states on a decay grid, not a time series |
| Marine Engine Fault (Zenodo 19857425) | Test-bench Matsui MU323DGSC marine diesel: 1 baseline + 15 fault runs (filter clogging, air-cooler fouling, nozzle clogging, cooling-water pump cavitation, turbine degradation) at 40–85 % load; ~70 channels, ~115k rows | 16 CSV; zip 26.5 MB [3] | CC BY 4.0 [3] | Aalto Univ. and Univ. of Turku (Finland), PoliMi (Italy). Engine maker is Japanese; bench location not stated [3][4] | [3] | calibrate exhaust and cooling temperatures vs % load; precursor signatures for injected genset faults | sample rate not stated; citation text has placeholders; lube-oil channels unconfirmed; propulsion test engine, not a genset |
| Auxiliary battery hybridization under N-1 (Zenodo 23089007) | Tanker (7,273 GT) operating logs, engine load profiles, fuel flowmeters, emissions | xlsx 2.2 MB [5] | CC BY 4.0 [5] | Istanbul Technical Univ., Türkiye [5] | [5] | aux/hotel load variability and step-size distributions; kWh-to-fuel sanity | sampling interval and time span not stated; published 2026-10-01, unreviewed; anonymised |
| LBNL FDD datasets: chiller plant | Simulated (EnergyPlus–Modelica) plant, 1 year at 1-min resolution; 7 faults incl. CHW leaving-temperature sensor bias ±1/±2 °C, ΔP sensor bias, valve leak/stuck, cooling-tower HX fouling | 22 CSV, 1.14 GB total [7]; Brick-schema TTL [6] | CC BY 4.0 (OEDI) [6] | LBNL, PNNL, NREL, ORNL, Drexel; USA [6][8] | [6] | sensor-bias and fouling templates for CHW fault injection; Brick point naming | land building with cooling tower, not seawater-cooled; pull only 2–3 files |
| ASHRAE RP-1043 chiller data (figshare copy) | Lab chiller under normal operation + 7 faults × 4 severities | zip 51 MB [9] | uploader states CC0 [9]; ASHRAE's own terms unconfirmed | uploaded by Zengrui Tian, no institution listed [9]; original project by ASHRAE (USA) | [9] | classic chiller fault signatures | uploader may not hold the rights, so the licence chain is unclear; avoid unless ASHRAE terms are confirmed |
| NASA/IMS bearing run-to-failure | Vibration from run-to-failure bearing tests | zip; size unconfirmed | "U.S. Government Works" on data.gov [11]; NASA asks for acknowledgement, use at own risk [10] | IMS Univ. of Cincinnati / NASA Ames, USA | [10][11] | shape of vibration-RMS degradation trends for drift injection | test rig, not marine; large download; use one run |
| CWRU Bearing Data Center | Drive-end/fan-end accelerometer, 12 k/48 k samples/s, seeded faults | .mat; total size unconfirmed [12] | **no licence stated** (© CWRU footer) [12] | Case Western Reserve Univ., USA | [12] | none, under our licence rule | fails the "openly licensed" rule |
| Paderborn KAt bearing data | Vibration + motor current at 64 kHz, 32 bearings | .mat | **CC BY-NC 4.0** [13] | Paderborn Univ., Germany | [13] | none | non-commercial; exclude |
| MFPT fault data sets | Bearing baseline at 97,656 samples/s; faults at 48,828 samples/s | .mat zip | "freely distributed"; no licence text [14] | MFPT society, USA | [14] | none unless clarified | licence unconfirmed |
| FuelCast (KROHNE Digital) | 3 ships: generator shaft power and fuel, propeller torque, speed | Parquet, ~174k rows [15] | **CC BY-NC-ND 4.0** [15] | KROHNE Digital; country not stated on page | [15] | reading only | NC-ND; exclude from the build |
| Port of Funchal power quality (Zenodo 22834087) | Port-side V, I, P, Q, THD at multiple intervals + vessel arrivals + weather | zip 33.8 MB [16] | CC BY 4.0 [16] | IST / INESC-ID, Univ. of Lisbon; Madeira, Portugal | [16] | shore-supply power-quality realism (optional) | port side; link to onboard shore power not stated |
| NASA PCoE Li-ion battery aging | 18650 cells (2 Ah), charge/discharge/EIS cycles to 30 % fade | .mat | NASA repository terms [10]; one data.gov mirror labels it "non-federal" [17] | NASA Ames, USA | [10][17] | UPS capacity-fade shape (optional) | cell-level only; licence label inconsistent |
| canboat PGN database | Field-level NMEA 2000 PGN definitions (units, resolution) + analyzer | JSON/XML/YAML | Apache 2.0 [18] | open-source project | [18] | schemas for our simulated N2K engine/fluid/battery messages | reverse engineered, not official |
| R/V Gunnerus sensor data (NTNU) | Seapath 10 Hz, wave radar, engine data, crane | by request [33] | none stated | NTNU, Norway | [33] | none | no open download |
| Flagged, not used | XJTU-SY and HUST bearing datasets | – | not checked | China-based universities | – | – | China-based origin; excluded as a precaution (not fetched) |

No open dataset was found for any of these: shipboard switchboard/PMS logs, seawater-cooled chilled-water plants, loading-computer outputs, fire/bilge/watertight-door event logs. Seawater temperature comes from the environment agent's SST source.

## 3. Synthetic generator specs

`plausible_rate` values are **test-design assumptions**, not field reliability statistics (OREDA-type data is proprietary). Shared state comes first; each signal block follows.

```yaml
# SHARED SIMULATOR STATE (not a signal)
consts: {P_GEN_KW: 450, N_GEN: 2, P_HARB_KW: 150, LOAD_LIMIT: 0.9, PEAK_EXTRA_KW: 250, PEAK_MAX_S: 60, MPL_LIMIT_KW: 150, F_NOM_HZ: 60,  # 60 Hz assumed, configurable
         Q_CHW_12C_KW: 160, Q_CHW_30C_KW: 120, DEGRADED: 0.6, INERTIA_KW: 30, INERTIA_S: 60, INERTIA_PERIOD_S: 600, CHW_SUP_SET_C: 7.0, CHW_MDOT_KGS: 7.6,
         MASS_MARGIN_T: 10, STAB_BUDGET_TEQ: 12, MULT: {deck: 1.0, hangar_flight_deck: 1.2, mast: 3.0}, GEN_RESTART_S: [300, 900]}
state: {hotel_kw: "250..400 (crew 14: 330-400, 6: 280-340, 0: 250-280; assumed) + diurnal ±20 + OU noise", ship_aux_kw: 55,  # assumed
        guests: [{draw_kw, line: MPL1|MPL2, on_chw: bool, mass_t, slot: deck|hangar_flight_deck|mast, zone}], gen_online: [bool, bool], cooling_degraded: bool,
        sw_temp_c: env, sea_state: env, crew_level: 14|6|0}
closure: "Cruise, 2 sets: usable 0.9*900 = 810; committed 400+55 = 455; guest cap 200 (policy) leaves 155 spinning margin. N-1: usable 405; PMS fast-sheds 150 kW non-essential hotel (400 to 250) [24]; 405-250-55 = 100 kW guest cap, matching the reference.
         Peak: 455+200+250 = 905, about 2 x 450 rated, for <=60 s. A trip with guests at 200: 655 kW lands on one set, so guests must drop to 100 within ~1 s."
```
```yaml
id: gen_kw[i]        # same model for harb_kw with P_HARB_KW
unit: kW
rate_hz: 5
derives_from: "gen_kw[i] = gen_online[i] * (hotel_kw + ship_aux_kw + sum(guest.draw_kw)) / n_online   # isochronous load sharing; step to 0 on trip"
noise: {type: gaussian, sigma: "0.5% of reading + 1 kW"}
lag_s: 0.5
failure_modes: [{type: dropout, params: {dur_s: [2, 60]}, plausible_rate: "1/500 h"}, {type: stuck_at, params: {value: last}, plausible_rate: "1/5000 h"}, {type: quantization, params: {step_kw: 1}, plausible_rate: always}, {type: latency, params: {extra_s: [1, 5]}, plausible_rate: "1/200 h (gateway congestion)"}]
calibrate_against: "Zenodo 23089007 load profiles (variability, step sizes) + closure arithmetic"
```
```yaml
id: bus_freq_hz
unit: Hz
rate_hz: 10
derives_from: "step dP onto online capacity C: f = F_NOM*(1 - 0.1*dP/C*exp(-t/3)) (est.); if P_load > C_rated: df/dt = -F_NOM*(P_load-C)/(2*H*C), H = 1.0 s (est.); under-frequency trip if f < 0.9*F_NOM for > 2 s (assumed)"
noise: {type: gaussian, sigma: 0.02}
lag_s: 0.1
failure_modes: [{type: desync, params: {skew_s: [0.5, 2]}, plausible_rate: "1/1000 h (PMS vs relay clocks)"}, {type: spike, params: {amp_hz: 2, dur_s: 0.2}, plausible_rate: "1/100 h (harmonics)"}, {type: stuck_at, params: {value: last}, plausible_rate: "1/10000 h"}]
calibrate_against: "physics; class transient/steady frequency limits (commonly quoted ±10 %/±5 %, clause unconfirmed)"
```
```yaml
id: gen_breaker_state[i]
unit: "enum {closed, open, tripped, withdrawn, unknown}"
rate_hz: 1          # plus events
derives_from: "tripped on injected trip OR relay: reverse power gen_kw < -0.05*P_GEN_KW for 3 s; overcurrent gen_kw > P_GEN_KW for > PEAK_MAX_S or > 1.45*P_GEN_KW for 1 s; under-frequency (above). Restart: closed after U(GEN_RESTART_S)"
noise: {type: none, sigma: 0}
lag_s: 0.05         # hard-wired digital input; 1.0 if read via Modbus
failure_modes: [{type: desync, params: {pms_shows: closed, relay_shows: tripped, dur_s: [1, 3]}, plausible_rate: "1/1000 h"}, {type: false_alarm, params: {aux_contact_chatter_s: 0.1}, plausible_rate: "1/2000 h"}, {type: stuck_at, params: {value: closed}, plausible_rate: "1/20000 h (welded aux contact)"}]
calibrate_against: "reference (instant trip, 5-15 min restart); preferential-trip timing [23]"
```
```yaml
id: pms_spinning_reserve_kw
unit: kW
rate_hz: 1
derives_from: "LOAD_LIMIT*P_GEN_KW*n_online - sum(gen_kw); governor guest budget = min(policy_cap{2 sets: 200, 1 set: 100, harbour set: 0.9*150 - hotel_harbour_kw(80-130, assumed)}, reserve + sum(guest.draw_kw))"
noise: {type: none, sigma: 0}
lag_s: 1.0
failure_modes: [{type: latency, params: {age_s: [2, 10]}, plausible_rate: "1/100 h"}, {type: desync, params: {n_online_not_updated_s: [1, 3]}, plausible_rate: "1/500 h (reports pre-trip reserve)"}, {type: stuck_at, params: {value: last}, plausible_rate: "1/5000 h"}]
calibrate_against: "closure arithmetic; reference numbers"
```
```yaml
id: gen_lo_press_bar[i]
unit: bar
rate_hz: 1
derives_from: "4.5*(rpm/rpm_rated)^2 - 0.01*(T_lo_c - 85); alarm 2.0, shutdown 1.0 (example values, OEM-specific [26]); precursor injection: linear decay to shutdown over U(30, 600) s before an injected LO trip"
noise: {type: gaussian, sigma: 0.05}
lag_s: 0.5
failure_modes: [{type: dropout, params: {mA: "<3.6 (wire break)"}, plausible_rate: "1/5000 h"}, {type: drift, params: {rate_bar_per_day: -0.2}, plausible_rate: "1/2000 h"}, {type: spike, params: {amp_bar: 1.5, dur_s: 0.5}, plausible_rate: "1/500 h"}]
calibrate_against: "Marine Engine Fault dataset pressure channels (lube-oil coverage unconfirmed) [3]; example setpoints [26]"
```
```yaml
id: gen_jw_temp_c[i]
unit: degC
rate_hz: 1
derives_from: "78 + 6*load_frac + 0.3*max(0, sw_temp_c - 25) + 8*cooling_fault; first-order tau 120 s; alarm 88, shutdown 95 (example values [26])"
noise: {type: gaussian, sigma: 0.3}
lag_s: 5
failure_modes: [{type: stuck_at, params: {value: last}, plausible_rate: "1/5000 h"}, {type: drift, params: {rate_k_per_h: 0.05}, plausible_rate: "1/3000 h"}, {type: dropout, params: {dur_s: [5, 300]}, plausible_rate: "1/2000 h"}]
calibrate_against: "Marine Engine Fault dataset, cooling-water pump cavitation runs [3]"
```
```yaml
id: gen_exh_temp_c[i][cyl]
unit: degC
rate_hz: 1
derives_from: "280 + 170*load_frac + offset_cyl (fixed N(0, 8)) + 40*air_cooler_fouling; tau 20 s; deviation alarm |T_cyl - mean| > 50 K (assumed)"
noise: {type: gaussian, sigma: 3}
lag_s: 10
failure_modes: [{type: dropout, params: {reads: "0 or full-scale (open thermocouple)"}, plausible_rate: "1/3000 h per channel"}, {type: spike, params: {amp_k: 100, dur_s: 1}, plausible_rate: "1/1000 h"}, {type: drift, params: {rate_k_per_day: 2}, plausible_rate: "1/5000 h"}]
calibrate_against: "Marine Engine Fault dataset exhaust temperatures vs % load; fouling/nozzle runs [3]"
```
```yaml
id: mpl_kw[line]
unit: kW
rate_hz: 10
derives_from: "sum(guest.draw_kw for guests on line); feeder trip if > MPL_LIMIT_KW for > 10 s or > 1.5*MPL_LIMIT_KW instantly (assumed settings)"
noise: {type: gaussian, sigma: "0.5% + 0.5 kW"}
lag_s: 0.2
failure_modes: [{type: dropout, params: {dur_s: [1, 30]}, plausible_rate: "1/500 h"}, {type: quantization, params: {step_kw: 1}, plausible_rate: always}, {type: stuck_at, params: {value: last}, plausible_rate: "1/5000 h"}, {type: latency, params: {extra_s: [0.5, 3]}, plausible_rate: "1/200 h"}]
calibrate_against: "physics (sum of guest draws); no public data"
```
```yaml
id: ups_soc_pct
unit: "%"
rate_hz: 1
derives_from: "dSoC/dt = -100*P_ups_kw/(E_kwh*eta*3600) while bus dead or peak-shaving; recharge 0.2C; E_kwh = 20, eta = 0.92 (assumed IAS + compute UPS)"
noise: {type: gaussian, sigma: 0.5}
lag_s: 1
failure_modes: [{type: drift, params: {soc_error_pct: "+5 per 100 cycles (coulomb-count)"}, plausible_rate: always}, {type: stuck_at, params: {value: last}, plausible_rate: "1/3000 h"}, {type: false_alarm, params: {bms_comm_loss: true}, plausible_rate: "1/500 h"}]
calibrate_against: "physics; NASA PCoE battery fade shape (optional) [10][17]"
```
```yaml
id: sw_inlet_temp_c
unit: degC
rate_hz: 0.2
derives_from: "env.sw_temp_c at intake depth (layered water column: use layer at sea-chest depth) + 0.3 K pipe pickup"
noise: {type: gaussian, sigma: 0.1}
lag_s: 30
failure_modes: [{type: stuck_at, params: {value: last}, plausible_rate: "1/5000 h"}, {type: drift, params: {rate_k_per_month: 0.5}, plausible_rate: "1/2000 h"}, {type: dropout, params: {dur_s: [10, 600]}, plausible_rate: "1/1000 h"}]
calibrate_against: "environment-agent SST source"
```
```yaml
id: chw_supply_temp_c
unit: degC
rate_hz: 1
derives_from: "Q_cap = min(160, 160 - (40/18)*(sw_temp_c - 12)) * (DEGRADED if cooling_degraded); Q_load = sum(guest.draw_kw if on_chw) + rack_kw (1 kW e = 1 kW heat); Q_load <= Q_cap: T to 7.0 (tau 60 s); else dT/dt = (Q_load - Q_cap)/C_loop, C_loop = 0.6 MJ/K (30 kW x 60 s = +3 K, assumed); buffer recharges over INERTIA_PERIOD_S; above 30 C extrapolate the slope (assumed)"
noise: {type: gaussian, sigma: 0.1}
lag_s: 10
failure_modes: [{type: drift, params: {bias_k: [-2, -1, 1, 2]}, plausible_rate: "1/4000 h"}, {type: stuck_at, params: {value: last}, plausible_rate: "1/5000 h"}, {type: dropout, params: {dur_s: [5, 120]}, plausible_rate: "1/1000 h"}]
calibrate_against: "LBNL chiller plant: fault-free + CHW leaving-temperature bias files [6][7]"
```
```yaml
id: chw_return_temp_c
unit: degC
rate_hz: 1
derives_from: "chw_supply_temp_c + Q_load/(CHW_MDOT_KGS*f_pump*4.186); f_pump = 0.6 if pump degraded else 1 (7.6 kg/s gives 160 kW at dT 5 K)"
noise: {type: gaussian, sigma: 0.1}
lag_s: 15
failure_modes: [{type: drift, params: {bias_k: [-2, 2]}, plausible_rate: "1/4000 h"}, {type: desync, params: {vs_supply_s: [5, 30]}, plausible_rate: "1/1000 h"}, {type: stuck_at, params: {value: last}, plausible_rate: "1/5000 h"}]
calibrate_against: "LBNL chiller plant [7]; energy balance"
```
```yaml
id: rack_inlet_temp_c[rack]
unit: degC
rate_hz: 0.2
derives_from: "chw_supply_temp_c + 12 (rear-door/CRAH approach, assumed) + 0.05*(rack_kw - rack_design_kw); outlet = inlet + rack_kw/(1.2*1.005*airflow_m3s); throttle at 27 C (ASHRAE recommended upper inlet, not re-verified)"
noise: {type: gaussian, sigma: 0.2}
lag_s: 20
failure_modes: [{type: dropout, params: {dur_s: [10, 300]}, plausible_rate: "1/500 h (SNMP poll miss)"}, {type: stuck_at, params: {value: last}, plausible_rate: "1/5000 h"}, {type: latency, params: {extra_s: [5, 30]}, plausible_rate: "1/200 h"}]
calibrate_against: "physics; vendor thermal specs"
```
```yaml
id: gen_vib_rms_mm_s[i]
unit: mm/s
rate_hz: 0.017       # one overall value per minute
derives_from: "4 + 3*load_frac + degradation(t) (exponential after injected onset, shape from an IMS run); evaluated per ISO 10816-6 class zones (values not reproduced) [29]"
noise: {type: lognormal, sigma: 0.05}
lag_s: 60
failure_modes: [{type: dropout, params: {dur_s: [60, 3600]}, plausible_rate: "1/1000 h"}, {type: spike, params: {x: 3, cause: "slamming, sea_state >= 5"}, plausible_rate: "1/10 h at sea_state >= 5"}, {type: drift, params: {gain: -0.3, cause: "loose mount"}, plausible_rate: "1/8000 h"}]
calibrate_against: "NASA/IMS trend shape [10][11]; Marine Engine Fault speed effects [3]"
```
```yaml
id: tank_level_pct[tank]
unit: "%"
rate_hz: 0.5
derives_from: "100*V/V_max; fuel tanks dV/dt = -sum(fuel_kg_h)/(rho*3600), fuel_kg_h = gen_kw*(205 + 60*(1-load_frac)^2)/1000 (SFC g/kWh, assumed); sloshing term sigma = 0.5%*sea_state"
noise: {type: gaussian, sigma: 0.3}
lag_s: 10
failure_modes: [{type: spike, params: {amp_pct: 10, cause: sloshing}, plausible_rate: "1/h at sea_state >= 5"}, {type: stuck_at, params: {cause: "radar foam/condensate"}, plausible_rate: "1/5000 h"}, {type: drift, params: {rate_pct_per_month: 1}, plausible_rate: "1/3000 h"}]
calibrate_against: "physics; SFC vs Zenodo 23089007 flowmeter data [5]"
```
```yaml
id: incl_heel_deg    # companion: roll_period_s
unit: deg
rate_hz: 10
derives_from: "57.3*(sum(m*y) + FSM_heel)/(Disp*GM) + A_roll(sea_state)*sin(2*pi*t/T); T = 2*C*B/sqrt(GM), C = 0.373 + 0.023*(B/d) - 0.043*(L/100) (IS Code 2008 weather-criterion form, clause unconfirmed); placeholders Disp 1200 t, B 12 m, d 3.5 m, L 65 m, GM 1.2 m give T ≈ 9.3 s"
noise: {type: gaussian, sigma: 0.05}
lag_s: 0.2
failure_modes: [{type: drift, params: {zero_offset_deg_per_month: 0.2}, plausible_rate: always}, {type: stuck_at, params: {value: last}, plausible_rate: "1/10000 h"}, {type: spike, params: {amp_deg: 3, cause: shock}, plausible_rate: "1/50 h"}, {type: latency, params: {extra_s: [0.5, 2]}, plausible_rate: "1/500 h"}]
calibrate_against: "physics; MSC.363(92)/ISO 19697 output requirements [30][31]"
```
```yaml
id: lc_gm_m
unit: m
rate_hz: 0.1
derives_from: "stab_used_teq = sum(m*MULT[slot]) (<= 12); mass_used_t = sum(m) (<= 10); GM = GM_lc0 - 3.0*stab_used_teq/Disp - FSM/Disp (MULT read as lever arm / 3 m, assumed)"
noise: {type: none, sigma: 0}
lag_s: 30            # recompute cycle after a loading change
failure_modes: [{type: latency, params: {stale_after_change_s: [60, 900]}, plausible_rate: "1 per 50 loading changes"}, {type: desync, params: {mass_list_vs_ledger: "missing item"}, plausible_rate: "1 per 100 changes"}, {type: dropout, params: {cause: "PC reboot", dur_s: [120, 600]}, plausible_rate: "1/2000 h"}]
calibrate_against: "governor's declared-mass ledger (physics); no public data"
```
```yaml
id: fire_zone_state[zone]
unit: "enum {normal, pre_alarm, alarm, fault, disabled}"
rate_hz: 0.5         # loop poll (est.); alarms also as events
derives_from: "scenario fire: zone T += U(1, 5) K/min, smoke obscuration ramp; pre-alarm/alarm thresholds; on alarm, HVAC fans/dampers in zone stop, so chilled-air cooling for that zone's guests/racks drops to 0"
noise: {type: none, sigma: 0}
lag_s: 30            # smoke transport 10-60 s (est.)
failure_modes: [{type: false_alarm, params: {cause: "steam/dust/galley"}, plausible_rate: "1/500 h per vessel"}, {type: dropout, params: {cause: "loop fault -> zone fault"}, plausible_rate: "1/1000 h"}, {type: latency, params: {extra_s: [5, 30]}, plausible_rate: "1/200 h"}]
calibrate_against: "scenario/physics; no open marine dataset found"
```
```yaml
id: bilge_level_state[comp]
unit: "enum {normal, high, high_high}"
rate_hz: 1
derives_from: "level += (leak_lpm - pump_lpm)*dt / area; switch at fixed heights with 5 s debounce (assumed); sloshing false trips scale with sea_state"
noise: {type: none, sigma: 0}
lag_s: 5
failure_modes: [{type: false_alarm, params: {cause: sloshing}, plausible_rate: "1/24 h at sea_state >= 5"}, {type: stuck_at, params: {value: normal, cause: "float jammed"}, plausible_rate: "1/5000 h"}]
calibrate_against: "physics; no public data"
```

## 4. How these sensors fail at sea, and the governor's conservative default

- **Genset kW**: dropout (gateway or Modbus timeout) or stuck value. Assume that set is at 0.9 × rated, so it offers no headroom; freeze new admissions; do not shed on this alone.
- **Breaker state**: aux-contact chatter, or PMS and relay disagree. Admit as if N-1 (100 kW guest cap). Shed only on a confirmed trip, meaning 2 of 3 agree: relay flag, kW ≈ 0, bus-frequency dip.
- **Bus frequency**: harmonic spikes, clock skew. Take the median of bus and both gensets. A sustained fall of more than 2 % with load rising counts as overload and triggers stage-1 guest shedding.
- **PMS reserve**: stale for more than 2 s, or n_online lags after a trip. Recompute from meters; if those are stale too, use the N-1 budget (100 kW at cruise, 0 on the harbour set).
- **Lube-oil pressure**: wire break (below 4 mA), transducer drift. Treat the set as at-risk and use the N-1 budget until the sensor is restored. A sub-4 mA reading is never "healthy".
- **Jacket water temperature**: stuck, or implausible for the load and seawater temperature. Use the N-1 posture and also assume cooling is degraded.
- **Exhaust thermocouple**: open circuit (reads 0 or full scale), common in hot, vibrating spaces. One channel: ignore it for trips and cap that set at 85 % for admission (assumed). Two or more channels: N-1 posture.
- **Vibration CM**: mount loosening, slamming spikes, gateway loss. No admission change, but disable any prognostic "extra headroom".
- **Mission line meter**: dropout or quantization. Assume the line is at 150 kW (no headroom); keep existing guests running.
- **Shore panel meter**: lost. Assume the shore breaker is at its limit; no new harbour admissions.
- **UPS SoC**: coulomb-count drift, or BMS comms lost. Assume 50 % of rated holdup; reject guests whose ride-through relies on the UPS.
- **Insulation monitor**: alarm or comms lost. No new guests on that IT network until the fault is isolated.
- **Seawater inlet temperature**: stuck, drift, dropout. Use max(last + 2 K, environment feed); if both are unknown, assume 30 °C (→ 120 kW capacity).
- **CHW supply/return temperature**: bias of ±1–2 K (as in the LBNL faults), stuck, out of sync. Assume a degraded loop (×0.6) and treat the thermal-inertia buffer as unavailable.
- **Chiller or pump status**: unknown. Assume degraded (−40 %). If flow is unknown, use design flow × 0.6.
- **Rack temperature**: SNMP poll misses. Assume the inlet is at the 27 °C throttle limit; no new compute in that rack.
- **Tank level**: sloshing spikes, radar foam. For mass, use the consumption-integrated estimate. For stability, take the worse of full or empty plus maximum free surface.
- **Draft gauges**: lost. Use loading-computer or ledger displacement.
- **Inclinometer**: zero drift, shock spikes, stuck. Fall back to ledger static heel and block new mast placements (×3) until restored.
- **Loading computer**: stale after a change, or its mass list disagrees with ours. The governor's ledger (Σm ≤ 10 t, Σm·mult ≤ 12 t-eq) is authoritative. Reject any placement that both do not accept.
- **Fire zone fault/disabled**: the zone is "unknown". No new powered guests there; existing guests stay unless the zone alarms.
- **Fire false alarm**: treat it as real until a crew member acknowledges it. At crew 0, treat it as real for the whole episode: shed the zone's guests; zone cooling is lost.
- **Bilge high**: possibly sloshing. Treat it as flooding: hold deck operations and freeze mass changes. Debounce only a single switch tripping in step with sea state, and only if the high-high switch stays clear.
- **Watertight door**: limit switch says closed while open, or status unknown. Assume open; block operations that need closed boundaries.
- **Gas detector**: catalytic-sensor poisoning makes it under-read; or the detector reports a fault. Assume alarm in that space: inhibit battery-charging guests and run maximum ventilation.

## 5. Recommendation for a 36-hour hackathon

Pull these (all openly licensed and declarable):
1. **LBNL FDD chiller plant subset** (CC BY 4.0) [6][7]. Only the fault-free file plus the CHW leaving-temperature bias and HX-fouling files; the full set is 1.14 GB. Gives realistic sensor-bias and fouling fault templates, plus Brick point names.
2. **Marine Engine Fault, Zenodo 19857425** (CC BY 4.0, 26.5 MB) [3]. Calibrates genset exhaust and cooling temperatures vs load, and the precursor shapes for injected trips. Check the CSV headers for lube-oil channels.
3. **UCI Naval Propulsion CBM** (CC BY 4.0, 0.55 MB, Univ. of Genoa) [1][2]. Decay-drift scenarios and a fuel-vs-load map; an Italian naval storyline for the pitch.
4. **Zenodo 23089007 tanker aux-load profiles** (CC BY 4.0, 2.2 MB) [5]. Load-variability and step statistics for hotel/aux load. Verify the columns and sampling interval on download.
5. **canboat definitions** (Apache 2.0) [18]. Not data: message schemas for our simulated NMEA 2000 engine, fluid and battery traffic.

Optional: Port of Funchal (CC BY 4.0, 33.8 MB) for shore-supply realism [16]; one IMS bearing run for a vibration trend [10][11].
Skip: CWRU (no licence), Paderborn (NC), FuelCast (NC-ND), MFPT (licence unconfirmed), RP-1043 figshare copy (rights chain unclear), XJTU-SY/HUST (China-based origin), Gunnerus (access by request).
**Stays synthetic**: switchboard, breaker and PMS logic (preferential trips, fast shedding), genset trip/restart, bus frequency, mission lines, shore, UPS, the whole CHW loop (seeded with LBNL-shaped faults), rack thermals, mass/stability (ledger, loading computer, inclinometer physics), all safety systems, and every fault injection in §3.

## 6. Sources

1. https://archive.ics.uci.edu/dataset/316/condition+based+maintenance+of+naval+propulsion+plants — UCI page: CC BY 4.0, 11,934 instances, file sizes, variables, DOI 10.24432/C5K31K.
2. https://iris.unige.it/handle/11567/713004 — Univ. of Genoa repository record of the associated Coraddu et al. paper (origin).
3. https://zenodo.org/records/19857425 — Marine Engine Fault dataset: CC BY 4.0, 26.5 MB, 16 CSV, fault list, creators.
4. https://arxiv.org/abs/2607.19444 — preprint describing the same test-bed engine and its five anomaly classes.
5. https://zenodo.org/records/23089007 — ITU tanker aux-load / fuel dataset: CC BY 4.0, 2.2 MB xlsx.
6. https://data.openei.org/submissions/5763 — LBNL FDD datasets on OEDI: CC BY 4.0, DOI 10.25984/1881324, Brick TTL.
7. https://pmc.ncbi.nlm.nih.gov/articles/PMC10235024/ — Sci. Data descriptor: chiller plant, 22 files, 1.14 GB, 1-min data, 7 faults.
8. https://faultdetection.lbl.gov/data — LBNL FDD site: chiller plant simulated with EnergyPlus–Modelica, 1 year.
9. https://api.figshare.com/v2/articles/28435232 — figshare copy of RP-1043: CC0 as stated by the uploader, 51 MB, no institution listed.
10. https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/ — NASA PCoE: IMS bearing and battery downloads, citation and use-at-own-risk terms.
11. https://catalog.data.gov/dataset/ims-bearings — IMS bearings data.gov record: licence "U.S. Government Works".
12. https://engineering.case.edu/bearingdatacenter/download-data-file — CWRU: .mat format, 12 k/48 k samples/s, no licence stated.
13. https://mb.uni-paderborn.de/kat/forschung/kat-datacenter/bearing-datacenter — Paderborn KAt: CC BY-NC 4.0 (seen via search; page returned 404 on fetch).
14. https://mfpt.org/fault-data-sets/ — MFPT: "freely distributed" statement, no explicit licence.
15. https://huggingface.co/datasets/krohnedigital/FuelCast — FuelCast: CC BY-NC-ND 4.0, three ships, generator shaft power and fuel.
16. https://zenodo.org/records/22834087 — Port of Funchal power-quality dataset: CC BY 4.0, 33.8 MB.
17. https://data.nasa.gov/dataset/li-ion-battery-aging-datasets — NASA Li-ion aging dataset listing.
18. https://github.com/canboat/canboat — canboat: Apache 2.0, NMEA 2000 database reverse engineered.
19. https://www.continuouswave.com/whaler/reference/PGN.html — PGN 127488 at 10 Hz, PGN 127489 at 1 Hz, with field list (via search excerpt).
20. https://elearning.vector.com/mod/page/view.php?id=420 — J1939 ET1 (PGN 65262) layout, 1 s rate.
21. https://www8.garmin.com/manuals/webhelp/GUID-413FE004-9D7D-474E-8423-3B787BC4A5BF/EN-US/GUID-306ABD0D-9E94-498A-B4FA-50991FD78276.html — SPN-to-PGN mapping (SPN 100, 110, 175, 183, 190).
22. https://teleport.withthegrid.com/installation-guide/asset-library/generator/deif/ — DEIF AGC 150 over Modbus TCP: kW, kVAr, V, I, f, PF.
23. https://www.marineinsight.com/marine-safety/preferential-trips-on-ship-construction-and-working/ — preferential-trip operation; example 5 s / 10 s / 15 s stages.
24. https://samkmoodle.samk.fi/mod/page/view.php?id=22185 — quotes DNV-RU-SHIP Pt.4 Ch.8 on load shedding and on loss of a paralleled set (exact clause unconfirmed).
25. https://mcgs.ac.in/assets/img/Tech-Specification-Generator.pdf — genset spec: low lube-oil pressure and high jacket-water temperature go alarm, then shutdown.
26. https://www.marineinsight.com/main-engine/how-marine-propulsion-engine-of-the-ship-is-protected/ — example setpoints: jacket water >88 °C alarm, >95 °C shutdown; lube oil <1 bar shutdown; overspeed 107 %.
27. https://webstore.ansi.org/standards/iec/iec61162450eden2018 — IEC 61162-450 scope (multicast, single network); ed. 3.0 (2024) is listed at vde-verlag.
28. https://webstore.iec.ch/en/publication/30632 — IEC/IEEE 80005-3 LV shore connection (2025 scope via national-store mirrors).
29. https://www.iso.org/standard/1553.html — ISO 10816-6: vibration of reciprocating machines >100 kW, incl. marine gensets.
30. https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MSCResolutions/MSC.363(92).pdf — IMO performance standard for electronic inclinometers.
31. https://ics.org.ir/IFleet/CLDFiles/PUB/1697c0ad-72d1-493e-9717-16a7edc22549_TI-25-15%20Electronic%20Inclinometer,%20made%20mandatory%20by%20MSC%20107.pdf — class technical note: ±90° range, IEC 61162 output at ≥5 Hz (secondary source).
32. https://www.lr.org/en/knowledge/class-news/14-18 — IACS UR L5 on stability software (approval, Type 4).
33. https://www.ntnu.edu/gunnerus/e-infrastructure — R/V Gunnerus data streams, access by request.
34. https://store.sfs.fi/en/ieee-453-2025 — IEEE 45.3-2025 listing that references IEC 61850 and IEC 60092-202.
