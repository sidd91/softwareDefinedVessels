# softwareDefinedVessels: a resource governor for a re-configurable vessel

Team entry for Fincantieri's **Software Defined Vessel** challenge (Maritime Dual-Use Hackathon, San
Francisco, 16-18 Oct 2026). The governor is the middleware the ship does not have: it owns the hull's
finite physical budget and decides, in seconds and in one plain sentence, which payloads come aboard,
where they go, who wins when two want the same thing, and what is shed when a generator trips.

> **Status (Sat 11:53 PDT): data model and test oracles done; the decision engine is not built yet.**
> Everything marked *planned* below is design.

## Run it

Works today (Python 3.12 via uv). The tests check the cards and priority
files against their schemas, the data against the brief's arithmetic, the expected outcomes and the
Scenario B timeline against the cards, and every requirement link:

```bash
uv sync
uv run pytest
```

The one demo command (planned; it needs the real engine, which the brief forbids mocking) starts the
decision engine and the screen and loads Scenario B; the priority file is picked and swapped on screen.
Entry point `sdv.cli:main` (`src/sdv/cli.py`, planned):

```bash
uv run sdv demo
```

## The idea in one line

**One ledger, one manifest language.** Everything that uses or supplies a resource is described the
same way and counted in one ledger of margins across the brief's eight resource classes: power, heat
rejection, deck positions, mast positions, mass and stability, data links, compute and response time.
Every decision names the ledger line that bound it. Host commitments are never shed; guests are
admitted, placed, throttled or shed; supply can degrade; crew are both hands and authority. Details: [GAMEPLAN, Core model](GAMEPLAN.md#core-model-locked-by-logan-fri-2100-pdt).

## Architecture

```mermaid
flowchart LR
  subgraph Inputs
    M[Guest manifests<br/>manifests/*.yaml]
    A[Platform assumptions<br/>config/assumptions.yaml]
    P[Mission priority file<br/>config/missions/*.yaml]
    E[Event timeline<br/>trips, cards, sensors, crew]
  end
  subgraph Core[Deterministic governor core]
    L[Ledger:<br/>capacity vs demand per class]
    D1[D1 admission]
    D2[D2 placement]
    D3[D3 right of way]
    D4[D4 shedding ladder]
    D5[D5 crew policy]
  end
  R[Decision record<br/>verdict, binding line, sentence, cost to loser]
  S[Screen: schematic, 8 gauges, decision log]
  M --> L
  A --> L
  P --> D3
  P --> D4
  E --> L
  L --> D1 & D2 & D3 & D4
  D5 --> D3 & D4
  D1 & D2 & D3 & D4 --> R --> S
```

Same inputs give the same decisions and sentences, so a standby node takes over by replaying the event
log (planned). Node A is the laptop; node B is an Arduino VENTUNO Q board (8 cores, 14 GiB RAM, Ubuntu
24.04), [up and measured](docs/NODE_B_BOARD.md). Data contracts: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Decision classes

D1 to D4 read one ledger (`src/sdv/ledger.py`, planned) and write the same
[decision record](docs/ARCHITECTURE.md#data-contracts); ceilings are the brief's (A.8).

| Class (ceiling) | Component | What it optimises |
|---|---|---|
| D1 Admission (30 s) | `src/sdv/admission.py` (planned) | A verdict that holds at both gensets, 200 kW and 30 °C, and survives one genset down by throttling (rule below); for yes-if, the least mission value lost |
| D2 Placement (30 s) | `src/sdv/placement.py` (planned) | Largest smallest remaining margin; preferred slots first; most future cards left admissible; rejected alternatives named |
| D3 Right of way (2 s) | `src/sdv/right_of_way.py` (planned) | Hard limits first (the drone's 12-minute landing rule), then mission-weighted value from the priority file; cost to the loser stated |
| D4 Degradation (5 s, 60 s) | `src/sdv/shedding.py` (planned) | Throttle before shed; least mission loss per kW freed on the binding line, power or cooling (DEC-40), both rechecked each step; safety-critical never shed; ladder precomputed every tick |
| D5 Crew as a setting | `src/sdv/crew_policy.py` (planned) | What a human confirms, what is automatic, what is forbidden at 14, 6 and 0 aboard; rule R3 in the [Scenario C memo](docs/SCENARIO_C_MEMO.md) |
| D6 Physical Account | `tools/physical_account.py` (built) | Every assumed number, with its reason and where code uses it: [docs/PHYSICAL_ACCOUNT.md](docs/PHYSICAL_ACCOUNT.md) |

**D1 rule.** Judged at both gensets, the 200 kW reserve (A.1) and cooling at 30 °C (A.10); it must also
survive one genset down by throttling to the 95 kW gate, otherwise yes-if, with the raw one-genset-down
line always shown (DEC-35). In port, installed guests may move between bays, each move reported with its
crane time (DEC-37). Links are judged at guests' minimum rates, any nominal shortfall shown as degraded
quality (DEC-38). The seawater tipping point is reported.

## Deliverables

- **Prototype, one documented command:** `uv run sdv demo` ([Run it](#run-it)); planned.
- **Manifest schema, five cards plus one of ours:** [manifests/schema.json](manifests/schema.json),
  [G1-G6](manifests/) (G6 is our desalination unit), [how to add a card](manifests/README.md); validated by tests.
- **README (at most 3 pages), Physical Account (1 page), Scenario C memo (PDF, at most 2 pages):** this
  file, the [account](docs/PHYSICAL_ACCOUNT.md) (from [config/assumptions.yaml](config/assumptions.yaml) and the cards) and
  the [memo](docs/SCENARIO_C_MEMO.md); `tools/build_pdfs.py` builds each PDF and checks its limit.
- **Live demo, 90 s of Scenario B, then Scenario A with the jury's card:** [storyboard](docs/DEMO_SCRIPT.md),
  planned. Scenario B runs G3, G4 and G5 (DEC-32). Minute 8: D3 decides between the drone (G4) and the
  seabed vehicle (G3) under both priority files. Minute 12: a genset trips; the load (48 or 81 kW) holds
  under the 95 kW ceiling, and D4 shows both armed ladders with no step needed. Minute 19: a labelled,
  added pump fault makes cooling bind (81 against 75 kW); D4 slows G4's charge to 10 kW (survey file) or
  takes G5 to 8 kW (rescue file) (DEC-40).

## Repository map

Every path and what it holds: [docs/REPOSITORY_MAP.md](docs/REPOSITORY_MAP.md). Every requirement, and how we address
it: [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md). Decisions and who made them: [WORKLOG.md](WORKLOG.md).

## Limitations (today)

- No decision engine, simulator, screen or edge failover exists yet; all of it is designed, not built.
- Numbers come from the brief's annexes and our labelled assumptions, never from a real vessel.
- By choice, both power lines survive a genset trip (A.9); a 40 % cooling loss is information only (DEC-36).
- Cameras are optional (the governor works with none); camera confidence is uncalibrated.

## With another week

- Calibrate the simulator's sensor models against the public datasets already identified.
- Run the governor on two real edge nodes with wired and wireless paths, and measure failover.
- Validate camera equipment checks on real shipboard footage, with exposure-locked cameras.
- Work through more priority files and jury cards, and harden the crew rule compiler.

## Declarations and licence

AI and software, with licences and origins: [docs/SOFTWARE_LOG.md](docs/SOFTWARE_LOG.md). Claude (Anthropic) is the
coding and research assistant; no model from a China-based company is used. Only open-source third-party
code or our own; code licence [MIT](LICENSE). Data (planned): sea temperature, waves and wind from
Open-Meteo (a source the brief names), cached offline. Weather data by [Open-Meteo.com](https://open-meteo.com/), CC BY 4.0.
