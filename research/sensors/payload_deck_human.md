# Payload telemetry, deck machinery, deck and human sensing

> Superseded for the build by WORKLOG DEC-44: everything on cameras, detectors and person detection (camera rows, the vision datasets, section 3, the `cam_detection_stream` spec, the detector advice); the payload, deck machinery and emission material still applies.

Scope: guest telemetry (G3 UUV, G4 VTOL drone), deck machinery (G2 winch, A-frame, crane, ramp), acoustic emission state, and deck and human sensing for the resource governor. Camera placement is covered in a separate file. Researched 2026-10-16. "Unconfirmed" means we could not verify the item. "Assumption" marks our own engineering numbers.

## 1. Sensor table

| Sensor | Measures | Data type & units | Typical rate | Interface/protocol | Feeds (guest / ship-state / rule) | Commonly fitted? |
|---|---|---|---|---|---|---|
| UAV battery (MAVLink `BATTERY_STATUS`, id 147) | Cell voltages, current, charge used, % left, time left, charge state, faults | `voltages[10]` mV; `current_battery` cA (-1 = not measured); `current_consumed` mAh; `energy_consumed` hJ; `battery_remaining` % (-1 = unknown); `time_remaining` s (0 = no estimate); `charge_state` enum OK/LOW/CRITICAL/EMERGENCY/FAILED/UNHEALTHY/CHARGING; `fault_bitmask` | about 0.5 Hz per battery [1] | MAVLink 2 over the telemetry radio (UDP/serial) | G4 return-to-ship, the "<20 % → land within 12 min or ditch" rule, deck-clear reservation | yes, on any PX4 or ArduPilot vehicle |
| UAV `SYS_STATUS` battery fields | Main pack voltage, current, % | `voltage_battery` mV, `current_battery` cA, `battery_remaining` %; unreliable with more than one battery [1][2] | 1–2 Hz (stream-rate setting) | MAVLink | G4 fallback when `BATTERY_STATUS` is missing | yes |
| UAV position, attitude, state | GNSS fix, attitude, VTOL state, landed state | `GPS_RAW_INT` (24), `GLOBAL_POSITION_INT` (33, degE7 and mm), `ATTITUDE` (30, rad), `EXTENDED_SYS_STATE` (245: `vtol_state`, `landed_state`) [2] | 1–10 Hz (configurable) | MAVLink | G4 position and ETA to deck, landed and disarmed → hangar charging | yes |
| UAV wind estimate | Wind vector the autopilot estimates | `WIND_COV` (231): NED m/s plus 1-sigma variability; ArduPilot `WIND` (168): direction (deg, from), speed (m/s), vertical speed [2] | 1–4 Hz (unconfirmed) | MAVLink | G4 wind ≤25 kn rule (cross-check with the ship anemometer), drain model | yes (estimated, not measured) |
| UAV failsafe flags | Failsafe state, failure bitmap | `HEARTBEAT.system_status` (MAV_STATE); `HIGH_LATENCY2` (235): `battery` %, `windspeed` (m/s×5), `failure_flags` (HL_FAILURE_FLAG_GPS/BATTERY/ENGINE/OFFBOARD_LINK/GEOFENCE/ESTIMATOR…) [2] | HEARTBEAT 1 Hz; HIGH_LATENCY2 for slow links | MAVLink | G4 emergency right of way | yes |
| UAV link quality | Radio RSSI and noise | `RADIO_STATUS` (109) for SiK/RFD radios; video-link RSSI is vendor-specific | 1 Hz | MAVLink, vendor API | G4 LOS video, emission normal/silent | yes |
| Ship landing beacon (ArduPilot moving-platform landing) | Ship position and heading, sent to the aircraft | `GLOBAL_POSITION_INT` from a Rover-firmware autopilot on the ship (dual-F9P GPS yaw advised); aircraft follows it via `FOLL_SYSID` with a Lua script [3] | 5–10 Hz (unconfirmed) | MAVLink forwarded to the aircraft | G4 recovery; needs deck clear and the ship holding course | sometimes (ArduPilot Plane feature) |
| UAV precision landing target | Pad offset seen by the aircraft | `LANDING_TARGET` (149) [2] | 10–50 Hz (unconfirmed) | MAVLink | G4 final approach | sometimes |
| UAV flight logs | Full onboard record | PX4 ULog `.ulg` (read with pyulog, BSD-3) [4]; ArduPilot DataFlash `.bin`, message `BAT` = Volt, VoltR, Curr, CurrTot, EnrgTot, Temp, Res, RemPct, H, SH [5] | 10–400 Hz | File on SD card, offloaded after landing | Post-flight calibration and replay | yes |
| Hangar charger | Charge power, connector state | kW, A, V, bool | 1 Hz (assumption) | CAN or Modbus, vendor-specific (unconfirmed) | G4 35 kW→10 kW profile, power class | yes for a hangar product |
| UUV battery and leg state | SoC, leg timer, mission state | %, s, enum; arrives as small acoustic packets while submerged | Every 10–60 s submerged (assumption); 1 Hz in the cradle | Acoustic modem: WHOI Micro-Modem bursts 80–5400 bps [6]; Ethernet or Wi-Fi in the cradle | G3 40-min leg / 60-min 25 kW charge, recovery window | yes (vehicle-reported) |
| UUV depth | Pressure depth | m (from dbar) | 1–10 Hz onboard; slower over the acoustic link | Onboard serial → acoustic packet | G3 surfacing and recovery planning | yes |
| USBL acoustic positioning | UUV range and bearing → position | Slant range from two-way travel time; Ranger 2 0.04 % of slant range when optimised [7] | About 1 Hz; slower with range (each fix needs the full acoustic round trip) [7][8] | Vendor serial or Ethernet, NMEA-like strings (unconfirmed) | G3 position; **active acoustic emission**, so it conflicts with emission = silent | sometimes (survey and research ships) |
| Acoustic sync unit (e.g. Kongsberg K-Sync) | Which acoustic systems transmit, and when | Trigger and "transmitting" feedback per system; up to 16 echo sounders or groups [9] | Per ping | TTL or serial trigger lines | Sonar emission active/passive variable, acoustic conflicts between G2, G3 and the ship | sometimes (research ships) |
| Echo sounder / ADCP / sonar status | Active-pinging flag, frequency | bool + kHz (e.g. EK80 18–333 kHz, HiPAP 20–30 kHz) [9] | Event | Vendor software, sync unit | Sonar emission state, noise level | yes (echo sounder) |
| Self-noise hydrophone | Ship-radiated noise level | dB re 1 µPa, spectrum | 1 Hz summaries | Audio ADC → computed band levels | Noise-level variable, G3 quiet-course check | rarely (research and naval) |
| Winch tensiometer / load pin | Line tension | kN or kgf (float) | UNOLS: 20 Hz acquisition, logging and alarms when factor of safety ≤2.0; 10 Hz display; 3–4 % accuracy [10] | Analog 4–20 mA → line-monitor box → serial/UDP string | G2 `winch_active`, deck machinery = busy, G3 "no deck machinery" rule | yes on research winches |
| Winch payout and speed | Wire out, line speed | m, m/s (encoder) | Payout display about 3 Hz [10] | WHOI/UNOLS comma-separated winch string: timestamp, winch ID, tension, payout, speed [10] | G2 probe depth, `winch_active` | yes |
| Winch drive | Motor current or hydraulic pressure, brake state | A or bar, bool | 1–10 Hz (assumption) | VFD or PLC over Modbus/CAN (vendor) | `winch_active` cross-check, power class | yes (in the PLC; not always exported) |
| A-frame / crane / ramp | Boom angle, ramp position, latch closed | deg, bool | 1–10 Hz (assumption) | PLC, limit switches | `ramp_clear` (with CV), G3 launch | sometimes |
| EO camera (virtual sensors) | People on deck, obstruction, ramp clear, winch in use | Detections: class, bbox, confidence, frame age; never video over degraded links | 1–5 Hz inference on CPU (assumption) | RTSP/ONVIF in → our detector → JSON | Deck clear/occupied, people_on_deck, ramp_clear | yes for CCTV; the analytics are ours |
| Thermal IR camera | Warm bodies on deck or in the water (night, MOB) | 8- or 14-bit radiometric frames → detections | Low-cost cores often <9 Hz (export class); 30/60 Hz cores exist (unconfirmed) | GigE/USB/RTSP | people_on_deck at night, MOB | sometimes |
| LiDAR | 3D occupancy of the flight deck | Point cloud (x, y, z, intensity) | 10–20 Hz (vendor-typical, unconfirmed) | Ethernet/UDP | Deck obstruction, independent of light | rarely on small ships |
| mmWave presence radar (e.g. TI IWR6843) | Moving and stationary people | Point cloud + tracked-object list | 120 ms default frame period in TI people-counting demo [11] | UART/CAN TLV frames | people_on_deck in enclosed spaces (hangar, ramp bay) | rarely |
| UWB crew tags | Tag position | x, y (m); chip claims 10 cm, module <15 cm 2D / <30 cm 3D [12] | Up to about 100 Hz in a lab prototype [12] | Anchors → RTLS server (TWR or TDoA) | Who is on the flight deck; crew-level confirmation | rarely (steel multipath unverified) |
| BLE beacons / RFID muster gates | Zone presence | Zone ID, timestamp | Event / 1 Hz | BLE or RFID reader → IP | Crew count per zone (14/6/0) | sometimes |
| PIR detector | Motion of warm bodies | bool | Event (hold time 1–2 s, assumption) | Dry contact | Indoor spaces only | rarely on open deck |
| Safety light curtain (Type 4) | Beam break at a hazard boundary | 2 OSSD outputs (safe = OFF) | 10–16 ms response (SICK deTec4 datasheets) [13] | OSSD → safety relay/PLC | Ramp or hangar door interlock | rarely at sea |
| Door / hatch switches | Open/closed | bool | Event | Reed switch → PLC | Hangar door, ramp gate, watertight-door state | yes |
| MOB detection (ISO 21195) | Person going overboard (no wearable needed) | Alarm + track; thermal + radar + video (vendor designs) [14] | Event | Vendor bridge system | Emergency; G4 tasked to SAR | sometimes (passenger ships) |
| AIS-MOB / PLB wearable | MOB position | AIS message (MOB MMSI prefix 972 per ITU-R M.585; not re-verified) | 1/min class | VHF AIS | G4 SAR target, G5 comms | sometimes |
| Ship anemometer | Apparent and true wind | kn, deg (NMEA MWV/MWD) | 1 Hz | NMEA 0183 | G4 wind ≤25 kn (covered in the ship-sensor file) | yes |

## 2. Public datasets

| Name | Content & classes | Format & size | Licence | Origin (org, country) | URL | What we would use it for | Caveats |
|---|---|---|---|---|---|---|---|
| PX4 Flight Review public logs | Thousands of user-uploaded flights; all PX4 vehicle types, including VTOL | ULog; bulk via `download_logs.py` with airframe filters | CC-BY [4] | PX4 / Dronecode community (international) | https://review.px4.io/browse | Real `battery_status` and wind traces for a few VTOL flights | Huge, so pull 5–10 logs only; mostly small vehicles; quality varies |
| CMU ALFA | 47 fixed-wing flights; 23 engine failures + 24 control-surface faults; 66 min normal, 13 min post-fault | processed.zip 272 MB, raw 721 MB, dataflash 541 MB, telemetry 211 MB (ROS bags, CSV, `.bin`) | CC BY 4.0 [15] | Carnegie Mellon AIR Lab, USA | https://doi.org/10.1184/R1/12707963 | Replaying engine failure / failsafe for G4 emergency right of way | Small fixed wing, not 140 kg VTOL; files exceed our download limit, so take one sequence |
| CMU DJI M100 package-delivery energy data | 209 flights, 10 h 45 min; GPS, IMU, voltage, current, **ultrasonic anemometer** (wind speed and angle); payload 0/250/500 g | flights.csv 107 MB, flights.zip 41 MB | CC BY 4.0 (data) [16]; metadata CC0 | Carnegie Mellon, USA | https://doi.org/10.1184/R1/12683453 | Calibrating the "battery drain vs wind" generator shape | 3.6 kg quadcopter; CMU summary says wind had little effect on total energy at these speeds [17]; sample rate unconfirmed |
| NASA PCoE Randomized Battery Usage 1–6 | 18650 Li-ion cells on random 0.5–5 A load profiles with reference cycles | MATLAB files; size unconfirmed | US Government work (data.gov) [18] | NASA Ames, USA | https://catalog.data.gov/dataset/randomized-battery-usage-1-random-walk | Voltage sag and SoC-vs-voltage curve for synthetic packs | Single cells, not packs; no wind |
| Girona underwater caves sonar set | Sparus II AUV: 2 imaging sonars, DVL, 2 IMUs, depth, camera | full_dataset.bag 395 MB (camera bag 3.3 GB separate) | **CC BY-NC-SA 4.0 (non-commercial)** [19] | Universitat de Girona, Spain | https://zenodo.org/record/7828405 | Realistic UUV depth/DVL timing | No USBL, no battery or leg data; non-commercial |
| IOOS Glider DAC | Real-time and delayed glider trajectories and profiles (depth, position) | NetCDF via ERDDAP; one deployment can be about 1.1 GB [20] | US Government data (licence text unconfirmed) | NOAA IOOS, USA | https://gliders.ioos.us/erddap | Dive/surface cycle timing for the UUV leg generator | Gliders, not UUVs; battery variable unconfirmed |
| NOAA/Navy SanctSound | Long-term hydrophone recordings + detection products, including "Active Sonar Recorded" sets | Audio + CSV detections; public Google Cloud bucket | US Government work (licence text not found) [21] | NOAA & US Navy, USA | https://www.ncei.noaa.gov/products/passive-acoustic-data | Labelled active-sonar events for the emission-state/noise example | Large; stream a few files only |
| Ocean Networks Canada hydrophones | Cabled hydrophones (Strait of Georgia etc.) | WAV/FLAC/spectrograms via Oceans 3.0 API (free token) | Open data policy; CC-BY claimed by third parties, unconfirmed [22] | Univ. of Victoria / ONC, Canada | https://data.oceannetworks.ca | Ship-noise background for the noise-level variable | Some data restricted (third-party/military); check terms |
| ShipsEar | 90 recordings of 11 vessel types + metadata | WAV; size unconfirmed | Not stated; access by request (unconfirmed) [23] | Univ. of Vigo, Spain | atlanttic.uvigo.es/underwaternoise/ (status unconfirmed) | Ship-noise examples | Small; access route uncertain |
| DeepShip | 47 h, 265 ships, 4 classes (cargo, passenger, tanker, tug) | WAV; part on GitHub, rest by email | Not stated [24] | **Northwestern Polytechnical University, Xi'an, China** (contact @mail.nwpu.edu.cn); audio recorded at ONC Strait of Georgia delta node | https://github.com/irfankamboh/DeepShip | **Do not use** (China-origin flag); use ONC raw data instead | Same source audio is available from ONC |
| SeaDronesSee (ODv2, MOT, multispectral) | Aerial maritime SAR: swimmer, boat, jetski, life_saving_appliances, buoy; ODv2 = 14,227 images | COCO JSON; test labels withheld | **CC0 1.0** (code MIT) [25] | Univ. of Tübingen, Germany | https://github.com/Ben93kie/SeaDronesSee | Fine-tuning person-in-water detection for G4 SAR, swimmer near the ramp | Drone viewpoint (5–260 m altitude), not deck cameras |
| MaSTr1325 | 1,325 USV images; sea / sky / obstacle masks | Images + PNG masks | CC BY 4.0 [26] | ViCoS, Univ. of Ljubljana, Slovenia | https://www.vicos.si/resources/mastr1325/ | Water/obstacle segmentation, horizon from the sea/sky boundary | No person boxes |
| LaRS | 4,006 keyframes (+9 frames each, 40k total); 3 stuff + 8 thing classes incl. swimmer, boat, buoy | Images 966 MB, labels 22 MB, COCO panoptic | Terms accepted at download; licence not shown (unconfirmed) [27] | Univ. of Ljubljana, Slovenia | https://lojzezust.github.io/lars-dataset/ | Robustness test set (fog, glare, night) | Read the T&C before use |
| MODS | About 81k stereo USV images, 60k objects, IMU-synced | Images + annotations | Unconfirmed [28] | ViCoS, Univ. of Ljubljana, Slovenia | https://www.vicos.si/resources/ | Optional | Licence unconfirmed |
| Singapore Maritime Dataset | 81 videos at 1080p: on-shore 40 (3 GB), on-board 11 (768 MB), NIR 30 (1.5 GB); horizon, object and track ground truth | Video + MAT ground truth (Google Drive) | **No licence stated**, only citation requested [29] | NUS / D. K. Prasad, Singapore | https://sites.google.com/site/dilipprasad/home/singapore-maritime-dataset | Horizon-tilt check on the 11 on-board videos | Treat as "permission unclear"; flag |
| ABOships / ABOships-PLUS | 9,880 images, 41,967 objects (boat, cargoship, ferry, sailboat, seamark…); PLUS = 33,227 objects in 4 classes | Zip about 8.2 GB each | CC BY 4.0 [30] | Åbo Akademi, Finland | https://zenodo.org/records/10469672 | Vessel detection from a moving watercraft | Large; no person class |
| COCO 2017 (person) | 80 classes, person dominant; 1.5 M instances | JSON + JPG | Annotations CC BY 4.0; images under Flickr terms [31] | COCO Consortium (Microsoft + universities), USA | https://cocodataset.org | Base weights for all detectors below | Image rights per image |
| Open Images V7 | 600 box classes incl. Person, Boat, Life jacket (unconfirmed) | CSV + JPG | Annotations CC BY 4.0; images listed as CC BY 2.0 without warranty [31] | Google, USA | https://storage.googleapis.com/openimages/web/index.html | Extra "life jacket" / "helmet" crops (unconfirmed) | Per-image licence not guaranteed |
| Teledyne FLIR free ADAS thermal set | 26,442 frames, 520k boxes, 15 classes incl. person; 9,711 thermal + 9,233 RGB | COCO-style JSON | **Non-commercial licence agreement** [32] | Teledyne FLIR, USA | https://www.flir.com/adasdataset | Thermal person-detector demo only | Road scenes; NC; declare it |
| IceHorizon | 12,360 frames with horizon lines (ice-covered sea) | Zenodo; CVAT labels | Source videos CC BY; dataset licence unconfirmed [33] | 2026 preprint (authors' origin unconfirmed) | https://doi.org/10.5281/zenodo.20411867 | Horizon-tilt check validation | Check origin before use |

## 3. Pretrained models table

| Model | Code licence | Weights licence | Training data | Origin | CPU speed if known | Verdict for us |
|---|---|---|---|---|---|---|
| torchvision `ssdlite320_mobilenet_v3_large` | BSD-3 | No explicit licence; torchvision says weights "may have their own licenses" from the training data [34] | COCO 2017 (21.3 box mAP; 3.4 M params; 0.58 GFLOPs) [34] | PyTorch/Meta (USA); SSD and MobileNetV3 designs from Google | Laptop CPU unconfirmed (low GFLOPs suggests tens of ms) | **Primary.** Fine-tune on SeaDronesSee (CC0) + our synthetic deck frames; export to ONNX |
| torchvision `fasterrcnn_mobilenet_v3_large_320_fpn` / `_fpn` | BSD-3 | As above | COCO (22.8 / 32.8 mAP; 19.4 M params; 0.72 / 4.49 GFLOPs) [34] | PyTorch/Meta, USA | Unconfirmed | Second opinion when people_on_deck confidence is low |
| MediaPipe EfficientDet-Lite0 / Lite2 (TFLite) | Apache 2.0 (MediaPipe) | Not stated on the model page (unconfirmed) [35] | COCO [35] | Google, USA | Lite0 int8 29 ms, fp32 61 ms; Lite2 int8 71 ms (Pixel 6 CPU) [35] | **Edge-box choice** (TFLite runs on Qualcomm); confirm weights licence before shipping |
| MediaPipe SSD MobileNetV2 | Apache 2.0 | Unconfirmed | COCO | Google, USA | fp32 36 ms (Pixel 6 CPU) [35] | Fallback |
| RF-DETR Nano/Small/Medium/Large | Apache 2.0 | Apache 2.0 for N/S/M/L/Seg; PML 1.0 for Atto/Femto/Pico/XL/2XL [36] | COCO-pretrained [36]; Roboflow's hosted training starts from Objects365 weights [37]; DINOv2 backbone | Roboflow (USA); **built on LW-DETR (Baidu, China) and Deformable DETR** [36][38] | Nano 2.3 ms on a T4 GPU; CPU unconfirmed; 30.5 M params | **Exclude** under our China-derived rule; flag to the team |
| Ultralytics YOLOv5/v8/11 | AGPL-3.0 | AGPL-3.0 | COCO | Ultralytics | n/a | **Excluded** (AGPL); this also covers SeaDronesSee YOLOv8 checkpoints on Hugging Face |
| YOLOX, YOLOv6, RT-DETR, D-FINE, LW-DETR | Apache-type | Varies | COCO / Objects365 | Megvii, Meituan, Baidu (China) | n/a | **Excluded** (China origin) |
| OpenCV `wechat_qrcode` | Apache 2.0 | CNN models from WeChat (Tencent) [39] | Unknown | Tencent, China | n/a | **Excluded.** Use `cv2.QRCodeDetector` or zxing-cpp |
| Classical CV checks (no ML) | OpenCV Apache 2.0 | n/a | n/a | OpenCV | Sub-ms to a few ms per frame | **Always on**: lens health, frame freeze, horizon tilt, QR guest cards |

Classical checks for robustness: (a) **blur / lens obstruction**: variance of the Laplacian on grayscale (Pech-Pacheco 2000); a common starting threshold is 100, but calibrate it per camera [40]. Per-tile variance finds partial occlusion (salt, a droplet, a cover left on). (b) **Frame freeze**: compare a perceptual hash or mean absolute difference of consecutive frames, and check the RTSP timestamp and frame counter. N identical frames plus a still clock means frozen. (c) **Horizon tilt**: Canny → `cv2.HoughLines`, keep the longest near-horizontal line, take its angle, and compare with ship roll from the IMU. A mismatch means the mount moved or the view is wrong. (d) **Guest card QR**: `cv2.QRCodeDetector().detectAndDecode` reads the guest manifest ID on the cradle, hangar or probe. (e) **Exposure/black frame**: histogram mean and saturation fraction.

## 4. Synthetic generator specs

All `plausible_rate` values are **assumptions** for fault injection, not measured. Every stream carries `ts`, `seq`, `source_id`, and `age_s = now - ts`. The governor sees streams only through these generators or real adapters with the same schema.

```yaml
id: g4_battery_pct
unit: percent
rate_hz: 0.5                      # MAVLink BATTERY_STATUS cadence [1]
derives_from: "E_bat_kWh (assume 15), phase power P_phase {hover: 28 kW, transition: 32 kW, cruise: 8 kW, loiter_hover_SAR: 26 kW} (assumptions for a 140 kg quadplane); d(pct)/dt = -100*P/(E_bat*3600); P *= (1 + 0.012*gust_sd_kn) (assumption); hover P *= f_translational(V_wind) (dips 5-10 % up to ~15 kn then rises, shape from Scicluna/arXiv 2109.04741 [41][42])"
noise: {type: gaussian, sd_pct: 0.5, quantise: 1}
lag_s: 1.0
failure_modes:
  - {type: dropout, params: {duration_s: [5, 60]}, plausible_rate: "2/h on LOS radio"}
  - {type: stuck_at, params: {value: last}, plausible_rate: "0.1/flight"}
  - {type: false_positive, params: {jump_pct: +8, cause: "voltage recovery after load drop"}, plausible_rate: "1/flight"}
  - {type: latency, params: {extra_s: [2, 10]}, plausible_rate: "on relay via G5"}
calibrate_against: "CMU M100 flights.csv (power vs anemometer wind) for shape; PX4 Flight Review VTOL logs for the 15/7/5 % PX4 default thresholds (BAT_LOW_THR 0.15, BAT_CRIT_THR 0.07, BAT_EMERGEN_THR 0.05) [43]"
```

```yaml
id: g4_time_to_deck_s
unit: s
rate_hz: 1
derives_from: "dist_to_ship / max(V_air_cruise - headwind_component, 3 m/s) + t_approach_hover(=180 s, assumption) ; in 22 kn (11.3 m/s) headwind with V_air 25 m/s the ground speed falls to 13.7 m/s, so cruise-back time rises x1.8; rule: if battery_pct < 20 and time_to_deck_s > 720 -> DITCH_PLAN, else recall with deck-clear reservation"
noise: {type: gaussian, sd_s: 15}
lag_s: 2
failure_modes:
  - {type: dropout, params: {cause: "wind estimate NaN (WIND_COV invalid)"}, plausible_rate: "5 % of samples in turns"}
  - {type: false_negative, params: {cause: "ship airwake burble not modelled", extra_s: 60}, plausible_rate: "1/recovery"}
calibrate_against: "Range/endurance wind-correction model arXiv 2109.04741 [42]; PX4 COM_FLTT_LOW_ACT semantics [43]"
```

```yaml
id: g4_mavlink_link_ok
unit: bool
rate_hz: 1
derives_from: "HEARTBEAT seen within COM_DL_LOSS_T (PX4 default 10 s) [43]; LOS range vs mast height; emission_state == silent forces false (radio off)"
noise: none
lag_s: 0
failure_modes:
  - {type: dropout, params: {duration_s: [10, 120], cause: "superstructure shadow"}, plausible_rate: "1/h"}
  - {type: false_positive, params: {cause: "HEARTBEAT ok but video dead"}, plausible_rate: "1/h"}
calibrate_against: "RADIO_STATUS rssi in PX4 logs"
```

```yaml
id: g3_uuv_leg_state
unit: enum {CRADLE_CHARGING, LAUNCH, LEG, SURFACING, RECOVERY, FAULT}
rate_hz: 0.1                       # acoustic packet cadence while submerged (assumption)
derives_from: "LEG timer 40 min; CHARGING 60 min at 25 kW; LAUNCH/RECOVERY need ship 3 kn steady, noise_level low, deck machinery idle (winch_active false), ramp_clear true"
noise: {type: none}
lag_s: 8                           # acoustic packet latency (assumption; 80-5400 bps burst [6])
failure_modes:
  - {type: dropout, params: {cause: "acoustic link lost (ship noise, K-Sync gating, multipath)", duration_s: [30, 600]}, plausible_rate: "1 per leg"}
  - {type: latency, params: {extra_s: [10, 60]}, plausible_rate: "when echo sounder active"}
  - {type: stuck_at, params: {value: LEG}, plausible_rate: "0.05/leg"}
calibrate_against: "Glider DAC dive/surface timing [20]; WHOI Micro-Modem rates [6]"
```

```yaml
id: g3_uuv_soc_pct
unit: percent
rate_hz: 0.05
derives_from: "linear drain to 25 % over a 40 min leg + 0.3 %/min per kn above 3 kn; charge +75 % in 60 min at 25 kW (taper above 90 %)"
noise: {type: gaussian, sd_pct: 1}
lag_s: 10
failure_modes:
  - {type: dropout, params: {inherits: g3_uuv_leg_state}, plausible_rate: "as acoustic link"}
  - {type: stuck_at, params: {value: last}, plausible_rate: "0.05/leg"}
calibrate_against: "NASA PCoE randomized-usage voltage curves (shape only) [18]"
```

```yaml
id: g3_usbl_fix
unit: {range_m: m, bearing_deg: deg, depth_m: m, sigma_m: m}
rate_hz: 1                         # ~1 Hz, drops with slant range [7][8]
derives_from: "true UUV track + sigma = 0.0004*slant_range (optimised) .. 0.013*slant_range (small system) [7]; period >= 2*slant_range/1500 s; emission_state == silent -> no fixes (USBL is an active emitter)"
noise: {type: gaussian, sd: sigma_m, outlier_p: 0.03, outlier_scale: 10}
lag_s: 1.5
failure_modes:
  - {type: dropout, params: {cause: "silent mode, aeration under hull, ship turning"}, plausible_rate: "5 % of fixes"}
  - {type: false_positive, params: {cause: "multipath ghost", offset_m: [20, 100]}, plausible_rate: "1 %"}
calibrate_against: "Sonardyne Ranger 2 spec [7]; Girona bag DVL/depth cadence [19]"
```

```yaml
id: sonar_emission_state
unit: enum {PASSIVE, ACTIVE_LF, ACTIVE_HF, UNKNOWN}
rate_hz: 1
derives_from: "OR of scheduled pings: ship echo sounder, USBL tracking G3, G2 probe altimeter/pinger; K-Sync slot table [9]; ship emission == silent forces PASSIVE or raises a violation"
noise: none
lag_s: 0.5
failure_modes:
  - {type: stuck_at, params: {value: PASSIVE, cause: "sync feedback line dead"}, plausible_rate: "0.01/day"}
  - {type: false_negative, params: {cause: "third-party sonar not on sync unit"}, plausible_rate: "per installation"}
calibrate_against: "SanctSound 'Active Sonar Recorded' detection sets [21]"
```

```yaml
id: g2_winch_active
unit: bool (+ tension_kN, payout_m, speed_mps)
rate_hz: 20                        # UNOLS tension rate at FoS <= 2.0 [10]
derives_from: "G2 cast schedule: payout at 1.0 m/s down / 0.8 m/s up to target depth, 2 min soak at bottom; tension = probe_wet_weight + wire_weight*payout + drag(speed) + heave_term(sea_state); winch_active = |speed| > 0.05 OR tension > tare + 0.5 kN OR brake_released"
noise: {tension: {type: gaussian, sd_pct: 3}, payout: {type: quantise, step_m: 0.1}}
lag_s: 0.1
failure_modes:
  - {type: stuck_at, params: {channel: tension, value: tare}, plausible_rate: "0.01/cast (load-pin cable)"}
  - {type: dropout, params: {channel: all, duration_s: [1, 30]}, plausible_rate: "0.05/cast (serial string lost)"}
  - {type: false_negative, params: {cause: "brake on but crew working at the winch"}, plausible_rate: "covered by CV person-at-winch"}
calibrate_against: "WHOI LCI-90i string format and UNOLS Appendix A rates [10]"
```

```yaml
id: people_on_deck
unit: "count (per zone: flight_deck, stern_ramp, winch_area)"
rate_hz: 1
derives_from: "crew_level {14,6,0} x activity {idle, launch_G4, recover_G4, launch_G3, cast_G2, maintenance}; Poisson(lambda) with lambda = {idle: 0.2, launch_G4: 2, recover_G4: 2, launch_G3: 3, cast_G2: 2} scaled by crew_level/14; crew_level 0 -> lambda 0, so ANY detection = anomaly (rescued person or intruder) and no human can confirm"
noise: {type: none}
lag_s: 0
failure_modes:
  - {type: false_negative, params: {cause: "occlusion behind hangar or cradle"}, plausible_rate: "10 % per person-frame"}
  - {type: false_positive, params: {cause: "foul-weather gear on a rail, shadows"}, plausible_rate: "1/h"}
calibrate_against: "UWB/BLE muster counts if available; otherwise scenario scripts"
```

```yaml
id: cam_detection_stream          # synthetic virtual-sensor output; lets the governor run with NO camera
unit: "json {camera_id, ts, seq, zone, counts: {person, obstruction, hook_or_load}, max_conf, mean_conf, age_s, health: {lap_var, frozen, tilt_deg, lens_ok}}"
rate_hz: 2
derives_from: "ground truth from people_on_deck + deck_obstruction + g2_winch_active; detection p_detect = 0.9*vis*(1 - 0.5*night)*(1 - 0.3*spray); conf ~ Beta(8,2) for TP, Beta(2,5) for FP; camera is a guest with manifest {power_W: 15, bandwidth_kbps_detections: 2, compute_ms_per_frame: 60}"
noise: {conf: beta, bbox_jitter_px: 4}
lag_s: 0.5
failure_modes:
  - {type: frame_freeze, params: {duration_s: [10, 600], tell: "seq increments, image hash constant"}, plausible_rate: "1/day/camera"}
  - {type: occlusion, params: {cause: "salt film, droplet, bird", lap_var_drop: 0.7, partial: true}, plausible_rate: "3/day/camera in spray"}
  - {type: dropout, params: {cause: "RTSP drop, PoE fault", duration_s: [5, 300]}, plausible_rate: "2/day/camera"}
  - {type: latency, params: {extra_s: [1, 20], cause: "CPU contention with G5"}, plausible_rate: "when G5 at 45 kW mode"}
  - {type: false_positive, params: {class: person, cause: "sun glint, reflections"}, plausible_rate: "0.5/h"}
  - {type: false_negative, params: {class: person, cause: "night without IR, crouching crew"}, plausible_rate: "15 % per person-frame at night"}
calibrate_against: "Detector P/R measured on SeaDronesSee val + 200 hand-labelled synthetic deck frames; lap_var threshold calibrated per camera [40]"
```

```yaml
id: deck_obstruction / ramp_clear
unit: bool + confidence
rate_hz: 1
derives_from: "scripted objects (tie-down chains, cradle, probe frame, loose gear) per activity; ramp_clear = NOT(ramp_gate_open AND object_on_ramp) AND light_curtain_unbroken; fused with cam_detection_stream"
noise: {type: none}
lag_s: 0.5
failure_modes:
  - {type: false_negative, params: {cause: "low-contrast object, wet deck glare"}, plausible_rate: "5 %"}
  - {type: false_positive, params: {cause: "standing water or foam on ramp"}, plausible_rate: "2/h in sea state >= 4"}
calibrate_against: "LaRS/MaSTr1325 obstacle masks for segmentation sanity; scenario scripts"
```

## 5. How these sensors fail at sea, and the conservative default

- UAV battery %: estimator jumps after load changes and is stuck when the link drops → assume worst-case drain from the last value, and recall early if the data is older than 10 s.
- UAV wind estimate: invalid in turns and hover → use the ship anemometer + 5 kn margin; above 25 kn means no launch.
- UAV link: shadowing by superstructure; silent mode forces radio off → treat the drone as on its own failsafe (PX4 default: data-link loss after 10 s triggers NAV_DLL_ACT), and keep the deck reserved and clear.
- Landing beacon: compass and GPS-yaw errors on a steel ship → no auto-landing on the moving platform (ArduPilot users report the VTOL refusing to land on bad beacon heading or position, forum report, unconfirmed); hold off at the loiter point [3].
- UUV acoustic telemetry: lost through ship noise, sync gating and multipath → assume the leg continues and the UUV may surface at any time; keep course and 3 kn, no deck machinery, no active sonar.
- USBL: outliers, and no fixes in silent mode → dead-reckon with a growing uncertainty circle; no prop or thruster work near the predicted surfacing area.
- Sonar emission state: feedback lines go dead and third-party sonars are not on the sync unit → treat UNKNOWN as ACTIVE (emitting), so it conflicts with silent mode and the G3 acoustic link.
- Tensiometer: cable or connector corrosion stuck at tare → treat winch as in use whenever payout > 0, the brake is released, or the drive draws current. UNOLS also limits factor of safety to 5 when the tensiometer fails [10].
- Payout/speed string: serial drop → winch active, G3 launch blocked.
- EO camera: salt, spray, glare, night, freeze → stale (>3 s) or unhealthy means deck = OCCUPIED, ramp = NOT CLEAR, people_on_deck = UNKNOWN (≥1).
- Thermal camera: rain and sea spray lower contrast; warm deck equipment gives false positives → never used alone to declare "clear"; only adds people.
- LiDAR: spray and rain return points, and mounts vibrate → a spurious return counts as an obstruction; dropout means occupied.
- mmWave radar: vibration and moving metal (wipers, cables) → indoor zones only; a fault means occupied.
- UWB/BLE tags: steel multipath, tags left in cabins, flat batteries → tags can add people but can never prove a zone is empty.
- PIR: sun and wind-driven heat on open deck → indoor only; a fault means occupied.
- Light curtain: salt film and misalignment cause nuisance trips → a trip or fault means ramp not clear (fail-safe by design: at least one OSSD OFF [13]).
- Door/hatch switches: corroded reed → unknown means open.
- MOB system: nuisance alarms (ISO 21195 testing is said to target under 1 per day, unconfirmed [14]) → every alarm raises G4 SAR readiness, and a human (if crew > 0) can stand it down.
- Any timestamp older than the stream's `max_age_s` → that stream's conservative state; the rationale is logged as "degraded: stale".

## 6. Recommendation (36-hour hackathon)

**Pull from public data (small slices only):**
1. 5–10 VTOL ULogs from PX4 Flight Review (CC-BY), parsed with pyulog, for real `battery_status` / `wind` cadence and to test our MAVLink adapter on real data.
2. CMU M100 `flights.csv` (107 MB, CC BY 4.0) to fit the shape of power vs anemometer wind. The 140 kg numbers stay synthetic and labelled as such.
3. One ALFA engine-failure sequence (CC BY 4.0) to demo G4 emergency right of way from a real fault.
4. SeaDronesSee ODv2 subset (CC0) for swimmer/boat fine-tuning or evaluation, plus a few hundred COCO person images.
5. 10 on-board SMD frames and IceHorizon/MaSTr1325 frames to show the horizon-tilt check works (SMD only if the team accepts "no licence stated"; otherwise use MaSTr1325, CC BY 4.0).
6. One SanctSound "active sonar" clip and one ONC hydrophone clip to illustrate the emission-state and noise variables.

**Synthesize:** everything about the 140 kg VTOL (power per phase, battery, 12-min rule), all UUV telemetry, USBL and leg state, the winch at 20 Hz, people_on_deck by crew level, deck obstruction, and the full `cam_detection_stream` with every failure mode. The demo must run with cameras unplugged: the governor sees only the stream schema.

**Detector:** torchvision `ssdlite320_mobilenet_v3_large` (BSD-3 code, COCO weights, 3.4 M params), exported to ONNX Runtime on the laptop. Use MediaPipe EfficientDet-Lite0 int8 on the Qualcomm box once its weights licence is confirmed. Run `fasterrcnn_mobilenet_v3_large_fpn` as a slower second opinion. Exclude RF-DETR (built on Baidu's LW-DETR), all YOLO variants (AGPL or China origin), and OpenCV `wechat_qrcode` (Tencent). Always run the classical health checks: Laplacian variance, freeze hash, Hough tilt and QR.

**Declare in the README:** FLIR ADAS and Girona caves are non-commercial; DeepShip is China-origin and not used; LaRS, MODS, SMD, ShipsEar and ONC have licences we could not confirm; torchvision and MediaPipe weights have no explicit weights licence and inherit COCO terms.

## 7. Sources

1. https://mavlink.io/en/services/battery.html: battery protocol; BATTERY_STATUS at about 0.5 Hz per battery; SYS_STATUS fields ambiguous with several batteries.
2. https://github.com/mavlink/mavlink/blob/master/message_definitions/v1.0/common.xml: field units for BATTERY_STATUS, WIND_COV, HIGH_LATENCY2, EXTENDED_SYS_STATE, charge-state enum, HL_FAILURE_FLAG, message IDs; `ardupilotmega.xml` for WIND (168).
3. https://ardupilot.org/plane/docs/common-ship-landing.html: ArduPilot moving-platform VTOL landing: Rover beacon, GLOBAL_POSITION_INT forwarding, holdoff approach.
4. https://docs.px4.io/main/en/dev_log/flight_log_analysis_statistical: Flight Review public logs are CC-BY; `download_logs.py`; pyulog.
5. https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_BattMonitor/LogStructure.h: DataFlash BAT message fields.
6. https://acomms.whoi.edu/micro-modem: WHOI Micro-Modem 80–5400 bps burst rates (FSK/PSK).
7. https://sonardyne.com/product/ranger-2-usbl/: Ranger 2 accuracy 0.04 % of slant range; Mini-Ranger 2 0.2–1.3 %; about 1 Hz updates (distributor).
8. https://www.advancednavigation.com/tech-articles/untangling-usbl-comparing-the-benefits-of-usbl-squared-usbl2-with-classic-and-inverted-usbl/: classic USBL about one fix per second; range from two-way travel time.
9. https://kongsberg.com/discovery/seafloor-mapping/ksync: K-Sync times up to 16 echo sounders to avoid acoustic interference. HiPAP 20–30 kHz, EK80 18–333 kHz and the lower ping rate when synced come from an operator training note seen in search results (https://spaces.awi.de/spaces/EFPW/pages/206831800/SyncUnit, not re-opened).
10. https://www.unols.org/sites/default/files/201611rvt_BreakOut_LCI90i_LineMonitoringDisplay.pdf and https://www.unols.org/sites/default/files/Append_A_AssistSheet_11_3_15.pdf: UNOLS Appendix A winch monitoring: 20 Hz tension for factor of safety ≤2.0, 10 Hz display, 3 Hz payout, accuracy, WHOI winch string.
11. https://dev.ti.com/tirex/explore/content/mmwave_industrial_toolbox_4_11_0/labs/People_Counting/3D_People_Counting/docs/3d_people_counting_user_guide.html: IWR6843 people counting outputs point cloud + tracks over UART; 120 ms default frame (TI E2E forum).
12. https://www.qorvo.com/products/p/DW3000 and https://qorvo.com/products/p/DWM3000 and https://par.nsf.gov/servlets/purl/10343337: UWB 10 cm chip claim; module <15 cm 2D; lab prototype at about 100 Hz.
13. https://www.motionworld.com/assets/SICK-deTec4_Set_30_450-Datasheet.pdf: Type 4 light curtain response 10–14 ms; at least one OSSD goes OFF on a fault.
14. https://www.iso.org/standard/76051.html and https://maritime-executive.com/corporate/zelim-s-zoe-becomes-first-fully-certified-man-overboard-detection-system: ISO 21195:2020 scope (non-wearable MOB detection); vendor thermal/radar designs.
15. https://api.figshare.com/v2/articles/12707963 (DOI 10.1184/R1/12707963) and https://arxiv.org/abs/1907.06268: ALFA licence CC BY 4.0, file sizes, flight counts.
16. https://api.figshare.com/v2/articles/12683453 (DOI 10.1184/R1/12683453): M100 delivery data CC BY 4.0, file sizes, sensors incl. anemometer.
17. https://www.cmu.edu/cee/news/news-archive/2021/06-2021-drone-package-delivery-study-published-by-scientific-data.html: payload and duration dominated energy; wind had little effect.
18. https://catalog.data.gov/dataset/randomized-battery-usage-1-random-walk: NASA PCoE randomized battery usage; US Government works.
19. https://zenodo.org/record/7828405: Girona underwater caves set, CC BY-NC-SA 4.0, sensors and file sizes.
20. https://ego-services.locean.ipsl.fr/storage/conferences/08_new-jersey_2019/presentations/number21-bob-fratantonio-fratantonio_bob_ioos_gliderdac.pdf and https://discourse.oceanobservatories.org/t/glider-data-missing-from-ioos-glider-dac/791: Glider DAC ERDDAP access; about 1.1 GB per deployment.
21. https://www.ncei.noaa.gov/products/passive-acoustic-data and https://catalog.data.gov/dataset/active-sonar-recorded-at-sanctsound-site-ci05_06: SanctSound GCP bucket; active-sonar detection products.
22. https://pypi.org/project/onc: ONC Oceans 3.0 API needs a token; data licence not confirmed.
23. https://portalcientifico.uvigo.gal/documentos/5fa620842999524ed108440c?lang=en: ShipsEar, 90 records, 11 vessel types, Univ. of Vigo.
24. https://github.com/irfankamboh/DeepShip: DeepShip recorded at the Strait of Georgia delta node; access via an NWPU email; no licence stated.
25. https://github.com/Ben93kie/SeaDronesSee: SeaDronesSee CC0 dataset, MIT code, splits and formats; classes via https://huggingface.co/dronefreak/seadronessee-yolov8n.
26. https://www.vicos.si/resources/mastr1325/: MaSTr1325 CC BY 4.0, 1,325 images, classes.
27. https://lojzezust.github.io/lars-dataset/: LaRS size, classes and format; terms accepted at download.
28. https://ar5iv.labs.arxiv.org/html/2105.02359: MODS benchmark size.
29. https://sites.google.com/site/dilipprasad/home/singapore-maritime-dataset: SMD contents and sizes; citation only, no licence.
30. https://zenodo.org/records/10469672 and https://zenodo.org/record/4736931: ABOships(-PLUS) CC BY 4.0, Åbo Akademi, about 8.2 GB.
31. https://research.google/blog/open-images-v7-now-featuring-point-labels/ and https://huggingface.co/datasets/HuggingFaceM4/COCO/blob/refs%2Fpr%2F5/README.md: Open Images and COCO annotation vs image licences.
32. https://www.flir.com/adasdataset: FLIR thermal set contents; non-commercial licence agreement.
33. https://arxiv.org/pdf/2608.07018: IceHorizon horizon dataset (12,360 frames, Zenodo).
34. https://docs.pytorch.org/vision/stable/models.html: torchvision detection mAP, params and GFLOPs; weights-licence caveat.
35. https://developers.google.com/edge/mediapipe/solutions/vision/object_detector: MediaPipe detector models, COCO training, Pixel 6 CPU latency.
36. https://github.com/roboflow/rf-detr: RF-DETR licence split (Apache 2.0 vs PML 1.0); builds on LW-DETR, DINOv2 and Deformable DETR.
37. https://roboflow.com/blog/train-rf-detr-on-a-custom-dataset: hosted RF-DETR training starts from Objects365 weights.
38. https://arxiv.org/abs/2406.03459v1: LW-DETR authors from Baidu Inc., China.
39. https://docs.opencv.org/4.9.0/dd/d63/group__wechat__qrcode.html and https://developer.cloud.tencent.com/article/1964995: wechat_qrcode CNN models contributed by WeChat (Tencent).
40. https://pyimagesearch.com/2015/09/07/blur-detection-with-opencv/: variance-of-Laplacian blur measure (Pech-Pacheco 2000); thresholds depend on the domain.
41. https://um.edu.mt/library/oar/handle/123456789/113350: hexacopter hover power falls as wind rises, lowest near 8 m/s.
42. https://arxiv.org/pdf/2109.04741: multicopter range/endurance with wind correction factors.
43. https://docs.px4.io/main/en/config/safety.html and https://github.com/PX4/PX4-Autopilot/blob/main/docs/en/advanced_config/parameter_reference.md: PX4 failsafes: BAT_LOW/CRIT/EMERGEN 0.15/0.07/0.05, COM_DL_LOSS_T 10 s, COM_WIND_MAX default disabled, COM_FLTT_LOW_ACT.
