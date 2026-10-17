# Design memo (Scenario C): nobody on the flight deck during recovery

This memo explains ArgOS's architecture and constraint handling through one implicit crew rule, R3, at 14, 6
and 0 aboard. Section references (A.3, B, D3) are to the challenge brief.

## Architecture and constraint handling

**Inputs and state estimation.** Guest cards, the ship profile (`config/assumptions.yaml`) and a swappable
priority file pass a loader that refuses any file naming something unknown. Each second the estimator turns
the simulator's instrument readings into one snapshot (`docs/STATE_ESTIMATION.md`), every field with its
source and age. A fault counts only once confirmed: a genset trip needs 2 of 3 signals, held 1 s. A stale
feed falls to the value that tightens limits.

**Ledger.** One ledger keeps capacity, committed and free for each line, such as power, heat or flight deck.
It covers all eight classes, degraded state included. One electric kilowatt is one kilowatt of heat, and the
chilled-water loop falls from 160 kW at 12 °C seawater to 120 kW at 30 °C (A.2).

**Decision engines.** D1 judges a card in 30 s (A.8) against the mission envelope (A.10), one genset down
included. D2 places it to keep the smallest margin largest. D3 settles right of way in 2 s (A.8): hard limits
first, then the priority file's weights. D4 keeps a shed ladder ready every tick. It throttles before it
sheds, acts within 5 s, finishes within 60 s (A.8) and never sheds a safety-critical guest automatically
(B.0). D5 sets, per rule and crew level, whether a human confirms, a standing plan applies, the action is
automatic or it is forbidden. A safety table rebuilt every tick answers stop, hold and secure within 200 ms,
with no solver on the path (A.8).

**Decision record and replay.** Each decision writes one record: verdict, binding line with capacity, demand
and free, lines also failing, cost to the loser and crew policy. Its sentence is filled from those fields.
Replaying the frame log rebuilds every record byte for byte, except the wall-clock timing log.

**Constraint handling.** Every constraint is a ledger capacity or a typed condition over named signals. The
binding line, the smallest margin, names the decision and gives its one sentence its numbers.

## The rule and why it exists

The flight deck must be free of people and obstacles (Glossary, A.3). Downwash from the 140 kg drone
G4 (B) throws loose gear on the 12 x 8 m deck, and a bad landing hurts whoever stands in the landing zone.
People are the hazard and the only hands that clear it: 3-5 min at 14 aboard, 8-12 min at 6, at 0 only if
already clear (A.6). Below 20 % battery G4 must land within 12 min or ditch (B, G4). So at 14 the rule is
about people, at 6 about time, at 0 about evidence. With no camera, the landing officer (HLO) reports the
zone at 14 and 6. At 0 the deck state latched at the last crew sweep is the only evidence.

## Trigger

R3 is on from when clearing must start to empty the zone before G4 must land, until G4 is secured.

```
deadline = G4.land_by_t_s = min(20 % crossing + 12 min, launch + 90 min)  # B, G4
lead     = confirm_max + clear_max: 1 + 5 min at 14, 3 + 12 min at 6      # A.6
recall   = first return order: D3 decision, sortie end, operator, silence # D3, B (G4)
opens    = launch if crew_aboard == 0 or lead > 12 min - approach         # 6 and 0
           else min(recall, deadline - approach - lead)                   # 14
window   = now >= opens and G4.activity in {airborne, launch_recovery}
deck_ok  = 14, 6: hlo_deck_report == clear (at 14 the bridge first confirms the call to clear)
           0:     deck_latched_clear (last_sweep clear, no deck_activity_since_sweep)
hold     = window and not deck_ok
```

Unknown never means clear: a missing HLO report, or one older than 5 min, counts as "not clear", and so does
a missing sweep. Deck movement after the sweep, other than G4's own launch, voids the latch. Stale telemetry
dates the 20 % crossing as early as the last report allows. An unreported crew level counts as the next lower
one. An unanswered confirmation is a no.

## How a crew rule becomes a constraint

`hold` above is a typed condition over signals named in `config/signals.yaml`: `crew_aboard`, `G4.activity`,
`G4.land_by_t_s`, `hlo_deck_report`, `bridge_requests`, `standing_plan` and `deck_latched_clear`. The
estimator refuses any name not in that file. While `hold` is true the flight-deck line has no free capacity,
so any decision that needs G4 on deck binds on it and its sentence names the signals that made `hold` true.
"Hold landing clearance" is a safety-table row, answered within 200 ms (A.8).

No priority file lifts it, because D3 applies hard limits before any weight. A file may set who decides at
each crew level (`confirm`), never `hold`. The loader refuses a live confirmation at 0 aboard (A.6).

## Effect

- **Holds** landing clearance while `hold` is true.
- **Forbids** winch, ramp and zone work in the window, except clearing and the sweep (A.3, B, G2).
- **Allows** landing on a clear zone within flight-deck limits (A.3), at 0 only on a latched deck. On an
  unlatched deck at 0, recovery is forbidden and the record states the cost to G4.

At 14: "Recovery held: the landing officer reports the zone not clear, and G4 at 18 % must start its 4 min
approach by minute 14.2 to land by 18.2." At 0: "Recovery forbidden: deck activity since the last crew sweep
voided the latch, so G4 at 18 % ditches by minute 18.2 and its rescue capability is lost."

## By crew level

In Scenario B, G4 reports 18 % at minute 8. At our slowest assumed drain, 1.11 %/min, it passed 20 % at
minute 6.2, so it must land by minute 18.2. The D3 decision at minute 8 recovers G4, so clearing starts at
once: confirm 1, clear 4 and approach 4 min land it at minute 17. With the worst-case 5 min clear it would
land at minute 18.0, 12 s inside the deadline. Without that order the window would open at minute 8.2, the
latest that still lands G4 in time. At 6 aboard the lead of 15 min exceeds the 8 min left after a 4 min
approach, so the zone stays clear from launch.

| Aboard | A human confirms | Automatic | Impossible |
|---|---|---|---|
| 14, patrol | The bridge confirms the call to clear the deck (15-60 s, A.6). The HLO reports and may override once | Clear-deck call when the window opens. Hold and release | Landing on a "not clear" report nobody overrode |
| 6, monitoring | The bridge approves a standing plan at launch. The HLO reports and may override once | Zone kept clear from launch. Deck, winch and ramp work refused for the sortie | A recovery that needs clearing first |
| 0, night transit | Nothing live (A.6). The departing crew's plan and last sweep stand | Recovery on a deck latched clear | Clearing the deck. Any confirmation or override. Launch or recovery on an unlatched deck |

The 6-aboard plan lapses when guests, priorities or crew level change. The departing crew approve the
0-aboard plan and make the last sweep at handover. The shore is told when a link exists but never asked. The
rule must work offline, and SATCOM is zero in emission silence (A.5).

## Live demo: 14, 6 and 0 aboard

The brief's should-have is two crew levels live. We show three, replaying Scenario B from minute 8.

1. **14 aboard.** The HLO reports "not clear": recovery held within 200 ms, released on "clear".
2. **6 aboard.** An INJECTED deck-work request is refused as "not now, after G4 is secured".
3. **0 aboard.** Latched deck: recovery automatic. Activity after the sweep: forbidden, cost stated.

**Assumptions.** R3's parameters (4 min approach, 1.11 %/min drain, telemetry stale after 10 s, zone, deck
evidence, override, latched deck, uncrewed launch) sit with their reasons in `rules.r3` of
`config/assumptions.yaml` and in the Physical Account. The report life (5 min) and the fastest drain for stale
telemetry (1.5 %/min) sit in `config/signals.yaml`.
