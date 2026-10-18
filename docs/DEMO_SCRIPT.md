# Demo storyboard (draft for team review)

Status: built and measured. Drafted Sat 12:43 PDT by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka);
the Scenario B run sheet, the presenter rules and the T-30 checklist were written Sat 22:41 PDT from the
rehearsal of origin/main 918478a ([DEMO_READINESS.md](DEMO_READINESS.md)) by Claude Fable 5.1 on behalf of
Siddharth Chawla (sidd91) and re-checked in review Sat 23:10 PDT on origin/main 6a91f5d (integrate/fix-pack-2).
Built on WORKLOG DEC-26: two deep examples, Scenario B with a live priority swap and Scenario A with
the jury's card, and everything else as one-line breadth. Aligned with the design freeze (DEC-44):
no cameras, webcam or failover beats; rule R3 runs on the landing officer's report and, with nobody
aboard, on the deck state latched at the last crew sweep. The two rule R3 breadth lines (landing zone
not clear, crew dial) run as one fixed segment of about 15 s after Scenario A, because the Scenario C
memo promises them live at 14, 6 and 0 aboard (review finding demo-10). Scenario B, the Mission compare and
Scenario A run live under `uv run sdv demo`; the Scenario C segment is not driven live on this build (see its
section).

The brief's format: a live demo on our laptop, **90 s of Scenario B, then Scenario A with the jury's
card**; the jury picks the priority set for B and a card (possibly with one number changed) for A. A
backup recording is welcome but does not replace the live run. Our order: Scenario B (90 s), Scenario
A, then the Scenario C segment (about 15 s). The laptop provides every input (the genset trip, the
jury's one-number edit, the landing officer's report); a board button or knob may only mirror them,
and nothing in the demo depends on the board.

## Scenario B load-out (decided, WORKLOG DEC-32)

Decided by DEC-63, which supersedes the G3, G4, G5 set of DEC-32: the demo runs **G1, G3, G4, G5**, the
organisers' load-out (Software-Defined Vessel forum, thread "Scenario B loadout", 17 Oct; question by Filip
Debef 08:22, answer by Graziano 08:55: "Use G1 + G3 + G4 + G5 for Scenario B ... G3 in Bay 1, G5 in Bay 2,
G1 on the mast, G5's antenna on the hangar roof. The Annexes take precedence over the demo narrative").
Mass 9.56 t of 10, stability 9.853 t-eq of 12 (G1's 45 kg on the mast counts x3, the antenna on the roof
x1.2), the mast full at 3 of 3. G1 is air-cooled: it draws 1.5 kW on the bus and nothing on the chilled-water
loop, so the POWER tile reads 1.5 kW above the COOLING tile from minute 0 (49.5 against 48 kW). The brief's
narrative set G2, G3, G4, G5 (13.015 t, Bay 2 needed twice) is still refused at the pier, mass the binding
line; a captain can force a refused load-out with a logged override for extreme situations, and the record
keeps the binding line and marks the decision as overridden.

## Scenario B, 90 s (deep)

Simulated time runs fast: the simulator ticks once per second of ship time, shown at about 5 s per ship
minute (about 12 minutes of ship time in about 60 s). Decisions run in real time and show their latency
against the ceiling. Location: Strait of Sicily cable corridor, 24 °C water.

Decided as WORKLOG DEC-40; event timeline in `config/scenarios/scenario_b.yaml`. Faults enter as
debounced, confirmed plant signals, and every record shows the raw-event and confirmation times.

Every wall-clock figure below was measured on origin/main 918478a at x12 (5 s per ship minute;
[DEMO_READINESS.md](DEMO_READINESS.md), section 2). A straight RESTART does not fit 90 s: minute 8 arrives at
41 s, minute 12 at 61 s and minute 19 at 96 s. The JUMP keys put all three records on screen in 35 s and the
rest is dwell; each JUMP lands 3 s before its event. The live priority swap applies from the next tick on: the
minute-8 record already on screen keeps its file, and a JUMP back rebuilds the run from tick 0 under the start
file and drops the swap. So the jury's file goes in force before RESTART, and the two-ships beat is the Mission
compare view.

| Clock | Key | Ship time | What happens, what to say | Survey file | Rescue file |
|---|---|---|---|---|---|
| -0:10 | PRIORITY RESCUE (the jury's file) while the clock runs | before T+0 | Applies next tick, 0.1 to 0.3 s: the header reads MISSION RESCUE · PRIORITY sar.yaml VALID and the SHED ORDER panel retitles. Say: "Rescue file in force; same code." Not while HELD or at T+20:00 (see Presenter rules). | | |
| 0:00 | RESTART | min 0 | First T+0 frame after 1.1 to 1.2 s. Baseline as in the brief: 3 kn over the cable route, 24 °C water, G1 listening on the mast, G3 on its 40-min leg, G4 airborne, G5 full. Say: "Eight gauges steady: 48.0 / 128.3 kW cooling, 49.5 / 245.0 kW power (G1's 1.5 kW is air-cooled, on the bus and not on the loop), 9.560 / 10.000 t, mast 3 / 3." | 49.5 kW (48 on the loop) | 49.5 kW (48 on the loop) |
| 0:00 to 0:05 | let it run | min 0 to 1 | The clock, the ship-state chips and G4's LAND BY countdown move; the tiles are step functions that move at events (DECK, MAST, MASS / STAB and COMPUTE never move in Scenario B: nothing is reconfigured). | | |
| 0:06 | JUMP 08 | min 8 | Freeze 1.2 to 1.4 s, lands at T+07:57. G4 reports 18 % in 22 kn; G3's and G4's condition sets collide: four CONFLICT rows (SPEED 3.0 kn now, G3 needs 3.0 kn, G4 needs 5 TO 12 kn; DECK MACHINERY OFF against ON; HEADING STEADY against FREE; EXCLUSION G3 SURVEYING EXCLUDES G4 LAUNCH RECOVERY). | | |
| 0:08 | the D3 record | min 8 | D3 decides within 2 s (measured 0.4 to 0.5 ms against 2.0 s); hard limit first: G4 BATT < 20 % · LAND WITHIN 12 min, LAND BY 00:18:12 · T-10:06 (counting down). Read the record's sentence; point at the CONFLICT rows, LAND BY and RESPONSE. The R3 block reads CREW 14 CONFIRM 00:08:00 and G4 must land by minute 18.2. | G4 recovers; G3 holds depth, survey paused to min 23, leg re-run: COST G3 SURVEY LOSS 25 TO 27 min | G4 recovers first; G3's leg aborted: G3 holds at sea and is recovered over the ramp only after G4 has landed (flight deck and ramp are mutually exclusive, A.3); COST OPEN-ENDED, RESERVED G4 35 kW. The release to manoeuvre is on the chips (COURSE FREE, SPEED 5.0 kn by minute 12), not in the sentence. |
| 0:08 to 0:25 | dwell, about 20 s | min 8 to 10 | Let the jury read the record. | | |
| about 0:25 | JUMP 12 | min 12 | Freeze 0.4 to 0.7 s. Genset trips, confirmed on 2 of 3 plant signals: TRIGGER GEN 2 TRIP · 00:12:00, log "Trip confirmed 2 of 3 at 00:12:01"; cooling nominal, LIMIT 100.0 - 5.0 = 95.0 kW. | 49.5 of 95 kW, holds (G4 airborne at 2 kW): 45.5 kW SPARE | 82.5 of 95 kW, holds (G4's 35 kW reserved): 12.5 kW SPARE |
| 0:26 | the D4 HOLD record | min 12 | D4 within 5 s (measured 0.5 ms): 0 steps, every loss "none" (G1 included), the whole armed ladder in order (the brief's explicit sequence, R-067, DEC-61; G1 to off is the last 5 S step, the mission-critical 60 S guest last) and why the envelope case, 106.5 kW with G1, does not arise, in the record's own sentence (on main since 1148d11; an older build stops at the first armed step: then say the minute-12 line under Presenter rules). | "Holds: 49.5 of 95 kW with one genset down, 0 steps, no capability lost. Armed in order: G5 full to low power, frees 37 kW (70 % lost), then G5 low power to off, frees 8 kW (30 % lost), then G4 standby to off, frees 2 kW (30 % lost), then G1 full to off, frees 1.5 kW (100 % lost), then G3 standby to off, frees 1 kW (30 % lost). The envelope case does not arise: G1 full 1.5 kW, G3 charging 25 kW, G4 fast charge 35 kW and G5 full 45 kW would be 106.5 kW against the 95 kW limit, but G3 is holding depth in standby (1 kW) and G4 is airborne in standby (2 kW)." | "Holds: 82.5 of 95 kW with one genset down, 0 steps, no capability lost. Armed in order: G5 full to low power, frees 37 kW (70 % lost), then G5 low power to off, frees 8 kW (30 % lost), then G3 standby to off, frees 1 kW (30 % lost), then G1 full to off, frees 1.5 kW (100 % lost), then G4 standby to off, frees 2 kW (30 % lost). The envelope case does not arise: G1 full 1.5 kW, G3 charging 25 kW, G4 fast charge 35 kW and G5 full 45 kW would be 106.5 kW against the 95 kW limit, but G3 is holding at sea in standby (1 kW)." |
| 0:26 to 0:45 | dwell | min 12 to 16 | Nothing is shed; the ladder stays armed with each guest's loss (70 % / 30 %, G1 off 100 % for 1.5 kW), footer ORDER COMPUTED · CLASS, THEN LOSS PER kW. G4 lands at min 17 and fast-charges (82.5 of 95 kW under both files, 81 on the loop); the next jump passes it. | | |
| about 0:45 | JUMP 19 | min 19 | Freeze 0.9 to 1.2 s. INJECTED EVENT, labelled in four places (trigger, plant cell, COOLING tile, log): chilled-water pump 1 fails, confirmed by the plant alarm plus flow or delta-T. Loop 133.3 to 80 kW, limit 75 kW; cooling binds on the loop's 81 kW (G3 1 + G4 35 + G5 45), not power: the bus is at 82.5 of 95, G1's 1.5 kW air-cooled and never on the loop (DEMAND 81.0 kW CHW · 82.5 kW TOTAL). | loop 81 against 75 (bus 82.5 of 95) | loop 81 against 75 (bus 82.5 of 95) |
| 0:46 | the shed | min 19 | D4 walks the same ladder: commanded at 0:46, the record's tag EXECUTED one tick later (83 ms), first action within 5 s (measured 0.5 ms), RECHECK 00:19:02 · HOLDS. Read the record's sentence (the loop's figures: "81 kW against the 75 kW limit ... the load is 56 kW"); point at INJECTED on the trigger, RESULT, the COOLING tile (the loop) and the POWER tile (the bus, CHW BINDS). | G4 fast charge to charge, frees 25 kW: RESULT 56.0 / 75.0 kW (POWER 57.5 / 95.0); G4 loses 30 % (CAP 100 → 70 %), G1, G3 and G5 nothing | G5 full to low power, frees 37 kW: RESULT 44.0 / 75.0 kW (POWER 45.5 / 95.0); G5 loses 70 % (CAP 100 → 30 %), G1, G3 and G4 nothing |
| 0:46 to about 1:20 | dwell | min 19 to 20 | T+20:00 ends the run (END_T_S); with the dwells above it arrives by about 1:20. DEC-40's optional minute-24 genset restart is not in the live run. | 56 of 75 kW on the loop; POWER 57.5 / 95.0 kW, USABLE 19.0 kW · CHW BINDS | 44 of 75 kW on the loop; POWER 45.5 / 95.0 kW, USABLE 31.0 kW · CHW BINDS |
| +20 s if wanted | MISSION COMPARE tab; click 00:08, then 00:19 on the timeline | | The two-ships beat: the same inputs under both files side by side, each with its sentence, CONFLICT table, CHW and POWER bars and guest table, and the DIFFERENCE table SAME INPUTS · PRIORITY FILE ONLY (instant; /api/compare 10 ms, from two reference runs the live swap cannot touch). | DECISION HOLDING DEPTH, LEG PAUSED, RESERVED --; at 00:19 FREED 25, RESULT 56, CAPABILITY G1 100 % · G3 30 % · G4 70 % · G5 100 % | HOLDING AT SEA, LEG ABORTED, RESERVED G4 35 kW; at 00:19 FREED 37, RESULT 44, CAPABILITY G1 100 % · G3 30 % · G4 100 % · G5 30 % |

The exact shed order comes from the ledger and the active priority file, not from this script. Neither
priority file declares a `shed_order`; D4 orders the ladder by response class, throttle before shed, then the
declared order, then mission value lost per kW freed (DEC-60). At minute 19 survey takes G4's charge
first because G4 has landed and is charging (0.0024 per kW, cheaper than G5's 0.0038); at minute 12 that
step does not exist yet.

### Presenter rules

Measured Sat 22:00 PDT on 918478a ([DEMO_READINESS.md](DEMO_READINESS.md), section 4). A rule that starts
"until X is merged" falls away when that branch lands; the others stay true on tonight's main. At Sat 23:10 PDT
origin/main 6a91f5d (integrate/fix-pack-2, 22:46 PDT) carries fix/jury-power-edit, fix/crew-chip-guards and
fix/live-run-log, so those three rules fall away on a freeze at or after 6a91f5d; fix/jury-card-file is pushed and
reviewed but not merged; fix/simbar-clicks is not on origin. On the frozen commit, `git branch -r --merged HEAD`
lists the fix branches it contains.

Do not, on stage:

- Open the page cold in front of the jury: a cold start builds the two reference runs, 4.1 s with the page blank.
  Have it at LINK UP with the clock running before the jury arrives.
- Press F5 or reload: the page comes back at T+00:00 under SURVEY, running, x12. Restart the engine mid-run after
  a swap: the run is rebuilt under the file in force, the minute-8 record becomes the rescue outcome and the
  "sar.yaml in force" log line disappears. Laptop inputs (the swap, the crew chip) are not replayed.
- Double-click JUMP or touch anything during a freeze (RESTART 1.1 to 1.2 s, JUMP 08 1.2 to 1.4 s, JUMP 12 0.4 to
  0.7 s, JUMP 19 0.9 to 1.2 s, JUMP 08 back from 15:36 2.5 s): the jump runs synchronously in the websocket
  coroutine, every browser on the server freezes together, and a second click costs a second freeze.
- JUMP 08 after a mid-run swap: the swap is dropped, SURVEY decides again and it looks as if the swap did nothing.
  Swap only as PRIORITY, watch the header flip, RESTART; or use Mission compare.
- Press PRIORITY while HELD or at T+20:00 and then RESTART: until fix/live-run-log is merged it restarts under the
  old file. Watch the header flip to the new MISSION first.
- Use x60: pace clicks fail while it runs (one took 14 s of retries); x12 is the rehearsed pace.
- Until fix/simbar-clicks is merged, expect a normal click on JUMP, PACE, PRIORITY or the crew chip to land at x12:
  the SIM bar is re-rendered 12 times a second and a 90 ms press registered 0 of 12. HOLD (Space), click,
  RUN (Space). HOLD/RUN is the measured static button (10 of 10).
- Undo an Admission edit by retyping the original value: the verdict stays flipped. Press REVERT.
- Until fix/jury-power-edit is merged, edit a power number anywhere: G4.consumes.power_kw.peak=50, nominal=60,
  peak=500 and G5 nominal=60 crash D1 (StopIteration: CLI exit 1, HTTP 500), and a hand-typed field path
  (G4.nope.x=1, G4.modes.0.power_kw=50) crashes the CLI. On screen the only inputs are the DRONE and HANGAR
  mass_t; on the CLI stay with mass_t, cooling, area_m2 and peak_duration_s. Once merged: any card number decides
  or is refused with the field named (CLI exit 2, API 422, previous verdict kept) and the screen offers NOMINAL and
  PEAK kW inputs.
- Until fix/jury-card-file is merged, put a jury YAML into manifests/: the loader refuses the whole set ("id: G7
  has no activity registry in config/signals.yaml") and `sdv demo` and `sdv admit` die at start-up until the file
  is removed. A new card runs on the CLI: add its id to config/signals.yaml activities (copy the closest guest's
  block), then `uv run sdv admit G7 --installed G4,G5 --mission disaster_relief` (1.6 ms measured). The Admission
  tab offers its 14 pre-baked cases only. Once merged (pushed as be7b83a, reviewed 2419405, 14 tests; not on main
  at 23:10 PDT): `uv run sdv admit --card path/to/G7.yaml --installed G4,G5 --mission disaster_relief` admits the
  file from where it is, a schema or vocabulary problem is refused with the field named (exit 2), a card whose
  activities are not registered is judged on its quantities, positions and relations and the output says so, and a
  bad file in manifests/ is reported once at start and skipped.
- Until fix/crew-chip-guards is merged, click the crew chip: to 6 before minute 9 the test double crashes on the
  scripted bridge answer and the browser silently reconnects into a fresh 14-aboard run; after minute 9 it only
  changes the label. Once merged (on origin/main since 6a91f5d), the chip holds or forbids the recovery with its
  reason and never crashes: 6 aboard before minute 9 gives "Recovery held at 6 aboard: no standing plan approved.
  G4 must land by minute 18.2." (seen on 6a91f5d: CREW 6 · R3 STANDING PLAN in the header, LINK UP, no error
  frame) and 0 aboard "Recovery forbidden at 0 aboard: …" with the deck state in the evidence. Either way the
  landing officer's report, the deck sweep and the standing plan have no screen control (the only key is Space):
  14 aboard is what is rehearsed, and the Scenario C segment is spoken from the memo, not driven.
- Pipe the CLI fallback: `uv run sdv run --mission sar --pace 12 | tail` shows nothing for 20 s (block-buffered).
  Run it in a TTY at 20 pt and 100 columns and accept the wrap: header at +2 s, first decision at +42 s, full run
  100 s.
- Ask the screen for Scenario A-prime: `card_presented` is not a laptop input, the Admission header is hard-coded
  ALONGSIDE · SHORE POWER and the engine returns yes, yes-if or no. Answer in words (below).

Spoken lines, each built from what the record shows:

- **Minute 12, fallback.** On main since 1148d11 the HOLD record's own sentence states the ladder and the
  envelope case; if the build on the laptop stops at "First armed step", say this with the HOLD record on screen
  (RESCUE file; survey numbers in brackets): "Gen 2 tripped at 00:12:00, confirmed 2 of 3 at 00:12:01. The limit
  is 100.0 - 5.0 = 95.0 kW. The governor holds at 82.5 of 95 kW [49.5 of 95] with one genset down: 0 steps, no
  capability lost, 12.5 kW spare [45.5], decided in 0.51 ms against the 5.0 s ceiling. The brief's 105 kW case, 106.5 with G1,
  (35 + 45 + genset-halved) does not occur on this ship because G4 is airborne drawing 2 kW with its 35 kW charge
  only reserved [never reserved under survey], and G3 is at sea on its own battery. The ladder is armed in the
  file's order, class first then loss per kW: G5 full to low power frees 37 kW at 70 % loss, G5 low power to off
  frees 8 kW at 30 %, G3 standby to off 1 kW [G4 standby to off 2 kW], G1 full to off 1.5 kW at 100 % (air-cooled,
  it helps the bus only), and G4 [G3] is mission-critical and last.
  Nothing is shed now; the executed shed comes at minute 19 on a pump fault we inject and label INJECTED (DEC-40)."
- **Scenario A-prime, if asked.** "Admission under way is designed, not built: every card carries its installation
  windows in the installation.at_sea block (Reference tab), but the governor today returns yes, yes-if or no, and
  'not now, at the next port call' exists only as a sentence template with no live producer."
- **"Is the plant real?"** "No: LIVE · SIM TEST DOUBLE in the SIM bar means the plant is tests/support/sim_stub.py,
  a scripted Scenario B model of the brief's A.6 states built from the frozen signal contract, with no ship physics;
  a simulator is swapped in through SDV_SIM, and the team's own simulator sits on feat/ship-state-fsm, not merged."
- **"Why LOS 0 / 20 · ACOUSTIC DOWN at minute 19?"** "LOS is demand over capacity: G4 drew 20 of 20 Mbit/s of
  line-of-sight radio while airborne and nothing once it landed; ACOUSTIC DOWN is rule A.5 as a state check, the
  link is up only on a steady course, quiet, with no deck machinery, and the ship has been manoeuvring for the
  recovery since T+09:06 (the tile shows ACOUSTIC DOWN from then under both files, reason 'course free,
  noise manoeuvring'; under survey at minute 19 'course free, settling to steady, noise normal'); the tile's state
  reads REDUCED from minute 0 because SATCOM demand at nominal, G5's 6 plus G1's 0.2 Mbit/s, is 6.2 of the 6.0 Mbit/s
  live link (admission judged the minimums, 1.2 of 2, DEC-38; the guests are carried at reduced rate), LOS is
  within capacity, and the acoustic state does not enter the tile."
- **"What capability was lost?"** The record states it as a mode change and a percentage (G4 FAST CHARGE → CHARGE
  · CAP 100 → 70 %; G5 FULL → LOW POWER · CAP 100 → 30 %), not as a named capability; the brief's ocean module is
  absent because G2 is not aboard (DEC-32, DEC-63); G1's RF detection is kept whole (G1 NONE in every LOSS row).

## Breadth strip (one line each, about 5 s each)

Each line is labelled **live** or **replayed** on screen. The two R3 lines run together as the fixed
Scenario C segment after Scenario A. The other four are the pool to pick from on the day; while
emission silence is open, the pool is three.

- **Crew dial 14 / 6 / 0 (rule R3, replayed):** what the bridge confirms, what is a standing plan, what
  is automatic or forbidden; see the Scenario C segment.
- **Landing zone not clear (rule R3, replayed):** the landing officer reports the zone not clear, and
  recovery is held within 200 ms with its sentence; see the Scenario C segment.
- **Over-consuming guest:** G5 draws 15 % over its declaration and is throttled with a sentence.
- **Emission silence (open design question, OPEN_QUESTIONS #42):** SATCOM and radio drop to zero; G4
  returns home and demands a clear deck. Not shown until #42 decides which wins.
- **Mission sets:** four priority files (survey, rescue, patrol, disaster relief) on one hull.
- **Data feed drops:** G4's battery telemetry goes stale (over 10 s); the governor falls to the
  conservative value, the earliest 20 % crossing the last reading allows, and says so in one sentence
  (R-458).

## Scenario A, jury's card (deep)

The ship is alongside on shore power; three guests are installed, and the jury presents a fourth card
and may change one number. Verdict within 30 s, judged against the mission envelope, not the pier. The
card and its edit are entered on the laptop, in the Admission review view.

| Step | What the governor shows |
|---|---|
| Card loaded, one number edited live | The edited value highlighted; the manifest re-validated |
| Verdict | yes, no, yes-if or not-now, with the binding resource class named in one sentence |
| Placement | Which bay, mast slot or deck position, and the rejected alternatives |
| Yes-if | A ranked list of what to displace or throttle and the capability lost |
| Degraded check | Three states (DEC-35): holds; holds by throttling, naming the guest, kW freed and capability lost, automatic within 5 s; or does not hold, so the guest to remove joins the yes-if list |
| Tipping point | The seawater temperature at which the verdict flips |

Prepared drills (the jury chooses, but we rehearse these):

- **The 35 kg case:** installed G1, G2, G3; card G4. Mass 10.035 t against 10 t: refused by 35 kg;
  yes-if G1 disembarks. Changing the hangar to 800 kg flips it to yes.
- **The free mast slot:** installed G2, G3, G4; card G1 or G5. G1 fits the free mast slot, but G1 to G4 together weigh 10.035 t against 10 t (the 35 kg case again), so it is yes-if one guest disembarks; G5 (13.015 t, 3.0 t over) is yes-if G2 or G3 leaves (ranked by the priority file), and its antenna has
  the mast or the hangar roof, but its node has no bay. Mass binds; cooling at 30 °C (125 against 120 kW)
  is listed as also failing.
- **The bay story:** installed G1, G2, G5; card G3. Two lines bind: G3 needs all of Bay 1, and the four
  weigh 12.07 t against the 10 t margin. Yes-if G5 leaves (9.045 t) or G2 leaves (8.57 t, G5 moves to
  Bay 2, Arch Q4), ranked by the active priority file.
- **Scenario A-prime (if time):** the same card under way gets "not now", with the next installation
  window and, at 0 crew, a logical reconfiguration instead. Not built: answer in words (Presenter rules).

## Scenario C, rule R3 at 14, 6 and 0 aboard (fixed, about 15 s)

Still breadth under DEC-26: two one-line examples, landing zone not clear and the crew dial, shown
together at three crew levels. It delivers the [Scenario C memo](SCENARIO_C_MEMO.md)'s "Live demo"
section exactly. It replays Scenario B from minute 8 with the same seed and the jury's priority file;
the screen labels it **replayed**. The landing officer's reports are single keys on the laptop. The 90 s
Scenario B table above is unchanged.

Status (Sat 22:00 PDT rehearsal): this segment cannot be driven live on tonight's main. No laptop key enters the
landing officer's report (the only key is Space, HOLD/RUN), and the crew chip is 14 aboard on stage until
fix/crew-chip-guards is merged. With that fix merged (origin/main 6a91f5d, Sat 22:46 PDT) the chip goes to 6 and 0
aboard without a crash and the recovery record states the hold or the prohibition (Presenter rules), but the
landing officer's report still has no key and the chip beat has no run sheet or rehearsal. Speak it from the
[memo](SCENARIO_C_MEMO.md) over the minute-8 R3 block, or drop it; see Presenter rules.

| Clock | Aboard | What happens | What the governor shows |
|---|---|---|---|
| +00 | 14 | Replay from min 8 in fast-forward; it slows to real time once the zone is clear at min 13 (8 + 1 + 4, seed) | R3 window opens at min 8 with the D3 recovery decision, which is the recall and comes before the drain-trend opening at min 8.2: clear-deck call with the bridge's confirm button, confirmed (seed: 1 min); crew clear and sweep (seed: 4 min) |
| +03 | 14 | The driver enters the landing officer's report "zone not clear", holds while the sentence is read, then enters "clear" | "Landing zone not clear": recovery held within 200 ms, latency shown against the ceiling, with its bridge sentence; "clear" report: released |
| +08 | 6 | Crew dial to 6; same replay | No confirm button: the standing plan approved at launch is shown; the log shows a 3 min deck work request at min 3 (INJECTED event, labelled) refused, "not now; when: after G4 is secured", where the 14 run allowed it because it ends before the window opens |
| +11 | 0 | Crew dial to 0; same replay, deck latched clear at handover | Recovery automatic, with no confirm or override button |
| +13 | 0 | Same replay with deck activity reported after the sweep (INJECTED event, labelled) | Latch void: recovery forbidden; the record states the cost to G4 (below 20 %: land within 12 min or ditch) |
| +15 | | End of the demo | |

Numbers: in Scenario B the clear-deck call starts at min 8 with the D3 recovery decision, because that
recall comes before the drain-trend opening. With the seed's confirm and clear times (`seed_pins` in
`config/scenarios/scenario_b.yaml`) the zone is clear at min 13 (8 + 1 + 4) and G4 lands at min 17
(DEC-40). Min 8.2 and the 12 s margin are the memo's, kept only as the latest the window could open
without the recall (deadline min 18.2, 4 min approach, 6 min lead at 14). The min-3 deck work request
and the deck activity after the sweep exist only in this replay. The memo states no duration for this
segment, so its timing lives here.

## Rehearsal and fallbacks

- Fixed seeds and cached public data, so every run decides the same way; the backup recording is made
  from a rehearsal run.
- The demo needs only the laptop. If the board is on the table, it only mirrors laptop inputs; unplug it
  if it misbehaves.
- The Scenario C segment is not driven live on tonight's main (no key enters the landing officer's report; the
  crew chip is 14 aboard on stage until fix/crew-chip-guards is merged): budget about 15 s to say it from the memo
  over the minute-8 R3 block, or drop it.
- Rehearse five times on Sun morning; freeze at 09:15 PDT.

T-30 min checklist, from the laptop (measured Sat 22:00 PDT on 918478a, [DEMO_READINESS.md](DEMO_READINESS.md)
section 5; the laptop serves on port 8000, the port numbers in the scorecard are the dev box's):

1. `cd softwareDefinedVessels && git log -1 --oneline` shows the `submission` tag or the commit the team froze
   (918478a was audited; main has moved since). Wi-Fi may stay off.
2. `uv sync` prints "Audited 27 packages" in under 2 s. If "No interpreter found for Python 3.12 ... offline
   mode": connect to Wi-Fi once and rerun (cold: CPython 3.12.14, 104 MB, plus 27 wheels; 1.7 s on the dev box,
   1 to 3 min on conference Wi-Fi).
3. `uv run pytest -q` prints "1278 passed" or more (1278 on 918478a in 114 s, 1457 on 6a91f5d in 193 s; every
   merged fix adds its own tests). Skip if under 20 min are left.
4. Port 8000 free (`lsof -i :8000` prints nothing), then `uv run sdv demo` prints "ArgOS screen on
   http://127.0.0.1:8000/ (live); Ctrl+C stops it" (since fix/live-run-log, in 6a91f5d, followed by a LOGS line
   naming runs/live); /api/meta answers after about 4 to 6 s (5.4 s on 918478a, 4.1 s on 6a91f5d). Nothing opens
   the browser for you. If "address already in use" (exit 3): `uv run sdv demo --port 8010` and open that port, or
   `lsof -ti :8000 | xargs kill`.
5. Chrome, fresh window, http://127.0.0.1:8000: LINK UP at the top right, the clock ticking, and the chip at the
   bottom left of the SIM bar reading LIVE · SIM TEST DOUBLE. Zoom 125 % on a 1920x1080 projector, 110 % on
   1600x1000, 100 % on 1280x800; F11; sleep and notifications off.
6. Dry run: PRIORITY RESCUE (header MISSION RESCUE), RESTART, JUMP 08 (D3 record at T+00:08:00), JUMP 12 (D4 HOLD
   82.5 / 95 kW), JUMP 19 (SHED 44 / 75 kW); ADMISSION REVIEW case A1, hangar 0.8 gives YES, then REVERT.
7. LINK DOWN or a frozen clock: Ctrl+C, rerun step 4, wait 7 s (LINK UP after 3.6 to 4.5 s, first payload at
   6.5 s); the clock resumes at the same minute under the file in force. If a swap had been made, press RESTART
   and JUMP 08 again (10 s) instead of trusting the resumed record.
8. Blank page: Cmd+Shift+R, then http://localhost:8000. Last resort, a second terminal at 20 pt and 100 columns:
   `uv run sdv run --mission sar --pace 12` (first decision at +42 s; never through a pipe).
9. Live loop misbehaving: `uv run sdv demo --source fixtures` (ready in 1.4 s; the chip reads REPLAY, every SIM
   bar control works under the same click rule, HOLD, click, RUN, since a plain click is dropped at x12 here too,
   0 of 10 measured; no crew chip, no inputs) and say it is replayed. Laptop dead: play the backup recording from
   the second laptop or the phone. The rehearsal's silent 80 s headless recording (RESCUE, JUMP 08 to T+20:00 at
   x12, then Mission compare) is on the dev box, not in the repo; record the narrated one on the laptop after the
   last rehearsal (Cmd+Shift+5): Scenario B with the swap, then Scenario A.
10. Terminal on the laptop display, browser on the projector, this file open on the phone. On 918478a the server
    prints nothing while it runs (log level warning; only a bind error or an ASGI exception shows); since
    fix/live-run-log (in 6a91f5d) it prints one `RUN n under <file>.yaml logs to runs/live/live-<file>-n` line per
    run and a LAST RUN line on Ctrl+C, and any run it showed replays with `uv run sdv replay runs/live/live-<file>-n
    --mission <file>`. To keep the terminal's own log: `mkdir -p runs && PYTHONUNBUFFERED=1 uv run sdv demo 2>&1 |
    tee runs/demo-$(date +%H%M).log` (runs/ is git-ignored and absent in a fresh clone; without the mkdir, tee says
    "No such file or directory" and writes nothing).

## Open questions for the team

1. Decided (DEC-63, after DEC-32): Scenario B runs G1, G3, G4, G5, the organisers' set; the brief's narrative set is refused at the pier with an override available.
2. The breadth lines are settled (OPEN_QUESTIONS #13); how many to show on the day is open, and emission
   silence waits on #42.
3. Who drives the laptop and who talks?
4. Where does the breadth strip go? Proposal (OPEN_QUESTIONS #12): after Scenario A, beside the Scenario C
   segment; only data feed drops could run inside B, as a labelled INJECTED event. The two R3 lines are
   settled: the fixed segment after Scenario A.
5. DEC-40 counted the camera-leak foreshadow as one mitigation for the injected minute-19 fault looking
   staged; the cameras are cut (DEC-44). Show a plant-signal trend on pump 1 instead, let the jury
   trigger the fault, or rely on the INJECTED label and its sourcing alone? (Logan, DEC-40)
6. Minute 12 is Siddharth's to decide as owner of the simulator and scenario timing (DEC-51); DEC-40
   stands as above until he does. The organizers said only that there is some flexibility (DEC-49); a
   follow-up naming both readings is drafted in [ORGANIZER_MESSAGE.md](ORGANIZER_MESSAGE.md).
