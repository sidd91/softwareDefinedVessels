# ArgOS architecture on one page

**ArgOS: Reliability through Automation**

- A general picture of the loop, not a code walk-through.
- Numbers come from [PITCH_FACTS.md](PITCH_FACTS.md) (F-nn rows).
- Written by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka), Sat 2026-10-17 PDT.

Terms:

- **Tick:** one ship second; the loop runs once per tick (1 Hz).
- **Frame:** the raw instrument readings of one tick.
- **Snapshot:** the estimated ship state of one tick, every field with its source and age.
- **Ledger:** capacity, demand and free space per resource line.
- **Record:** one decision, its numbers, and one sentence on why.

## The loop, once per ship second

```mermaid
flowchart LR
  P[Ship profile<br/>config/assumptions.yaml]
  G[Guest cards<br/>manifests/G1..G6]
  M[Priority file<br/>config/missions]
  LD[Loader<br/>names checked, bad file refused]
  PL[Plant and sensors<br/>simulator: labelled test double]
  SE[State estimator<br/>faults confirmed<br/>stale feed to safe value]
  SN[Snapshot, 1 Hz]
  LG[One ledger<br/>8 resource classes]
  D1[D1 admission]
  D2[D2 placement]
  D3[D3 right of way]
  D4[D4 shedding]
  D5[D5 crew rule]
  ST[Safety table<br/>stop, hold, secure in 200 ms]
  R[Records<br/>binding line and<br/>one-sentence why]
  CMD[Commands<br/>applied next tick]
  UI[Screen and decision log]
  LOGS[Logs<br/>frames, inputs, snapshots,<br/>decisions, timing]
  RP[Replay<br/>byte for byte]
  SB[Standby board<br/>same inputs, compared every tick]
  P --> LD
  G --> LD
  M --> LD
  LD --> LG
  PL -->|frame| SE
  SE --> SN
  SN --> LG
  LG --> D1
  LG --> D2
  LG --> D3
  LG --> D4
  LG --> D5
  D3 --> ST
  D4 --> ST
  D5 --> ST
  D1 --> R
  D2 --> R
  D3 --> R
  D4 --> R
  D5 --> R
  ST --> R
  R --> CMD
  CMD -->|tick n + 1| PL
  R --> UI
  PL --> LOGS
  SN --> LOGS
  R --> LOGS
  LOGS -->|frames and inputs| RP
  LOGS -->|frames and inputs| SB
```

## The components

| # | Component | Path | What it optimises |
|---|---|---|---|
| 1 | Loader | `src/sdv/loader.py` | no bad file replaces a good one: unknown names refused, the field named (F-64) |
| 2 | Plant and sensors | `tests/support/sim_stub.py`, a test double; `SDV_SIM` swaps in the real one | the brief's event timeline at 1 Hz, labelled as a double |
| 3 | State estimator | `src/sdv/estimator.py`, `config/signals.yaml` | one reading never sheds: faults confirmed, a stale feed falls to its safe value |
| 4 | Ledger | `src/sdv/ledger.py` | one model for all 8 classes: 1 kW electric is 1 kW of heat; cooling falls as seawater warms |
| 5 | D1 admission | `src/sdv/admission.py` | a verdict that holds at the envelope and one genset down; yes-if by least value lost |
| 6 | D2 placement | `src/sdv/placement.py` | every installed part placed, fewest moves, preferred positions first |
| 7 | D3 right of way | `src/sdv/arbitration.py` | hard limits first, then the priority file's weights; the loser's cost stated |
| 8 | D4 shedding | `src/sdv/shedding.py` | by response class; slow down before switching off; least mission value lost per kW |
| 9 | D5 crew rule, safety table | `src/sdv/core.py`, `src/sdv/safety.py` | who decides at 14, 6 and 0 aboard; stop, hold, secure answered by lookup (F-20) |
| 10 | Records and sentences | `src/sdv/records.py`, `src/sdv/explain.py` | one sentence from the binding numbers; no canned strings |
| 11 | Loop, logs, replay, standby | `src/sdv/loop.py` | same inputs, same decisions: replay equal (F-55), standby in step (F-56) |
| 12 | Screen, Reference Kit, Physical Account | `src/sdv/ui/`, `src/sdv/kit.py`, `tools/physical_account.py` | one screen for the bridge; the docs aboard (F-77); every assumed number traced (F-89) |
