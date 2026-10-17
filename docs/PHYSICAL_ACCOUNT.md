# Physical Account

Every number we rely on beyond Annex A and B, every Annex value we changed, and all we invented. Reasons and uses: [detail page](PHYSICAL_ACCOUNT_DETAIL.md).

<table>
<colgroup><col style="width:13%"><col style="width:15%"><col style="width:44.5%"><col style="width:17.5%"><col style="width:10%"></colgroup>
<thead><tr><th>Annex C row</th><th>What we assumed</th><th>Value</th><th>Why</th><th>Used in</th></tr></thead>
<tbody>
<tr><td>Electrical power</td><td>guest reserve</td><td>cruise 200, one set down 100 kW; slow 250, fast 150; admit at 200</td><td>propulsion out of scope</td><td>test</td></tr>
<tr><td></td><td>peak tolerance</td><td>peaks never credited; gate min(100, 120) - 5 headroom = 95 kW</td><td>peaks last 60 s (DEC-35)</td><td>test</td></tr>
<tr><td></td><td>mission lines</td><td>port: Bay 1, mast; stbd: Bay 2, deck, roof; line lost on a trip: none</td><td>total reserve binds</td><td>test</td></tr>
<tr><td></td><td>plant check</td><td>gensets at 0.9; hotel 400 kW; aux 55 kW; trip sheds 150 kW of hotel</td><td>consistency check only</td><td>test</td></tr>
<tr><td>Heat rejection</td><td>loop, seawater</td><td>-40 % = 1 of 2 pumps; chillers essential; scan 0.1 °C steps to 35 °C</td><td>cooling survives a trip</td><td>test</td></tr>
<tr><td>Positions</td><td>hull, roof, ramp</td><td>60 m hull; roof holds G5's antenna (60 kg); ramp craft up to 7 m</td><td>roof clears drones</td><td>card</td></tr>
<tr><td>Mass / stability</td><td>G4 hangar</td><td>850 kg, not Annex B's 900 kg</td><td>organizer fix (DEC-22)</td><td>card, test</td></tr>
<tr><td></td><td>Scenario B set</td><td>G3, G4, G5, 9.515 t; brief's G2-G5 (13.015 t of 10) refused</td><td>override logged (DEC-32)</td><td>test</td></tr>
<tr><td>Data links</td><td>rates judged</td><td>guests' minimum rates, nominal gap shown as degraded; SATCOM at its 2 Mbit/s floor; floors G3 acoustic 1 kbit/s, G5 SATCOM 1 Mbit/s</td><td>admission rule (DEC-38)</td><td>card, test</td></tr>
<tr><td></td><td>LOS radio</td><td>top rate 20 Mbit/s, G4 kept within 20 km (A.5 reach 20-40 km)</td><td>unverified; range is ours</td><td>test</td></tr>
<tr><td></td><td>acoustic link</td><td>up only while course steady, noise quiet, no deck machinery; lost at once; 60 s per message; Scenario B water not layered</td><td>A.5's rule, safe end</td><td>test</td></tr>
<tr><td>State transitions</td><td>R3 lead time</td><td>confirm 1 min at 14, 3 at 6; clear deck 5 at 14, 12 at 6</td><td>A.6 slow end, worst case</td><td>test</td></tr>
<tr><td></td><td>Scenario B seed</td><td>confirm 1, clear 4, approach 4 min: G4 lands at minute 17</td><td>replayable, inside A.6</td><td>test</td></tr>
<tr><td>Compute / response time</td><td>fault entry</td><td>trip on 2 of 3 signals, pump on alarm plus flow or delta-T, held 1 s; restore after 60 s; a feed silent 3 s falls to its conservative value</td><td>one reading never sheds</td><td>test</td></tr>
<tr><td></td><td>timeout, safety</td><td>on a miss: admit no, hold, run the ready ladder; safety by table lookup</td><td>no solver on 200 ms</td><td>not yet</td></tr>
<tr><td></td><td>compute</td><td>cores G1 2, G2 2, G3 4, G4 4; own use: watts, latency, CPU share</td><td>Annex B gives no compute</td><td>card, planned</td></tr>
<tr><td>Mission priorities / crew</td><td>R3 deck rules</td><td>14: officer reports, bridge confirms; 6: standing plan from launch; 0: only on a deck latched clear at the last sweep, else forbidden</td><td>no one clears deck at 0</td><td>test</td></tr>
<tr><td></td><td>R3 timing</td><td>approach 4 min; drain 1.11 %/min; stale 10 s; secured 60 s</td><td>drain unverified</td><td>test</td></tr>
<tr><td></td><td>mission weights</td><td>high 1.0, medium 0.5, low 0.2, ours if unstated; 1-2 critical each</td><td>Annex B: high/medium/low</td><td>code, missions, test</td></tr>
<tr><td>Anything else</td><td>guest modes</td><td>kW/kept: G2 sampling 6/0.8, standby 1/0; G3 standby 1/0.3; G4 charge 10/0.7, standby 2/0.3; G3 cradle 3.5 t, vehicle 2 t 5.5 m</td><td>Annex B gives only kW</td><td>card</td></tr>
<tr><td></td><td>invented</td><td>G6 card; pump fault at minute 19: loop 80 kW, ceiling 75, load 81</td><td>cooling binds (DEC-40)</td><td>card, code, test</td></tr>
</tbody>
</table>

**Closing question.** One change: a standby chilled-water pump, so losing a pump no longer costs 40 % of the loop (A.2), 48 kW at 30 °C. Our minute-19 pump fault then sheds nothing: at 24 °C the loop keeps 133.3 kW, not 80, so the 81 kW load fits under 95 kW, not 75. At 30 °C a pump loss today leaves guests 67 kW for up to 14 days with no repair at sea (A.6, A.10), against 105 kW for our Scenario B set and 100 for A5; with the pump both fit under 115 kW. An exchanger fault still costs 40 %. A 50 kW battery for a genset restart helps less: at 30 °C cooling caps it at 20 kW.
