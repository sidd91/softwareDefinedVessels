# Sensor catalog and data plan

> Superseded for the build by WORKLOG DEC-44: the camera and vision items (rows, datasets, weights questions), heartbeat failover and the NPU question; the rest still applies.

One page that ties the four sensor research files to the governor. Detail, sources and the
synthetic generator specs live in the domain files:

| Domain | File | Generator specs |
|---|---|---|
| Platform, power, thermal, mass, safety | `sensors/platform_power_thermal.md` | 20 |
| Navigation, motion, ocean and weather | `sensors/navigation_environment.md` | 12 |
| Comms links, ship network, edge compute | `sensors/comms_network_compute.md` | 11 |
| Guest payloads, deck machinery, deck and human sensing | `sensors/payload_deck_human.md` | 11 |
| Fixed camera placement by vessel domain | `camera_placement.md` | n/a |

All 54 YAML generator specs parse (checked Fri 20:46 PDT). Rates and fault rates marked
"assumed" or "unconfirmed" in those files are ours and go in the Physical Account.

## What feeds each governor input

| Governor input | Sensors | Rate | Demo source | When lost or stale |
|---|---|---|---|---|
| Power budget | genset kW, frequency, breaker and protection-relay flags, PMS preferential trips, mission-line current | 1–10 Hz | synthetic, calibrated on tanker load profiles and the marine engine fault set | admit as if one genset is down; shed only on a confirmed trip, 2 of 3: relay flag, kW near zero, frequency dip |
| Heat rejection | chilled-water supply/return temp, flow, pump and chiller status, seawater inlet temp | 1 Hz | synthetic loop; seawater temp from Open-Meteo and NOAA OISST | judge at the worse of measured inlet and forecast; pump status unknown counts as degraded |
| Deck and bay positions | bay power/data connection, door state, crane state | event | synthetic | occupied |
| Mast positions | static inventory, emitter states for the radio-sensor conflict | event | configuration | occupied |
| Mass and stability | tank levels, draft, inclinometer, loading computer | 0.1–1 Hz | synthetic | last known margin minus the largest pending admission |
| Data links | wired ring, Wi-Fi, GEO and LEO SATCOM, line-of-sight radio, acoustic modem | 1–10 Hz | synthetic; LEO latency shape from a public Starlink trace | path down after missed heartbeats; Wi-Fi is backup only for critical functions (IACS UR E22) |
| Compute | node CPU, temperature, power, accelerator load, heartbeat, disk health | 1–10 Hz | real from our own machines, plus synthetic | node dead after 1 s silence on all paths; its workloads re-placed |
| Response time | decision latency against 30 s / 2 s / 5 s / 200 ms ceilings | per decision | measured live | watchdog emits the safe default and names the missed ceiling |
| Ship state: course, speed | GNSS, gyro, speed log, autopilot mode | 1–10 Hz | synthetic | course not steady; speed band unknown blocks flight deck and ramp ops |
| Ship state: motion | motion reference unit roll, pitch, heave | 10 Hz | synthetic, JONSWAP spectrum driven by hourly Open-Meteo waves | unknown motion counts as out of limits |
| Environment | seawater temp, wave height and period, wind, water-column layering | hourly | public: Open-Meteo Marine and Archive, OISST, Argo profiles | stale data may only tighten a limit |
| Equipment and deck (camera) | change detection on fixed equipment: deck and lashing markers in place, leaks, smoke or small fire, damaged or out-of-place gear, foreign objects on the flight deck; lens, frozen-frame and view self-checks. Person counting optional and last (WORKLOG DEC-23) | 2 Hz | live webcam or the synthetic detection stream | unknown means not clear or changed; a camera may add a hazard, never clear one; people on deck come from the crew report |
| Guests | drone battery, wind and failsafe state; UUV leg, battery and USBL fix; winch tension and payout; sonar emission; comms node load | 0.5–20 Hz | synthetic, drone shape from PX4 logs and the CMU M100 energy set | winch unknown means in use; sonar unknown means active; USBL gives no fixes in silence |
| Emission state | radio, SATCOM and AIS transmit status | event | synthetic | treat as normal for conflicts, silent for link budget |

## Rules every sensor follows

1. Unknown never means safe. It means occupied, in use, active or out of limits.
2. Stale data may tighten a limit, never loosen one.
3. Corroborating sensors may add a hazard, never clear one.
4. Admit as if degraded when unsure; shed only on a confirmed fault.
5. Every value carries source, age and confidence, so the fallback ladder can step down from
   measured to camera-inferred to crew-reported to assumed.
6. Replay orders events by epoch and log index, never by wall clock.

## Demo location

Strait of Sicily at 37.30 N, 11.90 E, on the Mazara del Vallo to Kelibia cable corridor.
Mean sea temperature was 26.1 °C in August 2025 and 22.6 °C in October 2025, which matches
Scenario B's 24 °C. An Argo profile from 15 Aug 2026 shows a mixed layer about 10.5 m deep with a
sharp sound-speed drop below it, so the acoustic link should be unreliable below about 10 m.
Stress case: off Boca Raton, Florida, where August averaged 30.4 °C, above the 30 °C design point.

## Data plan

Nothing below is downloaded yet. Each pull needs Logan's go-ahead; sizes are as reported.

| Tier | Source | Licence | Size | Used for |
|---|---|---|---|---|
| 1 | Open-Meteo Marine and Archive, Sicily, 14 days | CC BY 4.0; free tier non-commercial | under 1 MB | waves, wind, seawater temp driving cooling and flight-deck limits |
| 1 | NOAA OISST via ERDDAP, one month | US government, public domain | under 1 MB | envelope check on seawater temp |
| 1 | Argo profiles via Ifremer ERDDAP, Sicily box | free and open | a few MB | layering and sound speed for the acoustic link |
| 2 | UCI naval propulsion, University of Genoa | CC BY 4.0 | 0.55 MB | drift scenarios; Italian naval storyline |
| 2 | Tanker auxiliary load profiles, Zenodo 23089007 | CC BY 4.0 | 2.2 MB | hotel and auxiliary load variability |
| 2 | Marine engine fault set, Zenodo 19857425 | CC BY 4.0 | 26.5 MB | genset temperatures and trip precursors |
| 2 | PX4 Flight Review, 5–10 VTOL logs | CC BY | tens of MB | drone battery and wind cadence |
| 2 | CMU M100 drone energy `flights.csv` | CC BY 4.0 | 107 MB | power against wind shape |
| 3 | SeaDronesSee subset | CC0 | subset, size to check | detector evaluation at sea |
| 3 | MaSTr1325 frames | CC BY 4.0 | subset | horizon-tilt check |
| 4 | Starlink latency trace, one day, Zenodo 10020034 | CC BY 4.0 | slice of 1.2 GB | LEO latency pattern |
| 4 | LBNL chiller fault subset | CC BY 4.0 | 2–3 files of 1.14 GB | chilled-water fault shapes |
| 4 | canboat message definitions | Apache-2.0 | small | NMEA 2000 schemas, not data |

Excluded: CWRU bearings (no licence), Paderborn (non-commercial), FuelCast (non-commercial, no
derivatives), CRAWDAD traces (no redistribution), DeepShip and the XJTU-SY and HUST bearing sets
(China origin), FLIR ADAS and Girona caves (non-commercial).

## Open questions for the organizers

- Does the hackathon count as non-commercial use for Open-Meteo's free tier? If not, use OISST
  and Argo only, which are public domain or open.
- Is Qualcomm's proprietary QAIRT runtime acceptable for the NPU? If not, run ONNX Runtime on CPU.
- Licences we could not confirm: LaRS, MODS, Singapore Maritime Dataset, ShipsEar, ONC hydrophone
  data, WetLinks, and the weights terms of torchvision and MediaPipe, which inherit COCO's.
