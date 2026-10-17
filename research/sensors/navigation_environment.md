# Navigation, ship motion and ocean/weather environment: sensors, data, synthetic generators

Scope: what the resource governor needs from navigation, motion and environment sensing on a 60–70 m multi-role vessel. Labels: **unconfirmed** = not verified in this research session. **assumption** = an engineering choice for our simulator, not a sourced fact. Bracketed numbers [n] refer to Sources (section 7). Researched 2026-10-16.

## 1. Sensor table

| Sensor | Measures | Data type & units | Typical rate | Interface/protocol (sentence/PGN) | Feeds (resource class / ship-state / operating limit) | Fitted on 60–100 m? |
|---|---|---|---|---|---|---|
| GNSS receiver (multi-constellation, SBAS/DGNSS) | Position, SOG, COG, UTC, fix quality, HDOP, satellites | lat/lon deg WGS84; SOG kn; COG °T; quality enum 0–8 [6] | 1 Hz typ., up to 10 Hz (unconfirmed) | 0183: GGA, RMC (status A/V), VTG, ZDA, GNS/GSA; N2K 129025, 129026, 129029, 129539, 126992 [6][7] | Speed band; course-keeping (COG/SOG steadiness); the timebase for every timestamp (response time); 5–12 kn flight-deck and 4–8 kn ramp windows | yes |
| Gyrocompass (or GNSS compass as backup) | True heading, rate of turn | heading °T; ROT °/min (neg = port) [6]; THS mode A/E/M/S/V (unconfirmed) | ~10 Hz heading (unconfirmed) | HDT (gpsd marks it deprecated 2008) / THS, ROT; IEC 61162-2 high-speed serial (unconfirmed); N2K 127250, 127251 [6][7] | Course-keeping steady/free; noise = manoeuvring (ROT threshold); true-wind and radar stabilisation | yes |
| Speed log (EM or Doppler) | Speed through water (longitudinal; Doppler adds transverse), distance | kn; nmi | 1 Hz typ. (unconfirmed) | VHW, VBW (long./transverse water and ground speed), VLW; N2K 128259, 128275 [6][7] | Speed band (STW); water-referenced true wind; current estimate = ground track − water track | yes |
| Echo sounder (navigation) | Depth below transducer | m, plus transducer offset [6] | ~1 Hz, depth-dependent (unconfirmed) | DPT, DBT; N2K 128267 [6][7] | Under-keel margin on survey lines; it's an active acoustic emitter (emission = silent, acoustic-link interference) | yes |
| MRU / IMU (helideck, LARS, multibeam) | Roll, pitch, heave, heave rate, angular rates, accelerations | deg, m, m/s, deg/s, m/s² | 10–200 Hz (Kongsberg MRU 5+: 200 Hz; real-time heave 5 cm/5 % [27]) | Vendor binary/ASCII over RS-232/422/Ethernet (NMEA sentence support unconfirmed); N2K 127257 Attitude, 127252 Heave [7] | Flight-deck limit (roll, pitch, inclination, significant heave rate, MSI); stern-ramp (heave at stern via lever arm); installation window; mass/stability (mean list/trim, roll period gives GM) | sometimes (yes if helideck/LARS/multibeam fitted) |
| Anemometer (ultrasonic or cup/vane, often port + starboard) | Apparent wind speed and angle; true wind computed | kn or m/s; deg relative; R/T flag; status A/V [6] | 1 Hz typ. (unconfirmed) | MWV (R = relative, T = true), MWD; N2K 130306 [6][7] | Flight-deck wind ≤25 kn (WSI = 10-min mean [26]); drone launch/recovery (Scenario B 22 kn); mast positions (sensor shadowing) | yes |
| Radar / ARPA (X and/or S band) | Tracked targets: range, bearing, course, speed, CPA/TCPA, target lat/lon, status (L/Q/T) | nmi, °T, kn, min [6] | Once per antenna revolution, ~2–3 s (unconfirmed) | TTM, TLL, OSD/RSD; N2K tracked-target PGN unconfirmed | Traffic clearance before deck ops; emission = silent (radar off); mast positions (arcs, blind sectors); electrical power | yes |
| AIS transponder (Class A) | Other ships' MMSI, position, SOG/COG, heading, nav status; own-ship echo | ITU-R M.1371 messages, 6-bit armoured payload | Class A: 10 s at 0–14 kn, 6 s at 14–23 kn, 2 s above 23 kn, 3⅓–2 s when turning, 3 min at anchor; static/voyage data every 6 min [32] | !AIVDM (others) / !AIVDO (own); N2K 129038, 129039, 129794, 129809/129810 [7] | Traffic picture; emission = silent (Tx off, Rx only); data links (VHF) | yes |
| Autopilot / heading and track control | Mode (standby/heading/track), set heading, rudder order and feedback, cross-track error | enum; deg; nmi | 1–10 Hz (unconfirmed) | HTC/HTD (unconfirmed), APB, RSA, XTE [6]; N2K 127237 Heading/track control, 127245 Rudder, 129283 XTE [7] | Course-keeping steady (track mode and small XTE) vs free; noise = manoeuvring (rudder activity) | yes |
| Weather station | Pressure, air temp, RH, dew point; visibility (separate sensor) | hPa, °C, %, nmi | 0.1–1 Hz (unconfirmed) | XDR, MDA (gpsd: obsolete 2009) [6]; N2K 130313 Humidity, 130314 Pressure, 130316 Temperature (130310/130311 obsolete) [7] | Heat rejection (HVAC load from air temp/RH); flight-deck visibility and pressure trend | yes (visibility: sometimes) |
| Wave radar (X-band backscatter processor, e.g. Miros WaveX) | Hs, period, wave direction, surface current, STW | m (0.1 m resolution, ±0.2 m for 0.5–5 m), s, deg, kn [33] | Minutes-scale (unconfirmed) | Vendor / proprietary NMEA (unconfirmed) | Sea state, so flight-deck SS ≤4, ramp SS ≤4, installation SS ≤3; needs wind ≥1–2 m/s [33] | sometimes (research/offshore) |
| Seawater inlet temperature (sea chest / cooling intake RTD) | Intake seawater temp | °C | 0.1–1 Hz (unconfirmed) | Machinery automation (IAS) via Modbus etc. (unconfirmed); MTW [6]; N2K 130316 [7] | Heat rejection (160 kW at 12 °C falling to 120 kW at 30 °C); cooling status | yes |
| Thermosalinograph (TSG) | Intake T and conductivity, giving salinity | °C, S/m, PSU | ~1 Hz (unconfirmed) | Vendor ASCII serial | Surface sound speed; cross-check of the SST feed | sometimes |
| CTD / sound-velocity profiler (cast) + hull SV sensor | T, S, pressure, giving a sound-speed profile | °C, PSU, dbar, m/s | One profile per cast (sensor 4–24 Hz, unconfirmed) | Vendor ASCII / SVP files | Acoustic link: layering indicator and mixed-layer depth; deck position (winch/A-frame); compute (ray tracing) | sometimes (survey: yes) |
| ADCP (hull-mounted) | Current profile, bottom track | m/s per depth bin | Ensembles averaged over ~1–5 min (unconfirmed) | Vendor binary (e.g. PD0, unconfirmed) | Current for station keeping and ramp approach; acoustic noise (needs ping sync with echo sounder/USBL/modem) | sometimes |
| USBL / acoustic modem link monitor | UUV range/bearing, SNR, packet success | m, deg, dB, % | Per ping, 1–10 s (unconfirmed) | Vendor; position often re-emitted as NMEA (unconfirmed) | Data links (acoustic); noise state; layering | sometimes (when UUV embarked) |

IEC 61162-1 is closely aligned with NMEA 0183 v2.30 [6]. IEC 61162-450 (current ed. 3.0, 2024) carries 61162-1 sentences over Ethernet UDP multicast, so any listener can receive any sender [8]. Its exact multicast groups and ports sit behind a paywall (unconfirmed). For the governor this means a single-socket listener on the ship LAN, with every sentence timestamped on receipt.

## 2. Public datasets and APIs

| Name | Variables | Format, resolution & size | Licence / terms | Origin | URL | What we would use it for | Caveats |
|---|---|---|---|---|---|---|---|
| Open-Meteo Marine API | wave_height/direction/period/peak_period, wind_wave_*, swell_wave_* (+secondary/tertiary), sea_surface_temperature, ocean_current_velocity/direction, sea_level_height_msl [1] | JSON/CSV, hourly. Models: MFWAM and SMOC 0.08°, ECMWF WAM 9 km, GFS-Wave 0.25°/0.16°, DWD EWAM 5 km (Europe), ERA5-Ocean 0.5° from 1940 (5-day delay); forecast up to 8 days; a few kB per call | CC BY 4.0. Free tier is non-commercial: 600/min, 5,000/h, 10,000/day, 300,000/month [2]. Commercial use needs an API key | Open-Meteo, aggregating Météo-France, ECMWF, NOAA, DWD (company country unconfirmed) | marine-api.open-meteo.com/v1/marine | Hs → sea state; Tp/direction for the motion model; SST → heat rejection; current | Docs say it is "not suitable for coastal navigation" and coastal accuracy is limited [1]. Our test returned 0.2 km/h at 26.375N −79.875 (Florida Current) [4], while that core is ~1.6–2 m/s [36]. Is a hackathon "commercial"? Unclear: ask the organisers |
| Open-Meteo Historical Weather (archive) | wind_speed_10m, wind_direction_10m, wind_gusts_10m, pressure_msl, temperature_2m, relative_humidity_2m (visibility not listed) [3] | JSON, hourly; ERA5 0.25° from 1940, ECMWF IFS 9 km from 2017; `wind_speed_unit=kn` | CC BY 4.0, same tiers | as above | archive-api.open-meteo.com/v1/archive | Wind field for flight-deck and drone limits; air T/RH for HVAC load | Reanalysis smooths gusts; ERA5 runs 5 days behind |
| NOAA NDBC (stdmet, ocean, realtime2) | WDIR, WSPD (8-min mean on buoys), GST, WVHT (20-min record), DPD, APD, MWD, PRES, ATMP, WTMP, DEWP, VIS; ocean files: DEPTH, OTMP, COND, SAL [9] | Fixed-width text; hourly (some sub-hourly); last 45 days realtime, older years as QC'd archives [10] | US federal data; explicit licence statement not fetched (unconfirmed) | NOAA NDBC, USA | ndbc.noaa.gov | Calibrate gust, Hs and SST generators; check Open-Meteo bias at FL/HI sites | US/partner waters only. Missing values are "MM" in realtime files and 99/999 in archives [9] |
| NOAA OISST v2.1 | Daily SST | 0.25°, 1981–present. NRT version has 1-day latency, final version follows ~2 weeks later [13]. ERDDAP point-month CSV is ~2 kB | Free use and redistribution; data.gov links CC0 but its rights field is ambiguous [14] | NOAA NCEI, USA | coastwatch.pfeg.noaa.gov/erddap/griddap/ncdcOisst21Agg_LonPM180 | Site SST statistics; envelope check against the 30 °C design point | Bulk-water SST, not intake temperature; coarse near coasts |
| Copernicus Marine GLOBAL_ANALYSISFORECAST_PHY_001_024 (+ Mediterranean MFC product) | 3-D temperature, salinity, currents, SSH (variable ids thetao/so are standard naming, unconfirmed here) [15] | netCDF/Zarr subsets via the `copernicusmarine` toolbox (EUPL-1.2) [17]; 0.083°, 50 depth levels, hourly/daily/monthly [15] | Copernicus Marine licence: free; credit "Generated using E.U. Copernicus Marine Service Information" [16] | Copernicus Marine Service / Mercator Ocean, EU (France) | data.marine.copernicus.eu | T/S profiles along the cable route, giving sound speed, MLD and layering forecasts | Free registration required [16]; Med product id unconfirmed |
| Argo profiles (Ifremer ERDDAP; Argovis) | T, S, pressure, 0–2000 dbar | ERDDAP tabledap `ArgoFloats` CSV with no key (tested) [18]; Argovis JSON needs a free key, HTTP 429 on rate limit [19] | Free and unrestricted; acknowledge Argo + DOI 10.17882/42182; CC BY 4.0 per catalogues [19] | International Argo Program (GDAC at Ifremer, France) | erddap.ifremer.fr/erddap/tabledap/ArgoFloats | Real profiles near the demo sites, giving the layering indicator | Sparse in space and time; check QC flags; few profiles on the shelf |
| ERA5 via Copernicus CDS | Hourly atmosphere 0.25°; waves (swh etc.) 0.5° [20] | GRIB/netCDF, 1940–present | Reported CC BY 4.0 (unconfirmed); needs account, token and acceptance of per-dataset terms [20] | ECMWF / C3S, EU | cds.climate.copernicus.eu | Not needed: Open-Meteo already serves ERA5 | Request queue; one forum report of missing wave variables [20] |
| World Ocean Atlas 2023 | Climatological T and S (O₂/nutrients at 1°) | netCDF/CSV; 1° and 0.25° (T/S); 102 standard levels; annual/seasonal/monthly; normals incl. 1991–2020 [21] | NOAA; licence statement not fetched (unconfirmed) | NOAA NCEI, USA | ncei.noaa.gov/access/world-ocean-atlas-2023 | Fallback monthly profile when no Argo/CMEMS data | Climatology smears thermoclines; subset via THREDDS |
| NOAA MarineCadastre AIS | MMSI, BaseDateTime, LAT, LON, SOG, COG, Heading, VesselName, IMO… [22] | US EEZ, filtered to 1 min. Daily GeoParquet (2024, "experimental"); CSV via AccessAIS (orders up to ~2 GB) | Marine Cadastre disclaimer; public-domain status unconfirmed [22] | NOAA OCM + BOEM + USCG NAVCEN, USA | github.com/ocm-marinecadastre/ais-vessel-traffic | Realistic traffic replay for the Florida/Hawaii sites | US waters only; daily files likely exceed our few-MB budget (size unconfirmed), so subset with DuckDB |
| Danish Maritime Authority AIS | AIS-derived records | Daily zipped CSV, Danish waters [23] | Free; terms not found (2017 reports cite the Danish PSI act) [23] | DMA (now under DEMA), Denmark | dma.dk/safety-at-sea/navigational-information/ais-data | Only to check message-rate realism | Far from all demo sites |
| ACE ship-motion sea-state dataset | Sea state reconstructed from 1 Hz IMU heave (5-min spectra) [24] | CSV, 1.7 MB total | CC BY 4.0 [24] | Derkani, Nelli, Alberello, Toffoli; vessel Akademik Tryoshnikov | zenodo.org/records/4541564 | Sanity-check our heave spectra vs Hs | Large Southern-Ocean icebreaker, not 60–70 m; raw roll/pitch columns unconfirmed |
| ISPRA RON buoy, Mazara del Vallo | Waves, every 30 min [35] | Via the mareografico.it portal | "Open licence", name unconfirmed [35] | ISPRA, Italy | www.mareografico.it | Hs ground truth for the Sicily site | 86 m depth, 8 nmi offshore; access method not tested |

No open full-scale roll/pitch/heave time series for a 60–100 m vessel underway was found, so ship motion stays synthetic.

## 3. Synthetic generator specs

**Shared models** (Python/NumPy, deterministic, seeded per scenario for replay):

- **Sea state from Hs** (WMO code 3700, the wind-sea part of the Douglas scale [25]): 0 calm-glassy 0 m · 1 rippled 0–0.1 · 2 smooth 0.1–0.5 · 3 slight 0.5–1.25 · 4 moderate 1.25–2.5 · 5 rough 2.5–4 · 6 very rough 4–6 · 7 high 6–9 · 8 very high 9–14 · 9 phenomenal >14 m. Codes 0 and 3–6 were verified; the others come from the same table. A value on a boundary goes to the higher code (conservative). So flight deck SS ≤4 means Hs < 2.5 m, installation SS ≤3 means Hs < 1.25 m, and the SS5 envelope means Hs < 4 m.
- **JONSWAP spectrum** (DNV-RP-C205 form; standard, not re-fetched): `S(ω) = (1 − 0.287 ln γ)·(5/16)·Hs²·ωp⁴·ω⁻⁵·exp(−1.25(ωp/ω)⁴)·γ^exp(−(ω−ωp)²/(2σ²ωp²))`, with γ = 3.3, σ = 0.07 (ω ≤ ωp) / 0.09. Tp comes from Open-Meteo `wave_peak_period`; otherwise use Tp = 4.5·√Hs (assumption). Swell is a second, narrow JONSWAP (γ = 6, assumption) from the `swell_wave_*` fields.
- **Encounter frequency**: `ωe = |ω − ω²·U·cos μ / g|`, where U is ship speed (m/s) and μ is the wave heading relative to the bow (180° = head seas).
- **Roll (1-DOF linear, closed form, run at 1 Hz)**: `φ(t) = Σᵢ r·kᵢ·aᵢ·|sin μ|·Hφ(ωe,i)·sin(ωe,i·t + εᵢ)`. Here `aᵢ = √(2 S(ωᵢ) Δω)`, `kᵢ = ωᵢ²/g`, effective slope factor r = 0.7 (assumption), `Hφ = 1/√((1−Λ²)² + (2ζΛ)²)` and `Λ = ωe/ωφ`. Natural period: `Tφ = 2·C·B/√GM` [31], with `C = 0.373 + 0.023·B/d − 0.043·L/100` (IS Code 2008 form; this C expression was not re-verified). Our hull (L 65, B 12.5, d 3.6, GM 1.2 m, assumption) gives C = 0.425 and Tφ ≈ 9.7 s. Re-checked Sat 00:52 PDT at the 60 m length now in config/assumptions.yaml: C = 0.427 and Tφ ≈ 9.75 s, no material change. Damping ζ = 0.08 stopped, rising linearly to 0.12 at 12 kn (bilge keels, assumption). Simplified roll-period formulas often err by more than 10 % [31].
- **Pitch and heave**: same sum with `|cos μ|`, a ship-length filter `|sinc(k·L·cos μ / 2)|` and a draft factor `e^(−k·d)`. Natural periods Tθ ≈ Tz ≈ 4.5 s, ζ = 0.3 (assumption). Point motion at a deck location (x aft-positive from CoG, y to port): `z_p = z − x·θ + y·φ` (small angles); heave rate is the analytic derivative.
- **Numerics**: N = 40 frequencies over 0.2–2.0 rad/s with random phases εᵢ. The sums are evaluated in closed form at each 1 Hz tick, with no ODE integration, so the model is stable and replayable. Note that 1 Hz sampling slightly under-reads heave-rate peaks.
- **Derived limit metrics**: inclination = `acos(cos φ · cos θ)`; significant heave rate SHR ≈ 2 × RMS heave rate over 20 min [26]; WSI = 10-min mean wind [26]. The governor gets a three-state deck status: green (all within limits), amber (MSI/WSI only out), red (roll, pitch, inclination or heave rate out) [26]. Numeric HCA limits are set per vessel and helicopter type and are not public [26]. Our thresholds are configuration values (unconfirmed placeholders: ±3° pitch/roll, 3.5° inclination, 1.3 m/s SHR).
- `plausible_rate` values below are fault-injection rates for testing (assumption), not field reliability statistics.

```yaml
id: env.hs_m                      # truth significant wave height; sea_state = WMO3700(hs)
unit: m
rate_hz: 1                        # hourly Open-Meteo wave_height, linearly interpolated
derives_from: "cached Open-Meteo marine wave_height/wave_peak_period/wave_direction; scenario overrides (e.g. ramp to SS5)"
noise: {measured_by: wave_radar, sigma_m: 0.2, update_s: 120}   # sigma per WaveX spec [33]; update interval is an assumption
lag_s: 0
failure_modes:
  - {type: latency, params: {feed_age_h: [6, 72]}, plausible_rate: "forced once per demo"}
  - {type: drift, params: {model_bias_m: 0.5}, plausible_rate: "always-on option"}
  - {type: dropout, params: {cause: "wind < 1-2 m/s or rain clutter", duration_min: [10, 120]}, plausible_rate: "1/day"}
calibrate_against: "NDBC 41122 WVHT; CDIP 238 / NDBC 51212; ISPRA RON Mazara del Vallo"
```

```yaml
id: nav.gnss_fix                  # lat, lon, SOG, COG, fix quality, HDOP -> GGA/RMC/VTG/ZDA
unit: "deg, kn, degT"
rate_hz: 1
derives_from: "truth track integrated from heading + STW + current; speed band setpoints stopped 0 / slow 3-5 / cruise 10-14 / fast >18 kn"
noise: {horiz_m_1sigma: 1.5, sog_kn: 0.05, cog_deg: "0.5 above 3 kn, random below 0.5 kn"}   # assumption
lag_s: 0.2
failure_modes:
  - {type: dropout, params: {gga_quality: 0, rmc_status: V, duration_s: [5, 1800]}, plausible_rate: "2/day (jamming scenario: continuous)"}
  - {type: spoofing, params: {offset_growth_m_per_s: [0.5, 5], zda_shift_s: [0, 2]}, plausible_rate: "1 per demo"}
  - {type: desync, params: {zda_offset_s: [1, 60]}, plausible_rate: "1/week"}
calibrate_against: "MarineCadastre 1-min AIS tracks for SOG/COG smoothness (qualitative)"
```

```yaml
id: nav.heading_true              # HDT/THS + ROT
unit: "degT, deg/min"
rate_hz: 10                       # decimated to 1 Hz for the governor
derives_from: "autopilot yaw model (1st order, T = 10 s) toward set heading + roll-coupled yaw 0.1*phi"
noise: {sigma_deg: 0.1}
lag_s: 0.1
failure_modes:
  - {type: stuck_at, params: {hold: last_value, ths_mode: "A (falsely valid)"}, plausible_rate: "1/week"}
  - {type: drift, params: {deg_per_h: [0.5, 2]}, plausible_rate: "1/week"}
  - {type: spike, params: {jump_deg: [5, 180], samples: 1}, plausible_rate: "1/day"}
calibrate_against: "GNSS COG at > 5 kn in calm water (agrees within drift + leeway)"
```

```yaml
id: nav.stw_kn                    # VHW/VBW
unit: kn
rate_hz: 1
derives_from: "speed-band setpoint with 1st-order response (tau 60 s); STW = SOG - current projected on heading"
noise: {sigma_kn: 0.1, wave_term_kn: "0.05*hs"}
lag_s: 1
failure_modes:
  - {type: drift, params: {fouling_pct_per_week: -3}, plausible_rate: "always-on in 14-day runs"}
  - {type: dropout, params: {cause: "aeration at SS>=5 (Doppler)", duration_s: [10, 300]}, plausible_rate: "5/day at SS5"}
  - {type: quantization, params: {step_kn: 0.1}, plausible_rate: "always"}
calibrate_against: "Open-Meteo ocean_current_* via SOG - STW consistency (not in boundary currents)"
```

```yaml
id: motion.roll_deg               # also roll rate
unit: deg
rate_hz: 1
derives_from: "JONSWAP(hs, tp) + swell, encounter shift, 1-DOF RAO, T_phi 9.7 s, zeta 0.08-0.12, wave heading from wave_direction - heading"
noise: {sigma_deg: 0.02}
lag_s: 0.05
failure_modes:
  - {type: stuck_at, params: {value: 0.0}, plausible_rate: "1/month"}
  - {type: latency, params: {delay_s: [1, 5]}, plausible_rate: "1/day"}
  - {type: dropout, params: {duration_s: [2, 120]}, plausible_rate: "1/day"}
calibrate_against: "roll RMS vs Hs relation (target ~1-3 deg RMS at SS4 beam seas, assumption); measured roll period gives GM check"
```

```yaml
id: motion.pitch_deg
unit: deg
rate_hz: 1
derives_from: "same wave components, |cos mu| forcing, length filter, T_theta 4.5 s, zeta 0.3"
noise: {sigma_deg: 0.02}
lag_s: 0.05
failure_modes:
  - {type: stuck_at, params: {value: last_value}, plausible_rate: "1/month"}
  - {type: spike, params: {jump_deg: [2, 10]}, plausible_rate: "1/day"}
calibrate_against: "ACE heave/pitch spectra shape (Zenodo 4541564), scaled"
```

```yaml
id: motion.deck_heave_rate_mps    # at flight deck (x=-20 m) and stern ramp (x=-30 m), assumption
unit: m/s
rate_hz: 1
derives_from: "d/dt of z - x*theta + y*phi; SHR = 2*RMS over 20 min; inclination = acos(cos(phi)*cos(theta))"
noise: {sigma_mps: 0.02}
lag_s: 0.1
failure_modes:
  - {type: drift, params: {heave_filter_offset_m: [0.1, 0.5], period_s: 25}, plausible_rate: "after each sharp turn"}
  - {type: dropout, params: {duration_s: [5, 600]}, plausible_rate: "1/day"}
calibrate_against: "ACE 1 Hz heave spectra; CAA SHR definition [26]"
```

```yaml
id: met.wind                      # true (TWS/TWD) and apparent (MWV R) wind
unit: "kn, deg"
rate_hz: 1
derives_from: "Open-Meteo wind_speed_10m/direction/gusts (kn); gust process OU, sigma=(gust-mean)/3, tau 20 s (assumption); apparent = true - ship velocity; mast height factor (z/10)^0.11 (assumption)"
noise: {sigma_kn: 0.3, sigma_deg: 2}
lag_s: 0.5
failure_modes:
  - {type: stuck_at, params: {cause: "icing/bird/bearing"}, plausible_rate: "1/month"}
  - {type: drift, params: {masking_pct: -30, sector_deg: [150, 210]}, plausible_rate: "whenever wind from the masked sector"}
  - {type: dropout, params: {duration_s: [5, 600]}, plausible_rate: "1/day"}
calibrate_against: "NDBC LKWF1 / 41122 WSPD-GST (8-min mean vs gust factor)"
```
True wind (ground-referenced): `v_true = v_apparent + v_ship`. Here `v_apparent = −AWS·(sin(HDG+AWA), cos(HDG+AWA))` and `v_ship = SOG·(sin COG, cos COG)`, both (east, north). Then TWS = |v_true| and TWD(from) = `atan2(−v_e, −v_n)`. To get water-referenced wind, use STW/heading in place of SOG/COG.

```yaml
id: env.seawater_inlet_c          # intake temperature driving heat rejection
unit: degC
rate_hz: 1
derives_from: "OISST/Open-Meteo SST at site + diurnal +-0.3 + intake-depth offset (0 to -0.5) + sea-chest recirculation +0.5 when stopped (assumptions); Q_kW = 160 - (40/18)*(T - 12)"
noise: {sigma_c: 0.05}
lag_s: 30                         # thermowell time constant, assumption
failure_modes:
  - {type: stuck_at, params: {value: last_value}, plausible_rate: "1/month"}
  - {type: drift, params: {c_per_day: 0.1}, plausible_rate: "always-on option"}
  - {type: spike, params: {jump_c: [-10, 40]}, plausible_rate: "1/day"}
calibrate_against: "NDBC WTMP (41122 at 0.46 m; LKWF1 at 1.6 m below MLLW); CDIP 238 SST"
```

```yaml
id: env.layering                  # sound-speed profile summary for the acoustic link
unit: "MLD m; max |dc/dz| 1/s; layered bool"
rate_hz: 0.000278                 # one profile per hour, held
derives_from: "nearest Argo profile (else CMEMS daily, else WOA23 monthly) -> c(z) by Mackenzie 1981 or gsw.sound_speed -> MLD (T(10 m) - 0.2 degC) -> layered = MLD < 30 m and max|dc/dz| > 0.2 1/s in 0-200 m (thresholds proposed)"
noise: {sigma_c_mps: 0.5}
lag_s: 3600
failure_modes:
  - {type: latency, params: {profile_age_h: [6, 240]}, plausible_rate: "forced once per demo"}
  - {type: dropout, params: {cause: "no profile within 50 km / 10 days"}, plausible_rate: "site-dependent"}
calibrate_against: "Argo 6903296 profile 2026-08-15 (section 4)"
```

```yaml
id: link.acoustic_quality         # UUV acoustic link packet success ratio
unit: "0..1"
rate_hz: 0.2
derives_from: "0.95 * f_layer(0.3 if layered and vehicle below MLD) * f_noise(0.4 manoeuvring, 0.6 deck machinery) * exp(-range/r0), r0 = 2 km; link broken below 0.5 (all assumptions)"
noise: {binomial_packets: 20}
lag_s: 5
failure_modes:
  - {type: dropout, params: {cause: "unsynchronised echo sounder/ADCP ping", duration_s: [5, 60]}, plausible_rate: "10/h if sync off"}
  - {type: latency, params: {delay_s: [2, 20]}, plausible_rate: "1/h"}
calibrate_against: "none public; synthetic only"
```

```yaml
id: nav.traffic_targets           # AIS !AIVDM types 1/2/3 and 5, radar TTM/TLL from the same truth
unit: "per target: lat, lon, SOG, COG, CPA nmi, TCPA min"
rate_hz: 0.5
derives_from: "scripted + Poisson-spawned targets; AIS at M.1371 intervals [32]; radar bearing 1 deg, range 1 %, one update per 2.5 s scan (assumptions)"
noise: {ais_pos_m: 10, radar_bearing_deg: 1}
lag_s: 2
failure_modes:
  - {type: dropout, params: {cause: "radar clutter at SS>=5 or emission silent"}, plausible_rate: "per state"}
  - {type: spoofing, params: {ghost_targets: [1, 5], shared_offset_km: [1, 20]}, plausible_rate: "1 per demo"}
  - {type: desync, params: {ais_radar_mismatch_m: [100, 1000]}, plausible_rate: "1/day"}
calibrate_against: "MarineCadastre density for FL/HI; synthetic for Sicily"
```

**Sound speed and layering, the formula.** Mackenzie (1981) nine-term equation (T °C, S ppt, D m) [28]:
`c = 1448.96 + 4.591T − 5.304e-2·T² + 2.374e-4·T³ + 1.340(S−35) + 1.630e-2·D + 1.675e-7·D² − 1.025e-2·T(S−35) − 7.139e-13·T·D³`.
Valid for T −2 to 30 °C, S 30–40 (NPL tabulates 25–40), D 0–8000 m; standard deviation about 0.07 m/s against Del Grosso [28]. Above 30 °C (August Florida), switch to TEOS-10 `gsw.sound_speed(SA, CT, p)` (BSD-3, 75-term specific volume [29]); UNESCO Chen-Millero is the pressure-based alternative. The layering indicator combines mixed-layer depth (de Boyer Montégut 2004: first depth where T drops 0.2 °C below T at 10 m, or σθ rises 0.03 kg/m³, linearly interpolated [30]) with the maximum |dc/dz| below it. A well-mixed column shows only the pressure term, 0.016 s⁻¹.

## 4. Demo location shortlist

SST statistics come from NOAA OISST v2.1 daily values for 2025 (31 days per month) via ERDDAP [13]. Heat rejection Q uses the brief's linear rule. Argo counts come from Ifremer ERDDAP queries run 2026-10-16 [18].

| Site | Coordinates (survey point / OISST cell) | Cables nearby (public sources) | Aug 2025 SST mean (min–max) → Q | Oct 2025 SST mean (min–max) → Q | Buoy | Argo nearby |
|---|---|---|---|---|---|---|
| **A. Strait of Sicily, Mazara del Vallo–Kelibia corridor** | 37.30N 11.90E / 37.375N 11.875E | Didon, Hannibal and Trapani–Kelibia cross from Kelibia to Mazara [34]; Minerva and LEV also land at Mazara [34]; Medusa planned via Bizerte/Mazara [34] | 26.1 (24.9–27.2) °C → 128.7 kW | 22.6 (21.3–24.6) °C → 136.4 kW | No NDBC; ISPRA RON buoy off Mazara (86 m depth, 8 nmi out, 30-min data) [35] | 46 profiles from 3 floats in 36–38N, 11–13.5E, Aug 2024 – Oct 2026 |
| **B. SE Florida, off Boca Raton** | 26.35N 80.03W / 26.375N 79.875W | Monet lands at Boca Raton (Equinix MI3) [34]; GlobeNet/Atlantica-1 station built in Boca Raton c. 2000 (current status unconfirmed) [34] | 30.4 (30.0–30.9) °C → 119.1 kW, **above the 30 °C design point** | 29.0 (28.6–29.4) °C → 122.2 kW | NDBC 41122 Hollywood Beach (26.001N 80.096W, 15.6 m, waves + SST 0.46 m + currents) [10]; LKWF1 Lake Worth Pier (wind, pressure, air/water temp) [11] | 69 profiles from 10 floats in 25–27.5N, 80.2–78.5W since 2023 |
| **C. Leeward Oahu, Kahe Point / Kapolei – Mākaha** | 21.33N 158.20W / 21.375N 158.375W | Hawaiki (Kapolei landing station) [34]; SEA-US (Mākaha Beach) [34]; Southern Cross (Kahe Point per 2000 report; current landing unconfirmed) [34] | 27.6 (27.3–27.8) °C → 125.3 kW | 27.3 (26.8–27.6) °C → 126.0 kW | NDBC 51212 / CDIP 238 Kalaeloa Barbers Point, 2.75 km offshore, SST at 0.45 m, 5-min data since 2022 [12] | 89 profiles from 6 floats in 20.5–22N, 159.5–157.5W, 2024–2026 |

- **Recommended: A (Sicily).** October SST of ~22.6–24.6 °C matches Scenario B's 24 °C (Q ≈ 133 kW), and the site is in Italian waters, which suits Fincantieri. It also has a strong layering case. Argo float 6903296 on 2026-08-15 (36.42N 13.01E) reads 29.96 °C at 6 dbar, 29.44 at 10, 26.73 at 15.5 and 22.21 at 25.5 dbar. That gives MLD ≈ 10.5 m and, by Mackenzie, c = 1547.2 → 1530.5 m/s over 10–25 m (≈1.1 s⁻¹), with a minimum of ~1515 m/s at 75–145 m. This is a strongly downward-refracting summer profile, so the acoustic link should be flagged unreliable below ~10 m. A winter profile from the same box (float 7901138, Jan 2026) is available for the mixed-water contrast. Open-Meteo on 2025-10-14 12:00 gave Hs 0.86 m (SS3), SST 23.1 °C and wind 17.2 kn gusting 20.6 [4][5]. Eastern-Mediterranean GNSS interference is widely reported [37], which justifies the jamming test (not specific to Sicily).
- **Stress case: B (Florida, August).** This is the only site above 30 °C, so it forces load shedding on heat rejection. The Florida Current core (~1.6–2 m/s, ~3–4 kn, ~20 km offshore [36]) makes a 3 kn survey and 4–8 kn ramp recovery hard, and it is exactly where Open-Meteo's current field failed our test. Use it to show the governor distrusting a feed.
- **C (Oahu)** has the best open buoy and Argo coverage, with long-period swell (Open-Meteo 2025-10-14: Hs 1.58 m, swell 12.4 s) that exercises roll resonance near Tφ ≈ 9.7 s.

## 5. How these sensors fail at sea, and the conservative default

- **GNSS loss** (GGA quality 0, RMC V, age > 3 s): dead-reckon from gyro + log with a growing error circle; block new position-critical tasks (installation over the cable, station-keeping); keep running tasks; raise an alarm.
- **GNSS jamming** (satellites and C/N0 fall, HDOP rises): treat as loss, and also distrust ZDA time; switch the governor's timebase to the local monotonic holdover clock.
- **GNSS spoofing** (smooth position walk, SOG ≠ STW ± current, GNSS–DR divergence, all AIS targets shifted alike [37]): GNSS is invalid once |GNSS − DR| exceeds the DR error bound; use DR and flag the time source as suspect; never let a GNSS-derived speed relax a limit.
- **Gyro stuck, drifting or settling**: use GNSS COG above 5 kn or the GNSS compass; mark course-keeping = free, so flight-deck and ramp ops are not admitted.
- **Speed log fouled or aerated**: speed band from SOG; flag if |SOG − STW| exceeds the current estimate by > 1 kn; choose the band that tightens limits.
- **Echo sounder dropout or false bottom** (aeration, emission silent, ADCP crosstalk): use charted depth minus margin; deny tasks that need measured under-keel clearance.
- **MRU stale, stuck or failed**: motion unknown counts as out of limits, so flight deck red, ramp closed, installation window closed.
- **MRU heave-filter transient** after turns (real-time heave period 25 s [27]): hold the deck status for one SHR window after any turn > 20° (assumption).
- **Anemometer masking, icing or dropout**: use the higher of port/stbd; if sensors disagree by > 5 kn or data is > 30 s old, use the larger of the last valid gust and the model gust. If true wind can't be computed (heading/SOG invalid), use the relative wind, which is what the aircraft sees.
- **Radar/ARPA clutter, target swap, or radar off (emission silent)**: the traffic picture is unknown, so require a manual lookout confirmation before launch/recovery; never treat "no tracked targets" as clear.
- **AIS gaps, spoofed ghosts, own transmitter off in silent mode**: keep every AIS-only target; missing AIS never means "clear".
- **Weather station drift, or visibility sensor missing**: assume visibility below flight minima until a valid reading arrives.
- **Wave radar** (needs wind ≥1–2 m/s [33]; rain clutter): Hs = max(wave radar, MRU-derived, forecast).
- **Seawater inlet temperature stuck or spiking**: use max(last valid, SST feed + 1 °C), capped at 30 °C design, giving heat rejection ≥ the 120 kW worst case. Above 30 °C, extrapolate and flag out of envelope.
- **CTD/SVP profile stale** (> 6 h or > 10 km, assumption) **or missing**: assume layered, so the acoustic link is unreliable; recommend a cast (deck/winch slot request).
- **ADCP/USBL/echo sounder ping collisions**: link quality = degraded until ping sync is confirmed.
- **Stale environment feed** (forecast cache older than its issue horizon, or the run exceeds 8 forecast days [1]): fall back to the monthly worst case (OISST monthly max, Hs upper band). A stale feed may only tighten a limit, never relax one.
- **Clock desync and NMEA corruption** (bad checksum, wrong talker, repeated timestamps): reject; timestamp on receipt; drop samples older than each signal's max age.

## 6. Recommendation

Pull these 3–5 sources once, cache them as files (JSON/CSV with a manifest of URL, retrieval time and licence), and run offline:

1. **Open-Meteo Marine + Archive** (top pick): hourly Hs/Tp/swell/SST/current and wind/gust/pressure/T/RH per site. No key; CC BY 4.0. Free tier is non-commercial, so confirm the hackathon's status with the organisers.
2. **NOAA OISST via ERDDAP**: monthly SST statistics and the envelope check (small CSV, no key).
3. **Argo via Ifremer ERDDAP**: 2–5 real T/S profiles per site for the layering indicator (no key).
4. **NDBC 41122 / LKWF1 or 51212** (only if Florida or Hawaii is used): one month of stdmet to calibrate gust factor and SST noise.
5. Optional: **Copernicus Marine** T/S subset for Sicily (free registration) if Argo is too sparse; **WOA23** monthly profile as last fallback.

Exact top query (tested 2026-10-16 with a 1-day range; multiple sites can be comma-separated):

```
GET https://marine-api.open-meteo.com/v1/marine?latitude=37.30&longitude=11.90
    &hourly=wave_height,wave_period,wave_peak_period,wave_direction,wind_wave_height,
            swell_wave_height,swell_wave_period,swell_wave_direction,
            sea_surface_temperature,ocean_current_velocity,ocean_current_direction
    &start_date=2025-10-01&end_date=2025-10-14&timezone=GMT&cell_selection=sea
GET https://archive-api.open-meteo.com/v1/archive?latitude=37.30&longitude=11.90
    &start_date=2025-10-01&end_date=2025-10-14
    &hourly=wind_speed_10m,wind_direction_10m,wind_gusts_10m,pressure_msl,temperature_2m,relative_humidity_2m
    &wind_speed_unit=kn&timezone=GMT
GET https://coastwatch.pfeg.noaa.gov/erddap/griddap/ncdcOisst21Agg_LonPM180.csv?sst[(2025-10-01T12:00:00Z):1:(2025-10-31T12:00:00Z)][(0.0)][(37.375)][(11.875)]
GET https://erddap.ifremer.fr/erddap/tabledap/ArgoFloats.csv?platform_number,time,latitude,longitude,pres,temp,psal&latitude>=36&latitude<=38&longitude>=11&longitude<=13.5&time>=2025-08-01T00:00:00Z&pres<=300
```
(Join the wrapped lines with no spaces. Ocean current velocity is returned in km/h.)

**What stays synthetic:**
- Every ship-borne sensor stream: GNSS, gyro, log, echo sounder, MRU, anemometer, autopilot, radar/AIS targets, inlet temperature, USBL/modem.
- The ship's motion response, and all high-frequency content (waves, gusts at 1 Hz). Public data only supplies hourly drivers.
- Traffic for Sicily (no open AIS archive was found there).
- The acoustic-link model.
- All fault injection (section 3 failure_modes).

## 7. Sources

1. https://open-meteo.com/en/docs/marine-weather-api: Marine API variables, models and resolutions, 8-day forecast, coastal and navigation caveats.
2. https://open-meteo.com/en/terms: CC BY 4.0; free-tier limits; non-commercial definition.
3. https://open-meteo.com/en/docs/historical-weather-api: archive endpoint, wind/pressure/RH variables, `kn` unit, ERA5/IFS coverage.
4. https://marine-api.open-meteo.com/v1/marine?latitude=37.30,21.33,26.35&longitude=11.90,-158.20,-80.03&hourly=wave_height,sea_surface_temperature,ocean_current_velocity&start_date=2025-10-14&end_date=2025-10-14&cell_selection=sea: live test (multi-site; Florida current 0.2 km/h).
5. https://archive-api.open-meteo.com/v1/archive?latitude=37.30&longitude=11.90&start_date=2025-10-14&end_date=2025-10-14&hourly=wind_speed_10m,wind_gusts_10m&wind_speed_unit=kn: live wind test, Sicily.
6. https://gpsd.gitlab.io/gpsd/NMEA.html: NMEA 0183 field lists (GGA, RMC, VTG, ZDA, HDT, VHW, VBW, DPT, DBT, MWV, TTM, TLL, ROT, MTW, MDA, XDR, APB, RSA); IEC 61162-1 ≈ NMEA 2.30.
7. https://www8.garmin.com/manuals/webhelp/gpsmap1002-1202/EN-US/GUID-0C4B3FAB-3E41-438C-B31E-9B5489790913.html: NMEA 2000 PGN numbers and names.
8. https://webstore.iec.ch/p-preview/info_iec61162-450%7Bed1.0%7Den.pdf and https://ccn-scc.ca/standardsdb/standards/2054015: IEC 61162-450 scope (Ethernet multicast), edition 3.0 (2024).
9. https://www.ndbc.noaa.gov/faq/measdes.shtml: NDBC stdmet/ocean columns, averaging periods, missing-value codes.
10. https://www.ndbc.noaa.gov/station_page.php?station=41122: Hollywood Beach FL buoy details.
11. https://www.ndbc.noaa.gov/station_page.php?station=lkwf1: Lake Worth Pier station details.
12. https://www.pacioos.hawaii.edu/water/buoy-kalaeloa/: CDIP 238 / NDBC 51212 location, SST depth, 5-min transmission.
13. https://coastwatch.pfeg.noaa.gov/erddap/griddap/ncdcOisst21NrtAgg: OISST v2.1 NRT/final latency; the same server answered our SST queries (ncdcOisst21Agg_LonPM180).
14. https://catalog.data.gov/dataset/sst-daily-optimum-interpolation-oi-avhrr-only-version-2-1-final-global-0-25-1981-present: OISST licence (CC0 link, ambiguous rights field).
15. https://data.marine.copernicus.eu/es/product/GLOBAL_ANALYSISFORECAST_PHY_001_024/description: 0.083°, 50 levels, hourly/daily/monthly.
16. https://help.marine.copernicus.eu/en/articles/4220332-how-to-sign-up-for-copernicus-marine-service and https://eds.hub.copernicus.eu/licences/CMEMS-licence: free registration; attribution wording.
17. https://pypi.org/project/copernicusmarine/2.0.0a4: toolbox subsetting (EUPL-1.2).
18. https://erddap.ifremer.fr/erddap/tabledap/ArgoFloats.html: Argo ERDDAP; profile counts and the 6903296 profile were retrieved here.
19. https://argo.ucsd.edu/?p=528 and https://argovis-keygen.colorado.edu/: Argo acknowledgement/DOI; Argovis free key and rate limiting.
20. https://github.com/ecmwf/cdsapi and https://forum.ecmwf.int/t/wave-data-missing-from-hourly-era5-reanalysis-at-single-levels/10906: CDS token and terms acceptance; wave-variable pitfall.
21. https://www.ncei.noaa.gov/access/world-ocean-atlas-2023/: WOA23 grids, 102 levels, periods, formats.
22. https://github.com/ocm-marinecadastre/ais-vessel-traffic and https://www.fisheries.noaa.gov/inport/item/73064: AIS GeoParquet/CSV, 1-min filtering, fields, agencies.
23. https://www.dma.dk/safety-at-sea/navigational-information/ais-data: Danish AIS download (free, zipped CSV).
24. https://zenodo.org/records/4541564: ACE ship-motion sea-state dataset (CC BY 4.0, 1 Hz IMU, 1.7 MB).
25. https://en.wikipedia.org/wiki/Sea_state and https://www.nodc.noaa.gov/OC5/WOD/CODES/s_18_sea_state.html: WMO code 3700 bands.
26. https://www.caa.co.uk/media/dsgjzgat/74th-meeting-hms-fest-18_05_17v3-updated-for-74th-hsrmc.pdf: helideck PRH limits via HCA HLL, SHR = 2×RMS over 20 min, MSI/WSI, traffic-light states.
27. https://www.kongsberg.com/discovery/inertial-solutions/mru-5/: MRU 5+ 200 Hz, real-time heave 5 cm/5 %, 25 s heave period.
28. https://www.mbari.org/wp-content/uploads/2016/03/Sndspd.txt and https://resource.npl.co.uk/acoustics/techguides/soundseawater/: Mackenzie coefficients and validity ranges.
29. https://pypi.org/project/gsw/: TEOS-10 GSW-Python (BSD-3), `sound_speed(SA, CT, p)`.
30. https://data-ww3.ifremer.fr/BIB/deBoyerMontegut_etalJGR2004.pdf: MLD criteria (0.2 °C or 0.03 kg/m³ from 10 m).
31. https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/AssemblyDocuments/A.562(14).pdf and https://proceedings.open.tudelft.nl/imdc24/article/download/881/893/1240: rolling period T = 2CB/√GM; >10 % error caution.
32. https://itu.int/dms_pubrec/itu-r/rec/m/R-REC-M.1371-2-200603-S!!MSW-E.doc: AIS Class A reporting intervals.
33. https://reecotech.com.vn/wp-content/uploads/2024/01/Miros-Wavex-Datasheet_26Apr2022.pdf: WaveX Hs accuracy/resolution; minimum wind.
34. https://en.wikipedia.org/wiki/Minerva_(cable_system), https://en.wikipedia.org/wiki/LEV_(cable_system), https://www.datacenterdynamics.com/en/news/orange-to-deploy-new-tunisia-france-subsea-cable/, https://files.hawaii.gov/dbedt/erp/EA_EIS_Library/2017-05-23-OA-FEA-Hawaiki-Submarine-Cable-Kapolei-Landing.pdf, https://files.hawaii.gov/dbedt/erp/EA_EIS_Library/2016-06-08-OA-FEA-Makaha-Beach-Cable-System.pdf, https://internetnews.com/it-management/southern-cross-completes-the-loop, https://en.wikipedia.org/wiki/Monet_(submarine_cable): cable landings for sites A–C (submarinecablemap.com could not be fetched; check it for exact routes).
35. https://www.unipa.it/i-waveNET-varata-la-boa-ondametrica-di-Mazara-del-Vallo-tra-i-primi-risultati-del-progetto-con-capofila-lUniversit-di-Palermo: ISPRA RON Mazara buoy, 86 m, 8 nmi, 30-min data, mareografico.it.
36. https://www.fau.edu/engineering/research/snmrec/data/adcp and https://agu.confex.com/agu/os16/preliminaryview.cgi/Paper92040.html: Florida Current core ~2 m/s about 20 km offshore; HF-radar median ~1.6 m/s.
37. https://www.iala.int/e-bulletin/gnss-jamming-and-spoofing-navigating-challenges-in-the-baltic-sea/ and https://arxiv.org/abs/2602.16257: GNSS jamming/spoofing at sea; shared-offset AIS spoofing patterns.
