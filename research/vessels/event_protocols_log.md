# Event protocols log: public grounding for the resource governor

Compiled 2026-10-16 for the Fincantieri "Software Defined Vessel" challenge. Public, non-proprietary,
non-export-controlled material only. Everything is paraphrased; quotes are under 15 words.
Conventions: `[n]` = numbered source in Section 6. "unconfirmed" = could not be verified against the
primary text in this pass. "inference" = our own reasoning from the cited material, not a published rule.
Candidate rules are tagged `R-E<event>-<n>` so rules written in data can trace them back to this file.

---

## 1. Event index

| Event | Our scenario / decision class | Key public sources | What it tells us about components and sequencing | Rule or constraint we can encode |
|---|---|---|---|---|
| E1 Generator trip, blackout, load shedding | Genset trip halves guest reserve to ~100 kW; first action <=5 s, full sequence <=60 s, throttle before shed / **shed + restore** | [1][2][6][8][11][64][66] | Power management sheds non-essential load in timed stages before the main breaker trips. On blackout the standby set must reach the main switchboard within 45 s, essential auxiliaries then restart in sequence, and propulsion reconnects after that. Emergency side recovers on its own | Shed order = declared priority; throttle scalable loads first; emergency-switchboard loads are outside governor authority; restore one load at a time behind a capacity check |
| E2 Cooling loss, high seawater temperature | Chilled-water derate cuts the heat-rejection budget / **throttle** | [18][26][27][28][64] | Chillers are big motor loads on the same bus. Design basis is typically 32 C seawater. Plant failures include pump deadheading. Cooling-water loss can trip propulsion engines | Heat budget derates with seawater temperature; throttle heat producers before shedding power; a chiller restart counts as a heavy-consumer start |
| E3 VTOL rescue-drone recovery | 18 % battery, 22 kn wind, land within 12 min; deck clear, wind <=25 kn, SS<=4, 5-12 kn steady course, 35 kW charging / **arbitrate deck, course, mast, power** | [29][31][33][34][35][36][39] | Flying stations means a deck sweep, aerials lowered, fire team ready, rescue boat ready, and the bridge holding course. Small VTOL UAVs have been trialled at 8-16 kn ship speed with wind up to 20 kn | Recovery owns deck, course band and approach-sector masts for its window; charging power reserved before clearance; abort to hold if any precondition drops |
| E4 UUV/USV launch, recovery, acoustic link | Survey UUV, 40-min leg over a cable at 3 kn, quiet steady course, no deck machinery while link is up / **admit + protect** | [39][42][45][48][51][52] | Stern-ramp availability is limited by pitch and sill depth, and risk rises above SS3. USBL tracking is degraded by own-ship propeller, hull and thruster noise | Acoustic-quiet lock: while the link is active, block deck machinery and thruster mode changes and hold the heading/speed band |
| E5 Winch and overboarding | Oceanographic winch and probe / **admit + monitor** | [39][41][70][71][72] | UNOLS RVSS sets factor-of-safety tiers (5.0 / 2.5 / 2.0 / 1.5) with stricter tension display, logging and alarms at each tier. It also requires danger zones and a written-competent operator, and notes that a lifted weight raises the CG | Winch admission needs a declared FS tier with the matching monitoring; stability check with the load at the sheave head; no winch while the UUV link is active |
| E6 Emission silence | Silence period / **mode change** | [54][55][56][60] | AIS is on by default. The master may switch it off for safety or security and must log the reason. Losing the shore link removes remote supervision | Silence closes transmit links and suspends dependent guests; log each switch; at 0 aboard silence needs a pre-declared autonomous fallback |
| E7 Mission modularity, payload install | Install payload at sea in a window vs in port / **admission** | [14][22][23][24][39][57] | Modules plug into fixed slots with mechanical, power, data and cooling interfaces. Navy design keeps space, weight and power margins plus a service-life allowance | Admit only if margins survive the guest's peak; at-sea install needs a stability and heavy-lift check plus a calm window with no concurrent deck evolutions |
| E8 Reduced, minimal, uncrewed | 14 / 6 / 0 aboard / **confirmation authority** | [58][59][60][61][63][66] | DNV classifies functions by mode (remote control, decision support, supervised autonomy, full autonomy) and control location. Under the MASS Code the master keeps responsibility even ashore. Minimal manning brings fatigue | Per-crew-level confirmation table; an action that needs hands on deck is inadmissible at 0 aboard unless automated and approved |
| E9 Fire, flooding, damage control | "Safety-critical, never shed automatically" / **invariant** | [1][4][67][68] | Emergency switchboard is independent of main and the interconnector opens automatically. Flooding spread via shafts and stuffing boxes; closure discipline failed | Governor never sheds emergency-switchboard or safety-tagged loads; damage-control state overrides guest priorities |
| E10 Accident cascades | Plausibility tests for the governor | [64][66][67][69][70][71] | Protective trips that share one condition (lube oil, cooling water, fuel pressure) remove all redundancy at once | Treat protective trips as correlated; flag "all redundant units depend on one condition" as a binding constraint |

---

## 2. Per-event sections

### E1 Generator trip, blackout and load shedding

**Physical sequence and who does what**
1. A running generator trips (or loses fuel, lube oil or cooling). The remaining sets take a sudden load step and frequency and voltage dip.
2. The power management system (PMS) sees overload or underfrequency and opens preferential-trip breakers on non-essential consumers (HVAC, galley, ventilation are typical) in timed stages. Training material gives example stages of about 5 s and 10 s, with the main breaker following at about 15 s if overload persists [8]. These are illustrative settings, not class values.
3. DNV main class (summarised by DNV in [1]): automatic load shedding or load reduction must prevent overload of the running sets; with sets in parallel, tripping one must not overload or trip the rest; interlocks must ensure enough generators are connected before large motors start (heavy-consumer blocking); consumers serving the same essential service are split across the two switchboard sections; protection is discriminative, so only the device nearest the fault opens. A DNV-based course text says shedding should start somewhat below 100 % of rated current [9] (secondary source).
4. Standby start. If a blackout occurs, the standby source must start and connect to the main switchboard within 45 s, and essential auxiliaries then restart automatically [1]. IACS UR M31 gives the same 45 s figure and asks for sequential restart where needed (as reproduced in [6]; UR text not read directly). DNV stresses that 45 s only gets power back on the switchboard; reconnecting propulsion takes longer [1]. Best-case full recovery is "within a minute" [1].
5. Emergency side. Main and emergency systems must recover independently: the interconnector opens automatically and the emergency generator starts and supplies its services within 45 s [1]. That requirement is SOLAS II-1/42 for passenger ships and II-1/43 for cargo ships [4]; paragraph numbers are unconfirmed, though secondary sources cite 43.3.1.3. For US passenger vessels the transfer to the final emergency source must also take no more than 45 s [5]. Passenger ships always have a transitional (battery) source; its often-cited 30 min duration is unconfirmed.
6. Stored energy for blackout start [1]: at least two stored-energy sources, enough for three start attempts on each engine; auxiliary supplies needed for the start (governors, voltage regulators, switchboard control, fuel supply) sized for the starts and/or at least 30 min; pre-lube and heating may go unpowered, provided start blocking does not set in within 30 min.
7. Unattended machinery (DNV E0): propulsion must restart automatically or be simple to start from the bridge [1].
8. Test regime. Every year the automatic start and connection of the standby set is tested by shutting down a running generator [7]. DNV's "enhanced" blackout-prevention test trips one generator and checks load shedding, load reduction and drive phase-back, then trips a large consumer to check for spurious overfrequency trips [1].

**Regulatory anchors**
- SOLAS II-1/41.5.1.2 (added by MSC.57(67) for ships built from 1 July 1998) requires load shedding or an equivalent to protect generators against sustained overload [2][3].
- The companion paragraph requires power for propulsion, steering and safety to be maintained or immediately restored if any one running generator is lost [2]. Verify both against the current consolidated SOLAS text.

**Timings for the Physical Account**

| Time | What it is | Source |
|---|---|---|
| 10 ms | Transient interruption that uninterruptible loads should ride through (switching to standby power) | [11] |
| 2 s | Window for switchgear to clear faults in a coordinated way and shed long-term-interrupt loads | [11] |
| ~5 s / 10 s / 15 s | Example staged preferential-trip settings | [8] |
| 45 s | Standby power on the main switchboard (DNV, IACS M31); emergency generator supplying (SOLAS) | [1][6] |
| <1 min | Best-case full blackout recovery | [1] |
| 30 min | Endurance of auxiliary power for blackout start; start-blocking grace period | [1] |
| 5 min | Nominal standby-generator start in the Navy QoS model; mission-priority shedding begins | [11] |
| 58 s vs ~10 s | Dali initial blackout as it happened vs with breakers in automatic (press report of NTSB statement; verify in MIR-25-40) | [65] |
| 39 min | Viking Sky time to restore power and propulsion | [66] |

Our scenario fits these numbers. A first action within 5 s matches the first preferential-trip stage, and a full sequence within 60 s matches the 45 s standby limit plus restart. Inference: when guests share a bus with uninterruptible loads, the throttle step should land inside the 2 s QoS window.

**Typical automation**
PMS functions: load sharing, standby start/stop, preferential trip, heavy-consumer request and blocking, drive load reduction ("phase back"), and blackout restart [1].

DNV's failure table names a sudden generator trip combined with weak PMS limitation as a direct route to overload and underfrequency of the remaining sets [1]. That is exactly the gap a governor fills.

**Crew roles and numbers**
- The engineer of the watch (or the bridge on unattended-machinery ships) confirms the standby set is on line and restores shed loads.
- Navy electrical casualty and load-shedding bills exist, but no official public copy was found. NSTM 320 (electric power distribution) is reported as Distribution A only on an unofficial copy [77]. The release status of NAVEDTRA 14344 (Electrician's Mate) is unconfirmed. NEETS modules are Distribution A but cover general theory [76].

Implications by crew level: **14 aboard**, a human engineer can confirm restorations; **6 aboard**, likely an unattended-machinery-style plant where the bridge confirms; **0 aboard**, only pre-approved automatic sequences, with remote-centre (ROC) confirmation for anything else.

Viking Sky had never drilled recovery from a full blackout without a standby generator, and the report links slow recovery to that [66]. USCG Safety Alert 10-24 stresses training for fast restoration of main power [75].

**Failure lessons**
- Dali: a single loose wire caused the blackout, the breakers were in manual, and fuel was supplied by the wrong pump [64].
- Viking Sky: a common-mode lube-oil low-pressure trip on all running sets [66].
- Both show that redundancy can vanish through one shared condition.

**Standards (title and scope only)**
- IEEE 45 (recommended practice for shipboard electrical installations) is cited by RVSS as an acceptable marine standard [39].
- IEC 60092 series ("Electrical installations in ships"): title only; scope not verified.

**Candidate crew rules**
- R-E1-1 "When a generator trips, throttle scalable guests first, then shed in declared order. Never shed emergency-switchboard loads." [1][11]
- R-E1-2 "Shed in stages, about 5 s apart, until running sets are below the shedding threshold (below 100 % rating)." [8][9]
- R-E1-3 "Do not start or restore a heavy consumer (chiller, winch, drone charger) until enough generators are confirmed on line." [1]
- R-E1-4 "After a blackout, essential auxiliaries and propulsion come back first; restore guests one at a time." [1][6]
- R-E1-5 "If N-1 generator redundancy is not available, refuse new non-essential guest admissions." [66]

### E2 Cooling: chilled-water failure and heat-load management

**Physical sequence**
1. A chiller trips (electrical trip, high condenser pressure with warm seawater, or a chilled-water pump problem).
2. Supply temperature rises, and compartments and electronics heat up over minutes because of thermal inertia.
3. Equipment protects itself with over-temperature trips.
4. Restarting a chiller is a large motor start on an already stressed bus.

**Published figures**
- A DDG-51 destroyer uses five 200-ton marine chillers [18].
- ESRDC argues that steady-state ratings say little about reconfiguration or failure cases, so dynamic thermal-electrical models are needed. Its DTMS framework includes chiller-based management of shipboard loads [18].
- Navy ships distribute 44 F (about 7 C) chilled water, while electronics typically want about 67 F (about 19 C) to avoid condensation. A Navy SBIR claims that distributing 67 F water would double the capacity of existing chillers [26].
- Destroyer case study: chilled-water pumps of mismatched capacity "dead-headed" one plant and shut it down. A piping cross-connect kept cooling available [27].
- Typical unrestricted-service design basis is 32 C seawater and 45 C engine-room air [28]. Attribution to IACS UR M40 is unconfirmed.
- No public heat-up rates were found (unconfirmed). Model each zone as a first-order thermal lag, with a time constant declared per zone.

**Crew roles**
No public source fetched; this is ship-specific. If the cooling cross-connect is a manual valve line-up, it needs a person in the space. At 0 aboard it is only available if it is remotely actuated.

**Failure lesson**
At Dali, the main engine was set to shut down automatically on low cooling-water pressure. Once the blackout stopped the pumps, cooling loss removed propulsion. NTSB recommendations M-25-24 and M-25-26 address this [64].

**Candidate crew rules**
- R-E2-1 "Heat-rejection budget = chiller rating derated for seawater above the 32 C design basis. Admit guests against the derated figure." [28]
- R-E2-2 "On chiller loss, throttle heat-producing guests before cutting power. The binding constraint is heat, not kW." [18] (inference)
- R-E2-3 "A chiller compressor restart is a heavy-consumer start: request and confirm generator capacity first." [1]
- R-E2-4 "If the cooling cross-connect is manual, treat the redundant plant as unavailable at 0 aboard." [27] (inference)

### E3 Helicopter and VTOL UAV flight-deck operations on small ships

**Physical sequence (helicopter practice, applied to UAV by analogy)**
1. Flying stations are piped.
2. A wide-area sweep removes or secures loose objects that downwash could move [31][32].
3. Aerials and rigging above or near the operating area are lowered or secured [31].
4. Fire pumps run at adequate deck pressure. Hoses, monitors and foam are ready near, but clear of, the area, with nozzles pointed away [31].
5. Deck crew are in position in PPE and distinctive clothing. The hook handler wears rubber gloves and rubber-soled footwear against static discharge [31].
6. A rescue party is briefed and the rescue boat is ready for lowering [31].
7. The bridge holds the agreed course and speed, and gives clearance.
8. The aircraft lands and is secured (harpoon/grid for small UAVs).
9. Stand down.

UNOLS RVSS Chapter 19 requires the master's approval and a ship-specific UAS launch and recovery checklist [39][40]. The checklist covers flight plan, risk assessment, notifications, communications plan, safety brief, debris retrieval, records and incident reporting.

**Limits and published envelopes**
- CAP 437 9th edition (February 2023; amendment 9.1, January 2026) puts helideck-movement limits in Chapter 6 and meteorological requirements in Appendix E [29]. Helideck monitoring follows the Rev 9C standard, with lower limits at night [30]. Numeric limits are aircraft-specific and were not extracted.
- Camcopter S-100 trials:
  - Indian Navy OPV, 2007: ship speed 8-16 kn, wind up to 20 kn, light to moderate seas. Autonomous approach to a waypoint about 50 ft above and 100 ft behind the pad, with an IMU and a GPS reference beside the pad [34].
  - Pakistan Navy frigate, 2008: 10-13 kn, wind up to 15 kn [35].
  - French OPV L'Adroit, 2011: 89 harpoon landings in four days [36].
  - Schiebel claims harpoon operations up to SS5 [37]; this is a vendor claim.
- Research names seaway deck motion plus ship air-wake as the main constraint on small ships, and uses motion prediction to find quiescent landing windows [38].
- Our envelope (wind <=25 kn, SS<=4, 5-12 kn): the speed band overlaps the trials. The 25 kn wind limit is above the documented 20 kn trial wind, so it must come from the aircraft's own limits.

**Crew roles and numbers**
- Superyacht guidance lists one helicopter landing officer (HLO), an aviation-trained fire team and helideck assistants [33].
- The ICS checklist adds a hook handler, a rescue party and rescue-boat crew [31].
- No public minimum headcount for UAV recovery was found (unconfirmed).

Implications by crew level:
- **14 aboard:** full flying stations is plausible: HLO, 2-3 fire team, 1-2 assistants, bridge, boat crew.
- **6 aboard:** flying stations consumes nearly everyone, so every other crewed deck evolution must be suspended.
- **0 aboard:** no fire team or hook handler. Recovery requires automatic landing and securing, a sensor-verified clear deck, fixed deck firefighting (availability unconfirmed), and clearance from the ROC.

**Failure lessons**
Near-miss analysis keeps finding loose objects and unsecured gear in or near the operating area [32].

**Candidate crew rules**
- R-E3-1 "No VTOL recovery unless the deck is declared clear and masts or aerials in the approach sector are lowered or inactive." [31]
- R-E3-2 "During recovery the ship holds the agreed course and speed band; other guests may not request course changes." [31][34]
- R-E3-3 "Fire main pressurised before approach. At 0 aboard, require fixed deck firefighting to be available." [31] (second clause inference)
- R-E3-4 "Reserve the 35 kW charging load before clearance to land. If it cannot be reserved, power is the binding constraint." (scenario)
- R-E3-5 "A low-battery rescue recovery outranks survey guests for deck and course, never safety-critical loads." (scenario priority; inference)

### E4 Small boat, USV and UUV launch and recovery

**Physical sequence**
1. Pre-launch checks on deck.
2. Launch by crane, A-frame or stern ramp with the ship slowed. One operator releases the AUV at right angles to the ship's heading [49].
3. The ship opens distance and tracks the vehicle by USBL and/or acoustic modem.
4. Mission.
5. Recovery approach (low speed, small boat or capture line).
6. Lift and secure.

RVSS asks the master and chief scientist to agree each autonomous-vehicle operation in order to limit risk [39].

**Limits**
- Stern-ramp availability is set mainly by sill depth and pitch, per USCG-sponsored work [42][43]. RHIB approach is disturbed by the ship's wake and waterjet flow [44].
- Operators report rising risk above SS3, with more than 2 m relative vertical motion and more than 10 degrees relative pitch between ship stern and boat bow [45] (industry interview).
- Speeds: one vendor LARS recovers at up to 6 kn relative speed [46]. A Navy stern-launch SBIR asked for 10 kn relative recovery [47] (topic page not opened).
- Running parallel to the seas to cut pitch is reported only in secondary sources (unconfirmed).
- A small-RV AUV system is rated safe to SS4 [48]. A NOAA AUV test was stopped as seas reached about 4-5 ft [50].
- A US Navy document surfaced by search puts SDV launch from JHSV at SS3 and support boats at SS2. The exact DTIC document is unconfirmed, so do not cite it until located.

**Acoustic link**
- USBL is disturbed by own-ship propeller and hull vibration. The transducer should sit below the keel, away from self-noise, and a ship noise survey is advised [52].
- A narrow receive cone rejects thruster noise [51].
- Acoustic-modem performance against ship and AUV noise has been measured [53].
- Inference: thruster mode changes, winch hydraulics and ramp machinery are the noise sources a governor controls.

**Crew roles and numbers**
No public minimum headcount found (unconfirmed). Typical roles are the crane/A-frame or ramp operator, 2+ deck hands, the vehicle technician, the bridge, and a 2-3 person boat crew for recovery.

Implications by crew level:
- **14 aboard:** feasible alongside one other evolution.
- **6 aboard:** recovery consumes the deck crew.
- **0 aboard:** needs an automated LARS or capture system.

**Candidate crew rules**
- R-E4-1 "While the UUV acoustic link is active: no deck machinery (winch, crane, ramp hydraulics) and no thruster mode changes." [51][52] (scenario + basis)
- R-E4-2 "Hold heading and speed in the declared survey band (e.g. 3 kn +/-0.5) for the whole leg. A course change needs release by the survey guest." (scenario)
- R-E4-3 "No stern-ramp launch or recovery above SS3 unless the ramp or LARS is rated higher." [45]
- R-E4-4 "UUV recovery is a crewed deck evolution: at 6 aboard it may not overlap flight-deck or winch operations." (inference)

### E5 Winch and overboarding operations (UNOLS RVSS)

**Factor-of-safety tiers (RVSS 11th edition, Appendix A, Tables A.8.1-A.8.4) [39]**

| FS tier | Tension monitoring | Alarms | Other requirements |
|---|---|---|---|
| >=5.0 | Not required; tension may be calculated (ABS g-factor 0.75 minimum) | None | Written "deemed competent" winch operator; wire tests every 2 years; logbooks |
| <5.0 to 2.5 | Display at the operator station, refresh >=3 Hz; log >=3 Hz; calibrate every 6 months; accuracy 4 % | Audible and visual, before FS 2.8 | Owner certifies operators |
| <2.5 to 2.0 | Display >=10 Hz with tension-trend graph; log >=20 Hz; accuracy 3 % | Before FS 2.2; alarms logged | D/d >=40:1; danger zones that exclude personnel |
| <2.0 to 1.5 (wire rope) | As the 2.0 tier | Before FS 1.7 | Slow-haul check about every 500 m; halt at FS 1.5 |

Each tier says to halt when its minimum FS is reached, or move to the next tier's rules [39].

**Other requirements**
- Appendix B: the overboard handling system must be strong enough to part the tension member before it fails itself (based on 46 CFR 189.35) [39][41].
- Stability [39]: a lifted weight acts at the top of the crane or A-frame, so the CG rises; an overside load adds list; tow tension heels the ship like a beam wind; the gear may stop the ship from taking its most stable course; the master must be consulted before heavy lifts or overside work.

**Crew roles and numbers**
- The owner and master deem winch operators competent in writing, and qualifications are refreshed after any change to controls or hardware [39].
- Danger zones are identified and personnel excluded [39].
- RVSS assumes a human operator, so at 0 aboard winch work falls outside RVSS. Inference: it would need a remote operator with live tension at the ROC.

**Failure lessons**

| Case | What happened |
|---|---|
| Tombarra [70] | A proximity switch failed to stop the winch and the fall wire parted. The switch had not been fitted per the manufacturer's instructions |
| RRS Sir David Attenborough [71] | An interlock had not reset after a test, so the winch brake released out of sequence |
| Marine Explorer [72] | Winch brake assembled incorrectly; no risk assessment |
| Dea Fighter [73] | An undersized sheave led to repeated wire failures |
| BSEE MC 759 [74] | An umbilical jumped an A-frame sheave and wedged |

**Candidate crew rules**
- R-E5-1 "No winch operation while the UUV acoustic link is active." (scenario) [39]
- R-E5-2 "A winch is admitted only with a declared FS tier. Below FS 5.0, require live tension at the operator station, logging and alarms." [39]
- R-E5-3 "Before any overside lift, recompute stability with the load at the sheave head; refuse if the margin is below the limit." [39]
- R-E5-4 "Never throttle winch power mid-lift: hold or recover the load instead. Halt payout at the tier limit." [39] (first clause inference)
- R-E5-5 "An interlock or limit switch that has not reset is a failed precondition, not a warning." [70][71]

### E6 Emission silence (public, civil level)

**Civil anchor**
IMO Resolution A.1106(29), paragraph 22 [54][55]: AIS should run whenever the ship is underway or at anchor. The master may switch it off if continued operation might compromise the safety or security of the ship. In a mandatory reporting system, the master reports the switch-off to the competent authority unless that would add risk. The switch-off and its reason are recorded in the logbook.

Charter-party practice (BIMCO AIS clause 2021) requires owners to answer charterer queries about apparent breaches within 72 h [56].

**What a silence period switches off**
General knowledge; no single public source fetched, so verify per ship: AIS transmit; navigation radar transmit; VHF/MF/HF transmit; satellite and terrestrial uplinks (VSAT, L-band, LTE, Wi-Fi); active acoustics (echo sounder, USBL interrogation, acoustic modem).

Receive-only systems (GNSS, weather fax, AIS receive) can continue. The UUV acoustic link is itself an emission.

**Effect on data links**
Remote supervision stops. The MASS Code builds remote operations centres into operation [60], so at 0 aboard silence amounts to a change of autonomy mode.

**Crew implications**
- **14 and 6 aboard:** the master orders and logs the silence.
- **0 aboard:** the order must be issued before the link drops, with a time-bounded autonomous plan (inference).

**Candidate crew rules**
- R-E6-1 "Silence closes every transmit link. Each guest that needs a transmitter is suspended, and the silence order is named as the binding constraint."
- R-E6-2 "Log every AIS and transmitter switch-off and switch-on with time and reason." [54]
- R-E6-3 "At 0 aboard, admit silence only if a pre-approved autonomous fallback covers the whole window." [58][60] (inference)
- R-E6-4 "The UUV acoustic link counts as an emission; silence and the survey leg must be arbitrated explicitly." (inference)
- R-E6-5 "Distress alerting is never blocked by the governor." (inference; GMDSS text not checked)

### E7 Mission modularity and payload integration

**What exists**
- StanFlex modules [57]: a stainless container of about 3.0 x 3.5 x 2.5 m, aligned by machined flanges, with interfaces for mounting, LAN, video, degaussing, interior communications, combat-system data and cooling. Flyvefisken class (about 320 t): one slot forward and three aft; Absalon class: five positions. No public power or cooling ratings were found (unconfirmed).
- ISO 668 ("Series 1 freight containers - classification, dimensions and ratings") and ISO 1496-1 (specification and testing, general cargo containers): titles only, abstracts not fetched.
- LCS mission packages were not researched in this pass (gap).
- IEEE 1826 (2012, superseded by 2020) defines open interfaces for >100 kW power electronics in zonal systems. It covers power, monitoring, information exchange, control and protection, plus conformance testing for plug-and-play [22].

**Margins**
- The NPES Technology Development Roadmap (2019, Distribution A) aims to keep enough space, weight and power margin for future loads. It notes that pulsed loads stress legacy plants, and it introduces the "energy magazine" [14][15][79].
- NAVSEA T9300-AF-PRO-020 (electrical systems design practice) defines "service life allowance" and "margin"; the values were not visible [23].
- History and practice of margins: the Navy set a weight-margin policy in 1963 and a KG-margin policy in 1978 [24]; a SAWE paper recommends a submarine service-life margin of 2-3.25 % of light-ship weight [24]; managing SWaP and cooling margins through life is discussed in [25].
- Current surface-ship percentages are unconfirmed.

**Installing at sea vs in port**
- RVSS heavy-lift and stability guidance applies [39].
- No public procedure for swapping a mission module at sea was found (gap).

**Candidate crew rules**
- R-E7-1 "Admit a guest only if every resource still holds its service-life allowance at the guest's peak demand." [23][24]
- R-E7-2 "Every guest declares its power, monitoring, information, control and protection interfaces before admission." [22]
- R-E7-3 "At-sea install needs an installation window: crane sea-state limit met, stability recomputed with the module on the hook, no concurrent flight, boat or winch operations." [39]
- R-E7-4 "A guest installed at sea runs in a reduced-reserve trial state until its first full functional test." (inference)

### E8 Reduced, minimal and uncrewed operation

**What exists**
- DNV-CG-0264 (first issued 2018, revised 2021 per [59]) covers navigation, engineering, remote control centres, communications and cyber.
- The AROS notation [58]: four function groups (navigation, engineering, operational, safety); modes RC (remote control), DS (decision support), SA (supervised autonomy) and full autonomy; control onboard, off-ship or hybrid (HC), for example AROS-NAV(DS,SA,HC).
- IMO MASS Code [60]:
  - adopted 22 May 2026 at MSC 111; non-mandatory; effective 1 July 2026; applies to SOLAS cargo ships;
  - the master keeps overall responsibility even when not aboard;
  - remote operations centres are integrated into operation;
  - the mandatory code is expected to be adopted by 1 July 2030 and enter into force 1 January 2032.
  - A draft summary says only one ROC is responsible for a ship at any time [61].
- BV NI 641 and the Lloyd's Register autonomy code were not verified in this pass.

**Minimal-manning lessons**
- A Navy internal review (not GAO) found LCS fatigue setting in by the third day with a core crew of about 40 [63].
- GAO-14-447 lists minimal crew among the LCS cost-saving operational concepts [62].
- DNV E0 expects simple bridge restart of propulsion [1]. Viking Sky shows that untrained recovery is slow [66].

**Confirmation table**
Applies E1-E7. Who can confirm, and what is inadmissible.

| Action class | 14 aboard | 6 aboard | 0 aboard |
|---|---|---|---|
| Automatic shed / throttle (declared order) | Automatic; engineer informed | Automatic; bridge informed | Automatic; ROC informed |
| Restore shed load | Engineer confirms | Bridge confirms | Pre-approved sequence; ROC confirms deviations |
| Flight-deck recovery | Full flying stations | Flying stations only if no other crewed evolution | Only with automated landing, sensor deck-clear, fixed firefighting, ROC clearance |
| Boat / UUV recovery | Crewed | Crewed, serialised | Automated LARS only |
| Winch below FS 5.0 | Competent operator | Competent operator, no concurrent evolution | Outside RVSS; refuse unless remote operation is approved |
| Emission silence | Master orders and logs | Master orders and logs | Pre-scheduled with autonomous fallback |
| At-sea install | Crewed lift team | Likely infeasible (inference) | Infeasible |

**Candidate crew rules**
- R-E8-1 "Every action carries the crew level that can confirm it. If nobody can, it is either automatic by rule or inadmissible."
- R-E8-2 "At 6 aboard, only one crewed deck evolution at a time." (inference)
- R-E8-3 "At 0 aboard, one ROC holds authority; loss of the link triggers the declared fallback." [60][61]
- R-E8-4 "At minimal manning, crewed evolutions longer than one watch need a declared relief before admission." [63] (inference)

### E9 Fire, flooding and damage control: why some loads are never shed

**What the rules require**
- The emergency source and switchboard must sit where a fire or casualty in the main machinery spaces cannot disable them [4].
- Main and emergency systems recover independently [1].
- Services on the emergency source include emergency lighting, navigation lights, radio, fire detection, the emergency fire pump, steering and watertight doors. The list is only partly verified. Durations often cited (18 h cargo, 36 h passenger; steering 10 or 30 min; watertight doors 30 min) are unconfirmed.

**Helge Ingstad (NSIA 2021/05) [67][68]**
- After grounding, water reached the gear room through the hollow propeller shafts, then the engine rooms through bulkhead stuffing boxes.
- Doors and hatches were not closed at evacuation.
- The on-board carpet plot was poorly suited to judging survivability.
- Better prioritisation could have helped save the ship. NSIA made 28 recommendations.

**Candidate crew rules**
- R-E9-1 "Loads on the emergency switchboard or tagged safety-critical are outside the shed list: fire, bilge, steering, navigation lights, distress comms, watertight-door power." [1][4]
- R-E9-2 "A fire or flooding alarm in a zone suspends admissions that use that zone's power, cooling or deck, and frees reserve for damage-control pumps." (inference)
- R-E9-3 "The governor only throttles or sheds guests. It never commands closures or damage-control equipment." (scope)
- R-E9-4 "Show reserves per zone and per survivability barrier, not only a load list." [67] (inference)

### E10 Cascades from machinery protection and automation
See Section 4. Common pattern: a protective trip that is correct for one machine fires on every redundant machine at once, because they all share one condition:
- Viking Sky: sump level under ship motion;
- Dali: power to signal wiring, cooling-water pressure, fuel pressure;
- Ingstad: watertight boundaries.

**Candidate crew rules**
- R-E10-1 "If all redundant units depend on one condition (one fuel pump, one lube level, one cooling loop), report it as the binding constraint and refuse optional load growth." [64][66]
- R-E10-2 "A configuration mode that disables automatic recovery (breakers in manual) is a degraded state the governor must display and plan around." [64][65]
- R-E10-3 "Long-lived derates declared by engineering (e.g. a speed limit from a gearbox defect) are first-class constraints with an owner and an expiry." [69]

---

## 3. Prior art for mission-priority power management

**Conventional class PMS** [1][8]
- How it prioritises: fixed priority tiers (preferential-trip groups), heavy-consumer blocking, drive phase-back, standby start, blackout restart.
- What it explains: an alarm list and which breaker opened.
- What it does not explain: why a given load was chosen, or any resource other than kW/kVA.

**US Navy Quality of Service, Doerry & Clayton (IEEE ESTS 2005)** [11][12][13]
- How it prioritises:
  - loads are classed by tolerable interruption: uninterruptible (cannot take 2 s; rides through 10 ms), short-term interrupt (2 s to 5 min), long-term interrupt (more than 5 min);
  - QoS shedding drops long-term-interrupt loads first;
  - if not restored within 5 min, mission-priority shedding protects higher-priority loads at the expense of lower ones;
  - the "exempt" category is used only for generator sizing.
- What it explains: why a load class was shed.
- What it does not explain: per-decision reasons or non-electrical resources.

**Next Generation Integrated Power System (NGIPS), electric ship architectures (Doerry)** [16][17]
- How it prioritises: zonal and integrated power architectures that underpin QoS.
- What it explains: design-level only.

**NPES Technology Development Roadmap 2019** [14][15][79]
- How it prioritises: SWaP margin, energy storage and the "energy magazine" for pulsed loads.
- What it explains: a strategy, not runtime logic.

**ESRDC thermal-electrical co-simulation (DTMS)** [18]
- How it prioritises: chiller-based load management with optimal chiller control.
- What it explains: a simulation, not operational explanations.

**IEEE ESTS research**
- Papari et al. 2019: distributed (ADMM consensus) load scheduling that identifies the lowest-priority loads to drop [19].
- Cramer et al. 2019: mission-based optimal control where loads scale rather than switch on/off [20].
- Sabah & Cramer 2023: energy magazines, solved as an MDP [21].
- What they explain: optimisers produce a schedule, not a one-sentence binding constraint.

**IEEE 1826 open zonal interfaces** [22]
- What it provides: interface categories and plug-and-play conformance, not prioritisation.

**DNV OR notation (2021)** [1]
- What it provides: class credit for operational reliability, blackout prevention and recovery; explanation is not covered.

**How our governor differs**
- One owner for many resources: kW, heat rejection, deck spots, mast sectors, mass/stability, links, compute, response time, and acoustic quiet as a resource. Existing work covers kW, plus heat in ESRDC.
- Admission control before the event (reserve-holding), not only shedding after it.
- Deterministic, auditable rules compiled from crew rules like those above, instead of optimisers. Every decision names its binding constraint in one sentence.
- Throttle before shed, following Cramer's scalable loads [20]. Shedding stages follow QoS timing (2 s / 45 s / 5 min) [11][1].
- Safety-critical loads are structurally outside its authority (E9). Crew level changes who confirms (E8).

---

## 4. Accident case studies

| Case | Year | What failed | Role of sensors/automation | Lesson for the governor | Source |
|---|---|---|---|---|---|
| Viking Sky, Hustadvika (NSIA 2024/05) | 2019 | Low lube-oil sump levels plus heavy pitching and rolling exposed the suction; all running gensets shut down on low lube-oil pressure; blackout; within about a ship's length of grounding; 39 min to restore | Remote level monitoring was inaccurate (sensor offsets, erroneous 3D model); dynamic-inclination limits never calculated; alarm design reduced effectiveness; sailed without required SRtP redundancy (one of four gensets unavailable). Recommendation 2024/16T asks Fincantieri to ensure accurate level monitoring on future ships | Protective trips on a shared condition are correlated; sensor validity is part of the budget; refuse optional load growth when N-1 is gone; weather-dependent limits must be computed, not assumed | [66] |
| Dali, Francis Scott Key Bridge (NTSB MIR-25-40) | 2024 | A loose signal wire at a terminal block (wire-label banding) caused the blackout; loss of propulsion and steering near the bridge; second blackout from low fuel pressure | HV breakers in manual, not automatic (press: initial blackout 58 s vs ~10 s [65]); flushing pump used for fuel supply; main engine set to shut down on low cooling-water pressure; emergency-generator radiator dampers can delay its auto start | A mode setting can silently remove automatic recovery; show it as a degraded state; machinery self-protection can remove propulsion when it is most needed; small wiring faults cascade | [64][65] |
| Helge Ingstad (NSIA 2021/05) | 2018 | Collision damage, then progressive flooding via hollow shafts and bulkhead stuffing boxes; openings not closed at evacuation; sank | Damage-stability tools (carpet plot) poorly suited; damage-control prioritisation and training deficient; 28 recommendations | Safety-critical domain must sit outside guest arbitration; present survivability per zone; closure state is a hard precondition | [67][68] |
| LCS Freedom variant, combining gear | 2015-2022 | Class-wide combining-gear design defect (Navy, Jan 2021); earlier at-sea breakdowns | In-service ships limited use of the combining gear, restricting speed to about 10 kn pending a fix; fix cost split 50-50 (2022). A GAO product on this was not located | Long-lived engineering derates must be modelled as constraints with owner and expiry | [69] |
| Tombarra (MAIB) | 2011 | Fast rescue boat fall wire parted during recovery in a drill | Proximity (limit) switch failed to stop the winch; switch not fitted per manufacturer | A limit or interlock is a safety function; verify before every evolution; failure means stop | [70] |
| RRS Sir David Attenborough (MAIB 2023) | 2023 | Lifeboat lowered prematurely during launch | Interlock had not reset after a previous test, so the brake released out of sequence; required davit checks not done since installation | Post-test reset is part of readiness; the governor must check interlock state, not assume it | [71] |
| Marine Explorer (MAIB 2/2002) | 2001 | Lifeboat winch ran away and struck the quay; 2 injured | Hand brake assembled incorrectly; no risk assessment | Maintenance state is an admission input for deck machinery | [72] |
| Dea Fighter (MAIB 39/2000) | 1999 | Repeated FRC davit wire failures | Undersized top sheave fitted | Configuration changes to handling gear re-qualify the system (RVSS: refresh operator qualification too) | [73][39] |

---

## 5. Public diagrams worth using

The URLs below point to documents. Figure numbers are given only where the text was read; otherwise the figure content is "unconfirmed". No image files were downloaded.

| Id | What it shows | Source document | Direct URL | Licence/release status | Reusable? |
|---|---|---|---|---|---|
| D1 | Notional AC zonal distribution (Fig. 1) and IPS MVAC one-line (Fig. 2) | Doerry & Clayton, QoS, ESTS 2005 [11] | http://doerry.org/norbert/papers/pid93966.pdf | Conference paper; IEEE copyright likely | link-only |
| D2 | Electric-ship power and energy architecture one-lines (slides) | Doerry 2017, marked Distro A [17] | http://www.doerry.org/norbert/papers/20170609Electric%20Ship%20Power%20and%20Energy%20System%20Architectures%20Part%20I%20DIstro%20A.pdf | Distribution A (approved for public release); copyright unconfirmed | link-only (verify) |
| D3 | Stepwise blackout-risk approach (Fig. 1), layers of requirements (Fig. 2), closed-bus failure modes (Table 1), blackout prevention/recovery test tables (Apps E-F) | DNV guidance paper [1] | https://maritimecyprus.com/wp-content/uploads/2022/04/DNV-MANAGING-THE-RISKS-of-BLACKOUT.pdf | DNV copyright; third-party host | link-only |
| D4 | Dali electrical and breaker arrangement (figure content unconfirmed) | NTSB MIR-25-40 [64] | https://www.ntsb.gov/investigations/AccidentReports/Reports/MIR2540.pdf | US federal work (normally public domain) | yes, once the figure is confirmed and credited |
| D5 | Viking Sky lube-oil sump and suction geometry (unconfirmed) | NSIA 2024/05 [66] | https://nsia.no/Marine/Published-reports/2024-05 | Government report; reuse terms unconfirmed | link-only |
| D6 | Helge Ingstad flooding progression (unconfirmed) | NSIA 2021/05 [67] | https://nsia.no/Marine/Published-reports/2021-05-eng | Government report; reuse terms unconfirmed | link-only |
| D7 | Helideck marking and helideck-motion/met diagrams (chapter numbers for markings unconfirmed) | UK CAA CAP 437 [29] | https://www.caa.co.uk/cap437 | Crown copyright (CAA) | link-only |
| D8 | Shipboard helicopter-operations checklist | ICS [31] | https://www.ics-shipping.org/publications/resources/Shipboard%20safety%20checklist%20for%20helicopter%20operations.pdf | ICS copyright | link-only |
| D9 | Stern-ramp motion and sill-depth criteria (figures unconfirmed) | SINTEF/MARINTEK 2003 [42] | https://www.sintef.no/globalassets/upload/marintek/pdf-filer/papers-articles/marine-vehicles/stern-boat-deployment.pdf | Author copyright | link-only |
| D10 | RHIB LARS arrangement | L3Harris Calzoni datasheet [46] | https://www.l3harris.com/sites/default/files/2020-10/ims-maritime-datasheet-calzoni-LARS.pdf | Vendor copyright | link-only |
| D11 | FS-tier tables A.8.1-A.8.4; overboard handling system appendix | UNOLS RVSS 11th ed. [39] | https://www.unols.org/sites/default/files/2026-06/RVSS_11_Master_Updated_June2026.pdf | Public; licence not stated | link-only (re-express as data) |
| D12 | Thermal-electrical co-simulation architecture (unconfirmed) | ESRDC history doc [18] | https://utw10356.utweb.utexas.edu/sites/default/files/ESRDC%20history%20co-simulation.pdf | University copyright | link-only |
| D13 | StanFlex module photos and layout | Wikipedia [57] | https://en.wikipedia.org/wiki/StanFlex | Commons licences vary per image | link-only until each image is checked |
| D14 | NPES roadmap figures (power-system evolution, energy magazine; unconfirmed) | NAVSEA NPES TDR 2019 [14] | https://www.navsea.navy.mil/Resources/NPES-Tech-Development-Roadmap (PDF link unconfirmed; file name per [79]) | Distribution A | yes (US government work; verify figure credits) |
| D15 | Rescue-boat davit and fall-wire arrangement | MAIB Tombarra [70] | https://assets.publishing.service.gov.uk/media/547c6f9de5274a429000003b/TombarraPartAReport.pdf | Crown copyright; MAIB reports normally under OGL v3 (verify) | likely yes (verify OGL) |
| D16 | USBL transceiver receive-cone concept | Sonardyne GDT datasheet [51] | https://www.sonardyne.com/wp-content/uploads/2021/07/GDT-USBL-Tranceiver.pdf | Vendor copyright | link-only |

**Gaps:** no public chilled-water schematic was located, and no mission-module interface drawing beyond StanFlex. LCS mission-package interface documents were not searched.

---

## 6. Sources

1. https://maritimecyprus.com/wp-content/uploads/2022/04/DNV-MANAGING-THE-RISKS-of-BLACKOUT.pdf : DNV guidance "Managing the risks of blackout". Main-class blackout prevention and recovery rules, 45 s standby, stored energy, enhanced tests.
2. https://nippon.zaidan.info/seikabutsu/1998/00225/contents/100.htm : SOLAS II-1/41.5 text as amended by MSC.57(67). Load shedding against sustained overload; supply maintained on loss of one generator.
3. https://legislation.gov.uk/uksi/1998/2514/regulation/54/1998-11-12/data.xht : UK SI 1998/2514 reg. 54. National transposition of the same load-shedding wording.
4. https://www.deutsche-flagge.de/de/redaktion/dokumente/interpretationen/solas/ii-1/msc-circ-736-interpretations-of-vague-expressions-in-solas-chapter-ii1_treeview_12666.pdf : MSC/Circ.736. Regs 42 (passenger) and 43 (cargo) emergency source; location requirement.
5. https://www.dco.uscg.mil/Portals/9/DCO%20Documents/5p/5ps/Alternate%20Compliance%20Program/DNVGL_Supplement_8-1-16.pdf : USCG supplement to DNV GL rules. Passenger-vessel emergency transfer within 45 s.
6. https://www.norclub.com/web-api/files/1krj06gt/production/e909e34159a508ab1704e94a81b0222676fc5b20.pdf : Norclub casualty circular reproducing IACS UR M31 (45 s standby, load shedding). Read only via search summary.
7. https://www.dnv.com/news/2019/testing-of-standby-generators-without-class-attendance-162892/ : DNV annual test of standby auto start and connection.
8. https://www.marineinsight.com/marine-safety/preferential-trips-on-ship-construction-and-working/ : Preferential-trip purpose and example staging (secondary).
9. https://samkmoodle.samk.fi/mod/page/view.php?id=22185 : DNV-based course text. Shedding threshold below 100 % of rated current (secondary).
10. https://rules.dnv.com/docs/pdf/dnvpm/rulesship/2003-01/ts603.pdf : 2003 DNV rules. Standby start on voltage or frequency drop (historical; not used in text).
11. http://doerry.org/norbert/papers/pid93966.pdf : Doerry & Clayton, "Shipboard Electrical Power Quality of Service". QoS categories; 10 ms / 2 s / 5 min; mission-priority shedding.
12. http://doerry.org/norbert/papers/070309doerryASNE07.pdf : Doerry, survivability and QoS (ASNE 2007).
13. https://apps.dtic.mil/sti/pdfs/ADA544434.pdf : Implementing Quality of Service in shipboard power system design (DTIC).
14. https://www.navsea.navy.mil/Resources/NPES-Tech-Development-Roadmap : NAVSEA NPES Technology Development Roadmap page. Also the press release https://www.navsea.navy.mil/Media/News/Article/1888251/navsea-releases-naval-power-and-energy-systems-technology-development-roadmap/
15. https://news.usni.org/2019/06/26/u-s-naval-power-and-energy-systems-technology-development-roadmap : USNI copy of the NPES roadmap.
16. http://www.doerry.org/norbert/papers/090106usna-ngips-final.pdf : Doerry, Next Generation Integrated Power Systems (not read in detail).
17. http://www.doerry.org/norbert/papers/20170609Electric%20Ship%20Power%20and%20Energy%20System%20Architectures%20Part%20I%20DIstro%20A.pdf : Doerry, electric-ship architectures (Distro A; not read in detail).
18. https://utw10356.utweb.utexas.edu/sites/default/files/ESRDC%20history%20co-simulation.pdf : ESRDC co-simulation history. DDG-51 has five 200-ton chillers; DTMS chiller-based load management.
19. https://impact.ornl.gov/en/publications/enhancement-of-energy-management-in-the-shipboard-power-systems-b/ : Papari et al., ESTS 2019. Distributed load shedding.
20. https://scholars.uky.edu/en/publications/mission-based-optimal-control-for-the-evaluation-of-power-and-ene/ : Cramer et al., ESTS 2019. Mission-based optimal control; scalable loads.
21. https://scholars.uky.edu/en/publications/optimal-control-based-evaluation-of-shipboard-power-systems-with-/ : Sabah & Cramer, ESTS 2023. Energy magazines.
22. https://standards.globalspec.com/std/14345116/ieee-1826 : IEEE 1826 scope (open interfaces above 100 kW; 2020 supersedes 2012).
23. https://apps.dtic.mil/sti/pdfs/ADA568950.pdf : NAVSEA T9300-AF-PRO-020 electrical design practice. Defines service life allowance and margin (values not seen).
24. https://sawe.org/product/paper-2356 and https://www.sawe.org/product/paper-3455 : SAWE weight/KG margin history; submarine service-life margin 2-3.25 %.
25. https://library.imarest.org/record/11168/files/INEC_2024_paper_12.pdf : INEC 2024. Managing space, weight, power and cooling margins.
26. https://www.navysbir.com/n22_1/N221-052.htm : Navy SBIR N221-052. 44 F chilled water vs 67 F electronics cooling.
27. https://www2.lce.com/pdfs/Ensuring%20Functional%20Air-Conditioning%20Units%20Helps%20to%20Keep%20Destroyer%20at%20Sea.pdf : LCE destroyer case. Chiller deadheading; cross-connect.
28. https://wartsila.com/encyclopedia/term/ambient-conditions : Typical design basis of 32 C seawater and 45 C engine room.
29. https://www.caa.co.uk/cap437 : UK CAA CAP 437, 9th edition and amendment 9.1. Helideck motion (Ch. 6) and met (App. E).
30. https://www.kongsberg.com/support-and-services/ocean-space/services/qa-hms-rev-9c/ : Helideck monitoring Rev 9C; lower night limits.
31. https://www.ics-shipping.org/publications/resources/Shipboard%20safety%20checklist%20for%20helicopter%20operations.pdf : ICS shipboard helicopter checklist (guide page https://ics-shipping.org/?p=10422).
32. https://rightship.com/insights/helicopter-operations-high-potential-near-miss-incidents : RightShip near-miss lessons on loose objects and fire hoses.
33. https://chirp.co.uk/app/uploads/2026/03/CHIRP-Card-Helicopter-Operations-2.pdf : CHIRP card. HLO, aviation fire team, helideck assistants.
34. https://schiebel.net/wp-content/uploads/2015/07/2007-11-12_CAMCOPTER_S-100_SUCCESSFULLY_COMPLETES_SHIPBOARD_TRIALS.pdf : Indian Navy OPV trials. 8-16 kn, wind up to 20 kn, approach waypoint.
35. https://schiebel.net/wp-content/uploads/2015/07/2008-04_CAMCOPTER_S-100_%E2%80%93_CONTINUED_SUCCESS_IN_SHIPBOARD_TRIALS.pdf : Pakistan Navy trials. 10-13 kn, wind up to 15 kn.
36. https://shephardmedia.com/news/uv-online/camcopter-s-100-completes-french-navy-opv-ladroit : French OPV L'Adroit; 89 harpoon landings.
37. https://oldain.ainonline.com/aviation-news/general-aviation/2019-10-07/unmanned-camcopter-completes-sar-sea-based-trials : Norwegian Coast Guard SAR trials; harpoon to SS5 (vendor claim).
38. https://saemobilus.sae.org/papers/vtol-uas-auto-recovery-using-a-tested-long-term-motion-prediction-method-define-deck-sm_avtol_2025-5315 : Deck-motion prediction for VTOL UAS recovery (abstract).
39. https://www.unols.org/sites/default/files/2026-06/RVSS_11_Master_Updated_June2026.pdf : UNOLS RVSS 11th ed. App. A FS tiers, App. B, stability, 8.4.7, Ch. 19 UAS.
40. https://www.unols.org/sites/default/files/UNOLS_UAS_Policy_July2016.pdf : UNOLS UAS policy (referenced from RVSS Ch. 19).
41. https://www.unols.org/sites/default/files/201611rvtap11.pdf : RVTEC Appendix A/B presentation. OHS design principle; 46 CFR 189.35.
42. https://www.sintef.no/globalassets/upload/marintek/pdf-filer/papers-articles/marine-vehicles/stern-boat-deployment.pdf : SINTEF 2003. Stern-ramp motion and availability criteria.
43. https://www.navalengineers.org/Symposia/Past-Symposia/Launch-and-Recovery-2016/Program/Roberts : ASNE 2016. USCG stern launch and recovery trials.
44. https://doaj.org/article/4eb7ec75a12240cb8d7fb74e67c6639c : IJNAOE 2012. RHIB stern-ramp recovery; wake and waterjet effects.
45. https://www.ust-media.com/ust-magazine/UST007/45/ : Industry interview. Stern-ramp risk above SS3; 2 m and 10 degree relative motion.
46. https://www.l3harris.com/sites/default/files/2020-10/ims-maritime-datasheet-calzoni-LARS.pdf : Calzoni LARS. Recovery at up to 6 kn relative speed.
47. https://www.navysbir.com/11_2/193.htm and https://www.navysbir.com/n11_2/N112-135.htm : Navy stern-launch SBIR topics. 10 kn relative recovery (which page holds it is unconfirmed).
48. https://epic2-clone.awi.de/35287/2/Poster-ROBEX-Jonas_Hagemann.pdf : AWI small-RV AUV launch system, safe to SS4.
49. https://www.marum.de/en/AUV-Operations.html : MARUM AUV operations. Crane or A-frame; release across the heading.
50. https://oceanexplorer.noaa.gov/explorations/08auvfest/logs/may17/may17.html : NOAA AUVfest log. Operations stopped as seas reached 4-5 ft.
51. https://www.sonardyne.com/wp-content/uploads/2021/07/GDT-USBL-Tranceiver.pdf : Sonardyne USBL. Narrow cone rejects thruster noise.
52. https://irso.info/wp-content/uploads/14_IRSO-2025-USBL-System-Optimisation-Final-rev-1-Duncan-Rigg.pdf : IRSO 2025. USBL self-noise, pole depth, noise survey.
53. https://tore.tuhh.de/handle/11420/13251 : TUHH. Acoustic modem against ship and AUV noise.
54. https://wwwcdn.imo.org/localresources/en/OurWork/Safety/Documents/AIS/Resolution%20A.1106(29).pdf : IMO A.1106(29) AIS guidelines, para. 22.
55. https://iumi.com/news/iumi-eye-newsletter-december-2019/regulatory-framework-for-ais-going-dark-and-switching-off : IUMI summary of AIS switch-off rules.
56. https://www.bimco.org/contractual-affairs/bimco-clauses/current-clauses/ais_switch_off_clause_2021 : BIMCO AIS Switch Off Clause 2021.
57. https://en.wikipedia.org/wiki/StanFlex : StanFlex dimensions, interfaces and slots.
58. https://www.dnv.com/maritime/autonomous-remotely-operated-ships/aros-class-notation/ : DNV AROS functions, modes, control location.
59. https://www.dnv.com/maritime/autonomous-remotely-operated-ships/class-guideline : DNV-CG-0264 page; edition history at https://standards.globalspec.com/std/13057765/dnvgl-cg-0264
60. https://www.imo.org/en/mediacentre/pressbriefings/pages/imo-adopts-mass-code.aspx : IMO MASS Code adoption, status and roadmap.
61. https://www.etp-logistics.eu/wp-content/uploads/2026/02/3_Updates-on-the-developments-of-the-IMO-MASS-Code.-Jerome-Faivre-BV-220226.pdf : BV presentation. Single responsible ROC (draft).
62. https://apps.dtic.mil/sti/html/tr/ADA604356/index.html : GAO-14-447 on the USS Freedom deployment; minimal-crew concept.
63. https://gcaptain.com/leaked-us-navy-report-slams-contested-lcs-progra/ : Navy internal review. LCS fatigue by day 3 with about 40 crew.
64. https://www.ntsb.gov/investigations/Pages/DCA24MM031.aspx : NTSB Dali probable cause and recommendations M-25-16 to M-25-29. Report: https://www.ntsb.gov/investigations/AccidentReports/Reports/MIR2540.pdf
65. https://local21news.com/news/nation-world/ntsp-dali-key-bridge-collaspe-loose-wire-final-report : Press on the NTSB board meeting. Breakers in manual; 58 s vs 10 s.
66. https://nsia.no/Marine/Published-reports/2024-05 : NSIA Viking Sky report 2024/05. Causes, 39 min recovery, recommendations including 2024/16T to Fincantieri.
67. https://nsia.no/Marine/Published-reports/2021-05-eng : NSIA Helge Ingstad part 2 (2021/05). Flooding, damage control, 28 recommendations.
68. https://www.marinelog.com/shipping/safety-and-security/investigators-safety-critical-concerns-with-f100-frigate-design/ : Preliminary findings on shafts and stuffing boxes.
69. https://news.usni.org/?p=82847 and https://news.usni.org/2022/08/15/navy-moving-ahead-on-combining-gear-fix-on-freedom-littoral-combat-ships-marked-for-decommissioning : LCS combining-gear defect, speed limit and fix.
70. https://assets.publishing.service.gov.uk/media/547c6f9de5274a429000003b/TombarraPartAReport.pdf : MAIB Tombarra. Limit switch failure; fall wire parted (also SB 2/11: https://assets.publishing.service.gov.uk/media/547c6f9fed915d4c0d00003f/SB2-11.pdf).
71. https://assets.publishing.service.gov.uk/media/6542426a9e05fd0014be7b39/2023-6-RRSSirDavidAttenborough-Report-Annexes.pdf : MAIB RRS Sir David Attenborough. Interlock not reset.
72. https://www.gov.uk/maib-reports/failure-of-lifeboat-winch-brake-on-research-vessel-marine-explorer-in-harwich-england-with-2-people-injured : MAIB Marine Explorer. Brake mis-assembly.
73. https://www.gov.uk/maib-reports/lifting-wire-failures-on-fast-rescue-craft-davit-of-stand-by-vessel-dea-fighter-first-at-aberdeen-harbour-scotland-with-1-person-injured-and-then-at-buchan-alpha-offshore-installation-with-2-people-injured : MAIB Dea Fighter. Undersized sheave.
74. https://www.bsee.gov/sites/bsee.gov/files/2026-07/MC%20759%20Beacon%20Growtco%20Operating%2020-Feb-26.pdf : BSEE. ROV umbilical jumped the A-frame sheave.
75. https://dco.uscg.mil/Portals/9/DCO%20Documents/5p/CG-5PC/INV/Alerts/USCGSA_1024.pdf : USCG Safety Alert 10-24. Swift restoration after blackout; training.
76. https://ia600608.us.archive.org/35/items/NEETSModules/NEETS%20Module%2019%20-%20The%20Technician%2527s%20Handbook.pdf : NEETS Module 19 (Distribution A example).
77. https://www.scribd.com/doc/191442486/ch320 : Unofficial copy of NSTM 320, reported as Distribution A (official source not found).
78. https://www.dco.uscg.mil/Portals/9/MSC/PRG/PRG.E2-08.2016.06.14.Emergency_Generators_and_Switchboards.pdf : USCG plan-review guide for emergency generators (returned HTTP 403; not read).
79. https://seapowermagazine.org/navsea-releases-naval-power-and-energy-systems-roadmap/?print=pdf : Seapower on the NPES roadmap release; Distribution A PDF file name.
80. https://www.mynavyhr.navy.mil/Portals/55/Reference/NEOCS/Vol1/EM_occs_CH_105_508.pdf : Navy Electrician's Mate occupational standards (scope of the rate; no shedding procedure).
