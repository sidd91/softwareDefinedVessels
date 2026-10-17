# Comms links, shipboard networks, edge-compute telemetry, redundancy practice

Research note for the resource governor (data links, compute, response time; touches power and heat). Web research done 2026-10-16.
Conventions: **unconfirmed** = I could not verify it at a primary source. **(assumed)** = an engineering assumption for our simulator, not a sourced fact. Numbers in [n] refer to Section 7.
Brief values (SATCOM 2–8 Mbit/s, 600–800 ms, 70–95 %; LOS 20–40 km, 1–20 Mbit/s; acoustic 1–5 kbit/s, 10–60 s; backbone 2×10 Gbit/s <1 ms) take precedence over vendor figures below.

## 1. Telemetry table

| Source | Measures | Data type & units | Typical rate | Interface/protocol | Feeds (resource class / ship-state) | Present on 60–100 m? |
|---|---|---|---|---|---|---|
| GEO VSAT modem (Ku/Ka) | Es/No or C/N, Rx lock, ACM MODCOD, Tx/Rx throughput, RTT | float dB; enum; bit/s; ms | 1 Hz poll | Vendor web/SNMP API; MIB names vendor-specific (unconfirmed) | Data links (SATCOM capacity/availability) | sometimes |
| VSAT antenna control unit (ACU) | Az/el, tracking state, programmed blockage-zone flag, dual-antenna mediator selection [15] | deg; enum; bool | 1 Hz | IP/serial; heading in via NMEA | Data links (predict blockage from heading); mast positions | sometimes |
| LEO terminal, Starlink (FHP) | `pop_ping_latency_ms`, `pop_ping_drop_rate`, `fraction_obstructed`, up/down throughput, alerts, `is_snr_above_noise_floor` [5][6] | ms; 0–1; 0–1; bit/s; bool | 1 s history samples, dish keeps last 15 min [5] | Local gRPC on the dish (read via Unlicense `starlink-grpc-tools`) | Data links; electrical power (110–150 W average per terminal [10]) | sometimes |
| LEO terminal, OneWeb (e.g. Intellian OW70M) | Link state, throughput, latency (~70 ms to PoP [11]) | ms; bit/s | unconfirmed | Vendor API unconfirmed | Data links | sometimes |
| L-band (Inmarsat FleetBroadband, Iridium Certus) | Signal level, registration, session, throughput (FB500 432 kbit/s, FB250 284 kbit/s [12]; Certus 700 704/352 kbit/s [13]) | dB-Hz; enum; kbit/s | 1 Hz | Vendor AT/web/SNMP (unconfirmed) | Data links (low-rate backup) | yes |
| LOS radio (Wi-Fi bridge / MANET, e.g. Doodle Labs Mesh Rider, Silvus StreamCaster) | RSSI, SNR, noise floor, MCS/PHY rate, retries, neighbour table | dBm; dB; Mbit/s; count | 1 Hz | SNMP/HTTP/vendor API; exact field names unconfirmed [16][17] | Data links; mast positions | sometimes |
| Acoustic modem topside unit (e.g. Benthos ATM-900, Sonardyne Modem 6, EvoLogics S2C) | Per-packet SNR, CRC ok, telemetry scheme / bit rate, two-way travel time → range, Doppler | dB; bool; bit/s; m; m/s | per packet (every 10–60 s) | Serial/Ethernet, vendor command set | Data links (acoustic); deck positions (over-side pole) | sometimes (only with UUV) |
| Backbone switches (ring) | Port up/down, CRC/error counters, utilisation, MRP/ERPS ring state, PRP lost/duplicate counters, LLDP | enum; counters; % | 1–10 s poll + traps | SNMP/syslog; IEC 61162-460 networks have a network monitoring function [26] | Data links (backbone); response time | yes |
| IEC 61162-450 navigation network | NMEA sentences over UDP multicast: heading, position, rate of turn, speed | sentences | 1–10 Hz per sentence (unconfirmed) | IEC 61162-450 (UDP multicast, IGMP snooping); -460 adds forwarder/gateway isolation and redundancy [26] | Ship state: heading → SATCOM blockage, rate of turn → acoustic break | yes |
| Intra-hull Wi-Fi (AP + client) | RSSI, retries, bitrate, roam/disassoc events | dBm; %; Mbit/s; event | 1 Hz | nl80211 (`iw`), hostapd control socket | Data links (backup node-to-node path) | sometimes |
| Compute node CPU/memory | Per-core utilisation, frequency, load, memory, OOM kills | %; MHz; MiB | 1 Hz | `/proc`, psutil | Compute | yes |
| Compute node thermal | SoC/CPU/GPU zone temperatures, trip points, throttle state | °C; bool | 1 Hz | Linux `/sys/class/thermal`, hwmon | Heat rejection; compute derate | yes |
| Compute node power | Package/board power, PSU input | W; V | 1 Hz | RAPL powercap on x86; board PMIC/INA hwmon on ARM (unconfirmed for Qualcomm kits); inline DC meter | Electrical power | yes |
| Accelerator | GPU util/power via vendor tools; Qualcomm NPU utilisation on Linux: unconfirmed | %; W | 1 Hz | Vendor tools | Compute (accelerator slot) | sometimes |
| Disk health | SMART reallocated/pending sectors, NVMe percent-used, temperature | counters; %; °C | ~1/h | smartctl (smartmontools) | Compute (20 TB store); node health | yes |
| Heartbeat / liveliness (ours) | seq, epoch, log index, per-path arrival gap | int; int; int; ms | 10 Hz per path (Section 4) | Own UDP, or DDS liveliness / Zenoh tokens | Response time; governor failover | n/a (ours) |
| Time sync | Offset, path delay, PTP port state, chrony estimated error | µs; enum | 1 Hz | linuxptp `pmc`, `chronyc tracking` | Replay confidence; timestamps in event log | sometimes (PTP) / yes (NTP from GNSS) |
| EMCON / emission silence | On/off, sectors | bool | event | Bridge input | Data links: SATCOM and LOS forced to 0 | sometimes (multi-role) |
| UPS feeding compute | On-battery, runtime left | bool; s | 1 Hz | NUT/SNMP | Electrical power; shedding trigger | yes |

## 2. Public datasets

| Name | Content | Format & size | Licence | Origin (org, country) | URL | What we would use it for | Caveats |
|---|---|---|---|---|---|---|---|
| LENS (LEO network measurement dataset) | Starlink RTT/loss traces (IRTT, ping) from ~20 fixed dishes; recent months add dish gRPC metrics [1] | CSV/JSON in monthly `.tar.zst`; tens of GB to TB per month | Data CC BY-SA 4.0 (Zenodo); code GPL-3.0 [1] | Univ. of Victoria, Canada | github.com/clarkzjw/LENS | Latency distribution, 15 s reconfiguration spikes, drop runs | Land-based, not maritime. ShareAlike applies to derived data. Take a 1-day slice only |
| Starlink latency & downlink throughput dataset (Zenodo 10020034) | IRTT + iperf3, 13–17 Sep 2023 [2] | 1.2 GB `.tar.zst` + scripts | CC BY 4.0 [2] | Univ. of Victoria, Canada | zenodo.org/records/10020034 | Calibrate LEO latency and throughput model | Fixed dish, one site, 5 days |
| WetLinks | Starlink up/down throughput, RTT, loss, traceroute every ~3 min for ~6 months, with co-located weather station [3] | ~140 k measurements; format unconfirmed | "Open data" per paper; exact licence unconfirmed | Osnabrück (DE) and Enschede (NL) vantage points | arxiv.org/abs/2402.16448 | Rain → throughput degradation curve | Check licence before use; land-based |
| Starlink web-performance dataset (TUM) | Cloudflare/M-Lab speed tests, 145 countries, Nov 2023–Sep 2025 [4] | Size unconfirmed | CC BY 4.0 [4] | TU Munich, Germany | mediatum.ub.tum.de/1840504 | Regional spread of LEO latency/throughput | Crowd-sourced, not maritime |
| starlink-grpc-tools (tool, not data) | Field schema for dish status, history, obstruction [5] | Python | Unlicense [5] | Community, GitHub | github.com/sparky8512/starlink-grpc-tools | Make synthetic telemetry match real field names | Firmware drops fields over time |
| CRAWDAD archive (IEEE DataPort) | Many Wi-Fi/cellular traces, e.g. `wiscwiscape` cellular TCP throughput/RTT with GPS (~141 MB) [52] | Varies | Dartmouth CRAWDAD licence: use permitted, **no redistribution** without approval; login needed [52] | Dartmouth College, USA (host IEEE) | ieee-dataport.org/collections/crawdad | Calibration only | Not an open licence: do not commit data to our repo |
| FFI Watermark | Physical-layer acoustic benchmark: measured channels from Norway (2 sites), France, Hawaii; bands 4–8, 10–18, 32.5–37.5 kHz [20] | MATLAB zip; size unconfirmed | Free download; licence not stated (unconfirmed) [20] | FFI, Norway | ffi.no/en/research/watermark | Use the published PER-vs-SNR results to shape the acoustic model | Needs MATLAB; physical layer, not packet traces |
| SFI Smart Ocean UAC dataset | Hydrophone recordings of comms and channel probes in a fjord, 3 bands, plus sound-speed profiles [21] | WAV/CSV, ~15 GB | Not stated; IEEE DataPort subscription/login [21] | FFI, NORCE, IMR, Norway | ieee-dataport.org (see [21]) | Cite only; thermocline context | Too large; licence unclear |
| pi5-thermal-proxy | Raspberry Pi 5 SoC temperature, CPU util, memory at 5 Hz, 13 h, 232 k samples [47] | Parquet, small | MIT [47] | Individual author (country unstated) | github.com/manunicholasjacob/pi5-thermal-proxy | Fit thermal time constant for node model | No power column, no throttling (governor pinned) |
| ENACT edge-cloud telemetry | Raspberry Pi 4 + VM: CPU %, energy (W) [48] | Zenodo; size unconfirmed | Unconfirmed | EU ENACT project (via Data in Brief/PMC) | pmc.ncbi.nlm.nih.gov/articles/PMC13091772 | Utilisation → power slope | Check licence |
| Hydra (Jetson Xavier/Orin/Thor LLM inference telemetry) | 107 k per-prompt records with telemetry aggregates [49] | Zenodo DOI 10.5281/zenodo.21844843 | Unconfirmed | Academic (see paper) | arxiv.org/html/2608.25053 | Accelerator power/thermal under load | NVIDIA only; licence unconfirmed |
| Backblaze Drive Stats | Daily SMART attributes + failure flag per drive [51] | CSV in zip, ~1–2 GB per quarter | Custom terms: cite Backblaze, you may not sell the data [51] | Backblaze, USA | backblaze.com/cloud-storage/resources/hard-drive-test-data | SMART field names, failure base rates | Too large to pull; terms are not CC |

## 3. Synthetic generator specs

Every link model runs per path and is driven by ship state (heading, rate of turn, speed, EMCON, door states, weather) from the scenario clock. Numbers marked (assumed) are for calibration, not for quoting.

```yaml
id: link.wired.backbone            # one instance per path A/B
unit: {up: bool, rtt: ms, loss: ratio, goodput: Gbit/s}
rate_hz: 10
derives_from: "brief 2x10 Gbit/s <1 ms; rtt = 0.1 ms + queue(utilisation); ring reconfiguration after a cut"
noise: {rtt_jitter_ms: 0.05, loss_floor: 1.0e-6}      # assumed
lag_s: 0
failure_modes:
  - {type: dropout, params: {duration_s: [0.01, 0.5], cause: ring_reconfig}, plausible_rate: "per cut; MRP 10-500 ms [29], ERPS ~50 ms [30]"}
  - {type: partition, params: {path: A_or_B, until: repaired}, plausible_rate: "1/month (assumed)"}
  - {type: degrade, params: {crc_error_rate: 1.0e-4, cause: connector_corrosion}, plausible_rate: "1/quarter (assumed)"}
  - {type: latency_spike, params: {rtt_ms: [5, 200], duration_s: [1, 30], cause: broadcast_storm}, plausible_rate: rare}
calibrate_against: "MRP/ERPS recovery figures [29][30]; ping + iperf3 on the demo Ethernet"
```
```yaml
id: link.wifi.intra                # node-to-node backup path inside the hull / on deck
unit: {rssi: dBm, snr: dB, phy_rate: Mbit/s, goodput: Mbit/s, rtt: ms}
rate_hz: 1
derives_from: "PL = 40 + 10*n*log10(d_m) + n_closed_doors*L_door + X; n = 2.0 open deck, 1.8 corridor (waveguide effect [18]), 3.0 machinery space (assumed); L_door ~ U(5,30) dB, median 20 dB [18]; RSSI = 20 dBm - PL; SNR = RSSI - (-92 dBm, assumed); phy_rate from SNR step table over 20 MHz 1SS MCS0-7 = 6.5-65 Mbit/s [19] (SNR thresholds assumed 5..25 dB); goodput = 0.6*phy_rate*(1-PER)"
noise: {shadowing_sigma_dB: 4, fast_fading: "Rician K=6 dB (assumed)"}
lag_s: 0.5                          # rate-control adaptation (assumed)
failure_modes:
  - {type: degrade, params: {extra_loss_dB: 20, trigger: watertight_door_closed}, plausible_rate: "several per day; all doors closed at action/flooding stations"}
  - {type: flap, params: {period_s: [2, 20], cause: roaming_or_interference}, plausible_rate: "1/day (assumed)"}
  - {type: latency_spike, params: {rtt_ms: [50, 500], duration_s: [1, 10]}, plausible_rate: "10/h on busy channel (assumed)"}
  - {type: dropout, params: {duration_s: [5, 120], cause: AP_reboot}, plausible_rate: "1/week (assumed)"}
calibrate_against: "USNA ~20 dB per bulkhead/door at 0.8-2.5 GHz [18]; PIER B 5-30 dB [18]; iperf3 laptop<->Qualcomm box with doors/walls in between"
```
```yaml
id: link.satcom.geo                # brief-default SATCOM model (Ku/Ka VSAT)
unit: {esno: dB, modcod: enum, throughput: Mbit/s, rtt: ms, available: bool}
rate_hz: 1
derives_from: "EsNo = 12 dB clear sky (assumed) - A_rain(t) - L_pointing(roll,pitch); ACM picks the highest MODCOD the EsNo supports; throughput = min(shared allocation 2-8 Mbit/s, symbol_rate*efficiency); blocked when heading puts satellite azimuth inside the ACU blockage sector (mast/funnel); 0 when EMCON"
noise: {esno_sigma_dB: 0.3, rtt_ms: "U(600, 800) per brief"}
lag_s: 2                            # ACM / uplink power control reaction (assumed)
failure_modes:
  - {type: degrade, params: {fade_rate_dB_s: {Ku: 1, Ka: [3, 5]}, depth_dB: [3, 15]}, plausible_rate: "per rain cell; fade rates from [14]"}
  - {type: partition, params: {trigger: relative_bearing_in_blockage_sector}, plausible_rate: "every manoeuvre crossing the sector"}
  - {type: dropout, params: {duration_min: [5, 15], cause: sun_outage}, plausible_rate: "seasonal around equinox (magnitude unconfirmed)"}
  - {type: latency_spike, params: {rtt_ms: [1000, 3000]}, plausible_rate: "under congestion of shared beam (assumed)"}
  - {type: partition, params: {trigger: EMCON}, plausible_rate: scenario}
calibrate_against: "brief ranges; ETRI Ka/Ku ACM+UPC dynamic range >20 dB [14]; availability 70-95 % (brief)"
```
```yaml
id: link.satcom.leo                # optional what-if (Starlink-like)
unit: {rtt: ms, drop_rate: ratio, fraction_obstructed: ratio, throughput: Mbit/s}
rate_hz: 1
derives_from: "base RTT resampled from LENS/Zenodo traces [1][2]; extra spike at seconds 12/27/42/57 of each minute (15 s reconfiguration [7]); obstruction when satellite direction falls in a superstructure mask; throughput capped at the ship's allocation"
noise: {rtt_jitter_ms: "empirical from traces"}
lag_s: 0
failure_modes:
  - {type: latency_spike, params: {extra_ms: [30, 300], duration_s: [0.2, 1]}, plausible_rate: "every 15 s [7]"}
  - {type: dropout, params: {duration_s: [1, 30], cause: obstruction_or_beam_switch}, plausible_rate: "in-motion studies report frequent multi-second outages [7][8]; maritime rate unconfirmed"}
  - {type: degrade, params: {throughput_factor: [0.3, 0.9], cause: rain}, plausible_rate: "per rain event; magnitude to fit from WetLinks [3]"}
  - {type: partition, params: {trigger: EMCON}, plausible_rate: scenario}
calibrate_against: "LENS / Zenodo 10020034 latency CDFs [1][2]; WetLinks weather data [3]"
```
```yaml
id: link.satcom.lband              # FleetBroadband / Certus backup
unit: {throughput: kbit/s, rtt: ms, registered: bool}
rate_hz: 1
derives_from: "cap 150-432 kbit/s (FBB [12]) or 352/704 kbit/s (Certus [13]); best-effort shared; rtt GEO 500-1000 ms, Iridium ~395 ms +/-100 (reseller figure [13])"
noise: {throughput_cv: 0.3}         # assumed
lag_s: 5                            # session set-up (assumed)
failure_modes:
  - {type: dropout, params: {duration_s: [10, 120], cause: re-registration}, plausible_rate: "1/day (assumed)"}
  - {type: partition, params: {trigger: EMCON}, plausible_rate: scenario}
calibrate_against: "datasheets [12][13]"
```
```yaml
id: link.los_radio                 # ship-to-ship / ship-to-shore / ship-to-USV
unit: {rssi: dBm, snr: dB, throughput: Mbit/s, rtt: ms}
rate_hz: 1
derives_from: "range_km from nav/AIS; horizon_km = 4.12*(sqrt(h_tx_m)+sqrt(h_rx_m)) (4/3-earth rule); SNR = Ptx + G - FSPL(d,f) - L_sea_multipath - NF; throughput = clip(f(SNR), 1, 20) Mbit/s (brief); 0 beyond horizon or in EMCON"
noise: {fading: "Rician, K 3-10 dB by sea state (assumed)"}
lag_s: 1
failure_modes:
  - {type: degrade, params: {null_depth_dB: [10, 20], cause: two_ray_sea_reflection}, plausible_rate: "at specific ranges (assumed)"}
  - {type: flap, params: {near: horizon, period_s: [5, 60]}, plausible_rate: "whenever range within 10 % of horizon"}
  - {type: latency_spike, params: {rtt_ms: [100, 1000], cause: mesh_reroute}, plausible_rate: "per topology change (assumed)"}
  - {type: partition, params: {trigger: EMCON}, plausible_rate: scenario}
calibrate_against: "Doodle Labs 47 km ship-to-shore case [16]; Silvus 75 km @ 10 Mbit/s claim [17]; Doodle field-test procedure (iperf3/ping) [16]"
```
```yaml
id: link.acoustic.uuv
unit: {snr: dB, pkt_success: ratio, bitrate: bit/s, latency: s}
rate_hz: 0.05                       # one slot per ~20 s
derives_from: "TL = 20*log10(r_m) + alpha_Thorp(f_kHz)*r_km; NL = NL_sea(sea_state) + 1.5*speed_kn + 15*deck_machinery_on (assumed); SNR = SL(185 dB re 1uPa, assumed) - TL - NL - 20*layering_index (shadow-zone loss, assumed); bitrate = highest of {1000, 2500, 5000} bit/s whose SNR threshold holds (SNR-driven scheme choice as in [23]); p_success = 1/(1+exp(-(SNR-10)/2)) (assumed); latency = airtime + r/1500 + queue, bounded to 10-60 s (brief); forced down if |rate_of_turn| > 3 deg/s or speed > 6 kn (assumed)"
noise: {snr_sigma_dB: 3, multipath: "per-packet Bernoulli with p from SNR"}
lag_s: 20
failure_modes:
  - {type: partition, params: {trigger: manoeuvre_or_speed}, plausible_rate: "every course change during UUV ops"}
  - {type: degrade, params: {snr_drop_dB: 15, trigger: winch_or_A_frame_running}, plausible_rate: "during launch/recovery"}
  - {type: degrade, params: {snr_drop_dB: [5, 20], trigger: layering_index>0.5}, plausible_rate: "summer stratification; receiver below thermocline [24]"}
  - {type: latency_spike, params: {latency_s: [60, 180], cause: retries}, plausible_rate: "when p_success < 0.5"}
calibrate_against: "Watermark PER-vs-SNR results [20]; Benthos 140-15 360 bit/s, 2-6 km by band [22]; Sonardyne 100-9000 bit/s schemes [23]; JANUS 80 bit/s floor [25]"
```
```yaml
id: node.thermal_power             # per compute node (laptop, Qualcomm box, simulated 4 nodes)
unit: {t_soc: degC, p_board: W, throttled: bool, freq: MHz}
rate_hz: 1
derives_from: "P = P_idle + (P_max - P_idle)*util; dT/dt = (T_amb + R_th*P - T)/tau; throttled when T >= T_trip (Jetson Orin observed ~95.6 C GPU / 99 C CPU [50]; Qualcomm trip points unconfirmed); freq drops while throttled; T_amb from compartment HVAC state"
noise: {t_sigma_C: 0.3, p_sigma_pct: 2}
lag_s: 60                           # tau 30-120 s (assumed; fit to [47])
failure_modes:
  - {type: degrade, params: {t_amb_rise_C: [10, 15], cause: HVAC_failure}, plausible_rate: "1/month (assumed)"}
  - {type: stuck_at, params: {sensor: t_soc}, plausible_rate: rare}
  - {type: dropout, params: {cause: node_power_loss}, plausible_rate: "1/quarter (assumed)"}
  - {type: flap, params: {cause: PSU_brownout_reboot_loop, period_s: [30, 120]}, plausible_rate: rare}
calibrate_against: "pi5-thermal-proxy [47]; Orin enclosure study [50]; own measurements on laptop and Qualcomm box"
```
```yaml
id: node.heartbeat                 # per (sender node, path)
unit: {seq: int, epoch: int, gap: ms}
rate_hz: 10
derives_from: "emitted by the governor's main decision loop (not a side thread); path delay from the link.* models"
noise: {gap_jitter_ms: {wired: 0.1, wifi: [2, 50]}}   # assumed
lag_s: 0
failure_modes:
  - {type: dropout, params: {cause: process_crash}, plausible_rate: scenario}
  - {type: stuck_at, params: {field: seq, cause: hung_loop_socket_alive}, plausible_rate: scenario}
  - {type: latency_spike, params: {pause_ms: [100, 2000], cause: GC_or_swap}, plausible_rate: "1/h (assumed)"}
  - {type: partition, params: {path: wired_or_wifi_or_both}, plausible_rate: scenario}
calibrate_against: "etcd/VRRP/Zenoh timing practice (Section 4)"
```
```yaml
id: time.sync_offset               # per node vs reference
unit: {offset: us, est_error: us, state: enum}
rate_hz: 1
derives_from: "wired software-timestamp PTP: tens of us; NTP on LAN ~200 us; untuned Wi-Fi: ms-level, tuned ~1 us possible [44][45]; GNSS loss -> holdover drift"
noise: {offset_sigma_us: {ptp_sw: 10, ntp: 100, wifi: 2000}}
lag_s: 1
failure_modes:
  - {type: clock_skew, params: {drift_ppm: [10, 50], cause: reference_lost}, plausible_rate: "GNSS outage/jamming (rate unconfirmed)"}
  - {type: degrade, params: {cause: wifi_packet_delay_variation}, plausible_rate: "whenever sync rides Wi-Fi"}
  - {type: latency_spike, params: {step_ms: [1, 500], cause: clock_step_on_resync}, plausible_rate: rare}
calibrate_against: "Oracle/LWN figures [44]; USENIX ATC21 Wi-Fi PTP study [45]"
```
```yaml
id: node.disk_health
unit: {reallocated: count, pending: count, wear_pct: pct, temp: degC}
rate_hz: 0.0003                     # ~1/h
derives_from: "age, bytes written (event log + guest data), temperature"
noise: {}
lag_s: 0
failure_modes:
  - {type: degrade, params: {reallocated_ramp_per_day: [1, 50]}, plausible_rate: "fit to annual failure rates in [51]"}
  - {type: stuck_at, params: {cause: SMART_unavailable_via_USB_bridge}, plausible_rate: common on dev kits (assumed)}
  - {type: dropout, params: {cause: device_vanishes}, plausible_rate: rare}
calibrate_against: "Backblaze Drive Stats schema and failure rates [51]"
```

## 4. Redundancy and failover patterns for a two-node demo

**Practice anchors**
| Mechanism | Send interval | Declared failed after | Source |
|---|---|---|---|
| VRRPv2 | advert 1 s | 3 × advert + skew ((256−prio)/256 s) ≈ 3.8 s at prio 50 | [41] |
| etcd (Raft) | heartbeat 100 ms (≈0.5–1.5 × RTT) | election timeout 1000 ms (10×) | [40] |
| Corosync | token 1000 ms or 3000 ms base (version-dependent) + 650 ms coefficient per node over 2 | token timeout | [42] |
| MQTT | client keep-alive K | broker drops client after 1.5 × K and publishes the Will | [38] |
| DDS | liveliness lease_duration (Fast DDS default reported as 20 s; RTI participant 100 s lease / 30 s assert) | lease expiry; EXCLUSIVE ownership passes to strongest live writer | [35][36] |
| Zenoh | keep-alive every lease/4 per link | no message for one lease → session dead, tokens deleted; session lives while ≥1 link is up | [37] |
| OPC UA | client reads ServiceLevel (0–255) | client fails over (non-transparent modes) | [39] |
| PRP (IEC 62439-3) | every frame duplicated on LAN A and B | zero switchover; duplicates dropped by (src, seq), entry forget time 400 ms | [27][28] |
| MRP / ERPS rings | — | ≤10 ms (≤14 switches) up to 500 ms (MRP); ~50 ms typical (ERPS) | [29][30] |

**Class anchor (single failure).** IACS UR E22 Rev.2 §5: loss of a data link must be in the risk assessment; a single data-link hardware failure must be handled automatically, and for Category III (propulsion, steering, power management, safety) must not affect correct operation; links must be self-checking and alarm; Category III should not use wireless links unless the class society specially considers them [31]. DNV (older editions) require that a single failure of an active component does not cause loss of a main function, and that essential systems are independent [33]. Implication: Wi-Fi may be a backup path but never the only path for anything safety-related, and per-path health must be alarmed even when traffic survives.

**Recommended demo settings (ours, derived from the practice above)**
- Heartbeat every 100 ms on **each** path (wired, Wi-Fi), carrying `node_id, epoch, seq, last_log_index, monotonic_send_ns`. Heartbeats come from the decision loop so a hung loop shows up as a frozen `seq`.
- Path down: wired after 3 misses (300 ms); Wi-Fi after 5 misses (500 ms), back up only after 10 good in a row (hysteresis against Wi-Fi jitter).
- Peer dead: no heartbeat on **any** path for 1000 ms (10× interval, as etcd). Standby adds a priority skew of 250 ms before promoting (VRRP idea). Takeover ≈1.3 s, under the 2 s arbitration ceiling and the 5 s first-shed deadline.
- Dual-path messaging: PRP-style duplicate-and-discard for all control traffic (heartbeats, log entries, grants). Send every message on both paths with `(src, epoch, seq)`; the receiver keeps a per-source window and drops repeats. No switchover delay, and control traffic is KB/s so doubling it is cheap. Use active/standby (wired first, Wi-Fi fallback) only for bulk transfers such as log snapshots.
- Split brain: two nodes cannot form a majority. Use (1) an **epoch fencing token**: promotion increments a persisted epoch, every grant carries it, and guest agents and actuator proxies reject anything below the highest epoch they have seen; (2) a **witness**: a third vote (Corosync QDevice-style), which in the demo could be a tiny process on a third device, or a majority of guest agents reporting "primary silent"; (3) **wait-for-all at start**: a node that boots joins as standby and never becomes primary until it has synced the log or an operator overrides it [43]; (4) a fence delay on the lower-priority node, so both nodes do not promote at once [43].
- Both paths drop: the primary keeps enforcing current grants, admits nothing new that needs the peer, allows only shedding and safety actions, keeps logging locally and raises the alarm. The standby promotes **only** with a witness vote; otherwise it stays in "isolated-candidate" and raises the alarm. Guests hold **leases** (e.g. 5 s TTL, renewed by the highest-epoch governor). An expired lease sends the guest to its declared safe state, so isolation degrades safely. The 200 ms safety commands must never wait on failover: they go through a local or hardwired path.
- Replay: order by `(epoch, log_index)`, never by wall clock. Wall time (PTP/NTP) is for display and deadlines only. Use a hybrid logical clock if events from several nodes have to be merged [46].

## 5. How these links and nodes fail at sea, with the conservative default

- **GEO VSAT**: rain fade (Ka worse, 3–5 dB/s [14]), mast blockage at some headings [15], seasonal sun outage, EMCON. Default: capacity = brief minimum (2 Mbit/s) × predicted availability, 0 when blocked or in EMCON; nothing safety-related depends on SATCOM.
- **LEO**: 15 s reconfiguration spikes, obstruction by superstructure, in-motion beam switching [7][8]. Default: plan on the p10 throughput and p95 latency, never the mean.
- **L-band**: shared, hundreds of kbit/s [12][13]. Default: reserve it for governor/ops traffic only; no guest bulk data.
- **LOS radio**: beyond the radio horizon, sea-surface multipath nulls, EMCON. Default: 0 beyond the computed horizon; brief minimum (1 Mbit/s) inside it.
- **Acoustic**: breaks during manoeuvres, deck machinery noise, layered water column [24]. Default: assume no link; the UUV runs autonomously with queued messages and pre-agreed rendezvous.
- **Wired backbone**: cable cut, switch failure, ring reconfiguration (≤500 ms MRP) [29]. Default: hold last state for up to one recovery time, then fail over to the other path.
- **Intra-hull Wi-Fi**: a closed watertight door adds ~5–30 dB [18], plus interference and roaming. Default: best-effort backup only; never the sole path for Category III-like functions [31].
- **Edge node**: thermal throttling when HVAC fails, power loss, disk wear, no hot-add (brief). Default: derate allocatable compute when temperature nears the trip point; on silence, treat a node as lost after 1 s.
- **Time sync**: GNSS loss or jamming, Wi-Fi delay variation [45]. Default: order the log by sequence; flag an offset above the bound; never trigger shedding from wall-clock comparisons across nodes.
- **Process / middleware**: hung loop with a live socket, GC pauses. Default: treat a frozen `seq` as dead; liveliness comes from the decision loop.

## 6. Recommendation

**Pull from public data (36 h, small slices only)**
1. LEO latency: one day from Zenodo 10020034 (CC BY 4.0, cleanest licence) [2], or a LENS daily CSV (CC BY-SA 4.0) [1]. Down-sample to a 1 Hz CSV under a few MB, commit it with attribution, and use it to drive `link.satcom.leo` and show the 15 s spike pattern.
2. Node thermal: pi5-thermal-proxy Parquet (MIT) [47], to fit `tau` and `R_th`.
3. Optional: WetLinks rain-vs-throughput [3], **only** if its licence turns out to be open.

**Synthesize everything else.** That is the GEO VSAT (brief values), L-band, LOS radio, acoustic, intra-hull Wi-Fi, heartbeats, time sync, disk, and every fault injection, all parameterised from the cited specs. Avoid CRAWDAD (redistribution banned) [52], SFI Smart Ocean (subscription, 15 GB) [21], Watermark (MATLAB, licence unstated) [20] and Backblaze bulk files [51]. Cite them as calibration references only.

**Middleware (open source, Python)**
- Governor core: our own small asyncio UDP layer, with heartbeats, PRP-style duplicate discard over both NICs, and log replication with epoch fencing. It is deterministic, needs no dependencies, and faults are easy to inject per path. This is what makes "replay to identical state" credible.
- Guest-facing pub/sub (optional): Eclipse Zenoh (`eclipse-zenoh`, EPL-2.0 OR Apache-2.0 [37]). A session survives while at least one link is up, and liveliness tokens map naturally to guest presence.
- Cyclone DDS (EPL-2.0/EDL-1.0, unconfirmed from the official repo [56]) is the option with naval pedigree: DDS grew out of Thales Splice (TACTICOS) and RTI NDDS for US Navy Aegis/Open Architecture [34]. EXCLUSIVE ownership plus liveliness gives standard hot-standby semantics [35]. It is a good talking point but costs more configuration time.
- Avoid an MQTT broker in the core: the broker is a single point of failure unless it is itself redundant. OPC UA redundancy [39] is rich but heavy for 36 h.

**Qualcomm edge hardware**
- RB3 Gen 2 (QCS6490): 12 TOPS, 6 GB RAM, 128 GB UFS, Linux [53]. Power draw is unconfirmed; measure it with an inline meter.
- QCS8550 boards: 48 INT8 TOPS (12 FP16) [53].
- Cloud AI 100: Standard 75 W/350 TOPS, Pro 75 W/400 TOPS, Ultra 150 W/870 TOPS; Dual M.2 edge 70 TOPS at 15 W [53].
- Runtimes: the ONNX Runtime QNN execution provider code is MIT [54], but it needs the Qualcomm QAIRT SDK, which is under Qualcomm's proprietary licence. Secondary summaries say it allows redistribution only as object code bundled with an app [54]. Qualcomm AI Hub compiles in Qualcomm's cloud and needs an account [55]. The compiled context binaries then run on-device (fully offline operation unconfirmed).
- Given the open-source-only rule, run guests on the ONNX Runtime CPU EP (MIT) by default. Treat the NPU as an optional accelerator only if the organisers accept a proprietary vendor runtime, and do any AI Hub compiles before the event.

## 7. Sources

1. https://github.com/clarkzjw/LENS: LENS Starlink dataset; data CC BY-SA 4.0, code GPL-3.0; dish list; formats.
2. https://zenodo.org/records/10020034: Starlink latency/throughput dataset, CC BY 4.0, 1.2 GB, UVic.
3. https://arxiv.org/abs/2402.16448: WetLinks: 6-month Starlink throughput/RTT/loss with weather, two EU sites.
4. https://mediatum.ub.tum.de/1840504: TUM Starlink web-performance dataset, CC BY 4.0.
5. https://github.com/sparky8512/starlink-grpc-tools: Unlicense; dish gRPC mode groups; 15 min history buffer.
6. https://github-wiki-see.page/m/sparky8512/starlink-grpc-tools/wiki/get_history-Notes: popPingLatencyMs and SNR field semantics.
7. https://arxiv.org/abs/2601.13790 and https://arxiv.org/pdf/2501.05302: 15 s reconfiguration at s 12/27/42/57; FHP in-motion obstruction and beam switching.
8. https://arxiv.org/html/2502.15552: Starlink in Northern Europe; unstable in-motion performance.
9. https://arxiv.org/pdf/2508.09839: Starlink in-flight study; fluctuating performance in motion.
10. https://www.networkinnovations.com/hubfs/docs/product/starlink/NI-Starlink-Flat_High_Performance.pdf: FHP 110–150 W average, 140° FoV.
11. https://intelsat.com/wp-content/uploads/2024/09/FlexMaritimeLEOSolutionBrief.pdf and https://satmarin.com/wp-content/uploads/2024/01/OW70M_Datasheet.pdf: OneWeb ~70 ms; OW70M up to 195/32 Mbit/s.
12. https://en.wikipedia.org/wiki/FleetBroadband: FB500 432 kbit/s, FB250 284 kbit/s, FB150 150 kbit/s.
13. https://www.iridium.com/services/iridium-certus-700/ and https://www.groundcontrol.com/product/thales-vesselink-700/: Certus 704/352 kbit/s; ~395 ± 100 ms latency (reseller).
14. https://gcc.kaist.ac.kr/Upl/_board/comm_0303_kr/comm_0303_kr_0_1465543340_7039.pdf: ETRI Ka/Ku VSAT, UPC+ACM, fade rates Ku ~1 dB/s, Ka 3–5 dB/s.
15. https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7570949 and https://alphatronmarine.com/de/product/v60ka-260: ACU blockage zones; dual-antenna mediator.
16. https://doodlelabs.com/case-studies/ship-to-shore/ and https://techlib.doodlelabs.com/mesh-rider-field-and-bench-testing-guide: 47 km ship-to-shore link; field-test method.
17. https://silvustechnologies.com/wp-content/uploads/2025/09/Silvus_Loitering-Munitions-Brochure.pdf: Silvus 75 km at 10 Mbit/s claim.
18. https://experts.boisestate.edu/en/publications/shipboard-radio-frequency-propagation-measurements-for-wireless-n/, https://personal.ntu.edu.sg/eyhlee/Prof%20Lee/PIERB_2012_Jan.pdf, https://personal.ntu.edu.sg/eyhlee/Prof%20Lee/2011AWPLJuly.pdf, https://hal-univ-rennes1.archives-ouvertes.fr/hal-00872320: ~20 dB per bulkhead/door; 5–30 dB; hull waveguide effect; ferry WSN across watertight doors.
19. https://documentation.extremenetworks.com/WiNG/5.9.6/WCSRG/GUID-D3C20B39-BE9E-4F6F-9775-EBED5973A461.shtml: 802.11n/ac MCS rate tables.
20. https://ffi.no/en/research/watermark and https://hal.archives-ouvertes.fr/hal-01630274: Watermark benchmark, channels, bands, MATLAB.
21. https://ieee-dataport.org/open-access/sfi-smart-ocean-dataset-underwater-acoustic-communications: SFI Smart Ocean dataset, ~15 GB, subscription.
22. https://pdf.nauticexpo.com/pdf/teledyne-benthos/dat-datasheet/40202-125133.html and https://www.teledynemarine.com/teledyne-marine-unveils-innovative-bluestreamx2: Benthos 140–15 360 bit/s, 2–6 km by band; BlueStreamX2 4800 bit/s.
23. https://www.sonardyne.com/?p=1399: Sonardyne Modem 6, 200–9000 bit/s, SNR-selected telemetry schemes TS0–TS7.
24. https://faculty.washington.edu/paymana/papers/oceans07.pdf: FSK BER differs strongly in surface duct vs thermocline.
25. https://spectrum.ieee.org/nato-develops-first-standardized-acoustic-signal-for-underwater-communications and https://www.popotomodem.com/blog/09-09-2019/: JANUS (ANEP-87), 11.52 kHz, FH-BFSK, ~80 bit/s.
26. https://www.vde-verlag.de/iec-standards/252784/iec-61162-460-2024.html: IEC 61162-460 scope (add-on to -450, network requirements, redundancy).
27. https://www.boutique.afnor.org/en-gb/standard/iec-6243932021/industrial-communication-networks-high-availability-automation-networks-par/xs140584/318144: IEC 62439-3 PRP/HSR, zero recovery time.
28. https://software-dl.ti.com/processor-sdk-linux/esd/docs/06_03_00_106/linux/Industrial_Protocols_HSR_PRP.html and https://patchwork.kernel.org/comment/23980249: EntryForgetTime 400 ms; 6-byte PRP trailer; Linux PRP duplicate discard.
29. https://en.wikipedia.org/wiki/Media_Redundancy_Protocol: MRP worst-case recovery 10/30/200/500 ms.
30. https://www.alliedtelesis.com/documents/g8032-ethernet-ring-protection-switching-feature-overview-and-configuration-guide: G.8032 ERPS ~50 ms.
31. https://www.millsblack.com/s/UR-E-22_rev2_June-2016.pdf: IACS UR E22 Rev.2: categories I–III; §5 data-link single failure, self-checking, wireless limits (later revisions unconfirmed).
32. https://www.pentestpartners.com/security-blog/iacs-ur-e26-and-e27-guidance/: UR E26/E27 scope (ships contracted from 1 Jul 2024), zones/conduits, untrusted networks.
33. https://rules.dnv.com/docs/pdf/dnvpm/rulesship/2016-07/ts401.pdf and https://rules.dnv.com/docs/pdf/dnvpm/rulesship/2003-01/ts409.pdf: DNV single-failure and independence principles (older editions).
34. https://www.rti.com/blog/20-years-of-dds-for-the-u.s.-navy and https://www.militaryaerospace.com/home/article/16724974/thales-naval-extends-partnership-with-prismtech-use-of-opensplice-dds-middleware: DDS origins in Navy/Aegis and Thales TACTICOS.
35. https://community.rti.com/docs/html/api_cpp/structDDS__OwnershipQosPolicy.html and https://community.rti.com/docs/html/api_cpp/structDDS__LivelinessQosPolicy.html: EXCLUSIVE ownership failover; liveliness lease semantics.
36. https://fast-dds.docs.eprosima.com/en/latest/fastdds/discovery/general_disc_settings.html: Fast DDS lease/announcement settings (20 s default reported by search, not read directly).
37. https://spec.zenoh.io/spec/1.0.0/transport/keep-alive.html, https://zenoh-cpp.readthedocs.io/en/1.9.0/liveliness.html, https://zenoh-python.readthedocs.io/en/1.7.2/_sources/api_reference.rst.txt: lease/4 keep-alive, multilink, tokens, EPL-2.0 OR Apache-2.0.
38. https://www.hivemq.com/mqtt-essentials-part-10-alive-client-take-over: MQTT keep-alive 1.5× rule and Will.
39. https://reference.opcfoundation.org/Core/Part4/6.6.2: OPC UA server redundancy, ServiceLevel, failover modes.
40. https://etcd.io/docs/v3.5/tuning/: etcd 100 ms heartbeat, 1000 ms election timeout.
41. https://infocenter.nokia.com/public/7210SAS229R1A/topic/com.nokia.TSR_Router_Config/master_down_int-ai9j4okj4o.html: VRRP master-down = 3 × advert + skew.
42. https://lore.proxmox.com/pve-devel/s8ocy247k6a.fsf@proxmox.com: Corosync token/token_coefficient defaults.
43. https://kb.linbit.com/pacemaker-stack/two-node-pacemaker-cluster-behavior/ and https://www.suse.com/support/kb/doc?id=7022467: two_node/wait_for_all, STONITH, fence-race delay.
44. https://docs.oracle.com/en/operating-systems/oracle-linux/8/network/network-AboutPTP.html and https://lwn.net/Articles/1000434/: PTP tens of µs (software) / sub-µs (hardware); NTP ~200 µs on LAN.
45. https://www.usenix.org/conference/atc21/presentation/chen and https://arxiv.org/pdf/2309.01006: PTP over Wi-Fi, from ms-level untuned to ~1 µs tuned.
46. https://arxiv.org/pdf/2407.00069: replay clocks for distributed replay ordering.
47. https://github.com/manunicholasjacob/pi5-thermal-proxy: Pi 5 thermal telemetry, MIT, 5 Hz Parquet.
48. https://pmc.ncbi.nlm.nih.gov/articles/PMC13091772/: edge-cloud CPU/power telemetry dataset.
49. https://arxiv.org/html/2608.25053: Hydra Jetson inference telemetry (Zenodo).
50. https://www.mdpi.com/2079-9292/15/11/2467: Jetson AGX Orin in an enclosure, throttling at ~95.6/99 °C (CC BY paper).
51. https://www.backblaze.com/cloud-storage/resources/hard-drive-test-data: Drive Stats terms and sizes.
52. https://docs.splunk.com/Documentation/MLApp/1.2.0/User/Datasetcredits and https://ieee-dataport.org/open-access/crawdad-wiscwiscape: CRAWDAD licence text (no redistribution); DataPort login requirement.
53. https://www.thundercomm.com/product/qualcomm-rb3-gen-2, https://www.qualcomm.com/internet-of-things/products/q8-series/qcs8550, https://www.qualcomm.com/products/technology/processors/cloud-artificial-intelligence/cloud-ai-100: RB3 Gen 2, QCS8550, Cloud AI 100 specs.
54. https://github.com/onnxruntime/onnxruntime-qnn and https://docs.radxa.com/en/dragon/q6a/app-dev/npu-dev/qnn-onnxrt-execution-provider: QNN EP MIT; separate QAIRT SDK download.
55. https://workbench.aihub.qualcomm.com/docs/hub/compile_examples.html and https://app.aihub.qualcomm.com/docs/hub/faq.html: AI Hub cloud compile/profile, target runtimes.
56. https://index.ros.org/r/cyclonedds/: Cyclone DDS (licence per README badges; confirm in the official repo).
