# Repository map

What each folder and file holds. Back to the [README](../README.md).

| Path | What |
|---|---|
| `config/assumptions.yaml` | Platform capacities, positions, envelope, ship-state and crew timings, fault entry, rule parameters; a `provenance` map tags each number as brief or assumed, with a reason |
| `config/missions/` | Four priority files (survey, rescue, patrol, disaster relief) and their schema, with the optional `shed_order` and per-rule `confirm` fields |
| `config/scenarios/scenario_b.yaml` | Scenario B event timeline (WORKLOG DEC-32, DEC-40) |
| `manifests/` | Guest manifest schema, the six cards G1-G6 (G6 is our desalination unit), and [how to add a card](../manifests/README.md) |
| `src/sdv/` | The ArgOS package: `cli.py` (the `sdv` command: admit, run, replay, kit), `loader.py`, `ledger.py`, `admission.py` (D1), `placement.py` (D2), `arbitration.py` (D3), `shedding.py` (D4), `core.py` (runs the decisions per snapshot, R3 by crew level as D5), `estimator.py` (frames to snapshots), `loop.py` (the tick loop, logs, replay, the standby in lockstep), `records.py` and `explain.py` (decision records and their sentences), `kit.py` (the governor's computers and the Deployment Reference Kit). The simulator is Siddharth's track (WORKLOG DEC-47) |
| `tests/` | Checks that the data reproduces the brief's numbers, the expected outcomes and the Scenario B timeline, and that every requirement link resolves |
| `tests/support/sim_stub.py` | A labelled test double of Siddharth's simulator, built from the contract only, so the estimator, loop and screen run before his lands |
| `docs/DEPLOYMENT.md` | The governor's computers aboard (boards, standby, edge nodes), the Deployment Reference Kit and its port upload (DEC-56 to DEC-58) |
| `tests/oracles/expected_outcomes.yaml` | Expected verdicts, numbers and ladders for the Scenario A drills and Scenario B, checked against the cards |
| `tools/physical_account.py` | Writes the one-page [PHYSICAL_ACCOUNT.md](PHYSICAL_ACCOUNT.md) and the full [PHYSICAL_ACCOUNT_DETAIL.md](PHYSICAL_ACCOUNT_DETAIL.md) from the assumptions and the cards |
| `tools/build_pdfs.py` | Builds the README, Scenario C memo and Physical Account PDFs and checks their page limits |
| `tools/render_requirements.py` | Renders `docs/requirements.yaml` into [REQUIREMENTS.md](REQUIREMENTS.md) and `docs/requirements/` |
| `docs/` | [Design freeze](DESIGN_FREEZE.md), [architecture and data contracts](ARCHITECTURE.md), [requirements matrix](REQUIREMENTS.md), [Scenario C memo](SCENARIO_C_MEMO.md), [Physical Account](PHYSICAL_ACCOUNT.md), [demo storyboard](DEMO_SCRIPT.md), [expected outcomes](EXPECTED_OUTCOMES.md), [message to the organizers](ORGANIZER_MESSAGE.md), [board bring-up](NODE_B_BOARD.md) (the measuring instrument), [software and AI log](SOFTWARE_LOG.md) |
| `research/` | Background research: sensors, cameras, Fincantieri vessels, shipboard procedures and accident lessons. Files headed "Superseded for the build by WORKLOG DEC-44" (cameras, computer vision, failover) stay as research only |
| `GAMEPLAN.md`, `WORKLOG.md` | Plan, and the team's shared log of decisions, conflicts and who made them; where the plan differs from [DESIGN_FREEZE.md](DESIGN_FREEZE.md), the freeze wins (DEC-44) |
| `pyproject.toml`, `uv.lock`, `.python-version` | Python 3.12 project; `uv sync` installs the pinned dependencies |
