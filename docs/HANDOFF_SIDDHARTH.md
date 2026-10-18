# Review handoff for Siddharth: status (Sun 02:10 PDT)

There was no handoff after Saturday night, so Logan's session fixed every code item below in this
session (Logan's decision, Sun 00:40 PDT). Each fix has a test that fails without it, every fix
group had an adversarial reviewer, and the scripted survey and rescue runs (frames, inputs,
snapshots, decisions) stay byte-identical to the tagged `submission` commit. Branches:
`fix/handoff-core`, `fix/handoff-shedding`, `fix/handoff-loop`, `fix/handoff-cards`, merged on
`integrate/logan-final`; cross-group leftovers on `fix/handoff-leftovers`.

| # | Status | Fixed in | Test |
|---|---|---|---|
| 22 | fixed: a word limit reads as words, the screen row too | core.py, explain.py, ui/view.py | tests/test_handoff_core.py::test_d3_on_the_endurance_limit_says_the_word_not_a_number, ::test_the_hard_limit_row_reads_a_word_limit_as_words |
| 3 | fixed: inputs logged exact, the standby gets its own copy | loop.py | tests/test_handoff_loop.py::test_a_profile_weight_off_the_tenth_decides_the_same_live_on_the_standby_and_in_replay |
| 1 | fixed: no shed on stand-in draws | shedding.py | tests/test_handoff_shedding.py::test_a_guest_meter_drop_sheds_nothing_on_stand_in_draws |
| 2 | fixed: only the binding line's stand-ins hold D4 back | shedding.py | ::test_a_pms_drop_does_not_hold_up_a_cooling_shed_on_fresh_data |
| 15 | fixed: `safety_request` laptop input and `sdv run --safety T:request` (no screen button, that is UI) | ui/live.py, cli.py, loop.py | tests/test_handoff_loop.py::test_a_safety_request_from_the_screen_is_answered_at_once_and_replayed, ::test_sdv_run_sends_a_safety_request_and_the_replay_is_equal |
| 5 | fixed: the wait runs from R3's own ask, a confirmation hidden by a feed drop still counts | core.py | tests/test_handoff_core.py::test_a_lost_laptop_feed_lets_the_bridge_request_lapse_and_holds_the_recovery, ::test_a_confirmation_hidden_by_a_feed_drop_clears_the_deck_when_the_feed_returns |
| 6 | fixed: one re-ask per hard-limit onset, none after a denial | core.py | ::test_a_lapsed_recall_is_asked_again_at_the_battery_limit_when_g3_is_already_holding, ::test_a_denial_after_an_early_recall_is_not_asked_again |
| 7 | fixed: G3 held by a safety request resumes after G4 is secured | core.py | ::test_a_g3_held_by_a_safety_request_resumes_after_g4_is_secured |
| 8 | fixed: a policy hold re-runs the policy each tick | core.py | ::test_a_standing_plan_approved_after_a_policy_hold_reopens_the_recovery |
| 9 | fixed: a delayed first action keeps its 5 s due tick | shedding.py | tests/test_handoff_shedding.py::test_a_delayed_first_action_keeps_the_5_s_due_tick |
| 16 | fixed: the unconfirmed D4 says why | records.py | tests/test_handoff_core.py::test_the_unconfirmed_d4_record_says_why |
| 17 | fixed: `add_input` takes the lock | loop.py | tests/test_handoff_loop.py::test_an_input_added_during_a_tick_is_stamped_for_the_next_one |
| 18 | fixed: safety latency counts the wait for the lock | loop.py, Core.safety | ::test_a_safety_request_waiting_for_the_tick_counts_its_wait |
| 21 | fixed: the snapshot names the file in force | loop.py | ::test_the_snapshot_names_the_priority_file_in_force |
| float frames | fixed: one frame for every side | loop.py | ::test_the_primary_decides_on_the_frame_the_log_holds |
| ws test race | fixed in the test | tests/test_ui_server.py | itself |
| soak 4, 5, 6, 8, 9, 10 | fixed: partial weights, a bad confirm block, an unknown swap, the laptop input contract, plain refusal sentences, finite numbers | arbitration.py, loader.py, core.py, ui/live.py, manifests/schema.json | tests/test_handoff_core.py, tests/test_handoff_loop.py, tests/test_handoff_cards.py |
| recovery lead | NOT fixed on purpose: `recovery_lead_s` drops the bridge confirm time (str vs int key). Fixing it moves the 6-aboard D5 off its pinned fixture | arbitration.py | strict xfail ::test_the_recovery_lead_counts_the_bridge_confirm |

Still yours, not code: the Douglas list and the plan speed on feat/ship-state-fsm, README:95 VENTUNO wording, the
response-class tags hard-coded in ops.js, builder.js and reference.js, and a screen button for safety requests.

---

## Original handoff (Sat 23:10 PDT, updated Sat 23:40)

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
