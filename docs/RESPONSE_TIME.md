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

## The decisions every record is tagged with

| Tag | Decision | Limit |
|---|---|---|
| **200 MS** | a safety command: stop G2's winch, hold G3 at depth, hold G4's landing, call G4 home | answered on arrival, applied next second |
| **2 S** | right of way (D3) and the crew rule (D5) | computed within 2 s |
| **5 S** | the first shed action after a fault | applied by fault + 5 s |
| **60 S** | the full shed sequence | every step applied by fault + 60 s |
| **30 S** | admission and placement (D1, D2), and restoring a shed guest | computed within 30 s |

**Restore (30 S).** Once every fault has read healthy for 60 s, ArgOS steps the last guest it shed back up,
one step per decision, only if the load still fits under the limit.

## Status words

On screen today: the class tags (200 MS, 5 S, 60 S, 30 S) on every guest and every shed-order row, the
response-class form in the profile builder, and the Reference page. The words below are in every decision record
(due ticks, queued steps) and in each tick's safety table. The screen does not show them yet.

| Word | Means |
|---|---|
| MET | applied by its due tick, and computed inside its limit |
| MISSED | applied after its due tick, or computed slower than its limit |
| DUE | a fault is open and the step is not yet applied, with its due tick |
| QUEUED | a 60 S step that will go next second if a fresh reading shows it is still needed |
| READY | a safety command that would go out now if asked |
| NOT NEEDED | a safety command with nothing to do now; the reason is named |
| CANNOT | a safety command that is impossible now (for example, G3's acoustic link is down); the reason and the crew's action are named |
| SENT | a safety command answered, its latency shown against 200 ms |

The two clocks are kept apart: ship time says whether a step was applied by its due tick; wall time (the timing
log) says whether the computation fitted its limit. They are never added together.
