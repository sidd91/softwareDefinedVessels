// Admission review: one guest card against the ship, D1 run by the engine on every committed edit (a part's mass,
// the card's nominal or peak kW). An edit the engine cannot apply comes back 4xx as {refused: {field, reason}}:
// the refusal is shown on the card and the last verdict stays on the panel.
import { esc, chip, tag, panel } from './util.js';
import { app, setHeader } from './app.js';

const state = { caseId: 'A1-survey', edits: {}, good: {}, data: null, refused: null, seq: 0 };

export function renderAdmit(root) {
  if (!root.__wired) {
    wire(root);
    root.__wired = true;
  }
  if (state.data) paint(root);
  load(root);
}

function wire(root) {
  root.addEventListener('change', e => {
    const el = e.target;
    if (el.matches('select[data-case]')) {
      state.caseId = el.value;
      state.edits = {};
      state.good = {};
      load(root);
    } else if (el.matches('input[data-field]')) {
      const base = Number(el.dataset.base);
      const raw = el.value.trim();
      if (raw !== '' && Number(raw) === base) delete state.edits[el.dataset.field];
      else state.edits[el.dataset.field] = raw === '' ? 'blank' : raw;
      load(root);
    }
  });
  root.addEventListener('keydown', e => {
    if (e.key === 'Enter' && e.target.matches('input[data-field]')) e.target.dispatchEvent(new Event('change', { bubbles: true }));
  });
  root.addEventListener('click', e => {
    if (e.target.closest('button[data-revert]')) {
      state.edits = {};
      state.good = {};
      load(root);
    }
  });
}

async function fetchAdmit(q) {
  const r = await fetch(`/api/admit?${q}`, { cache: 'no-store' });
  const body = await r.json().catch(() => null);
  if (!r.ok) throw Object.assign(new Error(`/api/admit: ${r.status}`), { status: r.status, body });
  return body;
}

async function load(root) {
  const seq = ++state.seq;
  const q = new URLSearchParams({ case: state.caseId });
  for (const [k, v] of Object.entries(state.edits)) q.append('edit', `${k}=${v}`);
  for (const [k, v] of Object.entries(state.good)) q.append('keep', `${k}=${v}`);
  let d;
  try {
    d = await fetchAdmit(q);
  } catch (err) {
    if (seq !== state.seq) return;
    state.refused = (err.body && err.body.refused) || { field: '', reason: err.message };
    if (state.data) paint(root);  // the previous verdict stays; the refusal is shown on the card
    else root.innerHTML = panel('ADMISSION REVIEW', `<p class="sentence" style="padding: 12px">${esc(state.refused.field)} ${esc(state.refused.reason)}</p>`);
    return;
  }
  if (seq !== state.seq) return;
  state.refused = null;
  state.data = d;
  if (!d.rejected) state.good = { ...state.edits };
  paint(root);
}

function paint(root) {
  const d = state.data;
  if (app.view === 'admit') {
    setHeader([
      chip(`MISSION ${esc(d.case.mission)}`, 'strong'),
      chip('ALONGSIDE · SHORE POWER'),
      chip(`INSTALLED ${esc(d.case.installed.join(' '))}`),
      chip(esc(d.envelope)),
    ].join(''), `RESPONSE ${d.latency_ms.toFixed(1)} ms / ${d.ceiling_s.toFixed(1)} s`, true);
  }
  const focused = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.field : null;
  root.innerHTML = `<div class="row">${card(d)}<div class="col" style="flex: 999 1 640px">${verdict(d)}
<div class="row"><div class="col" style="flex: 1 1 320px">${lines(d)}</div><div class="col" style="flex: 1 1 320px">${conditions(d)}${checks(d)}</div></div>
</div></div>`;
  if (focused) {
    const el = root.querySelector(`input[data-field="${CSS.escape(focused)}"]`);
    if (el) el.focus();
  }
}

// One editable number: the typed value while an edit is pending, else the card's; red when the engine refused or
// rejected this field, amber when the edit was accepted.
function numberInput(id, field, base, shown) {
  const typed = state.edits[field];
  const rej = state.data.rejected;
  const bad = (rej && rej.field === field) || (state.refused && state.refused.field === field);
  const edited = typed != null && !bad;
  const value = typed != null ? (typed === 'blank' ? '' : typed) : shown;
  const input = `<input id="${esc(id)}" class="massin${bad ? ' bad' : edited ? ' edited' : ''}" type="text" inputmode="decimal" data-field="${esc(field)}" data-base="${esc(base)}" value="${esc(value)}">`;
  return { input, cls: edited || bad ? ' class="hl"' : '' };
}

function card(d) {
  const opts = d.cases.map(c => `<option value="${esc(c.id)}"${c.id === d.case.id ? ' selected' : ''}>${esc(c.label)}</option>`).join('');
  const rej = d.rejected;
  const ref = state.refused;
  const parts = d.parts.map(p => {
    const n = numberInput(`m-${p.name}`, p.field, p.base, Number(p.mass_t).toFixed(3));
    return `<tr${n.cls}><td><label for="m-${esc(p.name)}">${esc(p.name.toUpperCase())}</label></td><td>${n.input}</td><td>${esc(p.pos)}</td></tr>`;
  }).join('');
  const power = (d.power || []).map(p => {
    const n = numberInput(`p-${p.name}`, p.field, p.base, String(p.kw));
    return `<tr${n.cls}><td><label for="p-${esc(p.name)}">${esc(p.label)}</label></td><td>${n.input}</td><td>${esc(p.mode)}</td></tr>`;
  }).join('');
  const nEdits = Object.keys(state.edits).length;
  const schema = ref
    ? `<span class="schema bad">EDIT REFUSED · ${esc(ref.field)} · ${esc(ref.reason)} · PREVIOUS VERDICT KEPT</span>`
    : rej
      ? `<span class="schema bad">SCHEMA FAIL · ${esc(rej.field)} · ${esc(rej.problem)} · PREVIOUS CARD KEPT</span>`
      : `<span class="schema">${nEdits ? `EDITED ${nEdits} · SCHEMA OK` : 'SCHEMA OK'}</span>`;
  const facts = d.facts.map(f => `<tr><th scope="row" style="color: var(--muted); font-weight: 600">${esc(f.k)}</th><td class="num">${esc(f.v)}</td></tr>`).join('');
  return `<section class="panel card" aria-label="Guest card"><div class="strip"><span>CARD · ${esc(d.case.card)} ${esc(d.case.card_name)}</span></div>
<div class="body">
<label class="schema" for="case-sel" style="color: var(--muted)">CASE</label>
<select id="case-sel" class="sel" data-case="1">${opts}</select>
<table class="big"><thead><tr><th scope="col">PART</th><th scope="col">MASS t</th><th scope="col">POSITION</th></tr></thead><tbody>${parts}</tbody></table>
<table class="big"><thead><tr><th scope="col">POWER</th><th scope="col">kW</th><th scope="col">MODE</th></tr></thead><tbody>${power}</tbody></table>
<div class="row" style="gap: 8px; align-items: center"><button type="button" class="btn" data-revert="1">REVERT</button>${schema}</div>
<table class="big"><tbody>${facts}</tbody></table>
</div></section>`;
}

function verdict(d) {
  const cls = 'v-' + d.verdict_raw;
  return `<section class="panel" aria-label="Verdict"><div class="verdict-head ${esc(cls)}"><span>VERDICT</span><span class="word">${esc(d.verdict)}</span></div>
<div class="body" style="padding: 12px; gap: 8px">
<div class="binding"><span class="bk">BINDING</span><span class="bv">${esc(d.binding)}</span></div>
<p class="sentence">${esc(d.sentence)}</p>
</div></section>`;
}

function lines(d) {
  const rows = d.lines.map(l => `<tr class="${l.binding ? (l.s === 'OVER' ? 'exec' : 'hl') : ''}"><th scope="row" style="font-weight: 600">${esc(l.k)}</th>
<td class="num">${esc(l.v)}</td><td class="num">${esc(l.free)}</td><td>${tag(l.s)}</td></tr>`).join('');
  return panel('RESOURCE LINES', `<table class="big"><thead><tr><th scope="col">LINE</th><th scope="col">DEMAND / CAPACITY</th><th scope="col">FREE</th><th scope="col"></th></tr></thead><tbody>${rows}</tbody></table>`);
}

function conditions(d) {
  if (!d.options.length) return '';
  const rows = d.options.map((o, i) => `<tr class="${i === 0 ? 'hl' : ''}"><td>${o.n}</td><td class="b">${esc(o.remove)}${o.mc ? '<span class="mc">MC</span>' : ''}</td>
<td class="num">${esc(o.value_lost)}</td><td class="num">${esc(o.mass_after)}</td><td>${esc(o.moves || '--')}</td></tr>`).join('');
  return panel('CONDITIONS · RANKED BY MISSION', `<table class="big"><thead><tr><th scope="col">#</th><th scope="col">REMOVE</th><th scope="col">VALUE LOST</th><th scope="col">MASS AFTER</th><th scope="col">MOVE</th></tr></thead><tbody>${rows}</tbody></table>`);
}

function checks(d) {
  const rows = d.checks.map(c => `<tr><th scope="row" style="font-weight: 600">${esc(c.k)}</th><td class="num">${esc(c.v)}</td><td class="b">${esc(c.s)}</td></tr>`).join('');
  return panel('CHECKS', `<table class="big"><tbody>${rows}</tbody></table>`);
}
