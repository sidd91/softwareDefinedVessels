// Profile builder: forms over a priority file (weights, response classes, shed order, crew policy) and over a guest card's
// typed rules. Every check is the loader's (POST /api/builder/check). A valid profile is saved as a new file or
// applied at sea through the live run; a valid card is saved as a new draft.
import { esc, panel, paint, getJSON } from './util.js';
import { app } from './app.js';

const CLASS_WORDS = { safety_command: 'SAFETY COMMANDS ONLY', shed_first_action: 'FIRST ACTION', shed_full_sequence: 'MISSION CRITICAL' };
const ORDER = [['', 'COMPUTED'], ['1', 'FIRST 1'], ['2', 'FIRST 2'], ['3', 'FIRST 3'], ['-3', 'LAST 3'], ['-2', 'LAST 2'], ['-1', 'LAST 1']];
const SHIP_GROUPS = ['plant', 'ship_state', 'environment', 'links', 'crew'];

const st = {
  cat: null, base: null, id: '', name: '', notes: '', weights: {}, order: {}, tier: {}, confirm: {},
  problems: null, checkSeq: 0, result: null, applied: null,
  gid: 'G4', rules: [], cardProblems: null, cardResult: null, label: 'rules', form: null,
};

export async function renderBuilder(root) {
  if (!st.cat) {
    st.cat = await getJSON('/api/builder');
    start(st.cat.profiles.find(p => p.id === 'sar') ? 'sar' : st.cat.profiles[0].id);
    pickCard(st.gid in st.cat.cards ? st.gid : Object.keys(st.cat.cards)[0]);
  }
  if (!root.__wired) {
    wire(root);
    root.__wired = true;
  }
  paintAll(root);
}

// ------------------------------------------------------------------------------------------- state

function start(id) {
  const p = st.cat.profiles.find(x => x.id === id).doc;
  st.base = id;
  st.id = `${id}_edit`;
  st.name = `${p.name} edited`;
  st.notes = p.notes || '';
  st.weights = {};
  for (const c of st.cat.capabilities) st.weights[c.name] = p.weights[c.name] ?? 0;
  st.order = { ...(p.shed_order || {}) };
  st.tier = {};
  for (const g of st.cat.guests) {
    const safety = (p.response || {}).safety_command || [];
    st.tier[g.id] = g.safety_critical || safety.includes(g.id) ? 'safety_command'
      : p.mission_critical.includes(g.id) ? 'shed_full_sequence' : 'shed_first_action';
  }
  st.confirm = {};
  for (const [rule, levels] of Object.entries(p.confirm || {})) st.confirm[rule] = Object.fromEntries(Object.entries(levels).map(([k, v]) => [String(k), v]));
  st.result = null;
  st.applied = null;
}

function profileDoc() {
  const d = { id: st.id, name: st.name, weights: {}, mission_critical: [] };
  for (const [k, v] of Object.entries(st.weights)) d.weights[k] = v;
  const safety = [];
  for (const g of st.cat.guests) {
    const t = st.tier[g.id];
    if (t === 'shed_full_sequence') d.mission_critical.push(g.id);
    else if (t === 'safety_command' && !g.safety_critical) safety.push(g.id);
  }
  if (safety.length) d.response = { safety_command: safety };
  const order = Object.fromEntries(Object.entries(st.order).filter(([, v]) => v));
  if (Object.keys(order).length) d.shed_order = order;
  const confirm = {};
  for (const [rule, levels] of Object.entries(st.confirm)) {
    const set = Object.fromEntries(Object.entries(levels).filter(([, v]) => v));
    if (Object.keys(set).length) confirm[rule] = set;
  }
  if (Object.keys(confirm).length) d.confirm = confirm;
  if (st.notes.trim()) d.notes = st.notes.trim();
  return d;
}

function pickCard(gid) {
  st.gid = gid;
  st.rules = JSON.parse(JSON.stringify(st.cat.cards[gid].hard_limits || []));
  st.form = null;
  st.cardResult = null;
}

function cardDoc() {
  const c = JSON.parse(JSON.stringify(st.cat.cards[st.gid]));
  if (st.rules.length) c.hard_limits = st.rules;
  else delete c.hard_limits;
  return c;
}

function num(raw) {
  const v = Number(raw);
  return raw.trim() === '' || Number.isNaN(v) ? raw : v;
}

// ------------------------------------------------------------------------------------------- events

function wire(root) {
  const onEdit = e => {
    const el = e.target;
    const d = el.dataset;
    if (d.f === 'start') { start(el.value); paintAll(root); return; }
    if (d.f === 'id') st.id = el.value.trim();
    else if (d.f === 'name') st.name = el.value;
    else if (d.f === 'notes') st.notes = el.value;
    else if (d.w) st.weights[d.w] = num(el.value);
    else if (d.o != null && d.o !== undefined && d.f === 'order') st.order[d.o] = el.value ? Number(el.value) : 0;
    else if (d.t) st.tier[d.t] = el.value;
    else if (d.c) { st.confirm.r3 = st.confirm.r3 || {}; st.confirm.r3[d.c] = el.value; }
    else if (d.f === 'card') { pickCard(el.value); checkCard(root); return; }
    else if (d.f === 'label') st.label = el.value.trim();
    else if (d.r) { formField(d.r, el.value); if (el.tagName === 'SELECT') paintCard(root); return; }
    else return;
    st.result = null;
    el.classList.add('changed');
    check(root);
  };
  root.addEventListener('input', e => { if (e.target.matches('input, textarea')) onEdit(e); });
  root.addEventListener('change', e => { if (e.target.matches('select')) onEdit(e); });
  root.addEventListener('click', async e => {
    const b = e.target.closest('button[data-act]');
    if (!b) return;
    const act = b.dataset.act;
    if (act === 'apply') {
      const doc = profileDoc();
      st.applied = { id: doc.id, from: app.tick ? app.tick.t_s : 0 };
      app.send({ cmd: 'input', input: { type: 'profile_applied', injected: false, payload: { profile: doc } } });
      paintStatus(root);
    } else if (act === 'save') {
      st.result = await post('/api/builder/save', { kind: 'profile', doc: profileDoc() });
      paintStatus(root);
    } else if (act === 'add-rule') {
      const r = ruleFromForm();
      if (r) { st.rules.push(r); st.form = null; checkCard(root); }
    } else if (act === 'drop-rule') {
      st.rules.splice(Number(b.dataset.i), 1);
      checkCard(root);
    } else if (act === 'save-card') {
      st.cardResult = await post('/api/builder/save', { kind: 'card', doc: cardDoc(), label: st.label });
      paintCard(root);
    }
  });
}

async function post(url, body) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  return r.json();
}

let timer = null;
function check(root) {
  clearTimeout(timer);
  timer = setTimeout(async () => {
    const seq = ++st.checkSeq;
    const out = await post('/api/builder/check', { kind: 'profile', doc: profileDoc() });
    if (seq !== st.checkSeq) return;
    st.problems = out.problems;
    paintStatus(root);
  }, 120);
}

async function checkCard(root) {
  const out = await post('/api/builder/check', { kind: 'card', doc: cardDoc() });
  st.cardProblems = out.problems;
  st.cardResult = null;
  paintCard(root);
}

// ------------------------------------------------------------------------------------------- rule form

function signalsFor(gid) {
  return st.cat.signals.filter(s => SHIP_GROUPS.includes(s.group) || s.name.startsWith(gid + '.'));
}

function formField(key, value) {
  st.form = st.form || {};
  st.form[key] = value;
  if (key === 'signal') {
    const s = st.cat.signals.find(x => x.name === value);
    st.form.op = s ? s.ops[0] : '';
    st.form.value = s && s.values ? String(s.values[0]) : (s && s.type === 'boolean' ? 'true' : '');
  }
}

function ruleFromForm() {
  const f = st.form || {};
  const s = st.cat.signals.find(x => x.name === f.signal);
  if (!s) return null;
  let value = f.value;
  if (s.type === 'boolean') value = value === 'true';
  else if (s.type === 'number' || s.type === 'integer') value = num(String(value));
  const then = { action: f.action || st.cat.actions[0] };
  if (then.action === 'mode') then.mode = f.mode || st.cat.cards[st.gid].modes[0].name;
  if (f.within !== undefined && String(f.within).trim() !== '') then.within_min = num(String(f.within));
  const rule = { when: { signal: s.name, op: f.op || s.ops[0], value }, then };
  if (f.note && f.note.trim()) rule.note = f.note.trim();
  return rule;
}

// ------------------------------------------------------------------------------------------- painting

function opt(v, label, sel) {
  return `<option value="${esc(v)}"${String(v) === String(sel) ? ' selected' : ''}>${esc(label)}</option>`;
}

function paintAll(root) {
  root.innerHTML = `<div class="row">
<div class="col" style="flex: 999 1 640px">${fileForm()}${weightsForm()}${tiersForm()}${crewForm()}</div>
<div class="col" style="flex: 1 1 380px"><div id="b-status"></div></div>
</div><div id="b-card"></div>`;
  paintStatus(root);
  checkCard(root);
  check(root);
}

function fileForm() {
  const starts = st.cat.profiles.map(p => opt(p.id, `${p.name.toUpperCase()} · ${p.id}.yaml`, st.base)).join('');
  return panel('PRIORITY FILE', `<div class="body"><div class="fields">
<label for="b-start">START FROM</label><select id="b-start" class="sel" data-f="start">${starts}</select>
<label for="b-id">ID</label><input id="b-id" class="txt mono" data-f="id" value="${esc(st.id)}" autocomplete="off">
<label for="b-name">NAME</label><input id="b-name" class="txt" data-f="name" value="${esc(st.name)}" autocomplete="off">
<label for="b-notes">NOTES</label><textarea id="b-notes" class="txt" data-f="notes">${esc(st.notes)}</textarea>
</div></div>`);
}

function weightsForm() {
  const rows = st.cat.capabilities.map(c => `<tr><th scope="row" class="mono" style="font-weight: 600">${esc(c.name)}</th><td>${esc(c.guests.join(' '))}</td>
<td><input class="num-in" type="text" inputmode="decimal" data-w="${esc(c.name)}" value="${esc(st.weights[c.name])}" aria-label="weight ${esc(c.name)}"></td>
<td><select class="sel sm" data-f="order" data-o="${esc(c.name)}" aria-label="shed order ${esc(c.name)}">${ORDER.map(([v, l]) => opt(v, l, st.order[c.name] ? String(st.order[c.name]) : '')).join('')}</select></td></tr>`).join('');
  return panel('MISSION WEIGHTS AND SHED ORDER', `<div class="scroll-x"><table class="big">
<thead><tr><th scope="col">CAPABILITY</th><th scope="col">GUESTS</th><th scope="col">WEIGHT 0 TO 1</th><th scope="col">SHED ORDER</th></tr></thead>
<tbody>${rows}</tbody></table></div>`);
}

function tiersForm() {
  const rows = st.cat.guests.map(g => {
    const sel = g.safety_critical
      ? `<span class="tag t-NEVER">200 MS · CARD</span>`
      : `<select class="sel sm" data-t="${esc(g.id)}" aria-label="response class ${esc(g.id)}">${st.cat.responses.map(r => opt(r.id, `${r.tag} · ${CLASS_WORDS[r.id]}`, st.tier[g.id])).join('')}</select>`;
    return `<tr><th scope="row" class="b">${esc(g.id)}</th><td>${esc(g.name)}</td><td>${sel}</td></tr>`;
  }).join('');
  return panel('RESPONSE CLASS', `<table class="big"><thead><tr><th scope="col">GUEST</th><th scope="col">NAME</th><th scope="col">CLASS</th></tr></thead><tbody>${rows}</tbody></table>
<div class="foot">200 MS NEVER SHED · 5 S FIRST ACTION · 60 S MISSION CRITICAL, ONE STEP A SECOND · THROTTLE BEFORE SHED IN EACH CLASS</div>`);
}

function crewForm() {
  const def = (st.cat.defaults.r3 || {});
  const set = (st.confirm.r3 || {});
  const rows = st.cat.crew_levels.map(n => {
    const opts = [opt('', `DEFAULT · ${String(def[n] || '').replace('_', ' ').toUpperCase()}`, set[n] || '')]
      .concat(st.cat.policies[String(n)].map(p => opt(p, p.replace('_', ' ').toUpperCase(), set[n] || ''))).join('');
    return `<tr><th scope="row" class="mono" style="font-weight: 600">${n}</th><td><select class="sel sm" data-c="${n}" aria-label="R3 at ${n} aboard">${opts}</select></td></tr>`;
  }).join('');
  return panel('CREW POLICY · R3 CLEAR DECK', `<table class="big"><thead><tr><th scope="col">CREW</th><th scope="col">RULE ACTION</th></tr></thead><tbody>${rows}</tbody></table>`);
}

function yaml(v, indent = '') {
  const flow = x => Array.isArray(x) ? `[${x.map(flow).join(', ')}]`
    : x && typeof x === 'object' ? `{${Object.entries(x).map(([k, y]) => `${k}: ${flow(y)}`).join(', ')}}`
      : typeof x === 'string' && /[:#{}\[\],&*?|<>=!%@`'"]|^\s|\s$|^$/.test(x) ? JSON.stringify(x) : String(x);
  return Object.entries(v).map(([k, x]) => {
    if (x && typeof x === 'object' && !Array.isArray(x)) {
      return `${indent}${k}:\n${Object.entries(x).map(([k2, y]) => `${indent}  ${k2}: ${flow(y)}`).join('\n')}`;
    }
    if (Array.isArray(x) && x.some(y => y && typeof y === 'object')) return `${indent}${k}:\n${x.map(y => `${indent}  - ${flow(y)}`).join('\n')}`;
    return `${indent}${k}: ${flow(x)}`;
  }).join('\n');
}

function paintStatus(root) {
  const el = root.querySelector('#b-status');
  if (!el) return;
  const live = app.tick && app.tick.source === 'live';
  const ok = st.problems && st.problems.length === 0;
  const head = st.problems == null ? '<span class="tag lg t-ARMED">CHECKING</span>'
    : ok ? '<span class="tag lg t-YES">VALID</span>' : `<span class="tag lg t-NO">${st.problems.length} PROBLEM${st.problems.length > 1 ? 'S' : ''}</span>`;
  const list = st.problems && st.problems.length ? `<ul class="problems">${st.problems.map(p => `<li>${esc(p)}</li>`).join('')}</ul>` : '';
  const inForce = app.tick ? app.tick.view.header : null;
  let result = '';
  if (st.result && st.result.path) result = `<div class="status-line"><span class="tag t-EXECUTED">SAVED</span><span class="mono">${esc(st.result.path)}</span></div>`;
  else if (st.result && st.result.problems) result = `<ul class="problems">${st.result.problems.map(p => `<li>${esc(p)}</li>`).join('')}</ul>`;
  result += applyLine();
  paint(el, panel('CHECK', `<div class="status-line">${head}<span class="schema">${esc(st.id || '--')}.yaml</span></div>${list}
<div class="status-line"><button type="button" class="btn primary" data-act="apply"${ok && live ? '' : ' disabled'}>APPLY AT SEA</button>
<button type="button" class="btn" data-act="save"${ok ? '' : ' disabled'}>SAVE AS NEW FILE</button></div>
<div class="status-line" style="padding-top: 0"><span class="flabel">IN FORCE</span><span class="mono">${esc(inForce ? inForce.priority_file : '--')}</span>${live ? '' : '<span class="hint">LIVE RUN ONLY</span>'}</div>
${result}`, { strip: 'navy' }) + panel('FILE', `<pre class="yaml">${esc(yaml(profileDoc()))}</pre>`));
}

function applyLine() {
  if (!st.applied || !app.tick) return '';
  const row = app.tick.view.log.find(e => e.tag === 'PROFILE' && e.t_s > st.applied.from);
  if (!row) return `<div class="status-line"><span class="tag t-COMMANDED">SENT</span><span class="mono">${esc(st.applied.id)}</span></div>`;
  const bad = row.msg.includes('refused');
  return `<div class="status-line"><span class="tag ${bad ? 't-NO' : 't-EXECUTED'}">${bad ? 'REFUSED' : 'IN FORCE'}</span><span class="mono">${esc(row.t)}</span><span>${esc(row.msg)}</span></div>`;
}

export function builderTick(root) {
  if (st.cat) paintStatus(root);
}

function paintCard(root) {
  const el = root.querySelector('#b-card');
  if (!el || !st.cat) return;
  const card = st.cat.cards[st.gid];
  const guests = st.cat.guests.map(g => opt(g.id, `${g.id} · ${g.name.toUpperCase()}`, st.gid)).join('');
  const rules = st.rules.map((r, i) => `<tr><td>${i + 1}</td><td class="num">${esc(r.when.signal)} ${esc(r.when.op)} ${esc(r.when.value)}</td>
<td class="num">${esc(r.then.action.replace(/_/g, ' ').toUpperCase())}${r.then.mode ? ' ' + esc(r.then.mode.replace(/_/g, ' ').toUpperCase()) : ''}${r.then.within_min != null ? ` · ≤ ${esc(r.then.within_min)} min` : ''}</td>
<td>${esc(r.note || '')}</td><td><button type="button" class="btn" data-act="drop-rule" data-i="${i}" style="min-height: 30px">REMOVE</button></td></tr>`).join('');
  const f = st.form || {};
  const sigs = signalsFor(st.gid);
  const groups = [...new Set(sigs.map(s => s.group))];
  const sigOpts = opt('', 'SIGNAL', f.signal || '') + groups.map(g => `<optgroup label="${esc(g.replace('_', ' ').toUpperCase())}">${sigs.filter(s => s.group === g).map(s => opt(s.name, s.name, f.signal || '')).join('')}</optgroup>`).join('');
  const s = st.cat.signals.find(x => x.name === f.signal);
  const ops = (s ? s.ops : st.cat.ops).map(o => opt(o, o, f.op || '')).join('');
  let valueIn = '<input class="txt mono" disabled>';
  if (s && s.values) valueIn = `<select class="sel sm" data-r="value">${s.values.map(v => opt(v, String(v), f.value)).join('')}</select>`;
  else if (s && s.type === 'boolean') valueIn = `<select class="sel sm" data-r="value">${opt('true', 'TRUE', f.value)}${opt('false', 'FALSE', f.value)}</select>`;
  else if (s) valueIn = `<input class="num-in" type="text" inputmode="decimal" data-r="value" value="${esc(f.value || '')}">`;
  const hint = s && s.range ? `${s.range[0]} TO ${s.range[1]} ${s.unit || ''}` : (s ? s.type.toUpperCase() : '');
  const actions = st.cat.actions.map(a => opt(a, a.replace(/_/g, ' ').toUpperCase(), f.action || st.cat.actions[0])).join('');
  const modes = card.modes.map(m => opt(m.name, m.name.replace(/_/g, ' ').toUpperCase(), f.mode || '')).join('');
  const ok = st.cardProblems && st.cardProblems.length === 0;
  const status = st.cardProblems == null ? '' : ok ? '<span class="tag lg t-YES">VALID</span>'
    : `<span class="tag lg t-NO">${st.cardProblems.length} PROBLEM${st.cardProblems.length > 1 ? 'S' : ''}</span>`;
  const plist = st.cardProblems && st.cardProblems.length ? `<ul class="problems">${st.cardProblems.map(p => `<li>${esc(p)}</li>`).join('')}</ul>` : '';
  const res = st.cardResult ? (st.cardResult.path ? `<span class="tag t-EXECUTED">SAVED</span><span class="mono">${esc(st.cardResult.path)}</span>`
    : `<ul class="problems">${(st.cardResult.problems || []).map(p => `<li>${esc(p)}</li>`).join('')}</ul>`) : '';
  el.innerHTML = panel(`RULES · ${st.gid} HARD LIMITS`, `<div class="status-line"><label class="flabel" for="b-card">GUEST CARD</label>
<select id="b-card" class="sel" data-f="card">${guests}</select>${status}</div>
<div class="scroll-x"><table class="big"><thead><tr><th scope="col">#</th><th scope="col">WHEN</th><th scope="col">THEN</th><th scope="col">NOTE</th><th scope="col"></th></tr></thead>
<tbody>${rules || '<tr><td colspan="5" class="empty">NONE</td></tr>'}</tbody></table></div>
<div class="rule-form">
<label>SIGNAL<select class="sel sm" data-r="signal">${sigOpts}</select></label>
<label>TEST<select class="sel sm" data-r="op">${ops}</select></label>
<label>VALUE ${hint ? `<span class="hint">${esc(hint)}</span>` : ''}${valueIn}</label>
<label>THEN<select class="sel sm" data-r="action">${actions}</select></label>
${(f.action || st.cat.actions[0]) === 'mode' ? `<label>MODE<select class="sel sm" data-r="mode">${modes}</select></label>` : ''}
<label>WITHIN min<input class="num-in" type="text" inputmode="decimal" data-r="within" value="${esc(f.within || '')}"></label>
<label>NOTE<input class="txt" data-r="note" value="${esc(f.note || '')}"></label>
<button type="button" class="btn" data-act="add-rule"${s ? '' : ' disabled'}>ADD RULE</button>
</div>${plist}
<div class="status-line"><label class="flabel" for="b-label">DRAFT LABEL</label><input id="b-label" class="txt mono" style="width: 160px" data-f="label" value="${esc(st.label)}">
<button type="button" class="btn" data-act="save-card"${ok ? '' : ' disabled'}>SAVE AS NEW DRAFT</button>${res}</div>`);
}
