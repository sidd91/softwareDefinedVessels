// Reference: status-tag criteria, terms and acronyms (D1 to D6 among them), units and limits, decision classes,
// crew levels, guests and priority files. Guests and priority files come from the cards and config/missions.
import { esc, chip, tag, panel, getJSON } from './util.js';
import { app, setHeader } from './app.js';

const TAGS = [
  ['NORMAL', 'Resource class', 'Within its limit with more than 10 % free. No confirmed fault on the class.'],
  ['NEAR LIMIT', 'Resource class', 'Less than 10 % of the limit free.'],
  ['DEGRADED', 'Resource class', 'Capacity below nominal after a confirmed fault while another class sets the limit. GEN 2 trip leaves 100 kW of guest reserve. One CHW pump down leaves 60 % of cooling.'],
  ['LIMITING', 'Resource class', 'Sets the active limit after a confirmed fault on the class. Limit = min(power reserve, CHW capacity) - 5 kW headroom.'],
  ['OVER', 'Resource class', 'Committed load above the limit.'],
  ['FULL', 'Resource class', 'Every discrete position of the class is assigned. Applies to deck and mast positions.'],
  ['REDUCED', 'Data link', 'Guests carried at their minimum rate, below nominal demand.'],
  ['DOWN', 'Data link', 'Acoustic link down by rule: it needs a steady course, a quiet ship and no deck machinery.'],
  ['EXECUTED', 'Shed step', 'Step applied. Demand is back within the limit.'],
  ['COMMANDED', 'Shed step', 'Step decided on this tick, applied on the next.'],
  ['ARMED', 'Shed step', 'Next steps, recomputed every tick. Applied automatically when demand exceeds the limit.'],
  ['LAST', 'Shed step', '60 S guest. Gives power only after every 5 S step, one step a second, all within 60 s of the fault.'],
  ['NEVER', 'Shed step', '200 MS guest. Never shed. Only stop, hold or secure, answered within 200 ms.'],
  ['200 MS / 5 S / 60 S', 'Response class', 'A.8 time limits as shed priority. 200 MS never shed, 5 S first action, 60 S mission critical. 30 S marks a restore.'],
  ['ALARM', 'Event log', 'Plant fault confirmed. Genset trip: 2 of 3 signals. CHW pump trip: plant alarm plus low flow or high delta-T.'],
  ['SHED', 'Event log', 'Load management step executed by D4.'],
  ['HOLD', 'Event log', 'D4 checked the load against the new limit and took 0 steps. The next step stays armed.'],
  ['ARBITRATION', 'Event log', 'Right-of-way decision by D3 between incompatible guest conditions.'],
  ['CREW POLICY', 'Event log', 'D5 decision on rule R3 at the crew level aboard: confirm, standing plan, automatic, forbidden, held or cleared.'],
  ['STATE', 'Event log', 'Guest or ship state change completed or reported.'],
  ['INJECTED', 'Event log marker', 'Fault entered by the scenario timeline, not by plant behaviour.'],
  ['VALID / PROBLEMS', 'Profile builder', 'The loader accepts the file, or names each field it refuses.'],
  ['STANDBY IN STEP', 'Title bar', 'The standby board, running its own estimator and core on the same frames, decides the same. OUT OF STEP names the first field that differs.'],
  ['YES', 'Admission verdict', 'Fits every line at the envelope: both gensets, 200 kW reserve, seawater 30 °C. Holds with one genset down.'],
  ['YES-IF', 'Admission verdict', 'Fits only after the listed conditions, ranked by mission value lost. Also set when one genset down does not hold.'],
  ['NO', 'Admission verdict', 'No removal or throttle set makes the card fit.'],
  ['NOT NOW', 'Admission verdict', 'Fits, but not in the current ship state or installation window. Next window shown.'],
  ['CARD REJECTED', 'Admission verdict', 'Card fails the manifest schema. Field named. Previous card kept.'],
  ['HOLDS', 'One genset down', 'Demand within the 95 kW gate with no action.'],
  ['HOLDS BY THROTTLING', 'One genset down', 'Within 95 kW after interruptible throttle steps, each named with kW freed.'],
  ['DOES NOT HOLD', 'One genset down', 'No throttle set fits. The verdict becomes YES-IF.'],
  ['OK / OVER', 'Resource line', 'Demand at or under capacity, or over capacity.'],
  ['RUN / TRIP / OFF', 'Plant equipment', 'Running, tripped on a confirmed fault, or stopped.'],
];

const TERMS = [
  ['ArgOS', 'Resource governor for the ship’s physical budget across eight classes.'],
  ['D1 ADMISSION', 'Whether a guest card can come aboard: YES, YES-IF, NO or NOT NOW, with the binding line named. Within 30 s.'],
  ['D2 PLACEMENT', 'Where an admitted guest goes: bay, flight deck or mast position, with rejected alternatives. Within 30 s.'],
  ['D3 RIGHT OF WAY', 'Who wins when two guests need ship states that cannot both hold. Hard limits first, then mission weights. Within 2 s.'],
  ['D4 SHEDDING', 'Degradation by response class when demand exceeds the limit. 5 S guests first, then mission-critical 60 S guests one step a second. Throttle before switch-off inside each class. First step within 5 s, all within 60 s.'],
  ['D5 CREW POLICY', 'How each rule acts at 14, 6 or 0 aboard: crew confirms, standing plan, automatic or forbidden.'],
  ['D6 PHYSICAL ACCOUNT', 'Every number assumed, narrowed or invented beyond the ship and guest data, with its reason.'],
  ['MRV-60', 'Multi-role vessel, 60 m reference hull.'],
  ['GEN 1, GEN 2', 'Generator sets, 450 kW each, 90 % load limit.'],
  ['CHW', 'Chilled-water loop. Rejects guest and electronics heat to seawater.'],
  ['CHW P1, P2', 'Chilled-water pumps. One pump down leaves 60 % of capacity.'],
  ['FD', 'Flight deck, 12 × 8 m, with hangar.'],
  ['BAY 1, BAY 2', 'Mission bays. BAY 1 is on the stern ramp.'],
  ['RAMP', 'Stern ramp. One craft of 7 to 9 m and up to 5 t.'],
  ['MAST', 'Three positions, up to 60 kg each, air cooling only. Two hold host terminals.'],
  ['HOST', 'Ship’s own mast equipment: navigation radar and satellite terminal.'],
  ['ANT', 'Antenna.'],
  ['UAV', 'Uncrewed aerial vehicle. G4.'],
  ['LOS', 'Line-of-sight radio. 1 to 20 Mbit/s, 20 to 40 km.'],
  ['SATCOM', 'Satellite link. 2 to 8 Mbit/s shared, 70 to 95 % availability.'],
  ['ACOUSTIC', 'Underwater link to G3. 1 to 5 kbit/s. Up only with steady course, quiet ship and no deck machinery.'],
  ['HLO', 'Helicopter landing officer. Reports the deck clear or not clear.'],
  ['R3', 'Clear-deck rule for G4 recovery. Bridge confirms at 14 aboard, standing plan at 6, latched deck state at 0.'],
  ['MC', 'Mission critical under the active priority file.'],
  ['RSV', 'Reserved. Capacity held for a guest before it draws.'],
  ['CAP', 'Capability kept by the current mode, % of full.'],
  ['LOSS', 'Capability a step takes away, % of full.'],
  ['HEADROOM', 'Kept free under the shed limit so a normal load swing does not re-trigger shedding. 5 kW.'],
  ['USABLE', 'Power still free under the active limit while cooling binds.'],
  ['STAB', 'Stability load in tonne-equivalent.'],
  ['PRIORITY', 'The priority file in force: mission weights and mission-critical guests.'],
  ['SIM ×12', 'Run pace. One ship minute every 5 s.'],
  ['LIVE', 'The tick loop running now: simulator frames, the state estimator, the core’s decisions.'],
  ['REPLAY', 'Recorded snapshots and decision records played back in ship time.'],
  ['PROFILE', 'A priority file: weights, mission-critical guests, response classes, shed order, crew policy. Applied at sea or saved as a new file.'],
  ['CLASS', 'Response class of a guest under the active profile: 200 MS, 5 S or 60 S.'],
  ['T+', 'Scenario ship time, hh:mm:ss.'],
  ['SW', 'Seawater temperature.'],
  ['ENV', 'Mission envelope: seawater 12 to 30 °C, slow and cruise bands, sea state up to 5, wind up to 30 kn.'],
];

const UNITS = [
  ['Power', 'kW', 'Guest reserve with two gensets: 250 kW slow, 200 kW cruise, 150 kW fast. 100 kW with one.'],
  ['Limit', 'kW', 'min(power reserve, CHW capacity) - 5 kW headroom.'],
  ['Heat', 'kW', '1 kW electric = 1 kW heat. CHW 160 kW at 12 °C to 120 kW at 30 °C, linear.'],
  ['Energy', 'kWh', 'Battery and charge budgets.'],
  ['Mission lines', 'kW', 'PORT and STBD, 150 kW each.'],
  ['Mass', 't', 'Margin 10.000 t above the base ship.'],
  ['Stability', 't-eq', 'Mass × position factor: BAY 1.0, FD 1.2, hangar roof 1.2, MAST 3.0. Budget 12.000 t-eq.'],
  ['Data', 'Mbit/s, kbit/s', 'Judged at each guest’s minimum rate.'],
  ['Compute', 'cores', '4 nodes × 32 cores, 80 % to guests: 102 cores.'],
  ['Seawater', '°C', 'Admission judged at 30 °C.'],
  ['Speed', 'kn', 'Bands: slow 3 to 5, cruise 10 to 14, fast 18.'],
  ['Battery', '%', 'G4 below 20 %: land within 12 min or ditch.'],
  ['Response', 's', 'Decision compute time against the A.8 ceiling. Replayed: ship time from the raw fault event to the first action.'],
];

const CLASSES = [
  ['D1 ADMISSION', 'Guest card verdict: YES, YES-IF, NO or NOT NOW.', '30 s'],
  ['D2 PLACEMENT', 'Bay, deck or mast position, rejected alternatives listed.', '30 s'],
  ['D3 RIGHT OF WAY', 'Incompatible guest conditions resolved. Hard limits first.', '2 s'],
  ['D4 SHEDDING', 'Degradation and shedding in the declared order.', '5 s first · 60 s all'],
  ['D5 CREW POLICY', 'Rule action per crew level.', 'with D3, D4'],
  ['D6 PHYSICAL ACCOUNT', 'Every assumed or narrowed number.', 'per run'],
  ['SAFETY', 'Stop, hold, secure. Answered from a precomputed table.', '0.2 s'],
];

const CREW = [
  ['14', 'CONFIRM', 'HLO reports the deck. Bridge confirms before recovery.'],
  ['6', 'STANDING PLAN', 'Plan approved at launch. Recovery proceeds on the HLO report.'],
  ['0', 'AUTO / FORBIDDEN', 'Recovery only if the deck was latched clear at the last crew sweep with no deck activity since. Otherwise forbidden.'],
];

const ORDER = [
  ['1', '200 MS', 'Never shed. Safety-critical cards and the profile’s response.safety_command list.'],
  ['2', 'Hard limits', 'A guest’s hard limit binds before any weight.'],
  ['3', 'Class', 'Every 5 S step before any 60 S step. 60 S steps go one a second after a fresh reading.'],
  ['4', 'Throttle before shed', 'Inside each class, every throttle step comes before any switch-off.'],
  ['5', 'Declared order', 'The profile’s shed_order, when it has one.'],
  ['6', 'Least value lost per kW', 'Mission weight × capability lost ÷ kW freed, lowest first. Ties by guest id.'],
];

const SECTIONS = [['tags', 'STATUS TAGS'], ['terms', 'TERMS'], ['units', 'UNITS AND LIMITS'], ['classes', 'DECISIONS'], ['order', 'DEGRADATION'], ['crew', 'CREW'], ['guests', 'GUESTS'], ['files', 'PRIORITY FILES'], ['kit', 'COMPUTERS']];

let data = null;

export async function renderReference(root) {
  setHeader(SECTIONS.map(([id, name]) => `<button type="button" class="chip" data-goto="ref-${id}">${name}</button>`).join(''));
  if (!root.__wired) {
    document.getElementById('chips').addEventListener('click', e => {
      const b = e.target.closest('button[data-goto]');
      if (b && app.view === 'ref') document.getElementById(b.dataset.goto).scrollIntoView({ block: 'start' });
    });
    root.__wired = true;
  }
  if (!data) data = await getJSON('/api/reference');
  root.innerHTML = `
${section('tags', 'STATUS TAGS · CRITERIA', table(['TAG', 'APPLIES TO', 'SET WHEN'], TAGS.map(t => [tag(t[0], true), `<span style="color: var(--muted)">${esc(t[1])}</span>`, esc(t[2])]), 'ref-tags', 760))}
<div class="row">
  ${section('terms', 'TERMS AND ACRONYMS', rows(TERMS), '', 'flex: 1 1 560px')}
  <div class="col" style="flex: 1 1 560px">
    ${section('units', 'UNITS AND LIMITS', table(['QUANTITY', 'UNIT', 'LIMIT OR RULE'], UNITS.map(u => [`<b>${esc(u[0])}</b>`, `<span class="mono">${esc(u[1])}</span>`, esc(u[2])])))}
    ${section('classes', 'DECISION CLASSES', table(['CLASS', 'DECIDES', 'CEILING'], CLASSES.map(c => [`<b>${esc(c[0])}</b>`, esc(c[1]), `<span class="mono">${esc(c[2])}</span>`])))}
    ${section('order', 'DEGRADATION ORDER · D4', table(['#', 'RULE', 'MEANING'], ORDER.map(o => [`<span class="mono">${esc(o[0])}</span>`, `<b>${esc(o[1])}</b>`, esc(o[2])])))}
    ${section('crew', 'CREW LEVELS', table(['CREW', 'RULE ACTION', 'DECK CLEAR, RECOVERY'], CREW.map(c => [`<span class="mono" style="font-weight: 600">${esc(c[0])}</span>`, `<b>${esc(c[1])}</b>`, esc(c[2])])))}
  </div>
</div>
${section('guests', 'GUESTS', table(['ID', 'GUEST', 'POSITION', 'COOLING', 'MODES, kW'], data.guests.map(g => [`<b>${esc(g.id)}</b>`, esc(g.name), esc(g.pos), esc(g.cooling), `<span class="mono">${esc(g.modes)}</span>`]), '', 700))}
${section('files', 'PRIORITY FILES', table(['FILE', 'WEIGHTS', 'MISSION CRITICAL', 'CLASSES'], data.missions.map(m => [`<b>${esc(m.name)}</b> <span class="mono" style="color: var(--muted)">${esc(m.id)}.yaml</span>`, `<span class="mono">${esc(m.weights)}</span>`, esc(m.mc), `<span class="mono">${esc(m.tiers)}</span>`]), '', 900))}
${data.devices.length ? section('kit', 'GOVERNOR COMPUTERS', table(['ID', 'KIND', 'ROLE', 'SITE', 'STORAGE'], data.devices.map(d => [`<b class="mono">${esc(d.id)}</b>`, esc(String(d.kind || '').replace(/_/g, ' ').toUpperCase()), esc(String(d.role || '').replace(/_/g, ' ').toUpperCase()), esc(String(d.site || '').replace(/_/g, ' ').toUpperCase()), d.storage_gb != null ? `<span class="mono">${esc(d.storage_gb)} GB</span>` : '--']), '', 700)) : ''}`;
}

function section(id, title, inner, cls = '', style = '') {
  return `<section id="ref-${id}" class="panel ref ${cls}" aria-label="${esc(title)}" style="scroll-margin-top: 8px; ${style}"><div class="strip"><span>${esc(title)}</span></div>${inner}</section>`;
}

function table(heads, body, cls = '', minWidth = 0) {
  const th = heads.map(h => `<th scope="col">${esc(h)}</th>`).join('');
  const tr = body.map(r => `<tr>${r.map((c, i) => i === 0 ? `<th scope="row" style="font-weight: 400">${c}</th>` : `<td>${c}</td>`).join('')}</tr>`).join('');
  return `<div class="scroll-x"><table class="big ${cls}"${minWidth ? ` style="min-width: ${minWidth}px"` : ''}><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table></div>`;
}

function rows(list) {
  return `<table class="big"><tbody>${list.map(([k, v]) => `<tr><th scope="row" style="white-space: nowrap; width: 130px">${esc(k)}</th><td>${esc(v)}</td></tr>`).join('')}</tbody></table>`;
}
