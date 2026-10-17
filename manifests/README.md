# Adding a guest card

A guest is any equipment that comes aboard to give the ship a capability it did not have. It describes
itself to the hull with one YAML file that must pass `manifests/schema.json`. Adding a guest never
needs a code change. Worked example: `G6.yaml`, our containerised desalination unit.

1. **Copy the closest card** to `manifests/G<n>.yaml` with the next free id.
2. **Say what it returns.** `capability.name` is a short weighted name such as `fresh_water`;
   `capability.relevance` records the card's own view per mission (high, medium, low).
3. **Say how it is cooled.** `chilled_water` loads the cooling loop 1 kW of heat per kW electric;
   `air` is only allowed at the mast or hangar roof, up to 2 kW.
4. **Say where it can go.** Each part lists `mass_t`, optional `area_m2`, `preferred` positions and
   `allowed` positions from: `bay1` (whole 20-ft bay), `bay1_half`, `bay2`, `flight_deck`, `mast_free`,
   `hangar_roof`. Set `needs_bay_clear` if its work needs the deck around its bay clear, and
   `uses_ramp` if it launches over the stern ramp.
5. **Say what it consumes**, per class, as `min`, `nominal`, `peak` and `peak_duration_s`: power in kW
   and, where they apply, backbone, SATCOM and line-of-sight data in Mbit/s, acoustic data in kbit/s,
   and compute cores. A peak longer than 60 s counts as sustained for admission.
6. **List its modes** from full capability down to `"off"` (quote it: YAML reads a bare off as false),
   each with `power_kw` and `capability_retained` between 0 and 1. The governor throttles down this
   ladder before shedding.
7. **State its conditions** on ship state per activity (speed, course, noise, deck, emission, wind,
   sea state), its relations (`part_of`, `requires`, `excludes`, absolute or conditional), its
   installation work in port and at sea (people, hours or minutes, via), its criticality
   (`safety_critical`; mission criticality comes from the priority file), and any `hard_limits`.
8. **Mark every number you invented** with `assumed: true` so it reaches the Physical Account.
9. **Give it a weight in every priority file**: add its capability name to `weights` in each
   `config/missions/*.yaml`.
10. **Validate.** Run the tests; they fail if the card breaks the schema or a priority file misses
    its capability.

```bash
uv run pytest
```

Planned: a `sdv validate manifests/G7.yaml` command that names the exact field that is missing or
wrong, so a guest's author can fix it without reading the schema.
