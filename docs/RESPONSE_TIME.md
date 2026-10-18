# Response time as degradation priority

Status: built Sat 2026-10-17 (DEC-60), by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka). The numbers
are the brief's own (Annex A.8, `config/assumptions.yaml` `response_time_s`). The screen formats every tag from
those numbers, so the config and the screen cannot disagree.

The brief gives each kind of decision a time limit. ArgOS uses those limits to decide who gives up power, and
in what order, when the ship loses a generator or a cooling pump.

## The classes every guest is in

| Tag | Who | What ArgOS does with it |
|---|---|---|
| **200 MS** | a card marked safety-critical, or a guest the profile adds | Never takes its power. Its only automatic actions are stop, hold or secure, answered within 200 ms from a table rebuilt every second. |
| **5 S** | every guest not listed below (the default) | Gives power first, in the first action, applied within 5 s of the fault. |
| **60 S** | the profile's mission-critical guests | Gives power last, only if the ship is still short after every 5 S step: one step per second, each after a fresh reading, all within 60 s of the fault. |

Inside each class: slow down before switching off, then the profile's shed order, then the least mission value
lost per kW freed. The order of the classes is fixed in code. Which guest sits in which class is the profile's.

## The time limit of each decision

| Tag | Decision | Limit |
|---|---|---|
| **200 MS** | a safety command: stop G2's winch, hold G3 at depth, hold G4's landing, call G4 home | answered on arrival, applied next second |
| **2 S** | right of way (D3) and the crew rule (D5) | computed within 2 s |
| **5 S** | the first shed action after a fault | applied by fault + 5 s |
| **60 S** | the full shed sequence | every step applied by fault + 60 s |
| **30 S** | admission and placement (D1, D2), and restoring a shed guest | computed within 30 s |

**Restore (30 S).** Once every fault has read healthy for 60 s, ArgOS steps the last guest it shed back up,
one step per decision, only if the load still fits under the limit.

## What the records carry, and what the screen shows

**Due ticks.** Every D4 record carries `first_shed_due_t_s` and `full_sequence_due_t_s`: 5 s and 60 s after the
fault's raw event, or after the load went over the limit when that came after the fault confirmed. Each step
carries its own `due_t_s`. Steps still to come after this second are in `queued`, each with its due tick.

**Safety commands.** Each tick's safety table gives every safety command one state and a reason:

| State | Means |
|---|---|
| `ready` | it would go out now if asked |
| `not_needed` | nothing to do now, for example G2's winch is not running |
| `cannot` | impossible now, for example G3's acoustic link is down. The reason names the crew's action |

An answered request is a record of kind `safety`. A ready command is answered with verdict `sent`. Otherwise the
verdict is the state, `not_needed` or `cannot`, with its reason. The timing log keeps every record's decision time
against its limit (`latency_ms`, `ceiling_ms`).

**Not computed yet: MET and MISSED.** Nothing yet compares the tick a step was applied with its due tick, or a
decision's time with its limit, to give a verdict word.

**On screen today: the class tags only.** 200 MS, 5 S and 60 S beside each guest in the guest list and on each
shed-order row (30 S on a restore step), in the response-class form of the profile builder, and on the Reference
page. The one due time on screen is in a D4 sentence with a queued step, which names the minute the next step
is due. The screen shows no safety state, and no control on it sends a safety request.

The two clocks are kept apart: ship time says whether a step was applied by its due tick. Wall time (the timing
log) says whether the computation fitted its limit. They are never added together.
