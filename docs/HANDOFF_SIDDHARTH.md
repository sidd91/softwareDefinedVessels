# Review handoff for Siddharth (Sat 23:10 PDT, updated Sat 23:40)

From two strong reviews of Logan's post-freeze work (each defect reproduced by a script). Items below are in your files. Logan's own fixes are on `fix/review-ours`. Severity first, then a one-line repro and the fix.

## Urgent: can show up live in the demo

| # | Sev | Where | Repro | Fix |
|---|---|---|---|---|
| 22 | high | explain.py:199 (`d3`) | Scripted Scenario B plus `feed_drop g4_telemetry` 480 to 520: the loop crashes at tick 908, `ValueError: Unknown format code 'f'` from `n('airborne')` (G4's endurance hard limit is a word, not a number). Same on main 4c4f93c. A G4 telemetry drop is a likely live injection | `v = when['value']; shown = n(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v).replace('_', ' ')`, then `{shown}{unit}` |
| 3 | high | loop.py:125, 178, 163 | Profile applied at 1100 with sar_air 0.45, coastal 0.35. Primary sheds G4 at 1141; replay and standby shed G5 (`canonical()` rounds the weights to 0.5 and 0.3). Screen shows STANDBY OUT OF STEP after a juror's own profile | Log inputs unrounded (canonical for frames and snapshots only); pass the standby `copy.deepcopy(to_core)` |
| 1 | high | shedding.py:26-28, 58 | `feed_drop guest_meter` at 1130 to 1150: every mode falls back to its highest draw, 105 against 95 kW, and D4 sheds G4 every tick (17 records), then G5 at 1141, which stays low after the feed returns | `acts` also needs a fresh mode and kW for every counted guest, else `unconfirmed` with the ladder armed |
| 2 | high | shedding.py:37, 58 | `feed_drop pms` at 1135 to 1175: at 1141 cooling binds 81 against 75 kW on fresh chilled-water data, the fault is confirmed, yet D4 waits until 1175 (due 1145) | Block only when the binding class's capacity or a counted draw is a stand-in value |
| 15 | med | ui/live.py:16, cli.py | No live way to send a 200 ms safety request (stop, hold, secure): the screen's laptop inputs have no `safety_request` | Add it to the screen's inputs (`loop.safety(request)`), plus `sdv run --safety T:request` |

## R3 and decisions

| # | Sev | Where | Repro | Fix |
|---|---|---|---|---|
| 5 | med | core.py:185-187 | `feed_drop laptop` at 490: R3 stays asked forever, G4 airborne past minute 18.2, recall refused as "under way" | When the request is missing or the feed is stale, count the wait from R3's own ask and record held |
| 6 | med | core.py:261 | Recall at 100 lapses at 161, G3 hold at 300: no D3 at 480, so nobody asks again at the battery limit | Let the `recovery_due` branch reopen a lapsed held R3, once per hard-limit onset |
| 7 | med | core.py:213-216 | G3 held by a safety request: after G4 lands nothing re-steadies the ship (no 1080 resume) | Resume after landing plus secure_s whenever G3 is held, not only through D3 |
| 8 | med | core.py:181-205 | Crew 6, "held: no standing plan" at 480, plan approved at 600: no new D5, G4 ditches | While R3 is held by policy (not a bridge denial), re-run `_r3_policy` each tick |
| 9 | med | shedding.py:71 | Delayed first action (repro #2) is tagged due 1200 (60 S) instead of 1145 | Keep first_due until the stretch's first step is taken |
| 16 | low | records.py:88-106 | `from_d4` drops `unconfirmed_because`, so the sentence never says why | Copy the field into the record |
| 17 | low | loop.py:101-109 | `add_input` takes no lock: a swap added mid-step is logged for one tick and applied on another | Take `self.lock` |
| 18 | low | core.py:349 | Safety latency timed after the lock: a request waiting 59 ms logs 0.08 ms | Time from `Loop.safety` entry |
| 21 | low | estimator run.mission | Snapshot `run.mission` stays survey after a swap (nothing reads it) | Loop passes the core's mission to the estimator (Logan's side once loop says so) |

## Data, docs and deliverables

| Item | Where | Note |
|---|---|---|
| Douglas scale off by one | your fbe59a5 `config/assumptions.yaml:150,189`, `tests/test_environment.py:46-48` | 0.3 m reads SS 1 (Douglas 2). Tops should be [0.0, 0.1, 0.5, 1.25, 2.5, 4.0, 6.0, 9.0, 14.0]. Fix before the environment port. The map is fixed on `feat/deployment-map` |
| Plan speed | `config/plans/sicily_cable_survey.yaml` | Mazara to mid is 52 km in 120 h (0.24 kn) while the provenance says 3 kn legs five days apart: say the legs are survey lines inside the corridor |
| Physical Account 2 pages | main since the tracer fix | `tools/build_pdfs.py account` gives Letter 2, A4 2 (limit 1) |
| README:90 | README | VENTUNO Q "instrument only" vs DEC-56 primary board: "instrument in the demo, primary in the deployment design" |
| If the map merges | README:161-163, REPOSITORY_MAP | Data cached (Open-Meteo, CC BY 4.0) and "Coastlines: Natural Earth (public domain)"; a `tools/deploy_map` row |
| Flaky test | tests/test_ui_server.py `test_ws_streams_the_live_loop_and_takes_laptop_inputs` | KeyError 'refused' at :204. After `hold`, a tick in flight sends one more held frame (tick 1143, running false) before the refusal frame, and the test takes the first held frame as the hold's answer. Slower ticks make it likelier (it failed 4 of 4 on a branch at 4.65 ms/tick, passed 4 of 4 at 4.39). Fix in the test: after the input, read frames until one carries `refused` |

## Found by the second review (not urgent)

| Item | Where | Note |
|---|---|---|
| A whole-number float crew level | loop.py `_step` | A websocket client sending `crew_aboard 6.0`: the primary core gets 6.0, the standby and replay get 6 (`canonical`). The estimator now casts integer signals on `fix/review-ours`, so the snapshot is 6 on both sides. `json.loads(canonical(frame))` in `_step` would close it at the source |
| Response tags hard-coded | ops.js:5 `CLASS_TAGS`, builder.js:236/241, reference.js:18-20/117-119 | A change to `response_time_s` in config makes the guest-list and shed-order tags vanish. Build the tags from `/api/meta` or the builder catalog's `responses[].tag` |
| Never-heard feeds with no fallback value | estimator (Logan's side) | pms, chw, emission, guest_backbone or g4_telemetry dropped from tick 0: fields whose fallback is "the last value" stay unknown (null, assumed), as on main. The safety table no longer calls an unreported G4 safe |
