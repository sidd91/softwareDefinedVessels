# Requirements traceability

Generated from `docs/requirements.yaml` by `tools/render_requirements.py`; edit the YAML, not this file.
Built Fri 2026-10-16 23:18-23:58 PDT by an 11-agent workflow (Claude Opus 5.5 on behalf of Logan Walker, GhostWalka), from every page of the slides and the brief, including the organizers'
corrections: G4 hangar 850 kg, not 900 kg; Three of the five possible sets of four exceed the 10 t margin.

**How to use it.** Each row says how we address a requirement, links the files and WORKLOG decisions
that do it, gives an honest status, and asks one brainstorming question for direction and scope.
Rows marked **Called out** are named explicitly by the slides or brief and must be answered at a
granular level (WORKLOG DEC-24). When work changes how a requirement is addressed, edit its row in
the YAML, re-render, and cite the ID in WORKLOG rows and entries (WORKLOG rules 8 and 9).
Status: done = finished and evidenced; drafted = a draft exists for review; planned = in the plan,
not built; gap = nothing addresses it yet; not-applicable = out of scope by the brief.

## Summary

| Section | Rows | Called out | done | drafted | planned | gap | not-applicable |
|---|---|---|---|---|---|---|---|
| [Deliverables](requirements/deliverables.md) | 26 | 26 | 0 | 19 | 7 | 0 | 0 |
| [Problem framing and resource classes](requirements/problem-framing-and-resource-classes.md) | 59 | 55 | 0 | 36 | 23 | 0 | 0 |
| [Must-have success criteria](requirements/must-have-success-criteria.md) | 14 | 14 | 0 | 7 | 7 | 0 | 0 |
| [Should-have success criteria](requirements/should-have-success-criteria.md) | 12 | 12 | 0 | 1 | 10 | 1 | 0 |
| [Decision classes (D1 to D6)](requirements/decision-classes-d1-to-d6.md) | 48 | 46 | 0 | 9 | 39 | 0 | 0 |
| [What we are judged on](requirements/what-we-are-judged-on.md) | 29 | 28 | 5 | 10 | 13 | 1 | 0 |
| [Reference scenarios](requirements/reference-scenarios.md) | 40 | 40 | 0 | 20 | 20 | 0 | 0 |
| [Live demo](requirements/live-demo.md) | 31 | 30 | 0 | 11 | 19 | 1 | 0 |
| [Platform model and ship state (Annex A)](requirements/platform-model-and-ship-state-annex-a.md) | 72 | 71 | 0 | 62 | 7 | 2 | 1 |
| [Guest manifest and cards (Annex B)](requirements/guest-manifest-and-cards-annex-b.md) | 72 | 70 | 5 | 64 | 2 | 1 | 0 |
| [Physical Account (Annex C)](requirements/physical-account-annex-c.md) | 25 | 25 | 0 | 23 | 2 | 0 | 0 |
| [Constraints](requirements/constraints.md) | 68 | 65 | 0 | 46 | 22 | 0 | 0 |
| [Stack, data and tools](requirements/stack-data-and-tools.md) | 38 | 10 | 1 | 13 | 20 | 3 | 1 |
| [Out of scope](requirements/out-of-scope.md) | 9 | 8 | 0 | 3 | 0 | 0 | 6 |
| [Data use and AI rules](requirements/data-use-and-ai-rules.md) | 11 | 9 | 0 | 7 | 3 | 0 | 1 |
| **All** | **554** | **509** | **11** | **331** | **194** | **9** | **9** |

## Gaps

Rows with status gap. Called-out rows still only planned are counted in the summary above.

- **R-088** (called out): With reduced crew (6) installation windows are shorter and rarer.
- **R-148** (called out): A scoring rationale names the verdict, the bound resource, its condition (loop temperature), the free amount and what the guest needs, with units.
- **R-207**: The chart's event spikes sit near 00:17 and 00:22 on the axis while the callouts say 00:08 and 00:12; treat the callout times as authoritative.
- **R-238** (called out): Drawing carries a vertical 6 m dimension labelled LOB (ambiguous label, likely a depth or height figure); confirm against the ship profile in the brief before using it.
- **R-239** (called out): Propulsion is two pods (labelled twice); propulsion is a power consumer and affects course and noise.
- **R-362** (called out): G1 loses 30 percent capability if own radar transmits nearby, unless 'quiet radio' is declared.
- **R-500**: Start from a Kubernetes resource request and design for what it cannot express.
- **R-514**: Copernicus Marine provides sound-speed and layering; registration is required and activation can take hours, so register early.
- **R-522**: Start the synthetic data generators in hour 1.

## Find a requirement

Each section page lists its rows in ID order. To find one ID quickly:

```bash
grep -rn '| R-064 |' docs/requirements/
```
