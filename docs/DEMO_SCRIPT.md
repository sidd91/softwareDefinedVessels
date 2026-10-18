# Demo storyboard (draft for team review)

Status: draft, updated Sat 12:43 PDT. Drafted by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka).
Built on WORKLOG DEC-26: two deep examples, Scenario B with a live priority swap and Scenario A with
the jury's card, and everything else as one-line breadth. Aligned with the design freeze (DEC-44):
no cameras, webcam or failover beats; rule R3 runs on the landing officer's report and, with nobody
aboard, on the deck state latched at the last crew sweep. The two rule R3 breadth lines (landing zone
not clear, crew dial) run as one fixed segment of about 15 s after Scenario A, because the Scenario C
memo promises them live at 14, 6 and 0 aboard (review finding demo-10). Nothing here is built yet.

The brief's format: a live demo on our laptop, **90 s of Scenario B, then Scenario A with the jury's
card**; the jury picks the priority set for B and a card (possibly with one number changed) for A. A
backup recording is welcome but does not replace the live run. Our order: Scenario B (90 s), Scenario
A, then the Scenario C segment (about 15 s). The laptop provides every input (the genset trip, the
jury's one-number edit, the landing officer's report); a board button or knob may only mirror them,
and nothing in the demo depends on the board.

## Scenario B load-out (decided, WORKLOG DEC-32)

The brief's narrative has G2, G3, G4 and G5 aboard together: 13.015 t against the 10 t mass margin, and
Bay 2 needed twice. At the pier the governor refuses that load-out, names mass as the binding line, and
recommends the feasible alternative G3, G4, G5 (9.515 t), which drops the ocean module. A captain can force
a refused load-out with a logged override for extreme situations; the record keeps the binding line and
marks the decision as overridden. The demo runs G3, G4, G5.

## Scenario B, 90 s (deep)

Simulated time runs fast: the simulator ticks once per second of ship time, shown at about 5 s per ship
minute (about 12 minutes of ship time in about 60 s). Decisions run in real time and show their latency
against the ceiling. Location: Strait of Sicily cable corridor, 24 °C water.

Decided as WORKLOG DEC-40; event timeline in `config/scenarios/scenario_b.yaml`. Faults enter as
debounced, confirmed plant signals, and every record shows the raw-event and confirmation times.

| Clock | Ship time | What happens | Survey file | Rescue file |
|---|---|---|---|---|
| 00:00 | min 0 | Baseline as in the brief: 3 kn over the cable route, 24 °C water, G3 on its 40-min leg, G4 airborne, G5 full | 48 kW | 48 kW |
| 00:10 | min 8 | G4 reports 18 % in 22 kn; G3's and G4's condition sets collide on screen | | |
| 00:12 | min 8 | D3 decides within 2 s; hard limit first (land by min 18.2) | G4 recovers; G3 holds depth, survey paused to min 23, leg re-run: 25-27 survey minutes lost | Survey suspended, ship free to manoeuvre, G4's 35 kW reserved first; G3's leg aborted: G3 holds at sea and is recovered over the ramp only after G4 has landed (flight deck and ramp are mutually exclusive, A.3) |
| 00:25 | min 8 | Swap to the other priority file, live (DEC-26); the Mission compare view shows the same event as two runs on one timeline, both records side by side | | |
| 00:40 | min 12 | Genset trips, confirmed on 2 of 3 plant signals; cooling nominal: ceiling 95 kW | 48 of 95 kW, holds (G4 airborne at 2 kW) | 81 of 95 kW, holds (G4's 35 kW reserved) |
| 00:42 | min 12 | D4 runs within 5 s: 0 steps needed, every loss "none", the whole armed ladder in order (the brief's explicit sequence, R-067) and why the brief's 105 kW case does not arise, in the record's own sentence | "Holds: 48 of 95 kW with one genset down, 0 steps, no capability lost. Armed in priced order: G5 full to low power, 45 to 8 kW, frees 37 kW (70 % lost), then G5 low power to off, 8 to 0 kW, frees 8 kW (30 % lost), then G4 standby to off, 2 to 0 kW, frees 2 kW (30 % lost). The envelope case does not arise: G3 charging 25 kW, G4 fast charge 35 kW and G5 full 45 kW would be 105 kW against the 95 kW limit, but G3 is holding depth in standby (1 kW) and G4 is airborne in standby (2 kW)." (G5's step at 0.0038 per kW; G4 has no charge to throttle) | "Holds: 81 of 95 kW with one genset down and G4's 35 kW reserved, 0 steps, no capability lost. Armed in priced order: G5 full to low power, 45 to 8 kW, frees 37 kW (70 % lost), then G5 low power to off, 8 to 0 kW, frees 8 kW (30 % lost), then G3 standby to off, 1 to 0 kW, frees 1 kW (30 % lost). The envelope case does not arise: G3 charging 25 kW, G4 fast charge 35 kW and G5 full 45 kW would be 105 kW against the 95 kW limit, but G3 is holding at sea in standby (1 kW)." (G5's step at 0.0189 per kW; the live run prints the moves without the kW ranges) |
| 00:48 | min 12-17 | Fast-forward: G4 lands at min 17 and fast-charges | 81 of 95 kW | 81 of 95 kW |
| 00:55 | min 19 | INJECTED EVENT, labelled: chilled-water pump 1 fails, confirmed by the plant alarm plus flow or delta-T. Loop 133.3 to 80 kW; ceiling 75 kW; cooling binds, not power | 81 against 75 | 81 against 75 |
| 00:57 | min 19 | D4 walks the same ladder: first action within 5 s, done within 60 s | G4 charge to 10 kW: 56 of 75; G4 loses 30 % | G5 to low power: 44 of 75; G5 loses 70 % |
| 01:05 | min 24 (optional) | Genset restarts: nothing given back, cooling still binds for the voyage | 56 | 44 |

The exact shed order comes from the ledger and the active priority file, not from this script. Neither
priority file declares a `shed_order`, so both ladders are priced. At minute 19 survey takes G4's charge
first because G4 has landed and is charging (0.0024 per kW, cheaper than G5's 0.0038); at minute 12 that
step does not exist yet.

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
  window and, at 0 crew, a logical reconfiguration instead.

## Scenario C, rule R3 at 14, 6 and 0 aboard (fixed, about 15 s)

Still breadth under DEC-26: two one-line examples, landing zone not clear and the crew dial, shown
together at three crew levels. It delivers the [Scenario C memo](SCENARIO_C_MEMO.md)'s "Live demo"
section exactly. It replays Scenario B from minute 8 with the same seed and the jury's priority file;
the screen labels it **replayed**. The landing officer's reports are single keys on the laptop. The 90 s
Scenario B table above is unchanged.

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
- Time the Scenario C segment in every rehearsal. The 14-aboard beat is two key presses, "not clear"
  then "clear"; if the segment still runs past about 15 s, budget about 20 s rather than rush the bridge
  sentence.
- Rehearse five times on Sun morning; freeze at 09:15 PDT.

## Open questions for the team

1. Decided (DEC-32): Scenario B runs G3, G4, G5; the full load-out is refused at the pier with an override available.
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
