# Expected outcomes (test oracles, draft for team review)

Hand-computed by three Claude Opus 5.5 agents on behalf of Logan Walker (GhostWalka); no governor code exists yet. Each row becomes a test once the ledger exists.

## Assumptions

1. **Envelope draw** = max(nominal, any peak over 60 s): G1 1.5 kW (air-cooled), G2 20, G3 25, G4 35, G5 45 (all four chilled water).
2. **Mass:** G1 0.045 t, G2 3.5, G3 5.5, G4 0.99 (hangar 0.85), G5 3.025. The G5 antenna goes on the mast if it is free. Otherwise it goes on the hangar roof (0.03 t-eq), which we assume clears drone operations.
3. **Cooling:** C(T) = 160 - (40/18) x (T - 12). That gives 120 kW at 30 °C and 133.3 kW at 24 °C. The loop binds at T = 12 + 0.45 x (160 - chilled kW). The scan runs in 0.1 °C steps up to 35 °C.
4. **Limits:** a load equal to its limit holds ("<="). The 5 kW headroom applies only to the shed ceiling.
5. **No "not-now":** the ship is alongside in Scenario A.
6. **Yes-if lists:** throttling frees no mass, so each yes-if list is made of minimal removal sets. They are ranked by value lost (weight x 1.0), then fewer guests, then guest id, with mission-critical guests last.
7. **Ladder order:** one-genset-down fixes and minute-12 ladders follow the GAMEPLAN ladder. Non-critical throttles come first, then mission-critical throttles, then sheds in the same order. Within a group: lowest cost per kW, then id. G3 charging cannot be interrupted, so it is never on the list.
8. **SATCOM** is judged at the guests' minimums: G1 0.2 + G2 0 + G5 1 = 1.2 of 2 Mbit/s. At nominal, G5's 6 Mbit/s alone exceeds 2, which would change A3 to A5.
9. **Scenario B minute 12:** ceiling = min(100, 133.3) - 5 = 95 kW.
   - G2 6 kW (sampling).
   - G4 35 kW, the brief's figure. Under sar it is reserved even before landing.
   - G5 45 kW.
   - G3 either 1 kW (set L, running on its own battery) or 25 kW (set B, charging; this gives the brief's 105 kW sum).
10. **R3:** drain 1.11 % per min, 4 min approach. At 14 aboard, confirming takes up to 1 min and clearing the deck up to 5 min.

## Scenario A

| Case | File | Verdict | Binding line | Placement | Yes-if ranking (value lost, result) | One genset down |
|---|---|---|---|---|---|---|
| A1 | survey | yes-if | Mass 0.045 + 3.5 + 5.5 + 0.99 = 10.035 t vs 10 t, 35 kg over. Passing: stability 10.323/12 t-eq, power 81.5/200, chilled 80/120, port 26.5, stbd 55 | G4 drone and hangar on flight deck; G3 Bay 1, G2 Bay 2, G1 mast | 1. G1, 0.2 (9.990 t); 2. G2, 1.0 (6.535 t); 3. G3, 1.0, mission-critical (4.535 t) | Yes, 81.5/100 |
| A1 | sar | yes-if | Same | Same | 1. G3, 0.2; 2. G1, 0.5; 3. G2, 0.5 (tie broken by id) | Yes |
| A2 | survey | yes-if | Same four guests: 10.035 t, 35 kg over | G1 on free mast slot: 45/60 kg, 0.5/0.6 m², 1.5/2 kW air | 1. G4, 0.2 (9.045 t); 2. G2, 1.0; 3. G3, 1.0, mission-critical | Yes, 81.5/100 |
| A2 | sar | yes-if | Same | Same | 1. G3, 0.2; 2. G2, 0.5; 3. G4, 1.0, mission-critical | Yes |
| A3 | survey | yes-if | Mass 13.015 t vs 10, 3.015 t over. Also failing: stability 13.263/12, no bay for the node, chilled 125/120 at 30 °C. G4 out alone: 12.025 t | If G2 leaves: node Bay 2, antenna mast. If G3 leaves: node half of Bay 1, G2 stays in Bay 2 | 1. G2, 1.0 (9.515 t, 9.763 t-eq); 2. G3, 1.0, mission-critical (7.515 t, 7.763 t-eq) | G2 out: no, 25 + 35 + 45 = 105/100, 5 short. G3 out: yes, 100/100, 0 spare |
| A3 | sar | yes-if | Same | Same | 1. G3, 0.2; 2. G2, 0.5 | Same |
| A4 | survey | yes-if | Two lines: G3 needs all of Bay 1 (the G5 node holds a half), and mass 12.07 t vs 10, 2.07 over. Stability 12.165/12 also fails. G1 out alone: 12.025 t, bay still blocked | G3 whole Bay 1; antenna stays on hangar roof | 1. G5, 0.2 (9.045 t, 9.135 t-eq); 2. G2, 1.0, plus moving the G5 node to Bay 2 (one crane move, 4 to 8 h) (8.57 t, 8.665 t-eq) | Yes, 46.5 or 71.5/100 |
| A4 | sar | yes-if | Same | Same | 1. G2 plus node move, 0.5; 2. G5, 1.0 | Yes |
| A5 | survey | yes | Tightest: chilled 20 + 45 + 35 = 100/120 at 30 °C, 20 free. Mass 7.56, stability 7.853, power 101.5/200, port 46.5, stbd 55 | G4 on flight deck (drone 140/150 kg); antenna stays on hangar roof | None needed | No: 101.5/100, 1.5 short. Step 1 G4 to charge, frees 25 kW, lost 0.2 x 0.3 = 0.06; then G5 low (0.14), G2 to sampling (0.2), G1 off (0.2) |
| A5 | sar | yes | Same | Same | None needed | No, 1.5 short. Step 1 G2 to sampling, frees 14 kW, lost 0.5 x 0.2 = 0.1; then G5 low (0.7), G4 to charge (0.3, mission-critical), G1 off (0.5) |
| A6 | survey | yes | Mass 0.045 + 3.5 + 5.5 + 0.94 = 9.985 t, 15 kg spare (tightest). Stability 10.263/12 | As A1 | None needed | Yes, 81.5/100 |
| A6 | sar | yes | Same | Same | None needed | Yes |

**A3 with one genset down:**
- **G2 out:** survey takes G4 to charge (frees 25 kW, load 80). Sar takes G5 to low power (frees 37 kW, load 68; G5 loses 70 %).
- **G3 out:** the load is exactly 100 kW, so a test using "<" or the headroom would say "no". Against 95 kW the ladder takes G4 to charge (survey) or G2 to sampling (sar).

**Seawater tipping points:**
- **A3 as given** is the only case that flips inside the scan. Chilled 125 kW gives T = 12 + 0.45 x 35 = 27.75 °C: it holds at 27.7 and fails at 27.8.
- **A3 after its yes-if:** 36.75 °C (G2 out) and 39.0 °C (G3 out).
- **Other cases:** A1, A2 and A6 48.0 °C; A4 63.75 °C (G5 out) or 52.5 °C (G2 out); A5 39.0 °C.

## Scenario B load-out checks

| Load-out | Mass vs 10 t | Stability vs 12 t-eq | Other |
|---|---|---|---|
| (i) G2, G3, G4, G5 | 13.015, 3.015 over (CON-12) | 13.263, 1.263 over | Bay 2 needed twice; chilled 125/120 at 30 °C |
| (ii) G3, G4, G5 | 9.515 | 9.763 | One genset down at envelope: 105/100 |
| (iii) G2, G3, G4 | 9.99, 10 kg spare | 10.188 | Fits |

## Scenario B, minute 8 (same outcome for all three load-outs)

**Hard limit, both files:** G4 is below 20 %, so it must land within 12 min or ditch.
- At 1.11 % per min, G4 crossed 20 % at minute 6.2, so the deadline is minute 18.2. That leaves 10.2 min.
- Less the 4 min approach, 6.2 min remain, against 1 + 5 = 6 min to confirm and clear the deck. The margin is 12 s.
- If the 12 min is counted from the report, the deadline is minute 20 and the margin is 2 min.
- The leg ends at minute 40, so waiting for it is infeasible. Ditching is not offered.

**Conflict:**
- G4 needs 5 to 12 kn, freedom to turn into the wind, a clear deck and the ramp unused.
- G3 needs 3 kn, a steady course, quiet and no deck machinery. Its card also excludes G4 recovery while G3 is surveying.

| File | Who proceeds | Cost to the loser (G3) |
|---|---|---|
| survey | G4 recovers; its charge is not reserved | G3 holds depth (1 kW) before the acoustic link breaks. The survey pauses for the minimum 15-min window (minutes 8 to 23) and the leg is re-run. Lost: 8 flown + 15 paused + 2 to 4 to settle and go quiet = **25 to 27 survey minutes**. The leg ends at about minute 65 to 67 |
| sar | G4 proceeds; the survey is suspended, the ship is free to manoeuvre, and the 35 kW charge is reserved ahead of everything | The leg is aborted with no resume time: at least 25 to 27 minutes, open-ended. G3's recovery over the ramp waits until G4 is secured |

## Scenario B, minute 12 (one genset trips, ceiling 95 kW, power binds)

| Load-out, draws | Load | Short | Survey ladder (step: kW freed, cumulative, load after; capability lost) | Sar ladder |
|---|---|---|---|---|
| (i) L: 6/1/35/45 | 87 | none, 8 spare | No step | No step |
| (i) B: 6/25/35/45 | 111 | 16 | G4 fast charge to charge: 25, 25, 86; the drone loses 30 % (slower recharge, later launch) | G5 full to low power: 37, 37, 74; G5 loses 70 % of coastal connectivity |
| (ii) L: -/1/35/45 | 81 | none, 14 spare | No step | No step |
| (ii) B: -/25/35/45 | 105 | 10 | G4 to charge: 25, 25, 80 | G5 to low power: 37, 37, 68 |
| (iii) L: 6/1/35/- | 42 | none | No step | No step |
| (iii) B: 6/25/35/- | 66 | none | No step | No step |

- Draws are given as G2/G3/G4/G5 in kW.
- Every other guest loses nothing. Survey keeps G3 whole; sar keeps G4 at 35 kW.
- Heat passes throughout: chilled load is at most 111 kW against 128.3.
- G2's winch is excluded in both files.

**Price lists** (cost per kW, then kW freed):
- **Survey throttles:** G4 to charge 0.0024, 25; G5 low 0.0038, 37; G4 to standby 0.010, 8; G2 to standby 0.16, 5.
- **Survey sheds:** G2 0, G5 0.0075, G4 0.03, G3 0.3 (mission-critical).
- **Sar throttles:** G5 low 0.0189, 37; G2 to standby 0.08, 5; G4 to charge 0.012, 25 (mission-critical); G4 to standby 0.05, 8 (mission-critical).
- **Sar sheds:** G2 0, G5 0.0375, G3 0.06, G4 0.15 (mission-critical).

**Robustness:**
- If G2's probe has paused because the course is free, every load is 5 kW lower and the steps are unchanged.
- Under survey, if G4 has not landed (2 kW, no reservation), (i) B is 78 kW and nothing is shed.
- The brief's sequence (node to 8 kW, then ocean module to standby) matches the first two sar steps, but only the first is ever needed.
- Set L sheds nothing, so the demo needs set B, or a stated reason why G3 is charging.

## Disagreements resolved

- **A3 verdict:** calculator 2 said "no as given, yes-if". Kept **yes-if**, because one removal admits it. DEMO_SCRIPT's "refused on mass" should be changed to match.
- **A3 one genset down, sar fix:** only calculator 1 gave it. Recomputed; kept G5 to low power.
- **A5 fix ordering:** calculator 2 ranked by value lost (G1 off before G2, G4 last); calculator 1 used the ladder. Kept the **ladder order**, because this fix is a trip ladder, not a yes-if. Step 1 is the same either way and alone closes the gap.
- **Minute 8 survey cost:** calculator 1 said 23 to 28 minutes, adding up to 5 min for a speed change; calculator 2 said 25 to 27. Kept **25 to 27**. 3 and 5 kn are both in the slow band, so there is no band change, and settling (1 to 3 min) overlaps with going quiet (2 to 4 min).
- **Minute 8 sar cost:** calculator 1 said at least 8 min, open-ended; calculator 2 said at least 23 to 27. Kept a lower bound of 25 to 27, because recovery still takes the minimum window and the leg must be re-settled and re-run.
- **Minute 12 envelope draw set (G2 winch at 20 kW):** only calculator 2 used it. Dropped, because G2's card excludes the winch while G4 recovers or G3 listens.
- **SATCOM:** calculator 2 flagged that judging at nominal would change verdicts. Kept judging at minimums (assumption 8), for the team to decide.

## Envelope rule (DEC-35) and the one-genset-down line

Verdicts above are unchanged under the rule Logan chose (option 3, refined by four critics and a judge). The
one-genset-down line now has three states, tested against a 95 kW gate. Checked against the cards by
`tests/test_envelope_gate_data.py`.

| Case | Set checked | As loaded (of 100 kW) | Survey: how it holds | Rescue: how it holds |
|---|---|---|---|---|
| A1, A2, A6 | G1, G2, G3, G4 | 81.5, fits | nothing needed | nothing needed |
| A3, if G2 leaves | G3, G4, G5 | 105, 5 short | G4 charge 35 to 10 kW, 80 kW | G5 to low power, 68 kW |
| A3, if G3 leaves | G2, G4, G5 | 100, fits but over the 95 gate | G4 charge 35 to 10 kW, 75 kW | G2 winch to sampling, 86 kW |
| A4, either option | G1, G2, G3 or G1, G3, G5 | 46.5 or 71.5, fits | nothing needed | nothing needed |
| A5 | G1, G2, G4, G5 | 101.5, 1.5 short | G4 charge 35 to 10 kW, 76.5 kW | G2 winch to sampling, 87.5 kW |
| Scenario B (DEC-32) | G3, G4, G5 | 105, 5 short | G4 charge 35 to 10 kW, 80 kW | G5 to low power, 68 kW |

G3 charging cannot be interrupted, so it never earns throttle credit. Information line only: with cooling at
-40 % the chilled-water gate at 30 °C is 67 kW; Logan kept this as information only (DEC-36, closing CON-13).

## Scenario B as decided (DEC-40)

Load-out G3, G4, G5; G3 underwater on its leg; G4 lands at minute 17. Checked by `tests/test_scenario_b_timeline_data.py`.

| Moment | Ceiling | Survey | Rescue |
|---|---|---|---|
| Min 12, genset trip, cooling nominal | min(100, 133.3) - 5 = 95 kW | G3 1 + G4 2 (airborne) + G5 45 = 48, holds | G3 1 + G4 35 (reserved) + G5 45 = 81, holds |
| Min 19, pump fault (x0.6), G4 fast-charging | min(100, 80) - 5 = 75 kW | 81 over; G4 35 to 10 kW, 56 | 81 over; G5 45 to 8 kW, 44 |
| After the fault, G3 asks to start its 25 kW charge (not interruptible) | 75 kW | G3 25 + G4 10 + G5 45 = 80 over; G5 to 8 kW first, then G3 starts: 43 | G3 25 + G4 35 + G5 8 = 68, starts at once |

The fault is tied to the event "G4 landed and fast-charging" plus 2 minutes, so it always falls inside G4's
20-minute fast charge (minutes 17 to 37). Restore order once cooling recovers is left to the engine build (T-tasks in BUILD_PLAN).
