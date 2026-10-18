# Response time as degradation priority

Status: built Sat 2026-10-17 (DEC-60), by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka). The numbers
are the brief's own (Annex A.8, `config/assumptions.yaml` `response_time_s`). The server formats the class tags
from `response_time_s`. Three places on the screen carry the A.8 values as fixed text: the operations screen's
set of known tags, the footer of the builder's response-class form, and the Reference page. A change to
`response_time_s` needs those three edited too.

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

**Due ticks.** Every shed or hold D4 record carries `first_shed_due_t_s` and `full_sequence_due_t_s`, and so
does an unconfirmed one. They are 5 s and 60 s after the fault's raw event. They count from the first over-limit
tick instead when no fault is confirmed, or when the overload started after the fault confirmed. A restore record
(verdict `restore`) carries no due tick. Its limit is the 30 s `ceiling_ms`. Each shed, armed or queued step
carries its own `due_t_s`. Steps still to come after this second are in `queued`.

**Safety commands.** Each tick's safety table gives every safety command one state and a reason:

| State | Means |
|---|---|
| `ready` | it would go out now if asked |
| `not_needed` | nothing to do now, for example G2's winch is not running |
| `cannot` | impossible now, for example G3's acoustic link is down. The reason says why, and the crew's action where there is one |

An answered request is a record of kind `safety`. A ready command is answered with verdict `sent`. Otherwise the
verdict is the state, `not_needed` or `cannot`, with its reason. The timing log keeps every record's decision time
against its limit (`latency_ms`, `ceiling_ms`).

**On screen: the acting decision's time against its limit.** In a live run the time is the decision's compute
time from the timing log. In a fixture replay it is ship time, from the raw event (or the record's own tick when
there is none) to the tick the first command applies. It shows in these places:

- the RESPONSE tile, as time / limit with NORMAL or LATE, and the decision it measures (D3 or D4, compute or
  ship time);
- the ledger's RESPONSE D4 row: the limit, the time, the margin, and NORMAL or LATE;
- the RESPONSE row of the D3 and D4 decision panels, and the action line of the active-constraint panel, as
  time / limit;
- the Admission header, as the D1 decision's compute time in ms against 30 s.

D3's panel also counts down to its LAND BY time, and G4's zone on the deck shows its own LAND BY countdown while
G4 is airborne or recovering. A D4 sentence with a queued step names the minute the next step is due.

**Not computed: MET and MISSED per step.** Nothing compares the tick each shed step was applied with its own
`due_t_s` to give a verdict word.

**Class tags.** 200 MS, 5 S and 60 S beside each guest in the guest list and on each shed-order row (30 S on a
restore step), in the response-class form of the profile builder, and on the Reference page. The screen shows no
safety state, and no control on it sends a safety request.

The two clocks are kept apart. Ship time runs from the raw event to the applied tick. Wall time (the timing log)
measures the computation. The screen shows one or the other, never the two added together.
