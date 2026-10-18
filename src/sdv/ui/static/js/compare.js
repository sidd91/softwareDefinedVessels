// Demo compare: the same inputs under two priority files, side by side, at the minute the bottom bar's run is on.
import { esc, chip, meter, paint, getJSON } from './util.js';
import { app, setHeader } from './app.js';
import { recordRows } from './ops.js';

const state = { pinned: null, cache: new Map(), loading: new Set() };

function marks() {
  const ms = app.meta ? app.meta.marks[app.meta.missions[0].id] : [];
  return [{ t_s: 0, at: 0, t: '00:00', label: 'START' }, ...ms.filter(m => m.t_s > 0)];
}

function followed() {
  const t = app.tick ? app.tick.t_s : 0;
  const ms = marks().filter(m => m.t_s <= t);
  return ms.length ? ms[ms.length - 1].t_s : 0;
}

export function renderCompare(root) {
  const t = followed();
  if (!root.__wired) {
    root.addEventListener('click', e => {
      const b = e.target.closest('button[data-t], button[data-follow]');
      if (!b) return;
      state.pinned = b.dataset.follow ? null : Number(b.dataset.t);
      renderCompare(root);
    });
    root.__wired = true;
  }
  const d = state.cache.get(t);
  if (!d) {
    if (!state.loading.has(t)) {
      state.loading.add(t);
      getJSON(`/api/compare?t=${t}`).then(x => { state.cache.set(t, x); state.loading.delete(t); renderCompare(root); })
        .catch(() => state.loading.delete(t));
    }
    if (!root.__last) paint(root, '<div class="empty">--</div>');
    return;
  }
  header(d);
  const mark = marks().find(m => m.t_s === t);
  paint(root, `<div class="row">${d.files.map(f => ship(f, d.ships[f], mark)).join('')}</div>`);
}

function header(d) {
  if (!app.tick || app.view !== 'compare') return;
  const h = app.tick.view.header;
  setHeader([chip(esc(h.crew)), chip(esc(h.sea)), chip(esc(h.sea_state)), chip(`SIM ×${esc(app.tick.speed)}`)].join(''), d.clock);
}

const KEEP = ['DECISION', 'LAND BY', 'ACTION', 'RESULT', 'PRIORITY'];
const ALERT_TITLE = { 'G4 LOW BATT': 'DRONE LOW BATTERY', 'GEN 2 TRIP': 'GENERATOR 2 OFFLINE', 'CHW P1 TRIP': 'COOLING PUMP 1 FAILED' };
const WHO = { G1: 'G1 radio sensor', G3: 'G3 underwater robot', G4: 'G4 drone', G5: 'G5 comms unit' };

// One or two operator sentences built from this mission's decision record: what happened, what ArgOS did and why.
function alertText(d) {
  const R = Object.fromEntries(d.rows.map(r => [r[0], r[1]]));
  if (R['HARD LIMIT'] && R['LAND BY'] && R.COST) {
    const by = R['LAND BY'].split(' · ')[0];
    const leg = /ABORTED/.test(R.LEG || '') ? 'aborts its dive' : 'pauses and holds depth';
    const lost = (R.COST.match(/\d+ TO \d+ min/) || [''])[0].replace('TO', 'to');
    const kept = R.RESERVED ? `, ${R.RESERVED.replace(/^G\d /, '')} kept for drone charging` : '';
    return { level: 'ALARM', text: `G4 drone battery below 20 %, must land by ${by}. G3 underwater robot ${leg} so the drone lands first: ${lost} of survey lost${/OPEN-ENDED/.test(R.COST) ? ', no resume time' : ''}${kept}.` };
  }
  if (R.LIMIT && R.DEMAND && R.ACTION) {
    const cool = /CHW/.test(R.DEMAND);
    const lim = R.LIMIT.split(' = ')[1];
    const dem = R.DEMAND.split(' ')[0] + ' kW';
    if (/^0 STEPS/.test(R.ACTION)) {
      const spare = (R.ACTION.split(' · ')[1] || '').replace('SPARE', 'spare');
      return { level: 'CAUTION', text: `${cool ? 'Cooling' : 'Power'} limit drops to ${lim}. Load of ${dem} still fits with ${spare}, nothing turned down.` };
    }
    const [tag, rest] = [R.ACTION.split(' ')[0], R.ACTION.slice(R.ACTION.indexOf(' ') + 1)];
    const [from, to] = rest.split(' → ').map(x => x.toLowerCase());
    const res = (R.RESULT || '').replace(' / ', ' of ');
    return { level: 'ALARM', text: `${cool ? 'Cooling' : 'Power'} demand of ${dem} is over the ${lim} limit. ${WHO[tag] || tag} turned down from ${from} to ${to} to free ${R.FREED}, ${cool ? 'cooling' : 'power'} back within limit at ${res}.` };
  }
  return { level: 'ALERT', text: d.headline || d.sentence };
}

function alertBox(d, mark) {
  if (!d || !mark || !mark.t_s) {
    return `<div class="alert-pop" style="border: 2px solid var(--frame); border-left: 10px solid var(--frame); padding: 12px 16px; border-radius: 6px; margin-bottom: 12px">
<div style="font-weight: 700; font-size: 16px; letter-spacing: 1px">STATUS · T+00:00:00 · ALL EQUIPMENT RUNNING</div>
<div style="font-size: 18px; font-weight: 600; margin-top: 6px; line-height: 1.35">Mission under way. No alerts.</div></div>`;
  }
  const a = alertText(d);
  const [edge, fill] = a.level === 'ALARM' ? ['var(--red)', 'var(--red-pale)'] : ['var(--amber)', 'var(--amber-pale)'];
  const title = ALERT_TITLE[mark.label] || mark.label;
  return `<div class="alert-pop" role="alert" style="border: 2px solid ${edge}; border-left: 10px solid ${edge}; background: ${fill}; padding: 12px 16px; border-radius: 6px; margin-bottom: 12px">
<div style="font-weight: 700; font-size: 16px; letter-spacing: 1px">&#9650; ${a.level} · T+${esc(mark.t)}:00 · ${esc(title)}</div>
<div style="font-size: 18px; font-weight: 600; margin-top: 6px; line-height: 1.35">${esc(a.text)}</div></div>`;
}

function ship(f, s, mark) {
  const d = s.decision;
  const hot = new Set(s.mimic.zones.filter(z => z.hot).map(z => z.guest.split(' ')[0]));
  // The alert carries the story, so only the few record rows an operator checks stay: it all fits one screen.
  const record = d ? `<div class="kv" style="padding: 0">${recordRows(d.rows.filter(r => KEEP.includes(r[0])))}</div>` : '';
  const bars = s.bars.map(b => `<div><div class="bl"><b>${esc(b.name)}</b><span class="mono">${esc(b.value)}</span></div>
${meter(b.pct, b.mark, b.state === 'LIMITING' ? 'warn' : '')}</div>`).join('');
  const rows = s.guests.map(g => `<tr class="${hot.has(g.id) ? 'exec' : ''}"><td class="b">${esc(g.id)}</td><td>${esc(g.pos)}</td><td>${esc(g.mode)}</td><td class="num">${esc(g.kw)}</td><td class="num">${esc(g.cap)}</td></tr>`).join('');
  return `<section class="panel ship ${esc(f)}" aria-label="${esc(s.name)}">
<div class="strip"><span>${esc(s.name)}</span><span class="w">${esc(s.weights)}</span></div>
<div class="body">${alertBox(d, mark)}${record}<div class="bars">${bars}</div>
<table><thead><tr><th scope="col">ID</th><th scope="col">POS</th><th scope="col">MODE</th><th scope="col">kW</th><th scope="col">CAP</th></tr></thead><tbody>${rows}</tbody></table>
</div></section>`;
}
