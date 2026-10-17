# Scenario C memo: Nobody on the flight deck during recovery

Status: **draft for team review, Fri 21:45 PDT.** Drafted by Claude Opus 5.5 on behalf of Logan
Walker (GhostWalka). Nothing is built yet.

Rule R3 answers brief D5 and Scenario C. It adapts research rule R-E3-1 without its mast clause,
which is a separate rule, so the memo covers one rule.

## The rule and why it exists

The brief's example crew rule: "Nobody on the flight deck during recovery." R3 guards the marked
landing zone on the 12 x 8 m deck (brief A.3): downwash from the 140 kg drone throws loose gear, and
a bad landing hurts whoever stands there (brief B, G4; research E3). We assume G4 is secured with no
deck hand, so the fire party and landing officer (HLO) stand near but clear of the zone.

People are the hazard and the only hands that clear it: 3-5 min at 14 aboard, 8-12 at 6, and at 0
only if already clear (brief A.6). Below 20 % battery G4 must land within 12 min or ditch (brief B,
G4). At 14 the rule is about people, at 6 about time, at 0 about evidence.

## Trigger

R3 is on from the moment clearing must start for the zone to be empty before G4 has to land, or from
launch when the crew are too few to clear in time, until G4 is secured.

```
deadline = when G4 passed 20 % + 12 min            # brief B, G4
lead     = confirm_max + clear_max                 # A.6: 1+5 min at 14, 3+12 at 6; 0: infinite (ours)
recall   = first return order: sortie end, operator, or emission silence (brief B, G4)
opens    = launch                                   if lead > 12 - approach   # 6 and 0
           min(recall, deadline - approach - lead)  otherwise                 # 14
window   = now >= opens and not G4.secured
people   = fresh, in-view camera count, else crew report (14, 6), else 1
clear    = people == 0 and (crew swept zone at 14, 6 | zone unchanged since sweep at 0)
hold     = window and not clear
```

Unknown never means clear. A crew report can replace a blind camera, never a fresh detection; only a
logged HLO override sets a detection aside. Stale G4 telemetry: assume the earliest 20 % crossing
the last reading allows. Unreported crew level: assume the next lower. Unanswered confirmation: no.
A standing plan lapses when guests, priorities or crew level change, unless a plan for the new level
was approved first; the departing crew approve the 0-aboard plan at handover.

## Effect

- **Holds** clearance to land while `hold` is true, within 200 ms (brief A.8); no priority file (D3) lifts it.
- **Forbids** new tasks in the zone inside the window; only clearing and the sweep may start.
- **Allows** landing once `clear` and the A.3 flight-deck limits hold.
- Exclusions the cards already declare apply while the window is open: no winch (brief B, G2), so a
  5 min cast starts only if it ends before the window opens, and no ramp work (A.3). No new rules.

Bridge sentence: "Recovery held: 1 person in the landing zone, which must be empty (frame 0.4 s
old); G4 at 18 % must land in about 10 min, needs 4 to approach, and confirm plus clear takes up to 6."

## By crew level

In Scenario B, G4 reports 18 % at min 8. At our assumed 100 % over 90 min (assumption 2) it passed
20 % about 1.8 min earlier, leaving 10.2 min; less our assumed 4 min approach (assumption 1), 6.2 min
against a 6 min lead at 14. That 12 s margin is why the window opens on the drain trend. At 6 the
lead is 15 min against at most 8, so the zone stays clear from launch.

| Aboard | A human confirms | Automatic | Impossible |
|---|---|---|---|
| 14, patrol | Bridge confirms the clear-deck call (A.6's 15-60 s, applied by us); HLO may override. Hands: crew clear and sweep, 3-5 min | Clear-deck call when the window opens; hold and release | Landing on a detection nobody overrode |
| 6, monitoring | Bridge approves a standing recovery plan at launch, since a live yes plus clearing (3 + 12 min) cannot fit in 8; HLO may override | Zone kept clear launch to secured; deck, winch and ramp work refused up to 90 min (endurance, brief B; extending the recovery-only exclusions is our choice) | A recovery that needs clearing first |
| 0, night transit | Nothing live (A.6); the departing crew's plan stands | Launch refused unless recovery stays possible for the 90 min sortie (assumption 8); land only on a fresh "unchanged, empty" reading | Clearing the deck; any confirmation or override |

At 0 a zero person count proves nothing, and a person detector cannot see loose gear. The hold
protects the ship: a bad landing meets no fire team (research E3). The camera checks that the zone is
unchanged since the last sweep, which at night needs deck lighting or a low-light channel; thermal
can add a hazard but never clear a zone. A blind camera means hold, so below 20 % G4 ditches, and the
decision record states that cost. Our choice: the shore is informed when a link exists, never asked,
because the rule must work offline (SATCOM is zero in silence, A.5); research E3 and E8 assume
shore clearance instead.

## Live demo (two levels required; 0 shown too)

1. **14 aboard, Scenario B min 9.** A teammate steps into view: held within 200 ms with that
   sentence; steps out: cleared. Webcam turned away: a 60 s confirm button; unanswered, still held.
2. **Same replay at 6.** A teammate stepping in at sortie min 3 is allowed at 14, refused at 6:
   "not now; when: after G4 is secured".
3. **At 0.** Webcam turned away: hold, no button, cost to G4 stated.

## Assumptions (Physical Account lines)

1. `r3.approach_min` = 4, or G4's estimate if longer; transit runs alongside clearing.
2. `r3.drain_pct_min` = 1.11 (100 % over 90 min, brief B); G4 never drains slower. Unverified.
3. `r3.stale_s`: camera 3 s, G4 telemetry 10 s.
4. `r3.person_confidence` = 0.4: a false alarm costs a hold, a miss an injury.
5. `r3.zone`: marked landing area, flying stations masked; G4 secured with no deck hand.
6. `r3.override`: HLO only, at 14 and 6; logged; one landing; a new detection cancels it.
7. `r3.camera`: fixed deck camera, inference in the 20 % ship-systems reserve (A.7), never shed.
8. `r3.uncrewed_launch`: automatic landing and securing, fixed deck firefighting (unconfirmed), lit or low-light view for 90 min.
9. `r3.unchanged`: all deck markers visible and the frame matches the last sweep.

## Open questions for the team

- At 6, who overrides if the bridge watch is also the HLO, and can the fire party muster in 8 min?
- Fixed deck firefighting: declare it, or forbid G4 launch at 0?
