# Repository map

What each folder and file holds. Back to the [README](../README.md).

| Path | What |
|---|---|
| `config/assumptions.yaml` | Platform capacities, positions, envelope, ship-state and crew timings, rule parameters; a `provenance` map tags each number as brief or assumed, with a reason |
| `config/missions/` | Four priority files (survey, rescue, patrol, disaster relief) and their schema |
| `config/scenarios/scenario_b.yaml` | Scenario B event timeline (WORKLOG DEC-32, DEC-40) |
| `manifests/` | Guest manifest schema, the six cards G1-G6 (G6 is our desalination unit), and [how to add a card](../manifests/README.md) |
| `src/sdv/` | The governor package: `cli.py` (`sdv demo`, `admit`, `sim`, `replay-check`), `data.py` (loaders, input hashes), `ledger.py` (capacity and demand lines, eight gauges, envelope draw), `decision.py` (the decision record and its latency), `priority.py` (priority-file validation and atomic swap), `admission.py` (D1), `placement.py` (D2), `right_of_way.py` (D3), `shedding.py` (D4), `governor.py` (runs D3/D4 inside the simulator tick, re-arms the ladder every tick). Planned: `crew_policy.py` (D5 table) |
| `src/sdv/plant/` | The simulated ship (DEC-47): `fsm.py` (A.6 ship-state machine with transition times, scenario pins, confirmed-event faults; DEC-52), `guests.py` (guest modes, declared vs actual draw, G4 battery), `sim.py` (seeded 1 Hz loop over a scenario timeline, JSONL run file). Contract: [PLANT_CONTRACT.md](PLANT_CONTRACT.md) |
| `tests/` | Checks that the data reproduces the brief's numbers, the expected outcomes and the Scenario B timeline, and that every requirement link resolves |
| `tests/oracles/expected_outcomes.yaml` | Expected verdicts, numbers and ladders for the Scenario A drills and Scenario B, checked against the cards |
| `tools/physical_account.py` | Writes the one-page [PHYSICAL_ACCOUNT.md](PHYSICAL_ACCOUNT.md) and the full [PHYSICAL_ACCOUNT_DETAIL.md](PHYSICAL_ACCOUNT_DETAIL.md) from the assumptions and the cards |
| `tools/build_pdfs.py` | Builds the README, Scenario C memo and Physical Account PDFs and checks their page limits |
| `tools/render_requirements.py` | Renders `docs/requirements.yaml` into [REQUIREMENTS.md](REQUIREMENTS.md) and `docs/requirements/` |
| `docs/` | [Architecture and data contracts](ARCHITECTURE.md), [requirements matrix](REQUIREMENTS.md), [Scenario C memo](SCENARIO_C_MEMO.md), [Physical Account](PHYSICAL_ACCOUNT.md), [demo storyboard](DEMO_SCRIPT.md), [expected outcomes](EXPECTED_OUTCOMES.md), [node B bring-up](NODE_B_BOARD.md), [software and AI log](SOFTWARE_LOG.md) |
| `research/` | Sensors, cameras, Fincantieri vessels, shipboard procedures and accident lessons |
| `GAMEPLAN.md`, `WORKLOG.md` | Plan, and the team's shared log of decisions, conflicts and who made them |
| `pyproject.toml`, `uv.lock`, `.python-version` | Python 3.12 project; `uv sync` installs the pinned dependencies |
