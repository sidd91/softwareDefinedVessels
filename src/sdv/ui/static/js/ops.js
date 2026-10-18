// Operations (ship mimic, plant, eight tiles, decision record, shed order, guests, event log) and its drill-down,
// the constraint ledger. Both render the `view` the server builds from one snapshot and its records.
import { esc, tag, injected, stateWord, meter, panel, paint } from './util.js';

const CLASS_TAGS = new Set(['200 MS', '5 S', '60 S', '30 S']);

export function tierTag(tag) {
  return CLASS_TAGS.has(tag) ? `<span class="mc" title="RESPONSE CLASS">${esc(tag)}</span>` : '';
}

export function mountOps(root) {
  root.innerHTML = `
<div class="row">
  <div class="col wide">
    <section class="panel" aria-label="Ship mimic"><div class="strip"><span>SHIP MIMIC · PLAN</span></div><div class="body" id="ops-mimic"></div></section>
    <section class="tiles" aria-label="Resource classes" id="ops-tiles"></section>
  </div>
  <div class="col side">
    <div id="ops-decision"></div>
    <div id="ops-shed"></div>
    <div id="ops-guests"></div>
  </div>
</div>
<div id="ops-log"></div>`;
}

export function renderOps(root, v) {
  if (!root.querySelector('#ops-mimic')) mountOps(root);
  paint(root.querySelector('#ops-mimic'), mimic(v));
  paint(root.querySelector('#ops-tiles'), v.tiles.map(tile).join(''));
  paint(root.querySelector('#ops-decision'), decision(v.decision));
  paint(root.querySelector('#ops-shed'), shedOrder(v.shed_order));
  paint(root.querySelector('#ops-guests'), guests(v.guests));
  paint(root.querySelector('#ops-log'), log(v.log));
}

function mimic(v) {
  const zones = v.mimic.zones.map(z => `
<div class="zone${z.hot ? ' hot' : ''}"><span class="zl">${esc(z.zone)}</span><span class="zg">${esc(z.guest)}</span>
<span class="zm">${esc(z.mode)}</span><span class="zx">${esc(z.extra)}</span></div>`).join('');
  const ss = v.ship_state.map(c => `<span class="ss${c.moving ? ' moving' : ''}"><b>${esc(c.k)}</b>${esc(c.v)}</span>`).join('');
  const plant = v.plant.map(p => `<div class="pcell${p.trip ? ' trip' : ''}"><b>${esc(p.tag)}</b><span class="v">${esc(p.state)}${injected(p.injected)}</span></div>`).join('');
  return `
<div class="hull-wrap"><div class="hull">
<div class="zone ramp">RAMP<br>${esc(v.mimic.ramp)}</div>${zones}<div class="zone bow">BRIDGE</div>
</div></div>
<div class="shipstate"><span class="lbl">SHIP STATE</span>${ss}</div>
<div class="plant">${plant}</div>`;
}

function tile(t) {
  const tone = t.state === 'OVER' || t.state === 'LATE' ? 'bad' : (t.state === 'LIMITING' ? 'warn' : '');
  return `
<div class="tile"><div class="tn">${esc(t.name)}</div><div class="tb">
<span class="tv">${esc(t.value)}</span>${meter(t.pct, t.mark, tone)}
<div class="ts"><span class="s">${esc(t.sub)}${injected(t.injected)}</span>${stateWord(t.state)}</div>
</div></div>`;
}

export function recordRows(rows) {
  return rows.map(([k, val, inj]) => `<div class="r"><span class="k">${esc(k)}</span><span class="v">${esc(val)}${injected(inj)}</span></div>`).join('');
}

export function conflictTable(d) {
  if (!d.conflicts || !d.conflicts.length) return '';
  const [a, b] = d.conflict_heads;
  const rows = d.conflicts.map(c => c.k === 'EXCLUSION'
    ? `<tr class="clash"><th scope="row">${esc(c.k)}</th><td colspan="3">${esc(c.a)}</td><td><span class="cword">CONFLICT</span></td></tr>`
    : `<tr class="clash"><th scope="row">${esc(c.k)}</th><td class="num">${esc(c.now)}</td><td class="num">${esc(c.a)}</td><td class="num">${esc(c.b)}</td><td><span class="cword">CONFLICT</span></td></tr>`).join('');
  return `<table class="conflicts"><caption>CONDITIONS · SHIP STATE</caption>
<thead><tr><th scope="col">SIGNAL</th><th scope="col">NOW</th><th scope="col">${esc(a)}</th><th scope="col">${esc(b)}</th><th scope="col"></th></tr></thead>
<tbody>${rows}</tbody></table>`;
}

export function decision(d) {
  if (!d) {
    return panel('DECISION RECORD', '<div class="empty">NO DECISION</div>', { strip: 'navy' });
  }
  return `<section class="panel record" aria-label="Decision record">
<div class="strip navy"><span>${esc(d.title)}</span><span class="rtag ${esc(d.tone)}">${esc(d.tag)}</span></div>
<p class="why" title="${esc(d.sentence)}">${esc(d.headline || d.sentence)}</p>
${conflictTable(d)}
<div class="kv">${recordRows(d.rows)}</div>
${d.recheck ? `<div class="foot">${esc(d.recheck)}</div>` : ''}
${r3(d.r3)}
</section>`;
}

function r3(x) {
  if (!x) return '';
  return `<div class="r3"><div class="r3h"><span>R3 · CREW ${esc(x.crew)}</span><span class="tag t-CREW-POLICY">${esc(x.verdict)}</span><span class="mono">${esc(x.t)}</span></div>
<div class="r3s">${esc(x.sentence)}</div></div>`;
}

function shedOrder(s) {
  const rows = s.rows.map(r => `<tr class="${r.state === 'EXECUTED' ? 'exec' : ''}">
<td>${esc(r.n)}</td><td class="b">${esc(r.g)}${tierTag(r.tier)}</td><td>${esc(r.step)}</td>
<td class="num">${esc(r.kw)}</td><td class="num">${esc(r.loss)}</td><td>${tag(r.state)}</td></tr>`).join('');
  return panel(`SHED ORDER · ${s.mission}`, `<div class="scroll-x"><table>
<thead><tr><th scope="col">#</th><th scope="col">GUEST</th><th scope="col">STEP</th><th scope="col">kW</th><th scope="col">LOSS</th><th scope="col">STATE</th></tr></thead>
<tbody>${rows}</tbody></table></div><div class="foot">${esc(s.source)}</div>`);
}

function guests(gs) {
  const rows = gs.map(g => `<tr><td class="b">${esc(g.id)}${tierTag(g.tier)}</td><td>${esc(g.pos)}</td><td>${esc(g.mode)}</td><td class="num">${esc(g.kw)}</td><td class="num">${esc(g.cap)}</td></tr>`).join('');
  return panel('GUESTS', `<table><thead><tr><th scope="col">ID</th><th scope="col">POS</th><th scope="col">MODE</th><th scope="col">kW</th><th scope="col">CAP</th></tr></thead><tbody>${rows}</tbody></table>`);
}

function log(rows) {
  const body = rows.map(e => `<tr class="${e.seq != null ? 'decision' : ''}"><td class="time">${esc(e.t)}</td><td class="type">${tag(e.type)}</td>
<td class="tagc">${esc(e.tag)}</td><td class="msg">${esc(e.msg)}${injected(e.injected)}</td></tr>`).join('');
  return panel('EVENT LOG', `<div class="scroll-x"><table class="log" style="min-width: 760px">
<thead><tr><th scope="col">TIME</th><th scope="col">TYPE</th><th scope="col">TAG</th><th scope="col">MESSAGE</th></tr></thead>
<tbody>${body}</tbody></table></div>`);
}

// ------------------------------------------------------------------------------------------- constraint ledger

export function mountLedger(root) {
  root.innerHTML = `
<div class="row stretch">
  <div id="led-constraint" style="flex: 999 1 620px; min-width: 0; display: flex"></div>
  <aside class="col" style="flex: 1 1 320px" aria-label="Alarms and positions">
    <div id="led-alarms"></div>
    <div id="led-positions"></div>
  </aside>
</div>
<div id="led-rows"></div>`;
}

export function renderLedger(root, v) {
  if (!root.querySelector('#led-constraint')) mountLedger(root);
  const c = v.ledger.constraint;
  paint(root.querySelector('#led-constraint'), constraintPanel(c, v.shed_order));
  paint(root.querySelector('#led-alarms'), alarms(v.ledger.alarms));
  paint(root.querySelector('#led-positions'), positions(v.mimic));
  paint(root.querySelector('#led-rows'), ledgerTable(v.ledger.rows));
}

function constraintPanel(c, shed) {
  const rows = c.rows.map(r => `<tr class="${r.style === 1 ? 'bind' : r.style === 2 ? 'short' : ''}"><th scope="row">${esc(r.k)}${injected(r.injected)}</th><td>${esc(r.v)}</td></tr>`).join('');
  const a = c.action;
  const action = a ? `<div class="action-card"><span class="al">ACTION ${esc(a.t)}</span><span class="aw">${esc(a.what)}</span>
<span class="ak">${esc(a.kw)}</span><span class="ai">${esc(a.impact)}</span></div>` : '<div class="action-card"><span class="al">ACTION</span><span class="aw">NONE</span></div>';
  const ladder = shed.rows.map(s => `<tr class="${s.state === 'EXECUTED' ? 'exec' : ''}"><td class="b">${esc(s.g)}${tierTag(s.tier)}</td>
<td>${esc(s.step)} · ${esc(s.kw)} kW</td><td class="num">${esc(s.loss)}</td><td>${tag(s.state)}</td></tr>`).join('');
  return `<section class="panel" aria-label="Active constraint" style="flex: 1 1 auto; display: flex; flex-direction: column">
<div class="strip ${c.tone === 'limit' ? 'amber' : 'navy'}" style="padding: 8px 12px; align-items: baseline">
<span style="letter-spacing: 0.08em">${esc(c.title)}</span><span class="headline">${esc(c.headline)}</span></div>
<div class="row" style="padding: 12px">
<table class="calc"><tbody>${rows}</tbody></table>
<div class="col" style="flex: 1 1 280px; gap: 8px">${action}
<table class="mini"><caption>SHED ORDER · ${esc(shed.mission)}</caption><tbody>${ladder}</tbody></table></div>
</div></section>`;
}

function alarms(list) {
  const body = list.length
    ? list.map(a => `<div class="alarm-row"><span class="at">${esc(a.t)}</span><span class="ag">${esc(a.tag)}</span><span>${esc(a.msg)}</span>${injected(a.injected)}</div>`).join('')
    : '<div class="empty" style="padding: 6px 0">NONE</div>';
  return panel('ALARMS', `<div style="padding: 6px 10px 10px">${body}</div>`);
}

function positions(m) {
  const cells = m.zones.map(z => `<div class="${z.hot ? 'hot' : ''}"><strong>${esc(z.zone)}</strong> · ${esc(z.guest)} · ${esc(z.mode)}</div>`).join('');
  return panel('POSITIONS', `<div class="positions"><div><strong>RAMP</strong> · ${esc(m.ramp)}</div>${cells}</div>`);
}

function ledgerTable(rows) {
  const body = rows.map(r => `<tr class="${r.state === 'LIMITING' ? 'limiting' : ''}"><th scope="row" class="b">${esc(r.name)}</th>
<td class="num">${esc(r.cap)}</td><td class="num">${esc(r.lim)}</td><td class="num">${esc(r.used)}</td><td class="num">${esc(r.free)}</td><td>${tag(r.state, true)}</td></tr>`).join('');
  return panel('RESOURCE LEDGER', `<div class="scroll-x"><table class="big" style="min-width: 820px">
<thead><tr><th scope="col">CLASS</th><th scope="col">CAPACITY</th><th scope="col">LIMIT</th><th scope="col">COMMITTED</th><th scope="col">FREE</th><th scope="col">STATUS</th></tr></thead>
<tbody>${body}</tbody></table></div>`);
}
