# SDV Resource Governor — Hackathon Game Plan

Fincantieri challenge, Maritime Dual-Use Hackathon, San Francisco, 16–18 Oct 2026.
Team repo: https://github.com/sidd91/softwareDefinedVessels (collaborators: sidd91, GhostWalka).

## Clock (Pacific time; the team is in San Francisco)

| | Pacific (PDT) |
|---|---|
| Plan started | Fri 2026-10-16 20:07 |
| Re-timed | Fri 2026-10-16 20:35, 37 h 25 m left |
| **Deadline** | **Sun 2026-10-18 10:00** |

The laptop clock runs on Central time; always convert with `TZ=America/Los_Angeles date`.

Rules we hold ourselves to: no compute beyond the local stack at runtime; every AI model declared
(coding assistant included); strong live demo plus runnable code; no models from China-based
companies or derived from them (brief, Data Use Authorization §2); check the hackathon's
authorized-AI list for any model other than Claude, which Logan confirmed is approved; **only open-source third-party code
or our own**, every dependency and every pretrained weight declared with its licence in
`docs/THIRD_PARTY.md`.

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
Note: the brief lists voice/natural-language interfaces as out of scope. Our rule compiler is
positioned as the mechanism for Core Mechanic 4 / D5 (tacit rule → execution constraint), not as
an NL interface; its deterministic grammar path is the product, the LLM assist is optional.

## Depth policy (Logan, Fri 23:10, WORKLOG DEC-24 and DEC-25)
- Anything the brief or slides call out explicitly is addressed at a granular level, with evidence,
  and traced in `docs/REQUIREMENTS.md`.
- Our own additions stay light where the facts are unclear.
- The demo shows breadth with a few deep examples.
- Cameras watch equipment first; person detection or tracking is last and optional.

## Core model (locked by Logan, Fri 21:00 PDT)

### One ledger, one manifest language
Everything that uses or supplies a resource is described in one manifest language and counted in
one ledger of margins. Roles differ, and the role decides what the governor may do:

| Role | Examples | What the governor may do |
|---|---|---|
| Host commitment | hotel load, safety systems, the 20 % ship-systems compute reserve, the governor itself | count it, never shed or outbid it |
| Guest | G1–G5, our G6, a portable camera, a mission analytics workload | admit, place, arbitrate, throttle, shed |
| Supply | gensets, cooling loop, bays, mast slots, network paths, compute nodes | track capacity; any loss is a degradation event |
| Crew | people aboard | hands for human-only actions, and authority for confirmation |

A guest is what the brief says it is: equipment that comes aboard to add a capability. A fixed
ship camera is supply; a portable camera brought aboard is a guest.

### Shedding ladder (D4), precomputed every tick
1. Ceiling: the tighter of the degraded power budget and the cooling budget at current seawater
   temperature, minus a headroom (assumed 5 kW, Physical Account).
2. Candidate steps: each guest's ladder of modes, nominal, low-power, standby, off. Each step frees
   kilowatts and costs capability.
3. Price: mission weight from the active priority file × share of capability lost ÷ kW freed.
4. Order: all throttles before any shed; cheapest mission loss per kW first; mission-critical last;
   safety-critical never on the list; ties broken by guest id for determinism.
5. Walk the list until the shortfall is closed, rechecking power and heat after every step; one
   sentence per step saying what that guest lost.
6. Restore in reverse order with a hold-off delay when supply returns.
The same computation runs every tick as "if a genset tripped now", so the first action at a real
trip is a lookup, and the crew can see and approve the plan before it is needed. A trip counts only
when 2 of 3 signals agree (relay flag, kW near zero, frequency dip); any shared condition across
redundant units is reported as a binding constraint (Viking Sky lesson).

### Crew in two roles (D5)
- **Hands.** Every action declares its actuation path: software (guest modes, going silent), ship
  state request (course, speed, noise, with A.6 transition times), or human-only with people ×
  minutes (clear deck, rig winch, swap drone, manual valves, installs). Human-only actions consume
  crew like guests consume kW. At 6 aboard two 4-person tasks cannot overlap; at 0 any plan that
  needs hands is infeasible and the binding constraint says so.
- **Authority.** People confirm contested decisions, approve standing plans, push priority
  overrides and write rules. Confirmation latency competes with the response-time ceilings:

| Crew | Confirm time | 5 s first shed | 60 s full sequence |
|---|---|---|---|
| 14 | 15–60 s | too slow | sometimes |
| 6 | 1–3 min | too slow | too slow |
| 0 | impossible | impossible | impossible |

So "confirm before shedding" is honoured ahead of time by approving the standing plan. Each rule
carries the brief's per-crew policy: human confirms, automatic, or not permitted.

## Architecture (one deterministic core, three bolt-ons)

```
 ┌───────────────────────────── one screen (FastAPI + static SVG/JS, 1 Hz websocket) ─────────────────────────────┐
 │ ship schematic (bays, mast, deck, ramp, hangar) │ 8 gauges │ event log + rationales │ mission/override │ rules │ cam │
 └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                     ▲ read-only view
 ┌─────────────────────────────────────── governor core (pure Python, no I/O) ────────────────────────────────────┐
 │ assumptions.yaml ──► PlatformModel (8 classes, cooling=f(T_sea), power↔heat 1:1, degraded)                      │
 │ manifests/*.json ──► Guest objects (min/nominal/peak+duration per class, conditions, ontology, flags)           │
 │ ShipState machine (A.6 vars + transition times)  ◄── virtual sensors (CV equipment watch) + sim events          │
 │ DecisionEngine:  D1 admit  D2 place  D3 right-of-way  D4 shed   — each returns Decision{verdict, binding, why}  │
 │ MissionContext = priority file (base) ⊕ override stack (captain) ⊕ crew level ⊕ envelope                        │
 │ RuleEngine: compiled crew rules (from CNL) evaluated every tick / every decision, with per-crew-level policy    │
 │ Simulator: seeded, 1 Hz, event timeline JSONL in → decision log JSONL out; `replay` asserts identical output     │
 └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
   bolt-on 1: CV equipment watch (camera → change detection on fixed equipment: leaks, smoke, out-of-place
              gear, deck markers → supply and ship-state events with confidence + age; people optional, last)
   bolt-on 2: Crew Rule Compiler (text → Lark grammar → AST → JSON Schema → compiled predicate + code view)
   bolt-on 3: optional local LLM paraphraser (free text → CNL candidate; still parsed, still approved)
```

### Explainability by construction: the constraint ledger
Every candidate configuration is scored class by class: `margin[class] = free − requested`
(normalised). The binding class is the smallest margin. Infeasible ⇒ the sentence names the class,
the free amount, the request and the condition ("Refused: cooling loop at 30 °C has 12 kW free,
G2 needs 20 kW sustained during winch operation"). Feasible ⇒ the sentence names the tightest
margin. No template strings beyond the ledger fields. Problem size is tiny (≤ 6 guests, ≤ 5
positions), so exhaustive enumeration beats a solver and keeps the ledger exact; OR-Tools stays
optional for D2 if we want to show a declared objective in a solver.

### Declared objectives (README table, one line each)
- D1 admission: feasibility over the **whole envelope grid** (T_sea 12–30 °C, gensets 2/1, sea state
  0–5, wind to 30 kn), not the pier. Reports the boundary ("holds to 27 °C with one genset down").
  Verdicts: yes / no / yes-if (ranked displacement list by mission value lost) / not-now-and-when
  (next installation window per A.11).
- D2 placement: maximise min normalised margin, tie-break on "future freedom" (how many archetype
  cards remain admissible); prints rejected alternatives with their binding class.
- D3 right of way: utility = Σ mission weight × capability delivered, after hard constraints
  (e.g. drone < 20 % ⇒ must land ≤ 12 min, so "wait for leg end" is infeasible). Cost to loser is
  computed (survey minutes lost = 15-min recovery window + re-run leg; or drone risk accepted).
- D4 degradation: the shedding ladder in "Core model" above; shortfall → throttle to low-power modes in declared order → standby → shed;
  safety-critical never auto-shed; mission-critical last; first action ≤ 5 s, sequence ≤ 60 s with
  A.6 transition times; also re-checks heat after each step (shedding kW frees cooling kW).
- D5 crew as a setting: crew in two roles, hands and authority (see "Core model"); every rule carries {14: confirm 15–60 s, 6: confirm 1–3 min, 0: auto | forbidden}.
- D6 Physical Account: generated from `assumptions.yaml`; a script greps each key's usage sites so
  "where used in code" is real file:line references.
- Time is a budget: each decision logs latency vs its ceiling; a watchdog falls back to the safe
  default (hold/deny) if a ceiling is ever missed.

## Mapping Logan's four additions

1. **Mission sets** → priority files (brief requires ≥ 2). Ship six: survey, search-and-rescue,
   patrol, environmental monitoring, disaster relief, night transit. Each file: capability weights,
   per-guest mission-critical flags, shed order policy, crew confirmation policy, envelope narrowing.
   Hot-swappable mid-run; swap re-arbitrates every standing decision (the "same code, two ships" moment).
2. **On-the-fly priority edits** → override stack layered over the mission file: entries
   {target, delta|absolute|protect, reason, author, expiry}. Effective priority = base ⊕ overrides,
   shown side by side, every override in the audit log, immediate re-arbitration.
3. **Computer vision where no sensor exists** (re-aimed by Logan Fri 23:10, WORKLOG DEC-23) →
   cameras watch EQUIPMENT for changes other sensors miss or report late: leaks (chilled-water loop,
   hydraulics, bilge sheen), smoke or a small fire in a bay or the hangar, damaged or out-of-place
   fixed equipment (boom not stowed, lashing or hatch marker missing, antenna bent), foreign objects
   on the flight deck. Each detection becomes a supply or ship-state event with source, age and
   confidence; for example a leak at the cooling loop makes the governor treat cooling as degraded
   before the pump fails. A stale or dropped feed degrades to the conservative state, which is
   exactly "keeps working when a data feed drops". Person detection or tracking of any kind is a
   nice-to-have, done last. Design: `research/cv_equipment_monitoring.md` (in progress).
   Recorded clip as fallback for bad lighting.
4. **Plain-language rules without LLM code edits** → Crew Rule Compiler:
   vocabulary (guests, ship-state vars, actions, phases) → controlled-natural-language grammar (Lark)
   → AST → JSON rule (schema-validated, versioned, author, status proposed/approved) → compiled
   predicate the engine evaluates → human-readable code view ("if G3.acoustic_active: forbid(winch)")
   → dry run against the recorded event log ("this rule would have fired twice at min 8 and min 12").
   Only approved rules are active. A structured builder (dropdowns) produces the same AST for
   people who do not want to type. Optional offline LLM turns loose text into a CNL candidate that
   must still parse and be approved; it never writes code.

## Invented sixth card (G6)
Containerised desalination unit: Bay 2 preferred or half Bay 1; 2.8 t; 18 kW continuous, 4 kW
low-power (recirculate); 2 Mbit/s telemetry; two people to start; high for disaster relief, low
elsewhere; not safety-critical. It is the natural first casualty in Scenario B's shed sequence and
mirrors the organisers' own slide. Alternative if we want a mast story instead: flat-panel SATCOM
terminal (competes with G1/G5 for the one free mast slot, excluded in emission silence).

## Stack (decided unless something breaks)
- Python 3.12 via `uv` (laptop has 3.14; detector/ML wheels will not be there yet). One command:
  `uv run sdv demo scenario-b --priority sar` and `uv run sdv serve` for the screen.
- Core: pure Python + pydantic + jsonschema + PyYAML + Lark + pytest. No solver dependency on the
  critical path; OR-Tools optional for D2.
- UI: FastAPI + uvicorn + websocket, one static HTML/JS/SVG page. No Node, no React, no build step
  (none installed, none needed). Every JS library vendored into the repo so the demo runs offline.
- 3D view: three.js (MIT), vendored, as a toggleable panel beside the scored 2D schematic. See the
  3D section below.
- CV: equipment change detection first: per-region reference-frame comparison and fiducial
  markers on fixed equipment (OpenCV, Apache-2.0), colour and flicker cues for smoke and flame,
  temporal growth for leaks, camera self-checks (blur, frozen frame, view moved); an unsupervised
  anomaly model only if its licence checks out. Person detectors (torchvision SSDlite, BSD-3) are
  optional and last. RF-DETR is out: it is built on LW-DETR from Baidu, which the brief's
  China-derived rule excludes.
  Ultralytics YOLO is out: AGPL-3.0 would bind the whole served app. All run on CPU at 30–80 ms/frame
  on this 16-core Ryzen; 2–5 fps is plenty for a deck-state sensor.
- Optional local LLM for rule paraphrase: Phi-4-mini (MIT, Microsoft) or Mistral-7B-Instruct
  (Apache-2.0) on the Qualcomm box when it lands. Llama and Gemma are excluded by the open-source-only
  rule (community licences are not OSI). Never on the critical path.
- Public data: Open-Meteo Marine (no key) for sea-surface temperature, wave height, wind at a real
  cable-route position; fetched once, cached in the repo, served offline at demo.
- Docs to PDF: markdown → pandoc or a Python PDF path; decide at M5.

AI-use declaration (keep current in `docs/AI_USE.md`): Claude Fable 5.1 and Claude Opus 5.5 (Anthropic, US)
as coding assistants and doc drafting; the detector above with weight licence and training-data origin; the
optional LLM above. Nothing else. `docs/THIRD_PARTY.md` lists every package with version and licence
(FastAPI MIT, uvicorn BSD-3, pydantic MIT, Lark MIT, PyYAML MIT, jsonschema MIT, numpy BSD-3,
torch/torchvision BSD-3, opencv-python Apache-2.0, three.js MIT). Policy: permissive or weak copyleft
only; no AGPL; no non-OSI model licences.

## 3D ship view (demo layer, deliberately not the scored screen)
The brief says it outright: one screen, schematic, gauges, event log, "3D earns nothing". So the
2D schematic + gauges + rationale log stays the primary screen and the 3D view is the demo's visual
hook, built after M3 and time-boxed to 3 hours.
- Engine: three.js (MIT), vendored. No React: it adds a build step and Node we do not have, and the
  page is one file of state → scene updates.
- Geometry: procedural low-poly ship generated from Annex A numbers (65 m hull, Bay 1 aft 20-ft,
  Bay 2 midships 10-ft, flight deck 12 × 8 m, hangar, stern ramp, three mast positions). Same source
  of truth as the governor, so when the jury changes a dimension the model changes with it.
  CAD import only if a CC0/CC-BY glTF hull turns up in the first 20 minutes of looking; FreeCAD
  (LGPL) or OpenSCAD (GPL) export is the fallback route, not the plan.
- What it shows: each position coloured by governor state (free / committed / displaced / shed),
  guests appearing on admission, the drone on approach while the deck is not clear, heat
  as a loop tint that reddens as the cooling margin closes, mast slot pulsing when it is the binding
  class. Camera follows the event log.
- Rule for the build: every 3D element binds to a field that already exists in the 1 Hz state
  message. No new logic lives in the 3D layer.

## Edge compute, redundancy and failsafes (Logan's emphasis)
A ship is several computers on two cables, not one laptop. The governor is designed as a small
distributed system from the first commit, and the demo shows it surviving the things that actually
break at sea: a node, a cable, a radio, a camera.

- **Topology.** Governor = replicated service on the ship's rack (A.7) plus edge inference nodes
  next to sensors. Demo: laptop is node A (governor primary + screen), Qualcomm box is node B
  (camera equipment-watch inference + governor hot standby). Until the box lands, node B is a second process on
  the laptop on its own port, so failover is built and tested before the hardware exists.
- **Determinism is the redundancy mechanism.** The standby holds the same event log. Takeover is a
  replay to the last sequence number: no state-sync protocol, no divergence. Fencing by epoch: the
  standby promotes after three missed heartbeats, the old primary demotes itself when it sees a
  higher epoch on reconnect. Config (mission file, rules, overrides) is versioned by hash and
  replicated; on mismatch the standby refuses promotion and says why.
- **Two transports, one bus.** Every inter-node message carries a sequence number and goes over the
  wired path first. One heartbeat per path per second tracks health. Wired loss → Wi-Fi within 2 s,
  shown as a path indicator on screen. Both lost → the node runs autonomous on safe defaults and
  buffers its log for reconciliation. Honesty with A.5: detections are bytes, video is Mbit/s, so the
  edge node never ships video over a degraded path, only counts and confidences. In emission silence
  radio is zero by rule, so Wi-Fi is itself forbidden and the wired path is the only one.
- **Stale and missing feeds.** Every virtual sensor carries age and confidence; thresholds live in
  `assumptions.yaml`. Stale → conservative state (deck occupied, ramp not clear). The rule engine
  then falls back to the crew policy: confirm at 14 and 6, forbidden at 0. That closes the loop with D5.
- **Watchdogs and safe defaults.** Per-decision ceilings (30 s / 2 s / 5 s / 200 ms) with a
  watchdog; on a miss the safe default (hold / deny / keep state) is emitted with a rationale naming
  the ceiling. Write-ahead event log on disk; a restart is a replay.
- **Compute-class honesty.** The governor and the inference are themselves entries in the compute
  budget (A.7 reserves 20 % for ship systems) and in the Physical Account. A per-node compute ledger
  shows where inference runs and what moves when a node is lost.
- **Failsafe demo moments.** Pull the Ethernet cable: path flips to Wi-Fi, no decision missed. Kill
  Wi-Fi too: the equipment watch goes stale, so its zones fall back to crew reports at 14 and 6 and
  to "not clear" at 0. Kill the primary process: standby promotes by replay in under 3 s and the log continues with
  the same sequence numbers.

## Cameras: an inventory, not an assumption
Fixed cameras exist on some zones of some ships. The ship profile therefore carries a camera
inventory (`cameras:` in `assumptions.yaml`: id, zones covered, interface wired/Wi-Fi, fixed or
portable). Virtual sensors declare the zones they need; no coverage → the sensor reports
"no coverage" and the rule falls back to crew policy. A portable camera can be registered at runtime,
and the clean way to do that is the lateral we should lean on: **a camera is a guest.** It has a
manifest (consumes compute, a data link, a mounting position; returns the capability
`deck_state@flight_deck`), is admitted through the same governor, and is shed through the same
ledger. Default inventories per domain, from `research/camera_placement.md`:

| Zone | Naval / OPV with helo | Coast guard | Offshore (NCS) | Research |
|---|---|---|---|---|
| Flight deck | fixed PTZ, wired, low-light/thermal | sometimes | yes, recorded 30 days (Norway) | owner option |
| Hangar | sometimes (IPMS) | rarely | n/a | rarely |
| Stern ramp / boat deck | portable | portable | n/a | one launch-area camera, else portable |
| Mission bay | sometimes | rarely | n/a | rarely |
| Machinery spaces | yes, IPMS network | yes | sometimes | sometimes |
| Winch / deck machinery | read the drive signal; winch camera only corroborates | same | winch cameras common | winch cameras common |

Design consequences: the flight-deck camera is usually a single PTZ that gets slewed onto the
approach, so the deck sensor needs a field-of-view check (printed fiducial marker on deck; not
visible means "unknown", never "clear"). IPMS cameras and security CCTV are separate networks.
Ship CCTV is wired PoE; a portable camera is a separate best-effort feed. Crew confirmation remains
the only source for ramp water approach, mission-bay contents on non-SOLAS hulls, and any zone whose
only camera is pointed elsewhere.

## Schedule (Pacific, PDT)

| Block | When | Deliverable / milestone |
|---|---|---|
| Setup | Fri 20:35–21:30 | Repo access; scaffold; `assumptions.yaml` from Annex A; manifest schema v0; G1–G6 cards |
| Core | Fri 21:30–Sat 01:30 | Platform model, ship state machine, sim tick, **D1 with ledger + envelope sweep**, CLI. **M1 Sat 01:30**: ticking sim, 3 guests consuming, 8 gauges, one card refused with a sentence |
| Sleep | Sat 01:30–06:30 | Claude overnight: unit tests for ledger math, public-data fetch + cache, synthetic sensor generators from the research, README skeleton, manifest docs |
| Decisions | Sat 06:30–11:30 | D2 placement, D3 right of way with priority files, D4 shedding with standing contingency plans. **M2 Sat 11:30**: Scenario A and B pass in CLI with both priority sets; `replay` test green |
| Screen + edge | Sat 11:30–16:30 | Web screen (schematic, gauges, log); mission selector; override stack; crew dial; two-node topology (node B process, dual-path bus, heartbeats, path indicator). **M3 Sat 16:30**: Scenario B watchable end to end on screen |
| Rules + CV | Sat 16:30–21:30 | Crew Rule Compiler (grammar, AST, approval, dry run, code view); Scenario C rule live at 14/6/0; CV equipment watch on node B (leak, smoke, out-of-place gear) with camera self-checks; failover by replay; stale-feed fallback ladder. **M4 Sat 21:30** |
| Polish | Sat 21:30–Sun 01:00 | 3D view (time-boxed 3 h, M3 state message only). Jury drills: change one number on a card, swap priority mid-run, drop the camera feed, over-consuming guest. Docs: README, generated Physical Account, Scenario C memo PDF, AI and software declaration. Backup recording. **M5 Sun 01:00** |
| Sleep | Sun 01:00–05:30 | Claude overnight: polish docs, regenerate Physical Account, lint, final tests |
| Rehearse | Sun 05:30–09:15 | Rehearse the demo five times; fix only what breaks; **freeze Sun 09:15** |
| Buffer | Sun 09:15–10:00 | No new features. Submit |

Cut order if behind (first cut first): person detection → LLM paraphraser → 3D view (keep 2D schematic) → structured
rule builder UI → A′ installation windows → six mission files (keep three) → CV live (keep recorded
clip) → OR-Tools.
Never cut: ledger rationales, both scenarios, replay, link failover + stale-feed policy, Physical
Account, Scenario C memo.

## Demo script: 90 s of Scenario B, Scenario A with the jury's card, failsafe encore
00:00 Baseline: 3 kn over a cable route, 24 °C water, G3 listening, eight gauges steady, mission = survey,
      two nodes green, wired path active.
00:08 Drone reports 18 % in 22 kn wind. Two incompatible condition sets appear on the ship state.
      Governor decides in < 2 s: hard constraint named (land ≤ 12 min), survey pauses for the 15-min
      recovery window, cost stated in minutes.
00:20 Jury swaps the priority file to SAR. Same event replayed: survey suspended, ship released to
      manoeuvre, 35 kW reserved ahead of everything, one sentence says why.
00:32 A marked item is left on the landing zone (deck marker covered): "Held: flight deck not clear,
      marker FD-2 covered since 00:31 (camera, 0.4 s old), rule R3". Removed: deck clear, recovery
      proceeds. Breadth line on screen: leak at the cooling loop turns cooling to degraded early.
00:45 Ethernet cable pulled: path indicator flips to Wi-Fi, equipment watch keeps reporting, nothing missed.
00:55 Genset trips, reserve ~100 kW. First shed action within 5 s: G5 to 8 kW low-power, G6 to
      standby, G2 to standby; winner kept alive; every guest's loss listed.
01:10 Crew dial 14 → 0: the same shed step flips from "confirm (60 s)" to "automatic", on screen.
01:20 Scenario A: jury's card loaded, one number changed live, verdict in < 30 s with binding
      class, placement, displacement list and "holds with one genset down: yes/no".
01:30 Done. Encore if the jury wants it (30 s): kill Wi-Fi too → equipment watch stale → hold
      becomes "crew confirms"; kill the primary governor process → standby promotes by replay in < 3 s.

## Open questions for Logan
- Who owns what between Logan (GhostWalka) and Siddharth (sidd91): engine / screen / CV + rules / docs.
- Qualcomm box arrives Sat about 10:00 PDT, just before the Sat 11:30 edge block. Still need its model
  and OS, and the organizers' answer on Qualcomm's proprietary NPU runtime; default is CPU.
