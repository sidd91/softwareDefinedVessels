# Adding a guest card

A guest is any equipment that comes aboard to give the ship a capability it did not have. It describes
itself to the hull with one YAML file that must pass `manifests/schema.json`. Adding a guest never
needs a code change. Worked example: `G6.yaml`, our containerised desalination unit. It declares
ship-state conditions, an exclusion, hard limits and the two people it needs to start. `G3.yaml`
shows an assembly of two parts.

1. **Copy the closest card** to `manifests/G<n>.yaml` with the next free id.
2. **Say what it returns.** `capability.name` is a short weighted name such as `fresh_water`;
   `capability.relevance` records the card's own view per mission (high, medium, low).
3. **Say how it is cooled.** `chilled_water` loads the cooling loop 1 kW of heat per kW electric;
   `air` is only allowed at the mast or hangar roof, up to 2 kW.
4. **Say where it can go.** Each part lists `mass_t`, optional `area_m2`, `preferred` positions and
   `allowed` positions from: `bay1` (whole 20-ft bay), `bay1_half`, `bay2`, `flight_deck`, `mast_free`,
   `hangar_roof`. Set `needs_bay_clear` if its work needs the deck around its bay clear, and
   `uses_ramp` if it launches over the stern ramp. A part that belongs to another part names it in
   `part_of` (G3's vehicle rides on its cradle), and a craft that crosses the ramp gives `length_m`.
5. **Say what it consumes**, per class, as `min`, `nominal`, `peak` and `peak_duration_s`: power in kW
   and, where they apply, backbone, SATCOM and line-of-sight data in Mbit/s, acoustic data in kbit/s,
   and compute cores. A peak longer than 60 s counts as sustained for admission.
6. **List its modes** from full capability down to `"off"` (quote it: YAML reads a bare off as false),
   each with `power_kw` and `capability_retained` between 0 and 1. The governor throttles down this
   ladder before shedding.
7. **State its conditions, relations and limits in typed form.** Every name comes from
   `config/signals.yaml`, and the loader (`src/sdv/loader.py`) refuses an unknown name or value with
   the field named.
   - Register each activity under the guest in `config/signals.yaml` `activities` first.
   - `conditions`: per activity, `requires` maps a signal to an exact value, a list of allowed values,
     or a range: `{activity: launch_recovery, requires: {deck_flight_deck: clear, wind_kn: {max: 25},
     speed_kn: {min: 5, max: 12}, ramp: free}}`.
   - `relations.excludes`: `{activity: winch, excludes: G3.surveying}`, one of this guest's activities
     against another guest's activity. `relations.requires` lists ship positions (`stern_ramp`).
   - `hard_limits`: `{when: {signal: G4.battery_pct, op: "<", value: 20}, then: {action: land_or_ditch,
     within_min: 12}}`. Actions: `land_or_ditch`, `land`, `return_and_land`, `mode` (with `mode`), `hold`.
   - Installation work in port and at sea (people, hours or minutes, via, and `parts` when only some
     parts move), criticality (`safety_critical`; mission criticality comes from the priority file).
     Port hours follow A.11: 4 to 8 h per bay guest, 2 to 4 h per mast guest.
8. **Mark every number you invented** with `assumed: true` (on the quantity, mode or part) so it
   reaches the Physical Account.
9. **Give it a weight in every priority file**: add its capability name to `weights` in each
   `config/missions/*.yaml`.
10. **Validate.** Run the tests; they fail if the card breaks the schema, uses a name the vocabulary lacks, a priority file misses
    its capability, or a bay or mast guest's port hours fall outside A.11.

```bash
uv run pytest
```

To check a new file before it goes into `manifests/`, admit it from where it is:

```bash
uv run sdv admit --card path/to/G7.yaml --installed G4,G5 --mission disaster_relief
```

A missing or wrong field is named (`refused path/to/G7.yaml: placement.parts[0].mass_t: 'abc' is not of
type 'number'`, exit code 2). With no activity registered yet for its id, the card is judged on its quantities,
positions and relations and the output says `activities not registered: conditions not judged`. A file in
`manifests/` that fails is reported once at start-up (`refused manifests/G7.yaml: <field>: <problem>`) and
skipped; the other cards load.
