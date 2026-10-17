# Design freeze: the two designs, their deltas, and recommendations

Status: **proposal, Sat 11:50 PDT.** Written by Claude Fable 5.1 on behalf of Siddharth Chawla (sidd91)
for the team to settle in one sitting. Nothing here is decided until a WORKLOG `DEC-` row says so.

Two designs exist for the same system:

- **S** — Siddharth's, from a design conversation before coding (protobuf schema, policy compiler,
  CP-SAT admission, 10 Hz plant). Handed over as `RESEARCH_EXPORT.md` + `sdv-datamodel/`; not in this repo.
- **L** — Logan's, on this branch (`feat/governor-core`): JSON Schema + YAML, `config/assumptions.yaml`,
  six cards, four priority files, WORKLOG DEC-01…41, hand-computed oracles, 265 passing tests, no engine code yet.

The brief is the referee. Where the brief is silent, the tiebreak is: fewer moving parts, decided faster.

## 1. What the challenge is, in four lines

A ship has a fixed budget in eight classes (power, heat, deck slots, mast slots, mass, data links, compute,
time). The jury wants a program that decides in seconds whether a payload fits, who wins when two collide,
and what to switch off when a genset trips, and says why in **one sentence built from the number that bound**.
They score honesty of the physics, a decision engine with declared objectives, swappable priorities that
change the outcome, the 30 s / 2 s / 5 s ceilings, and a sharp Physical Account over a polished demo.

## 2. Where S and L already agree (freeze as is)

- Three inputs: ship profile, guest cards, a swappable priority file. Cards and priority files never name
  each other; the **capability name** joins them, so a swap needs no code change.
- Guests run in **modes** (full / low-power / standby / off); degradation walks down the modes before shedding.
- Ship state is a **finite-state machine** (A.6 variables with transition times); a conflict is two guests'
  incompatible conditions on that state, not an alarm.
- D3 decides hard limits first, then mission-weighted value; D4 is a ladder precomputed every tick.
- Every decision is a **record** (trigger, snapshot, binding line, loser cost, alternatives, latency, input
  hashes); the sentence is a template over record fields; replay must reproduce records byte for byte.
- Every assumed number lives in one file with a reason, and Annex C is generated from it.
- The board is not a demo dependency.

## 3. Deltas

| # | Area | S (Siddharth) | L (Logan) | Brief says | Recommendation |
|:--|:--|:--|:--|:--|:--|
| 1 | Schema format | protobuf `manifest.proto`, YAML parsed 1:1 | JSON Schema `manifests/schema.json`, YAML cards, tested | "JSON Schema, Protobuf or TOML" | **L.** Protobuf only pays if the board exchanges messages with the governor; it does not (delta 10). |
| 2 | Typing of conditions | typed `Condition` tree over named signals; loader rejects any state, position or capability name not in the ship profile | `conditions.requires` is an untyped object; `hard_limits.when` and `excludes.when` are free text; field names drift (`speed_kn`, `speed_kn_max`; G2/G3 reference `G4.recovering`, G4 defines `launch_recovery`) | manifest must express "conditions on course and noise" and structure | **S, applied to L's schema.** Small typed vocabulary (`speed_band`, `course`, `noise`, `deck`, `emission`, `ramp`, `deck_machinery`, `wind_kn_max`, `sea_state_max`) with values taken from `assumptions.yaml`'s `ship_state`; hard limits as `{signal, op, value, then: {action, within_min}}`; unknown name = file refused. Do this **before** engine code. |
| 3 | Priority file contents | weights + declared `shed_order` + rules with hysteresis + crew settings; a "policy compiler" checks names, rule collisions, static feasibility; a hostile file is a test | `weights` + `mission_critical` only, schema-validated; shed order computed as mission value lost per kW; rules live in cards; confirmation policy in `assumptions.yaml` | "shed in a declared order"; mission context includes a "per-rule confirmation policy" | **L plus two optional fields:** `shed_order` (overrides the computed order when present) and per-rule `confirm: {14, 6, 0}`. Keep the name check and the hostile-file test from S; drop the rest of the compiler. |
| 4 | Admission envelope | judge at the worst corner, cooling already −40 %; headline story "G4 → YES-IF, cooling binds 72 vs 86 kW" | DEC-35/36: verdict at both gensets, 30 °C, lower reserve; then one-genset-down line in three states (holds / holds by throttling / does not hold); −40 % cooling as information only | A.10: "one-genset-down assumed possible; judge cooling at 30 °C" | **L.** Closer to A.10, and the brief's own phrase "states whether it holds with one genset down" is exactly L's third column. S's story disappears (A5 becomes a plain yes at 100/120 kW) but "cooling binds" still appears in A3 (125/120) and at the Scenario B pump fault. |
| 5 | Scenario B load-out and minute 12 | brief's G2–G5 as written; shed at minute 12 (node → 8 kW, module → standby) | DEC-32/40: G3, G4, G5 (G2–G5 is 13.0 t vs 10 t); minute 12 **holds** (81 of 95 kW, 0 steps, armed ladder shown); shedding at an added, labelled pump fault at minute 19 | must-have: "min-12 explicit shedding sequence"; organisers' own sum (105 kW) assumes G3 is charging, which their minute-8 story contradicts | **Open; see §4.** L's arithmetic is right. The risk is the must-have's wording. Ask the organisers today. |
| 6 | Admission engine | CP-SAT (OR-Tools) over compiled IR | ledger checks + enumeration; OR-Tools last on the cut list | "CSP or small MIP" suggested, not required; "a perfect solver that takes four minutes has answered the wrong question" | **Enumeration.** Six guests, six positions, Bay 1 in halves: a few thousand assignments, milliseconds. Binding line and rejected alternatives come out directly; no unsat core to translate. |
| 7 | Scenario C rule | "no winch while the survey vehicle is listening" | R3 "nobody on the flight deck during recovery", chosen by three judging agents; at 0 crew needs a camera to prove the deck stayed clear | any one implicit rule; ≤ 2 pages | **L's R3, without the camera.** At 0 crew: recovery allowed only if the deck was left clear (A.6: "uncrewed only if already clear"), otherwise forbidden. One paragraph. |
| 8 | Cameras / computer vision | none | leak, smoke, out-of-place gear; one replayed "leak line" in the demo; camera host on node B | not mentioned; "no specialised hardware"; ML "for forecasting, not for the decision" | **Cut entirely.** See §5. |
| 9 | Beyond-the-brief items | none | 3D view (toggle), crew rule compiler (controlled grammar), LLM paraphraser, person detection, NPU inference, two-node failover by replay | "3D earns nothing"; natural-language interfaces out of scope; no LLM in the decision path; laptop only | **Cut all.** Two-node failover may return only if the screen milestone lands early; it is unscored. |
| 10 | Role of the Ventuno Q board | instrument: same container, reports watts, latency per decision class, CPU share vs A.7; button trips the genset; knob is the jury's "one number" | second governor node with wired + Wi-Fi failover, camera host, NPU | A.7 is "a modelling constraint"; cybersecurity out of scope | **S.** Measurements feed the Physical Account (compute / response-time rows); nothing in the demo depends on it. |
| 11 | Fault entry | threshold rules with hysteresis (`clear_at`, `min_dwell_s`) | trip confirmed by 2 of 3 signals; cooling fault by plant alarm plus flow or ΔT | "keeps working when a data feed drops" | **Both, as one rule:** every fault is a debounced, confirmed plant signal before it can trigger a decision (a DTC, not a pixel). Decision record is the freeze frame. |
| 12 | Safety commands (200 ms) | plan lookup, no solver on the path | not addressed | A.8: "safety commands (stop, hold, secure) 200 ms" | **S.** Precomputed plan, answered from a table. |
| 13 | Acoustic link | simple drop model (manoeuvre, deck machinery, layering) | not modelled | A.5; "the vehicle holds depth before the acoustic link breaks" | **S.** Three-condition boolean plus a drop delay; enough for the sentence. |
| 14 | Simulator | 10 Hz, scenario as data, time-scale ≈ 6 s per ship-minute | 1 Hz proposed, ≈ 5 s per ship-minute, event timeline as data | "small deterministic simulator consuming an event timeline" | **L at 1 Hz.** 10 Hz buys nothing the jury sees. |
| 15 | Stale numbers | hangar 900 kg; G2–G5 arithmetic; A/B figures under S's envelope rule | hangar 850 kg (organisers' correction, DEC-22); oracles under DEC-35 | updated Hack Pack is the source of truth | **L.** Use `docs/EXPECTED_OUTCOMES.md` and `tests/oracles/`; discard S's figures. |
| 16 | Prior art | PMS preferential trips, NAVSEA "smart load shedding", Mitra & Venayagamoorthy 2009 (cite only) | shipboard procedures and accident lessons in `research/` | README ≤ 3 pages | **Both.** Two sentences in the README: the governor is the mission-aware, explainable version of the preferential-trip ladder sailors already have. |

## 4. Open: Scenario B, minute 12

With L's load-out the trip at minute 12 does not bite: G4 35 + G5 45 + G3 at depth 1 = **81 kW against a
95 kW gate** (min(100, cooling 133 kW at 24 °C) − 5 kW headroom). The brief's 105 kW needs G3 charging at
minute 12, but its own minute-8 story has G3 holding depth (survey) or being recovered after G4 lands (SAR;
flight deck and ramp are mutually exclusive). L's DEC-40 therefore shows "holds, 0 steps, armed ladder" at
12 and sheds at a labelled pump fault at 19. Honest, but the must-have reads "min-12 explicit shedding sequence".

Recommendation, in order:

1. **Ask the organisers today**: "At minute 12, is G3 charging? Your 105 kW sum says so; your minute-8
   narrative says it is at depth." Their answer sets the timeline and goes into the Physical Account.
2. If no answer: keep DEC-40 and make the minute-12 sentence carry the must-have: *"Holds: 81 of 95 kW with
   one genset down. G3's 25 kW charge (not interruptible) is NOT NOW until G4's fast charge ends at minute 37.
   Armed, in declared order: G5 → 8 kW low power (frees 37 kW, 70 % connectivity lost); G4 → 10 kW charge."*
   The armed ladder *is* the explicit sequence; the pump fault at 19 then runs it live.

## 5. Why cameras, smoke and computer vision come out

They were Logan's beyond-the-brief addition on Friday night (DEC-02, DEC-06), before the depth policy
(DEC-24), and were demoted twice since (equipment only, DEC-23; "not the hero", one replayed line, DEC-27).
The reasons given were honest: leaks and smoke where sensors are weak, proof of a clear deck at 0 crew, and
a use for the sponsor board's camera and NPU. None survives contact with the scoring:

- The governor's inputs are plant signals the ship already has: genset online/tripped, cooling nominal/−40 %,
  seawater temperature, deck clear/occupied, the drone's own battery report. Discrete, confirmed, instant.
- A camera is a slow, uncertain copy of the same signal: L's own design says a leak takes 10–60 s to grow
  visibly, the confidence index is uncalibrated, and the plant alarm is still required before anything is shed.
  So it never changes a decision; it adds a pipeline, a model, a licence check and a failure mode in front
  of a 2 s / 5 s budget.
- The one place it did real work (deck clear at 0 crew) is answered by A.6 itself.

Rule for the freeze: **inputs are confirmed, debounced plant signals; every decision is a freeze-frame record;
nothing on the 200 ms / 2 s / 5 s paths runs a solver or a model.**

## 6. The frozen design, in one picture

```
 ship.yaml (assumptions.yaml)   guests/G1..G6.yaml        missions/*.yaml (jury swaps this)
        └──────────────────────────┼──────────────────────────────┘
                                   ▼
                  LOADER: names checked against ship.yaml; bad file refused, old one kept
                                   ▼
           LEDGER (1 Hz) ──────────────────────────── SHIP STATE (A.6 FSM)
           capacity / committed / free / degraded     course, speed band, noise, deck,
           per class; power→heat 1:1; cooling(T);     emission, gensets, cooling;
           reserve(speed, gensets); lines; mass ×k     transition times; debounced faults
                                   ▼
   D1/D2 ADMIT+PLACE     D3 RIGHT OF WAY      D4 SHED LADDER        D5 CREW POLICY
   enumeration, judged   hard limits first,   declared order,       rule × crew level →
   at envelope (30 s)    then weights (2 s)   throttle first,       confirm / automatic /
                                              precomputed (5 s)     forbidden
                                   ▼
            DECISION RECORD → EXPLAINER (templates over record fields) → REPLAY
                                   ▼
            SIMULATOR (seeded, event timeline as data) → ONE SCREEN (schematic, 8 gauges, log)
            tools/physical_account.py → Annex C, closing answer from binding-class counts
```

## 7. Build order once frozen

Typed conditions (delta 2) → ledger → Scenario A against `tests/oracles/` → simulator + D3 → D4 → screen →
replay → README, memo, Physical Account. Done means: the hostile priority file is refused with the expected
errors; the two priority files give the two Scenario B outcomes; A3 names cooling at 30 °C; N replays give
identical logs; every sentence is template-filled; Annex C is generated, not typed.

## 8. Decisions requested

| # | Decision | Proposed |
|:--|:--|:--|
| F1 | Base and cut list (deltas 1, 8, 9, 10) | L as base; cut CV, 3D, rule compiler, paraphraser, person detection, NPU, failover; board as instrument |
| F2 | Typed conditions before engine code (delta 2) | yes |
| F3 | Priority file gains `shed_order` and per-rule `confirm` (delta 3) | yes, both optional |
| F4 | Scenario B minute 12 (§4) | ask organisers; fallback as written |
| F5 | Scenario C rule (delta 7) | R3 without the camera |
| F6 | Who builds what | after F1–F5; the engine is one track, screen and docs another |
