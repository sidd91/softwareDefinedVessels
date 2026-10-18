# Design memo (Scenario C): nobody on the flight deck during recovery

This memo explains ArgOS's architecture and constraint handling through one implicit crew rule, R3, at 14, 6
and 0 aboard. Section references (A.3, B, D3) are to the challenge brief.

## Architecture and constraint handling

**Inputs, estimator, ledger.** Guest cards, the ship profile (`config/assumptions.yaml`) and a swappable priority
file pass a loader that refuses any file naming something unknown. Each second the estimator turns the plant's
readings into one snapshot, every field with its source and age; a fault counts only once confirmed (a genset trip
needs 2 of 3 signals, held 1 s) and a stale feed falls to the value that tightens limits. One ledger keeps capacity,
demand and free per line: mass, stability, power, heat (1 kW electric is 1 kW of heat; 160 to 120 kW by seawater,
A.2; 60 % with a pump down), the two mission lines, the three data links at the cards' minimum rates, compute, the
mast and flight-deck limits; positions are placed by D2, response time is a ceiling per decision class logged with
every record. The binding line, the smallest margin, names the decision and gives its sentence its numbers.

**Decision engines and records.** D1 judges a card in 30 s (A.8) against the mission envelope (A.10), one genset
down included. D2 places every part by enumeration under a lexicographic rule: installed parts keep a position,
most parts placed, fewest port moves, preferred positions first. D3 settles right of way in 2 s (A.8): the hard
limit opens it, the priority file's weights decide how the loser yields. D4 keeps a shed ladder ready every tick,
throttles before it sheds, acts within 5 s and finishes within 60 s (A.8), never shedding a safety-critical guest.
D5 sets, per rule and crew level, whether a human confirms, a standing plan applies, the action is automatic or it
is forbidden. A safety table rebuilt every tick answers stop, hold and secure within 200 ms (A.8). Each decision
writes one record whose sentence is filled from its fields; replaying the logs rebuilds every record byte for byte.

## The rule and why it exists

The flight deck must be free of people and obstacles (Glossary, A.3). Downwash from the 140 kg drone G4 (B)
throws loose gear on the 12 x 8 m deck, and a bad landing hurts whoever stands in the landing zone. People are the
hazard and the only hands that clear it: 3-5 min at 14 aboard, 8-12 min at 6, at 0 only if already clear (A.6).
Below 20 % battery G4 must land within 12 min or ditch (B, G4). So at 14 the rule is about people, at 6 about
time, at 0 about evidence: the landing officer (HLO) reports the zone at 14 and 6; at 0 only the deck state latched
at the last crew sweep counts.

## Trigger

R3 is on from when clearing must start to empty the zone before G4 must land, until G4 is secured.

```
deadline = G4.land_by_t_s = min(20 % crossing + 12 min, launch + 90 min)  # B, G4
lead     = confirm_max + clear_max: 1 + 5 min at 14, 3 + 12 min at 6      # A.6
recall   = first return order: D3 decision, sortie end, operator, silence # D3, B (G4)
opens    = launch if crew_aboard == 0 or lead > 12 min - approach         # 6 and 0
           else min(recall, deadline - approach - lead)                   # 14
window   = now >= opens and G4.activity in {airborne, launch_recovery}
deck_ok  = 14, 6: the deck reads clear, or a fresh hlo_deck_report == clear (at 14 the bridge confirms first)
           0:     deck_latched_clear (last_sweep clear, no deck_activity_since_sweep)
hold     = window and not deck_ok
```

Unknown never means clear: a missing HLO report, or one older than 5 min, counts as not clear, as does a missing
sweep; deck movement after the sweep, other than G4's launch, voids the latch; stale telemetry dates the 20 %
crossing as early as the last report allows; an unanswered confirmation is a no.

## How a crew rule becomes a constraint

`hold` above is a typed condition over signals named in `config/signals.yaml` (crew aboard, G4's activity and
land-by time, the HLO report, bridge requests, standing plan, latched deck); the estimator refuses any other name.
While `hold` is true the flight-deck line has no free capacity, so a decision that needs G4 on deck binds on it and
its sentence names the signals that made `hold` true. "Hold landing clearance" is a safety-table row, answered
within 200 ms (A.8). No priority file lifts it: a file may set who decides at each crew level (`confirm`), never
`hold`; the loader refuses confirm at 0 (A.6).

## Effect

- **Holds** landing clearance while `hold` is true: the 200 ms row `r3_hold_landing`, lifted only by a fresh
  landing-officer report of a clear zone.
- **Refuses** a recovery the crew aboard cannot clear the deck for: not now at 6 (the lead against the minutes
  left, until the landing officer reports the zone clear); forbidden at 0 on an unlatched deck, G4's cost stated.
- **Allows** landing on a clear zone within flight-deck limits (A.3), at 0 only on a latched deck. Refusing winch,
  ramp and zone work during the window (A.3, B, G2) is designed, not built.

## By crew level

In Scenario B, G4 reports 18 % at minute 8; at our slowest assumed drain, 1.11 %/min, it passed 20 % at minute
6.2, so it must land by minute 18.2. The D3 decision at minute 8 recovers G4 at once: confirm 1, clear 4 and
approach 4 min land it at minute 17 (18.0 with a 5 min clear). At 6 aboard the 15 min lead exceeds the 8 min left
after the approach, so the zone must stay clear from launch.

| Aboard | A human confirms | Automatic | Impossible |
|---|---|---|---|
| 14, patrol | The bridge confirms the clear-deck call (15-60 s, A.6); the HLO reports the zone | Clear-deck call when the window opens; hold and release | Landing on a "not clear" report |
| 6, monitoring | The bridge approves a standing plan at launch; the HLO reports the zone | Zone kept clear from launch; deck work refused (design) | A recovery that needs clearing first |
| 0, night transit | Nothing live (A.6); the departing crew's plan and last sweep stand | Recovery on a deck latched clear | Clearing the deck; any confirmation; recovery on an unlatched deck |

## What runs: 14, 6 and 0 aboard

Three crew levels run through the same loop (`uv run sdv run`, the crew chip on the Operations view,
`tests/test_crew_levels.py`), each ending in a D5 record built from its fields; the brief asks for two live.

1. **14 aboard**, Scenario B as scripted: the bridge is asked at minute 8 on the landing officer's report, confirms
   at minute 9, the deck is cleared at the A.6 pace and G4 lands at minute 17. A "not clear" report is the 200 ms
   row `r3_hold_landing`: held until a fresh "clear" report.
2. **6 aboard**: without an approved standing plan the recovery is held ("no standing plan approved"); with one,
   "Not now at 6 aboard: G4 recovery under rule R3 waits until the landing officer reports the zone clear. Deck
   clearing lead 15 min against 8 min, 7 min over", then cleared at the 8-12 min pace on that report. The plan and
   the report are laptop inputs (`standing_plan`, `deck_report`) the loop and the `/ws` socket accept, with no button.
3. **0 aboard**: automatic on a deck latched clear at the last sweep (`sdv run --variant crew0`); with no sweep, or
   an occupied deck, "Recovery forbidden at 0 aboard: ... G4 ditches by minute 18.2."

The plan at 6 lapses when guests, priorities or crew change; the departing crew approve the 0-aboard plan and make
the last sweep. Designed, not built: refusing winch, ramp and zone work in the window, and the HLO's single override.
R3's parameters (approach 4 min, drain 1.11 %/min, telemetry stale after 10 s, deck evidence, latched deck, uncrewed
launch) sit with their reasons in `rules.r3` of `config/assumptions.yaml` and in the Physical Account; report life (5 min) and fastest drain (1.5 %/min) in `config/signals.yaml`.
