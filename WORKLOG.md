# Team worklog

Shared, append-only log for the people on this team and the AI agents working for them.
Read it before you start. Add to it at least every 30 minutes while you work.
Deadline: **Sun 2026-10-18 10:00 PDT**.

## How to use this file (people and agents)

1. **Pull first.** Read the Conflicts and Deferrals tables and the newest Entries before starting.
2. **Append only.** Add rows at the bottom of a table and entries at the bottom of the file.
   Never edit or delete someone else's text; correct it with a new row or entry.
3. **Say who.** Every row and entry names the person and, for agents, the model, e.g.
   "Claude Opus 5.5 on behalf of Logan Walker (GhostWalka)".
4. **Pacific time** (PDT), written like `Sat 14:05`.
5. **Commit the worklog on its own**, with a message starting `worklog:`, and push straight away.
6. **Merges:** `.gitattributes` sets `merge=union` for this file, so concurrent appends merge
   without conflicts in local git. Check the merged file reads correctly.
7. **Ownership:** hardware decisions and granular code or design decisions belong to whoever owns
   that work. If your plan conflicts with a teammate's, follow theirs, add a row to Deferrals,
   and tell your person.

## Who's who

| Person | GitHub | Agents |
|---|---|---|
| Logan Walker | GhostWalka | Claude (Anthropic) in Claude Code desktop: Fable 5.1 until Fri 20:27 PDT, then Opus 5.5 |
| Siddharth Chawla | sidd91 | to be filled in by Siddharth |

## Decisions

| When (PDT) | Decision | Decided by | Logged by |
|---|---|---|---|
| Fri 20:07 | Runtime compute is local only; every AI model is declared; we finish with a live demo and runnable code | Logan | Claude for Logan |
| Fri 20:07 | Beyond the brief: swappable mission priority sets, live priority overrides, camera-based virtual sensors, plain-language rules through an approved grammar with no LLM-written code | Logan | Claude for Logan |
| Fri 20:15 | Only open-source third-party code or our own; every dependency and model weight declared with its licence | Logan | Claude for Logan |
| Fri 20:15 | 3D ship view for the demo with three.js, kept as a toggle beside the scored 2D screen because the brief says 3D earns nothing | Logan; framing by Claude | Claude for Logan |
| Fri 20:20 | Claude is approved for use at the event | Logan | Claude for Logan |
| Fri 20:20 | Emphasise edge compute across several devices, wired and Wi-Fi paths that can each fail, and cameras that are not guaranteed | Logan | Claude for Logan |
| Fri 20:35 | Work on Pacific time; deadline Sun 10:00 PDT | Logan | Claude for Logan |
| Fri 20:38 | Logan's commits use GhostWalka with the GitHub noreply email; work so far is on branch `docs/game-plan-and-research` | Logan | Claude for Logan |
| Fri 20:44 | Excluded as China-derived under the brief: RF-DETR (built on Baidu's LW-DETR), OpenCV `wechat_qrcode` (Tencent), DeepShip, XJTU-SY and HUST datasets. Excluded as not open: Ultralytics YOLO (AGPL), Llama and Gemma licences | Claude, applying the brief and Logan's open-source rule | Claude for Logan |
| Fri 20:55 | Crew is a co-orchestrator at times and a resource at others; people are a necessary resource for components that cannot be controlled remotely or automatically | Logan | Claude for Logan |
| Fri 20:55 | PROPOSED: thesis "one ledger, one manifest language" with four roles: host commitment, guest, supply, crew | Proposed by Claude; awaiting Logan | Claude for Logan |
| Fri 20:55 | PROPOSED: load shedding as a ladder precomputed every tick, priced by the priority file, rechecking power and cooling after each step | Proposed by Claude; awaiting Logan | Claude for Logan |
| Fri 20:55 | PROPOSED stack: Python 3.12 via uv, FastAPI and websockets, vanilla JS, vendored three.js, no Node or React; detector torchvision SSDlite | Proposed by Claude; team may override | Claude for Logan |
| Fri 20:58 | Qualcomm edge hardware arrives Sat about 10:00 PDT. Until then node B runs as a second process on the laptop. Using its NPU still depends on the organizers accepting Qualcomm's proprietary runtime | Logan (arrival); Claude (interim plan) | Claude for Logan |

## Conflicts and risks to watch

| Opened (PDT) | Issue | Status | Logged by |
|---|---|---|---|
| Fri 20:15 | The brief puts natural-language interfaces out of scope; our rule editor must be presented as a controlled grammar with an approval step | Mitigated by framing; watch the demo script | Claude for Logan |
| Fri 20:15 | 3D view versus the brief's "3D earns nothing" | Logan's call; demo layer only, second in the cut order | Claude for Logan |
| Fri 20:34 | The brief bans proprietary or export-controlled information on real vessels | Managed: fleet research uses public sources only and informs scope, never values in code | Claude for Logan |
| Fri 20:45 | The Qualcomm NPU needs the proprietary QAIRT SDK and a cloud compile, against the open-source and local-only rules | Open: ask the organizers; default to CPU | Claude for Logan |
| Fri 20:46 | Open-Meteo's free tier is non-commercial | Open: ask the organizers; fallback is NOAA OISST and Argo | Claude for Logan |
| Fri 20:47 | The plan and research are on branch `docs/game-plan-and-research`; main has none of it yet | Open: needs a pull request, Siddharth's call as repo owner | Claude for Logan |
| Fri 20:55 | Work split between Logan and Siddharth not agreed; risk of building the core twice | Open | Claude for Logan |
| Fri 20:55 | The brief's peak-power allowance is ambiguous right after a generator trip | Our reading will be recorded as an assumption | Claude for Logan |

## Deferrals

| When (PDT) | Deferred to | On | Our prior position | Logged by |
|---|---|---|---|---|
| none yet | | | | |

## Entries

Template:

```
### <Day HH:MM> PDT · <model or person> on behalf of <Person (GitHub)>
Work done:
Decisions:
Conflicts:
Deferrals:
Next:
```

### Fri 20:07–20:53 PDT · Claude (Fable 5.1, then Opus 5.5) on behalf of Logan Walker (GhostWalka)

All work in this entry was done by Claude on Logan's behalf.

Work done:
- Read the challenge brief and slide deck; wrote `GAMEPLAN.md` with scoring criteria,
  architecture, schedule, demo script and cut order.
- Got repo access working for GhostWalka, cloned the repo to Logan's laptop, created the branch
  and pushed commits `8271229` and `06d54b3`.
- Ran seven research agents: camera placement, four sensor domains, the Fincantieri fleet since
  2000, and shipboard event procedures. Six have landed in `research/`; the fleet log is running.
- Started `docs/SOFTWARE_LOG.md`, tracking every tool, model, dataset and licence.
- Checked the research: all 54 generator specs parse after fixing two. The Viking Sky report's
  recommendations addressed to Fincantieri, 2024/06T and 2024/16T, are confirmed on the NSIA site.

Decisions, conflicts: see the tables above. Deferrals: none.

### Fri 20:53 PDT · Data modeling picked up from the research · Claude Opus 5.5 on behalf of Logan Walker (GhostWalka)

All work in this entry was done by Claude on Logan's behalf. These models come from the research
files and will be built into the simulator. Every number marked assumed goes in the Physical
Account. Full detail and generator specs: `research/SENSOR_CATALOG.md` and `research/sensors/`.

Power (`research/sensors/platform_power_thermal.md`, `research/vessels/event_protocols_log.md`):
- The budget closes against the brief. Two 450 kW gensets at an assumed 0.9 load limit give
  810 kW. Hotel load 400 kW plus an assumed 55 kW of ship auxiliaries leaves the brief's 200 kW
  guest cap with 155 kW spare. With one genset down, the PMS drops an assumed 150 kW of
  non-essential hotel load, leaving the brief's 100 kW for guests.
- A generator trip counts as confirmed only when 2 of 3 signals agree: relay flag, output near
  zero, frequency dip. While generator state is uncertain, admit as if one is down.
- Protective trips that share a condition are correlated. Viking Sky lost every running genset to
  one lube-oil condition. The governor reports "all redundant units depend on one condition" as a
  binding constraint.
- Published timings anchor ours: 45 s for standby power back on the main switchboard, and
  preferential trips staged at roughly 5, 10 and 15 s in training material. Our first shed within
  5 s and full sequence within 60 s fit inside them.

Cooling:
- Guest heat budget falls linearly from 160 kW at 12 °C seawater to 120 kW at 30 °C, ×0.6 when
  degraded. At Scenario B's 24 °C it is about 133 kW.
- The +30 kW for 60 s inertia is modelled as loop heat capacity, about 0.6 MJ/K with a 3 K allowed
  rise, refilling over 10 minutes.

Ship motion and environment (`research/sensors/navigation_environment.md`):
- Sea state maps to wave height by WMO bands. Waves come from a JONSWAP spectrum driven by hourly
  Open-Meteo data. Roll, pitch and heave come from a closed-form model at 1 Hz; roll period is
  about 9.7 s for an assumed 65 × 12.5 m hull with 3.6 m draft and 1.2 m GM.
- Sound speed uses the Mackenzie formula. Layering uses the mixed-layer test, 0.2 °C below the
  10 m temperature, plus the steepest sound-speed gradient. A Sicily Argo profile shows a 10.5 m
  mixed layer, so the acoustic link is unreliable below about 10 m.
- Demo site: Strait of Sicily on the Mazara del Vallo to Kelibia cable corridor. Stress case: off
  Florida, where August averaged 30.4 °C.

Links, network and compute (`research/sensors/comms_network_compute.md`):
- Link models: Wi-Fi loses about 20 dB per closed watertight door; GEO SATCOM rain fade of
  3–5 dB/s and heading-driven blockage; LEO latency spikes every 15 s; acoustic loss with Thorp
  absorption plus noise, layering and manoeuvring penalties. Magnitudes assumed until calibrated.
- Failover: heartbeat every 100 ms per path; wired marked down after 3 misses, Wi-Fi after 5; peer
  dead after 1 s silent on all paths; control traffic sent over both paths with duplicates
  dropped; epoch fencing plus a witness vote; guests hold leases that put them in a safe state;
  replay ordered by epoch and log index. Takeover about 1.3 s.
- IACS UR E22: a single data-link failure must be handled automatically, and critical functions
  should not rely on wireless, so Wi-Fi is a backup path only.

Guests and deck (`research/sensors/payload_deck_human.md`):
- Drone battery from power draw against wind, physics-based because no 140 kg-class data is
  public; a 22 kn headwind makes the return leg about 1.8 times longer. PX4 defaults for
  reference: battery warnings at 15, 7 and 5 %, link-loss failsafe after 10 s.
- UUV leg state and battery. USBL gives no fixes in emission silence because it is an active
  emitter.
- Winch tension at 20 Hz and payout at 3 Hz. Below a factor of safety of 5 the winch needs live
  tension display and alarms (UNOLS RVSS).
- People on deck by zone and by crew level 14, 6 and 0. A synthetic camera detection stream with
  counts, confidence, age and lens health lets the demo run with no camera.

Rules every sensor follows:
- Unknown never means safe. Stale data may only tighten a limit. Corroborating sensors may add a
  hazard, never clear one. Every value carries source, age and confidence.

Not modelled yet:
- Mass and stability use the brief's multipliers only; no public stability data fits this hull.
- Helideck motion limits are placeholders; real ones are set per vessel and aircraft.

Next: these values go into `assumptions.yaml` when the core build starts at 21:30.
