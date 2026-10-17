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
not built; gap = nothing addresses it yet; not-applicable = out of scope by the brief, or met by
leaving out a part the design freeze cut (DEC-44).

## Summary

| Section | Rows | Called out | done | drafted | planned | gap | not-applicable |
|---|---|---|---|---|---|---|---|
| [Deliverables](requirements/deliverables.md) | 26 | 26 | 0 | 19 | 7 | 0 | 0 |
| [Problem framing and resource classes](requirements/problem-framing-and-resource-classes.md) | 59 | 55 | 0 | 36 | 23 | 0 | 0 |
| [Must-have success criteria](requirements/must-have-success-criteria.md) | 14 | 14 | 0 | 7 | 7 | 0 | 0 |
| [Should-have success criteria](requirements/should-have-success-criteria.md) | 12 | 12 | 0 | 1 | 11 | 0 | 0 |
| [Decision classes (D1 to D6)](requirements/decision-classes-d1-to-d6.md) | 48 | 46 | 0 | 9 | 39 | 0 | 0 |
| [What we are judged on](requirements/what-we-are-judged-on.md) | 29 | 28 | 5 | 11 | 13 | 0 | 0 |
| [Reference scenarios](requirements/reference-scenarios.md) | 40 | 40 | 0 | 20 | 20 | 0 | 0 |
| [Live demo](requirements/live-demo.md) | 31 | 30 | 0 | 12 | 19 | 0 | 0 |
| [Platform model and ship state (Annex A)](requirements/platform-model-and-ship-state-annex-a.md) | 72 | 71 | 0 | 64 | 7 | 0 | 1 |
| [Guest manifest and cards (Annex B)](requirements/guest-manifest-and-cards-annex-b.md) | 72 | 70 | 5 | 64 | 3 | 0 | 0 |
| [Physical Account (Annex C)](requirements/physical-account-annex-c.md) | 25 | 25 | 0 | 24 | 1 | 0 | 0 |
| [Constraints](requirements/constraints.md) | 68 | 65 | 0 | 46 | 22 | 0 | 0 |
| [Stack, data and tools](requirements/stack-data-and-tools.md) | 38 | 10 | 1 | 14 | 21 | 0 | 2 |
| [Out of scope](requirements/out-of-scope.md) | 9 | 8 | 0 | 2 | 0 | 0 | 7 |
| [Data use and AI rules](requirements/data-use-and-ai-rules.md) | 11 | 9 | 0 | 7 | 2 | 0 | 2 |
| **All** | **554** | **509** | **11** | **336** | **195** | **0** | **12** |

## Gaps

Rows with status gap. Called-out rows still only planned are counted in the summary above.

- none

## Find a requirement

Each section page lists its rows in ID order. To find one ID quickly:

```bash
grep -rn '| R-064 |' docs/requirements/
```
