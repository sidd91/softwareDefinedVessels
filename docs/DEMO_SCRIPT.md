# Demo storyboard (draft for team review)

Status: draft, Fri 23:56 PDT. Drafted by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka).
Built on WORKLOG DEC-26: two deep examples, Scenario B with a live priority swap and Scenario A with
the jury's card, and everything else as one-line breadth. Nothing here is built yet.

The brief's format: a live demo on our laptop, **90 s of Scenario B, then Scenario A with the jury's
card**; the jury picks the priority set for B and a card (possibly with one number changed) for A. A
backup recording is welcome but does not replace the live run.

## Scenario B load-out (decided, WORKLOG DEC-32)

The brief's narrative has G2, G3, G4 and G5 aboard together: 13.015 t against the 10 t mass margin, and
Bay 2 needed twice. At the pier the governor refuses that load-out, names mass as the binding line, and
recommends the feasible alternative G3, G4, G5 (9.515 t), which drops the ocean module. A captain can force
a refused load-out with a logged override for extreme situations; the record keeps the binding line and
marks the decision as overridden. The demo runs G3, G4, G5.

## Scenario B, 90 s (deep)

Simulated time runs fast (about 12 minutes of ship time in about 60 s); decisions run in real time
and show their latency against the ceiling. Location: Strait of Sicily cable corridor, 24 °C water.

| Clock | Ship time | What happens | What the jury sees |
|---|---|---|---|
| 00:00 | min 0 | Baseline: 3 kn over the cable route, G3 surveying on its acoustic link, G5 at 45 kW, G4 airborne on a SAR sortie | Schematic, eight gauges steady, priority file the jury chose, crew 14 |
| 00:10 | min 8 | G4 reports 18 % battery in 22 kn wind. G3's conditions (3 kn, steady, quiet, no deck machinery) and G4's (deck clear, 5-12 kn, turn into wind, ramp free) collide | The conflict appears as two condition sets, not an alarm |
| 00:12 | min 8 | **D3 decides within 2 s.** Hard limit first: below 20 % G4 must land within 12 min or ditch, so "wait for the end of the leg" is off the table | Decision record with latency, binding constraint and cost to the loser |
| | | *Survey priority:* G3 holds depth before its acoustic link breaks; the survey pauses for the minimum 15-minute recovery window and the leg is re-run | Sentence names the survey minutes lost |
| 00:25 | min 8 | **We swap to the other priority file (rescue if the jury chose survey, survey if it chose rescue). Same event, re-decided.** The survey is suspended, the ship is released to manoeuvre, and G4's 35 kW charge is reserved ahead of everything | Both decisions side by side: same code, two ships |
| 00:40 | min 12 | **Genset trips.** The guest reserve halves to about 100 kW while G4 draws 35 kW and G5 45 kW | Power gauge drops; cooling gauge rechecked |
| 00:42 | min 12 | **D4 sheds in a declared order** within 5 s for the first action and 60 s for the sequence: throttle before shed (with G3 charging, 105 kW against a 95 kW ceiling: survey slows the drone's charge to 10 kW; rescue drops the comms node to 8 kW), the winner kept alive, every guest's loss stated | Ladder with timestamps against the 5 s and 60 s ceilings; one line per guest |
| 01:00 | | **Breadth strip**, one line each, labelled live or replayed (below) | |
| 01:25 | | Close: "Same code, two ships, explained in one sentence each." | |

The exact shed order comes from the ledger and the active priority file, not from this script.

## Breadth strip (one line each, about 5 s each)

Pick four on the day; each is labelled **live** or **replayed** on screen.

- **Camera (replayed):** a leak under chilled-water pump 1 makes the governor plan cooling as degraded
  before any pump alarm; it sheds only on a confirmed fault ([camera design, C1](../research/cv_equipment_monitoring.md)).
- **Crew dial 14 to 0:** the same drone recovery under rule R3 moves from "bridge confirms the clear deck" (14) to a standing plan approved at launch (6) to an automatic hold or a refused launch (0), and the standing
  plan approved ahead of time is shown ([Scenario C memo](SCENARIO_C_MEMO.md)).
- **Landing zone not clear:** a marked item on the landing zone holds the drone's recovery (rule R3).
- **Cable pull (live):** the link path flips to Wi-Fi and no decision is missed.
- **Over-consuming guest:** G5 draws 15 % over its declaration and is throttled with a sentence.
- **Emission silence:** SATCOM and radio drop to zero; G4 returns home and demands a clear deck.
- **Mission sets:** four priority files (survey, rescue, patrol, disaster relief) on one hull.

## Scenario A, jury's card (deep)

The ship is alongside on shore power; three guests are installed, and the jury presents a fourth card
and may change one number. Verdict within 30 s, judged against the mission envelope, not the pier.

| Step | What the governor shows |
|---|---|
| Card loaded, one number edited live | The edited value highlighted; the manifest re-validated |
| Verdict | yes, no, yes-if or not-now, with the binding resource class named in one sentence |
| Placement | Which bay, mast slot or deck position, and the rejected alternatives |
| Yes-if | A ranked list of what to displace or throttle and the capability lost |
| Degraded check | "Holds with one genset down: yes or no", with the binding line |
| Tipping point | The seawater temperature at which the verdict flips |

Prepared drills (the jury chooses, but we rehearse these):

- **The 35 kg case:** installed G1, G2, G3; card G4. Mass 10.035 t against 10 t: refused by 35 kg;
  yes-if G1 disembarks. Changing the hangar to 800 kg flips it to yes.
- **The free mast slot:** installed G2, G3, G4; card G1 or G5. G1 fits the free mast slot, but G1 to G4 together weigh 10.035 t against 10 t (the 35 kg case again), so it is yes-if one guest disembarks; G5 (13.015 t, 3.0 t over) is yes-if G2 or G3 leaves (ranked by the priority file), and its antenna has
  the mast or the hangar roof, but its node has no bay.
- **The bay story:** installed G1, G2, G5; card G3. Two lines bind: G3 needs all of Bay 1, and the four
  weigh 12.07 t against the 10 t margin. Yes-if G5 leaves (9.045 t) or G2 leaves (8.57 t, G5 moves to
  Bay 2, Arch Q4), ranked by the active priority file.
- **Scenario A-prime (if time):** the same card under way gets "not now", with the next installation
  window and, at 0 crew, a logical reconfiguration instead.

## Rehearsal and fallbacks

- Fixed seeds and cached public data, so every run decides the same way; the backup recording is made
  from a rehearsal run.
- Our own travel router or phone hotspot for the Wi-Fi path, never the venue network.
- If the webcam misbehaves, the camera line runs from the replayed stream, labelled as such.
- Rehearse five times on Sun morning; freeze at 09:15 PDT.

## Open questions for the team

1. Decided (DEC-32): Scenario B runs G3, G4, G5; the full load-out is refused at the pier with an override available.
2. Which four breadth lines?
3. Who drives the laptop and who talks?
4. Where does the breadth strip go? The brief asks for 90 s of Scenario B, then Scenario A; inside B it
   takes about 25 s from the minute-12 shedding. Options: keep it in B (as drafted), move it after
   Scenario A as a 30 s encore, or show only the lines that happen inside Scenario B anyway (cable pull,
   crew dial).
