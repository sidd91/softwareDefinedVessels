# ArgOS screen designs

Reference mockups for the one ArgOS screen (Operations with the constraint-ledger drill-down, Mission compare,
Admission review) and its Reference page. Source of the live design canvas (Claude Design, private to Logan):
https://claude.ai/artifact/N3H2L85Xez4h5AS9NhbTVE

| File | View |
|---|---|
| `screens/Main.dc.html` | Operations console: title bar, ship mimic, plant strip, eight resource tiles, load management record, shed order, guests, event log |
| `screens/TwoShips.dc.html` | Mission compare: two priority files side by side on one timeline (minutes 8, 12, 19) |
| `screens/Ledger.dc.html` | Constraint ledger: active constraint, limit arithmetic, ledger table (drill-down of Operations) |
| `screens/JuryCard.dc.html` | Admission review: the jury's card with a live one-number edit, verdict, lines, conditions, checks |
| `screens/Reference.dc.html` | Reference: status-tag criteria, terms and acronyms, units and limits, decision classes, crew levels, guests |

The `.dc.html` files use a small template runtime (holes like `{{ x }}` filled from `renderVals()`); read the markup
and the data in each file's script block. Style rules: naval control-room HMI for a Fincantieri audience (Titillium
Web and IBM Plex Mono, navy title bars, panel title strips, alarm colours), no Fincantieri logo or brand marks, no
text that explains the demo, terse operator labels and status words, injected faults tagged INJECTED.
`UI_CRITIQUE.md` holds the seven-lens critique of these screens and its ranked changes.
