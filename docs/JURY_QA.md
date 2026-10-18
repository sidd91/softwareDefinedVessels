# ArgOS jury Q&A

**ArgOS: Reliability through Automation**

- 30 likely jury questions, each answered in at most 2 lines.
- Numbers point at rows in [PITCH_FACTS.md](PITCH_FACTS.md): F-nn a fact, X-nn do not claim.
- Answers 7, 12, 14, 15, 18 and 27 are honest about gaps: keep them that way.
- Written by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka), Sat 2026-10-17 PDT. Refreshed Sun 00:20 PDT against main `4c4f93c`.
- Team: Logan Walker (GhostWalka) and Siddharth Chawla.

Terms used below:

- **Guest:** a payload that comes aboard (G1 to G6).
- **Card:** a guest's manifest: what it draws, needs and where it fits.
- **Priority file:** the mission's weights and rules. The jury swaps it.
- **Ledger:** one table of capacity, demand and free space for every resource.
- **Binding line:** the ledger row that decided: the most over, or the tightest.
- **D1 to D5:** admission, placement, right of way, shedding, crew rule.
- **Test double:** a labelled stand-in for the simulator.
- **Scenario A:** admission in port, with the jury's card.
- **Scenario B:** a 20-minute run with one clash and two faults.
- **Rule R3:** our crew rule: nobody on the flight deck while the drone recovers.

## Product

**1. What is ArgOS, in one line?**
- A resource governor: it owns the ship's budget and decides which payloads come aboard, who wins, what is shed.
- Every decision names the number that bound it, in one sentence (F-22, F-43).

**2. What problem does it solve?**
- Payloads nobody aboard has seen arrive between missions, onto a fixed budget in 8 classes (F-02).
- Today the crew works it out by common sense. ArgOS writes it down and checks it every second.

**3. What is unique?**
- One ledger for every class, and one sentence from the binding numbers, never a canned string.
- The same code, two priority files, two different and coherent outcomes (F-44, F-50).

**4. A power management system already sheds load. Why this?**
- A power management system trips in a fixed order. ArgOS's order follows the mission.
- It throttles before it trips, judges cooling and mass as well as power, and says why.

**5. What will we see in the demo?**
- Scenario B under your priority file: minute 8 clash, minute 12 genset trip, minute 19 pump fault (F-43 to F-54).
- Mission compare for both files side by side, then Scenario A with your card and one number changed (F-22 to F-42).

## Logic edge cases

**6. Two hard limits at once?**
- Minute 19: power 100 kW, cooling 80 kW. The tighter one decides: 80 minus 5 = 75 kW against 81 (F-52).
- In admission every failing line is listed and the most over binds. A3: mass, stability and cooling (F-26, F-36).

**7. A stale feed?**
- A feed silent for 3 s falls to its safe value: genset down, deck occupied, link at 0. A stale plant feed blocks the shed.
- Honest answer: a dropped guest meter still sheds on its fallback draw. On the team's fix list (X-25).

**8. Nobody aboard (crew 0)?**
- Nobody can confirm, so the rule is automatic: on a deck swept clear, "Recovery automatic at 0 aboard" (F-100).
- No sweep: "Recovery forbidden at 0 aboard ... G4 ditches by minute 18.2", the cost stated (F-102).

**9. Six aboard?**
- Clearing the deck live takes longer than the drone can wait, so it needs a standing plan approved at launch.
- Without one: "Recovery held at 6 aboard: no standing plan approved". The crew chip on screen gives the same (F-101, F-103).

**10. The bridge never answers?**
- An unanswered request counts as a no: "Recovery held at 14 aboard: no answer from the bridge" (F-99).

**11. A malformed jury card?**
- Refused with the field named. The previous card stays in force (F-38, F-39). A new card file loads with `--card` (F-105).
- 15 kinds of hostile card are tested, each refused with its field (F-64).

**12. A malformed priority file?**
- Applied at sea: refused with the field named, the previous profile kept (F-64).
- Dropped on disk: the CLI stops with a traceback that names the field. Fix the file (X-10).

**13. You change a power number on the card?**
- It decides. G5 at 60 kW: yes-if on mass, and with one genset down it holds by throttling (F-42).
- A field that does not exist is refused by name, previous card kept (F-107). On screen: mass and kW inputs (F-106).

**14. Two guests clash with no hard limit?**
- Today right of way covers one contention: drone recovery against the survey vehicle, triggered by a hard limit (X-05).
- The priority file then decides whether the loser pauses or is suspended.

**15. Why does minute 12 shed nothing?**
- The load fits: 48 kW on the survey file, 81 kW on the rescue file, under 95 (F-47). The armed ladder is shown.
- The minute-19 pump fault, labelled injected, sheds live (F-50) (changes when fix/scenario-b-loadout-g1 merges: 49.5 and 82.5 kW).

## Engine and evidence

**16. Why rules, not machine learning or a language model?**
- The brief: deterministic, inspectable rules. Machine learning for forecasting, not for the decision.
- Rules replay byte for byte, decide in under a millisecond, and a captain can audit the reason (F-15, F-55).

**17. Is it deterministic? Can you replay it?**
- Yes: 1201 ticks replayed, every snapshot and all 6 records equal byte for byte (F-55). Every screen run is logged (F-109).
- No randomness and no network in the engine (F-59). Wall-clock time stays in a separate log (F-58).

**18. What is mocked?**
- Only the simulator: a labelled test double that plays the scenario timeline (X-08).
- The engine is real: loader, state estimator, ledger, D1 to D5, records, replay, standby in one process (F-56).

**19. How fast is it?**
- Admission under 8 ms against 30 s. Right of way 0.3 ms against 2 s (F-13, F-15).
- First shed 0.3 to 0.4 ms against 5 s. A safety command under 0.05 ms against 200 ms (F-16, F-20).

**20. What do the response classes mean?**
- Each guest answers to one of the brief's limits: 200 MS never loses power, only stop, hold or secure.
- 5 S gives power first. 60 S, the mission's critical guests, gives power last (F-67, F-68).

**21. Why is time a resource?**
- The brief puts time next to kilowatts (A.8): a right answer after the limit is a wrong answer.
- The screen shows each decision's time against its limit, NORMAL or LATE (F-104), and the limits order who gives first (F-65).

**22. How does the Physical Account work?**
- Every assumed number lives once in `config/assumptions.yaml`, with its source and reason.
- A tool builds the account from it and traces where code reads each number (F-89, F-90).

**23. What would you change on the next ship?**
- One standby chilled-water pump: minute 19 would then shed nothing, 81 kW under 95 (F-53, F-92).

**24. How many tests?**
- 1476 pass on main (F-60), including 15 hostile cards and 8 hostile priority files (F-64).

## Ship and deployment

**25. Certification and safety?**
- Out of scope by the brief. ArgOS only requests ship states. It never drives machinery.
- A safety-critical guest is never on a shed ladder (tested, F-69). Every decision is logged and replayable (F-55).

**26. Does it scale to other hulls?**
- The ship is a data file: positions, capacities, envelope. Boards follow length, 2 at 25 m to 5 at 100 m (F-72).
- Two constants are still in code: two gensets, three mast slots (audit gap 26).

**27. Where does it run aboard, and what if a board dies?**
- 4 identical boards on 60 m, the standby in the engine control room, 6 edge nodes (F-71, F-74).
- Built: the standby in step every tick, in one process (F-56). Design: takeover after 3 s, edge nodes with a shed table (X-17, X-24).

## Data and compliance

**28. Data sources and licences?**
- Annex A and B plus labelled assumptions. Open-Meteo weather (CC BY 4.0) in the deployment map only (F-88, F-96).
- Natural Earth coastlines, public domain. Our code MIT. 26 packages, all MIT, BSD, Apache or PSF (F-93, F-94).

**29. Did you use AI?**
- Claude (Anthropic) as the coding and research assistant, declared in the software log (F-97).
- No AI in the decision path: each sentence is built from its record's numbers (`src/sdv/explain.py`, F-59).

**30. What with another week?**
- Calibrate the simulator on public data. Measure on hardware close to the brief's rack (A.7).
- The emission-silence rule live. More hostile cards and priority files (README, "With another week").
