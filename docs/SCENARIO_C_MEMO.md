# Scenario C memo: Nobody on the flight deck during recovery

**Architecture and constraint handling.** ArgOS keeps one ledger of the ship's eight resource classes,
rebuilt every second from the ship profile, the guest cards and a 1 Hz plant snapshot; every electrical
kilowatt also counts as a kilowatt of heat against the cooling loop at the present seawater temperature.
Card conditions are typed against the ship's state machine (course, speed band, noise, deck, emission),
so a conflict is two guests' incompatible conditions, not an alarm. Every decision takes the same order:
safety-critical guests and hard limits first, then the weights of the swappable priority file. Faults
enter only as confirmed plant signals, and a stale feed falls to its conservative value. Each decision
is a record of the binding line, its numbers and the cost to the loser, and its sentence is filled from
that record, so a replay gives the same sentence. Rule R3 (brief D5) is one such constraint: one hold
condition, `hold` below, on the ledger's flight-deck line. While it is true, landing clearance is
withheld within the 200 ms safety-command ceiling (brief A.8), answered from a table precomputed every
tick, and no priority file lifts it; D5 sets by crew level what a human confirms, what is automatic and
what is impossible.

## The rule and why it exists

The brief's own example rule guards the marked landing zone on the 12 x 8 m deck (brief A.3):
downwash from the 140 kg drone G4 throws loose gear, and a bad landing hurts whoever stands there
(brief B, G4; research E3). We assume G4 is secured with no deck hand, so the fire party and landing
officer (HLO) stand near but clear of the zone. People are the hazard and the only hands that clear
it: 3-5 min at 14 aboard, 8-12 at 6, at 0 only if already clear (brief A.6). Below 20 % battery G4
must land within 12 min or ditch (brief B, G4). At 14 the rule is about people, at 6 about time, at
0 about evidence. The deck state comes from the HLO's report at 14 and 6. At 0 it is the state the
platform latched at the last crew sweep.

## Trigger

R3 is on from the moment clearing must start for the zone to be empty before G4 has to land (from
launch when the crew are too few to clear in time) until G4 is secured.

```
deadline = time G4 passed 20 % + 12 min        # brief B, G4
lead     = confirm_max + clear_max             # A.6: 1+5 min at 14, 3+12 at 6
recall   = first return order: D3 decision, sortie end, operator, silence  # brief D3; B, G4
opens    = launch if lead > 12 - approach or nobody aboard    # 6 and 0
           else min(recall, deadline - approach - lead)        # 14
window   = now >= opens and not G4.secured
deck_ok  = 14, 6: HLO reports the zone clear (the bridge confirms at 14)
           0: latched clear at the last crew sweep, no deck activity since
hold     = window and not deck_ok
```

Unknown never means clear: a missing or stale HLO report is "not clear", and so is a missing latch. Deck
activity is any movement the platform reports on deck after the sweep (a hatch, a hangar door, a winch)
other than G4's own launch; it voids the latch, and nothing aboard can latch the deck clear again. Stale
G4 telemetry: assume the earliest 20 % crossing the last reading allows. Unreported crew level: assume
the next lower. Unanswered confirmation: no. A standing plan lapses when guests, priorities or crew
level change, unless one for the new level was approved first; the departing crew approve the 0-aboard
plan and make the last sweep at handover.

## Effect

- **Holds** landing clearance while `hold` is true, within 200 ms (A.8); no priority file lifts it.
- **Forbids** new tasks in the zone inside the window, except clearing and the sweep; the cards' own
  exclusions also apply: no winch (brief B, G2), so a 5 min cast must end before the window opens,
  and no ramp work (A.3).
- **Allows** landing once the zone is clear and the A.3 flight-deck limits hold; at 0 aboard only on a
  deck latched clear, otherwise recovery is forbidden and the record states the cost under G4's hard limit.

Bridge sentence at 14: "Recovery held: the landing officer reports the zone not clear, G4 at 18 % must
land in about 10 min, needs 4 to approach, and confirm plus clear takes up to 6." At 0: "Recovery
forbidden: the deck was not latched clear at the last crew sweep, so G4 at 18 % must ditch by min
18.2, and its rescue capability is lost."

## By crew level

In Scenario B, G4 reports 18 % at min 8. At our assumed drain of 100 % over 90 min it passed 20 %
1.8 min earlier, so it must land by min 18.2. The D3 decision at min 8 recovers G4, which is the
recall, so clearing starts then: confirm 1 + clear 4 + approach 4 lands G4 at min 17 (demo seed).
Without that order the window would open at min 8.2 at the latest: 10.2 min left, less our assumed
4 min approach, is 6.2 min against a 6 min lead at 14, a 12 s margin. At 6 the lead is 15 min against
at most 8, so the zone stays clear from launch.

| Aboard | A human confirms | Automatic | Impossible |
|---|---|---|---|
| 14, patrol | HLO reports the zone; the bridge confirms the clear-deck call in 15-60 s (A.6, applied by us); HLO may override. Hands: crew clear and sweep in 3-5 min | Clear-deck call when the window opens; hold and release | Landing on a "not clear" report nobody overrode |
| 6, monitoring | Bridge approves a standing plan at launch, since a live yes plus clearing (3 + 12 min) cannot fit in 8; HLO reports and may override | Zone clear from launch until G4 is secured; deck, winch and ramp work refused up to 90 min (endurance, brief B; our choice) | A recovery that needs clearing first |
| 0, night transit | Nothing live (A.6); the departing crew's plan and last sweep stand | Launch only if recovery stays possible for the whole 90 min sortie; recovery on a deck latched clear with no deck activity since | Clearing the deck; any confirmation or override; recovery on a deck not latched clear |

In the governor, R3 carries one setting per crew level, one of confirm, standing plan, automatic or
forbidden: confirm at 14, standing plan at 6, automatic at 0. A priority file may override a level, but
the loader refuses confirm at 0 (A.6). At 0 the latch is a platform-reported state, which we record as an
assumption: nothing aboard sees loose gear shift in the wind after the sweep, and a bad landing meets no
fire team (research E3). With no latch, recovery is forbidden, so below 20 % G4 ditches, and the record
states that cost. Our choice: the shore is told when a link exists, never asked, because the rule must
work offline (SATCOM is zero in silence, A.5); research E3 and E8 assume shore clearance instead.

## Live demo: 14, 6 and 0 aboard

The brief's should-have is the rule at two crew levels, shown live; we show three. Right after
Scenario A, a short fixed segment replays Scenario B from minute 8 as the crew dial turns:

1. **14 aboard.** The bridge confirms the clear-deck call and the crew clear the zone. The HLO then
   reports the zone not clear: recovery held within 200 ms with its bridge sentence; a "clear" report
   releases it.
2. **6 aboard.** No live call: the standing plan approved at launch is shown, and the log shows a deck
   work request at min 3, an injected event labelled INJECTED on screen, refused: "not now; when: after G4 is
   secured" (allowed at 14).
3. **0 aboard.** Deck latched clear at handover: recovery automatic, with no confirm or override button.
   The same replay with deck activity reported after the sweep: recovery forbidden, cost to G4 stated.

## Assumptions

The rule's parameters (`rules.r3.*`: approach time, drain rate, telemetry staleness, zone, override,
uncrewed launch and the latched deck state) live in `config/assumptions.yaml` with their reasons, and
appear in the Physical Account.
