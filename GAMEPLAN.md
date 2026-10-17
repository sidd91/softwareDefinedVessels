# ArgOS: hackathon game plan

Fincantieri challenge, Maritime Dual-Use Hackathon, San Francisco, 16–18 Oct 2026.
Team repo: https://github.com/sidd91/softwareDefinedVessels (collaborators: sidd91, GhostWalka).
Project name ArgOS (DEC-45). This plan follows the design freeze approved Sat 12:04 PDT (WORKLOG DEC-44,
[docs/DESIGN_FREEZE.md](docs/DESIGN_FREEZE.md)) and the work split (DEC-47). Rewritten Sat 12:39 PDT.

## Clock (Pacific time; the team is in San Francisco)

| | Pacific (PDT) |
|---|---|
| Plan started | Fri 2026-10-16 20:07 |
| Design frozen | Sat 2026-10-17 12:04 |
| **Deadline** | **Sun 2026-10-18 10:00** |

The laptop clock runs on Central time; always convert with `TZ=America/Los_Angeles date`.

Rules we hold ourselves to: no compute beyond the local stack at runtime; every AI model declared
(coding assistant included); strong live demo plus runnable code; no models from China-based
companies or derived from them (brief, Data Use Authorization §2); AI services only from the
hackathon's authorized list (Logan confirmed Claude is approved, DEC-05; the organizer message asked
where the list is published, DEC-49); **only open-source third-party code or our own**, every dependency
declared with its licence in `docs/SOFTWARE_LOG.md`.

## What the jury scores (from the brief)

Must-have: manifest schema for all five Annex B cards + one invented card; platform budget with all
eight resource classes, power–heat coupling, degraded state; Scenario A end-to-end (verdict ≤ 30 s
against the mission envelope, binding constraint in one sentence); Scenario B end-to-end (min-8
decision ≤ 2 s with rationale and cost to loser; min-12 shedding in a declared order; two priority
sets give different coherent outcomes); identifiable decision engine covering D1, D3 and one of
D2/D4; Scenario C memo (≤ 2 pages) and the Physical Account (Annex C).

Should-have: D2 placement with rejected alternatives; Scenario A survives a jury-changed number;
A′ installation windows; real public data for cooling/deck; over-consuming guest detected and
handled; Scenario C rule live at two crew levels; deterministic replay; every rationale from the
actual binding constraint.

Explicit traps: "Kubernetes with a ship label", a dashboard instead of a decision engine, canned
rationale strings, hard-coded priorities, a solver that takes four minutes, an empty Physical Account.
The brief also puts voice and natural-language interfaces out of scope and says 3D earns nothing, so the
freeze cut our rule compiler, LLM paraphraser and 3D view (DEC-44).

## Depth policy (Logan, Fri 23:10, WORKLOG DEC-24 and DEC-25)
- Anything the brief or slides call out explicitly is addressed at a granular level, with evidence,
  and traced in `docs/REQUIREMENTS.md`.
- Our own additions stay light where the facts are unclear.
- The demo shows breadth with a few deep examples.
- The freeze applied this policy to our beyond-the-brief items and cut them (DEC-44).

## Core model (locked by Logan, Fri 21:00 PDT)

### One ledger, one manifest language
Everything that uses or supplies a resource is described in one manifest language and counted in
one ledger of margins. Roles differ, and the role decides what the governor may do:

| Role | Examples | What the governor may do |
|---|---|---|
| Host commitment | hotel load, safety systems, the 20 % ship-systems compute reserve, the governor itself | count it, never shed or outbid it |
| Guest | G1–G5, our G6, a mission analytics workload | admit, place, arbitrate, throttle, shed |
| Supply | gensets, cooling loop, bays, mast slots, network paths, compute nodes | track capacity; any loss is a degradation event |
| Crew | people aboard | hands for human-only actions, and authority for confirmation |

A guest is what the brief says it is: equipment that comes aboard to add a capability.

### Shedding ladder (D4), precomputed every tick
1. Ceiling: the tighter of the degraded power budget and the cooling budget at current seawater
   temperature, minus a headroom (assumed 5 kW, Physical Account).
2. Candidate steps: each guest's ladder of modes, nominal, low-power, standby, off. Each step frees
   kilowatts and costs capability.
3. Price: mission weight from the active priority file × share of capability lost ÷ kW freed.
4. Order: safety-critical guests are never on the list, and hard limits come first. All throttles
   before any shed. Then the priority file's `shed_order`, if it has one (F3). Otherwise the price:
   cheapest mission loss per kW first, mission-critical last, ties broken by guest id. No shipped
   priority file sets `shed_order`; disaster relief already keeps G5 last through `mission_critical`.
5. Walk the list until the shortfall is closed, rechecking power and heat after every step; one
   sentence per step saying what that guest lost.
6. Restore in reverse order with a hold-off delay when supply returns.

The same computation runs every tick as "if a genset tripped now", so the first action at a real
trip is a lookup, and the crew can see and approve the plan before it is needed. The armed ladder
covers current draws and reservations. Faults enter as debounced, confirmed plant signals: a trip
counts when 2 of 3 signals agree (relay flag, kW near zero, frequency dip), and a cooling fault needs
the plant alarm plus flow or delta-T. Each record carries the raw-event and confirmation times. Any
shared condition across redundant units is reported as a binding constraint (Viking Sky lesson).

Scenario B under DEC-40 ([EXPECTED_OUTCOMES](docs/EXPECTED_OUTCOMES.md)): at minute 12 the trip holds
under both files against the 95 kW ceiling, with 0 steps. Survey loads 48 kW: G4 is airborne at 2 kW
with no charge to throttle, so the first armed step is G5 full to low power (frees 37 kW, 0.0038 per kW).
Rescue loads 81 kW with G4's 35 kW reserved, and the first armed step is also G5 full to low power
(0.0189 per kW). At minute 19 an INJECTED chilled-water pump fault drops the ceiling to 75 kW and the
ladder runs: survey slows G4's charge from 35 to 10 kW, rescue takes G5 from 45 to 8 kW. Minute 12 is
Siddharth's to change as owner of the scenario timing (DEC-51).

### Crew in two roles (D5)
- **Hands.** Every action declares its actuation path: software (guest modes, going silent), ship
  state request (course, speed, noise, with A.6 transition times), or human-only with people ×
  minutes (clear deck, rig winch, swap drone, manual valves, installs). Human-only actions consume
  crew like guests consume kW. At 6 aboard two 4-person tasks cannot overlap; at 0 any plan that
  needs hands is infeasible and the binding constraint says so.
- **Authority.** People confirm contested decisions, approve standing plans and set the crew level.
  Confirmation latency competes with the response-time ceilings:

| Crew | Confirm time | 5 s first shed | 60 s full sequence |
|---|---|---|---|
| 14 | 15–60 s | too slow | sometimes |
| 6 | 1–3 min | too slow | too slow |
| 0 | impossible | impossible | impossible |

So "confirm before shedding" is honoured ahead of time by approving the standing plan. Each rule
carries a policy per crew level: confirm, standing plan, automatic or forbidden. A priority file may
set it per rule (F3), and `confirm` is refused at 0 aboard, because A.6 makes confirmation impossible
uncrewed.

**Rule R3, "nobody on the flight deck during recovery"** (Scenario C, freeze F5, no camera). At 14
aboard the landing officer reports the deck and the bridge confirms. At 6 a standing plan approved at
launch applies. At 0 recovery is allowed only if the deck was latched clear at the last crew sweep with
no deck activity since, a platform-reported deck state recorded as an assumption. Otherwise it is
forbidden, and the record states the cost under G4's hard limit: below 20 % it must land within 12
minutes or ditch. Memo: [docs/SCENARIO_C_MEMO.md](docs/SCENARIO_C_MEMO.md).

## Architecture (the frozen design)

```
 config/assumptions.yaml    manifests/G1..G6.yaml    config/missions/*.yaml (the jury swaps this)
         └─────────────────────────┼─────────────────────────┘
                                   ▼
          LOADER: every name checked; a bad file is refused, the old one kept
                                   ▼
  LEDGER (1 Hz) ◄──── 1 Hz SNAPSHOT ◄──── SIMULATOR + SHIP STATE (A.6)   [Siddharth]
                                   ▼                      ▲ COMMANDS
  D1/D2 admit + place   D3 right of way   D4 shed ladder   D5 crew policy   safety table (200 ms)
                                   ▼
  DECISION RECORD → EXPLAINER (templates over record fields) → decision log + timing log → REPLAY
                                   ▼
  ONE SCREEN: Operations (constraint ledger drill-down) │ Mission compare │ Admission review
  tools/physical_account.py → Annex C          board instrument → measured compute and latency rows
```

- **Inputs.** Three files: the ship profile, the guest cards and a swappable priority file. They join
  by capability name, so a swap needs no code change. The loader checks every name and refuses a bad
  file with the failing field while the previous file keeps running.
- **Ship state.** Siddharth's simulator owns the A.6 state machine and its transition times. It emits
  a 1 Hz snapshot in ship time; the core sends it commands. The snapshot and command contract comes
  first (CON-21).
- **Core.** The ledger, the ladder core, D1 to D5 and the safety-command table: pure Python, no I/O,
  no solver or model on the 200 ms, 2 s or 5 s paths.
- **Records.** Every decision is a record. The sentence is a template over record fields. Wall-clock
  latency and timestamps go to a separate timing log, so a replay matches on every other field.
- **Screen.** One screen with three views: Operations, with the constraint ledger as its drill-down;
  Mission compare, two runs on one timeline; Admission review, the jury's card and its one-number edit.

Components, owners and data contracts: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### Explainability by construction: the constraint ledger
Every candidate configuration is scored class by class: `margin[class] = (free − requested) /
capacity`. The binding class is the smallest margin, and every other class over its limit is listed as
also failing. A3 is the check: mass binds at 13.015 against 10 t, and cooling at 125 of 120 kW at 30 °C
is listed as also failing. Infeasible means the sentence names the class, the free amount, the request
and the condition, for example "Yes if G1 disembarks: mass 10.035 of 10.000 t with G1 aboard, 35 kg
over" (A1). Feasible means the sentence names the tightest margin. No template strings beyond the
ledger fields. The problem is tiny (six guests, a few positions, Bay 1 in halves), so enumeration of a
few thousand assignments runs in milliseconds and gives the binding line and the rejected alternatives
directly. No solver (freeze delta 6).

### Declared objectives (README table, one line each)
- D1 admission: judged at both gensets, the 200 kW reserve and cooling at 30 °C, and it must survive
  one genset down by throttling to the 95 kW gate, otherwise yes-if (DEC-35). Verdicts: yes / no /
  yes-if (ranked displacement list by mission value lost) / not-now-and-when (next installation
  window per A.11). Reports the seawater tipping point. By enumeration.
- D2 placement: maximise the smallest normalised margin, tie-break on "future freedom" (how many
  archetype cards remain admissible); prints rejected alternatives with their binding class. The
  mast rule is written before T2 (CON-18).
- D3 right of way: hard limits first (drone < 20 % ⇒ must land ≤ 12 min, so "wait for leg end" is
  infeasible), then utility = Σ mission weight × capability delivered. Cost to the loser is computed:
  under survey, 25 to 27 survey minutes; under rescue, G3's leg is aborted, it holds at sea and is
  recovered over the ramp only after G4 has landed, because the flight deck and the ramp are
  mutually exclusive.
- D4 degradation: the shedding ladder in "Core model" above; first action ≤ 5 s, sequence ≤ 60 s
  with A.6 transition times; heat rechecked after each step (shedding kW frees cooling kW).
- D5 crew as a setting: crew in two roles, hands and authority; every rule carries a policy at 14, 6
  and 0 aboard.
- D6 Physical Account: generated from `assumptions.yaml` by `tools/physical_account.py`; compute and
  response-time rows take the board instrument's measured values if it runs.
- Safety commands (stop, hold, secure): answered within 200 ms from a table precomputed every tick.
- Time is a budget: each decision logs latency against its ceiling; a watchdog falls back to the safe
  default if a ceiling is ever missed (`decision_watchdog` in `assumptions.yaml`).

## Mapping Logan's four additions

1. **Mission sets** → priority files: kept. Four exist in `config/missions/`: survey, search and
   rescue, patrol, disaster relief. Each has capability weights and mission-critical guests, and may
   carry `shed_order` and a per-rule `confirm` (F3). Hot-swappable mid-run; a swap re-arbitrates every
   standing decision, and Mission compare runs two files on one timeline.
2. **On-the-fly priority edits** → an override stack over the mission file: not in the build order.
   [OPEN_QUESTIONS](docs/OPEN_QUESTIONS.md) #49 proposes deferring it. The jury's one-number edit on a
   card is in scope, in Admission review.
3. **Computer vision where no sensor exists:** cut (DEC-44). The governor's inputs are confirmed plant
   signals the ship already has; a camera is a slower, uncertain copy of the same signal and never
   changes a decision (freeze section 5).
4. **Plain-language rules without LLM code edits:** cut (DEC-44). Natural-language interfaces are
   out of scope. R3 is written as typed conditions in data, checked at load.

## Invented sixth card (G6)
Containerised desalination unit: Bay 2 preferred or half Bay 1; 2.8 t; 18 kW continuous, 4 kW
low-power (recirculate); 2 Mbit/s telemetry; two people to start; high for disaster relief, low
elsewhere; not safety-critical. It is not in Scenario B (the brief's G2 to G5 load-out is over the mass
margin and refused at the pier; we run G3, G4, G5, DEC-32), so it sheds first only in runs that carry it;
it mirrors the organisers' own slide. Alternative if we want a mast story instead: flat-panel SATCOM
terminal (competes with G1/G5 for the one free mast slot, excluded in emission silence).

## Stack (decided unless something breaks)
- Python 3.12 via `uv` (the laptop also has 3.14, unused). One documented command: `uv run sdv demo`.
- Core: pure Python + jsonschema + PyYAML + pytest, all installed. No solver: admission and placement
  by enumeration. pydantic is considered, not approved (`docs/SOFTWARE_LOG.md`).
- UI: FastAPI + uvicorn + websockets (approved, DEC-39), one static HTML/JS/SVG page with three views.
  No Node, no React, no build step. Every JS library vendored into the repo so the demo runs offline.
- Public data: Open-Meteo Marine (no key) for sea-surface temperature, wave height and wind at a real
  cable-route position; fetched once, cached in the repo, served offline at demo. The brief names it,
  so CON-05 can close on that line; CC BY 4.0 attribution goes in the README.
- Docs to PDF: `uv run python tools/build_pdfs.py` (pandoc and headless Chromium; LibreOffice fallback)
  builds the README, memo and Physical Account into `docs/pdf/` and checks each page limit.
- Board instrument: the same container on the VENTUNO Q; any install on it needs Logan's OK.
- Not used after the freeze: three.js, Lark, torch and torchvision, any vision use of opencv or
  onnxruntime, any LLM (DEC-44).

AI-use declaration (kept current in `docs/SOFTWARE_LOG.md`): Claude Fable 5.1 and Claude Opus 5.5
(Anthropic, US) as coding assistants and for doc drafting. No AI model runs in ArgOS itself. Policy:
permissive or weak copyleft only; no AGPL; no non-OSI model licences.

## Failsafes, stale feeds and the board instrument
- **Stale and missing feeds** (R-458). Every snapshot input carries its source and age; limits live in
  `assumptions.yaml`. A stale feed falls to its conservative value, the record says so in one sentence,
  and decisions continue: genset state unknown means admit as if one is down; pump status unknown
  means cooling degraded; deck report unknown means not clear; course unknown means not steady. This
  is the "data feed drops" breadth line.
- **Watchdogs and safe defaults.** Per-decision ceilings (30 s / 2 s / 5 s / 200 ms) with a watchdog.
  On a miss the safe default from `decision_watchdog` is emitted with a sentence naming the ceiling:
  admission "no, timed out", placement and arbitration keep the current state, shedding uses the last
  precomputed ladder.
- **Safety commands.** Stop, hold and secure come from a table precomputed every tick next to the D4
  ladder, so no solver runs on the 200 ms path.
- **Acoustic link.** Up only while the course is steady, the noise quiet and no deck machinery runs; it
  drops after an assumed delay. So under survey G3 holds depth before the link breaks.
- **Restart is a replay.** The event timeline and the decision log are on disk, and a restart replays
  them.
- **Compute-class honesty.** The governor is itself an entry in the compute budget (A.7 reserves 20 %
  for ship systems) and in the Physical Account. The board instrument measures watts, latency per
  decision class and CPU share against A.7 for those rows ([docs/NODE_B_BOARD.md](docs/NODE_B_BOARD.md)).
  The laptop provides every demo input; a board button or knob may only mirror one; nothing in the
  demo depends on the board.

## Cut by the design freeze (DEC-44)

| Cut | Why |
|---|---|
| Cameras and computer vision: leak (C1), smoke (C2), deck gear (C3), camera virtual sensors, camera-unknown rules, the webcam demo beats | Plant signals already give each input, confirmed and instant; a camera is a slower, uncertain copy and never changes a decision; A.6 answers the deck question |
| Person detection | the same, and last in priority since DEC-23 |
| 3D view and three.js | "3D earns nothing" (brief) |
| Crew rule compiler, controlled grammar and Lark | natural-language interfaces are out of scope |
| LLM paraphraser | out of scope, and no LLM belongs in the decision path |
| NPU inference | nothing left to infer |
| Two-node failover: heartbeats, epochs, duplicate paths, failover by replay, the cable-pull line, Wi-Fi backup | unscored; one laptop, and A.7 is a modelling constraint |
| torch, torchvision (SSDlite), and the vision uses of opencv and onnxruntime | no vision left |

The research behind these items stays in `research/` as research, each file headed "Superseded for the
build by WORKLOG DEC-44."

## Schedule (Pacific, PDT)

Proposed; Logan and Siddharth confirm it (CON-10, CON-17). Tasks and pass checks are in
[docs/BUILD_PLAN.md](docs/BUILD_PLAN.md).

| Block | When | Milestone |
|---|---|---|
| Contracts | Sat 12:30–14:00 | **S1**: typed conditions, loader, snapshot and command contract (CON-21). Siddharth's simulator track starts here |
| Ledger | Sat 14:00–16:00 | **S2**: ledger and ladder core |
| Scenario A | Sat 16:00–18:30 | **M1**: A1 to A7 from the engine within 30 s; A3 names mass and lists cooling at 30 °C as also failing |
| Scenario B | Sat 18:30–22:30 | **M2**: D3, D4 and the safety table with the simulator, under both priority files |
| Screen | Sat 22:30–Sun 01:30 | **M3**: Operations, Mission compare, Admission review |
| Replay and breadth | Sun 01:30–03:00 | **M4**: replay match; breadth lines |
| Rest | Sun 03:00–06:30 | |
| Docs | Sun 06:30–08:00 | **M5**: README, memo, Physical Account against the built engine; PDFs within limits |
| Rehearse | Sun 08:00–09:15 | five rehearsals; backup recording; **freeze Sun 09:15** |
| Buffer | Sun 09:15–10:00 | No new features. Submit by the checklist in `docs/BUILD_PLAN.md` |

Cut order if behind (first cut first): emission silence line → board instrument → A′ installation
windows → patrol and disaster relief in the demo (keep survey and rescue) → Mission compare (fall back
to the swap on one run) → Admission review (fall back to the D1 record in Operations).
Never cut: ledger rationales, both scenarios, replay, the stale-feed policy, Physical Account,
Scenario C memo.

## Demo script: 90 s of Scenario B, then Scenario A with the jury's card

The storyboard is [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md). Scenario B runs G3, G4 and G5 (DEC-32) on
the DEC-40 timeline with the jury's priority file: D3 at minute 8; minute 12 holds with both armed
ladders shown; the INJECTED pump fault at minute 19 runs the ladder. Then Scenario A with the jury's
card and one number changed, in Admission review. Then the Scenario C segment (R3 at 14, 6 and 0
aboard) and the breadth strip: landing zone not clear (from the landing officer's report), crew dial,
over-consuming guest, emission silence (waits on OPEN_QUESTIONS #42), mission sets, data feed drops.
Injected faults are labelled INJECTED on screen.

## Open questions for Logan
All of them, with proposals: [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md). First: the snapshot and
command contract with Siddharth (CON-21), the milestones (#3), emission silence (#42), owners for the
board instrument and the final PDFs (#46, #51), and the board's default login (CON-15).
