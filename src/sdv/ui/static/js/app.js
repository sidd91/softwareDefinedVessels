// The ArgOS page: one title bar, five views, the SIM bar, and the /ws stream (the live loop, or the fixture replay).
import { esc, chip, getJSON } from './util.js';
import { renderOps, renderLedger } from './ops.js';
import { renderCompare } from './compare.js';
import { renderAdmit } from './admit.js';
import { renderReference } from './reference.js';
import { renderBuilder, builderTick } from './builder.js';

const VIEWS = {
  ops: { sub: 'RESOURCE GOVERNOR · MRV-60', sim: true },
  ledger: { sub: 'CONSTRAINT LEDGER · MRV-60', sim: true },
  compare: { sub: 'MISSION COMPARE · MRV-60', sim: true },
  admit: { sub: 'ADMISSION · MRV-60', sim: false },
  build: { sub: 'PROFILE BUILDER · MRV-60', sim: true },
  ref: { sub: 'REFERENCE · MRV-60', sim: false },
};

export const app = {
  view: 'ops',
  meta: null,
  tick: null,          // the latest /ws message: {tick, t_s, mission, snapshot, records, view, running, speed}
  ws: null,
  header: null,        // chips and clock set by a view that owns the title bar (admission, reference)
  errors: [],          // engine errors the server reported on the stream ({type: "error"}), newest first, for the event log
  send(msg) { if (this.ws && this.ws.readyState === 1) this.ws.send(JSON.stringify(msg)); },
};

const $ = id => document.getElementById(id);
const CREW_NEXT = { 14: 6, 6: 0, 0: 14 };

// ------------------------------------------------------------------------------------------- title bar

function replayChips(v) {
  const h = v.header;
  const gens = v.plant.filter(p => p.tag.startsWith('GEN')).filter(p => p.state === 'RUN').length;
  return [
    chip(`MISSION ${esc(h.mission)}`, 'strong'),
    chip(`PRIORITY ${esc(h.priority_file)} <span class="dim">VALID</span>`),
    app.tick.source === 'live'
      ? `<button type="button" class="chip" data-crew="${CREW_NEXT[app.tick.snapshot.crew.crew_aboard.value] ?? 14}" title="Next crew level">${esc(h.crew)} <span class="dim">· R3 ${esc(h.crew_policy)}</span></button>`
      : chip(`${esc(h.crew)} <span class="dim">· R3 ${esc(h.crew_policy)}</span>`),
    chip(esc(h.sea)),
    chip(esc(h.speed)),
    app.view === 'ledger' ? chip(`GEN ${gens} OF 2`) : '',
    chip(`SIM ×${esc(app.tick.speed)}`),
    h.standby ? chip(`STANDBY ${esc(h.standby)}`, h.standby === 'IN STEP' ? '' : 'alarm') : '',
  ].join('');
}

export function setHeader(chips, right = null, small = false) {
  app.header = { chips, right, small };
  paintHeader();
}

function paintHeader() {
  const cfg = VIEWS[app.view];
  $('subtitle').textContent = cfg.sub;
  const alarms = $('alarms');
  const clock = $('clock');
  if (!cfg.sim || (app.view === 'compare' && app.header)) {
    $('chips').innerHTML = app.header ? app.header.chips : '';
    alarms.hidden = true;
    clock.className = 'clock' + (app.header && app.header.small ? ' small' : '');
    clock.textContent = app.header && app.header.right != null ? app.header.right : '';
    clock.hidden = !(app.header && app.header.right);
    return;
  }
  if (!app.tick) return;
  const v = app.tick.view;
  $('chips').innerHTML = replayChips(v);
  alarms.hidden = false;
  alarms.className = 'alarm-count' + (v.header.alarms ? '' : ' none');
  alarms.textContent = `ALARMS ${v.header.alarms}`;
  clock.hidden = false;
  clock.className = 'clock';
  clock.textContent = v.header.clock;
}

// ------------------------------------------------------------------------------------------- SIM bar

function simbar() {
  const t = app.tick;
  if (!t || !app.meta) return;
  $('sim-run').textContent = t.running ? 'HOLD' : 'RUN';
  $('sim-run').classList.toggle('on', !t.running);
  $('sim-speed').innerHTML = '<span class="gl">PACE</span>' + app.meta.speeds.map(s =>
    `<button type="button" data-speed="${s}" class="${s === t.speed ? 'on' : ''}">×${s}</button>`).join('');
  const marks = (app.meta.marks[t.mission] || []).filter(m => m.t_s > 0);
  $('sim-jump').innerHTML = '<span class="gl">JUMP</span>' + marks.map(m =>
    `<button type="button" data-jump="${Math.max(0, m.at - 3)}" title="${esc(m.label)}">${esc(m.t.slice(3))}</button>`).join('');
  $('sim-file').innerHTML = '<span class="gl">PRIORITY</span>' + app.meta.missions.map(m =>
    `<button type="button" data-file="${esc(m.id)}" class="${m.id === t.mission ? 'on' : ''}">${esc(m.name)}</button>`).join('');
  $('sim-fill').style.width = `${Math.round(100 * t.t_s / t.end_t_s)}%`;
  $('sim-source').textContent = t.source === 'live' ? `LIVE · SIM ${String(t.sim || '').toUpperCase()}` : 'REPLAY';
  if (t.refused) $('sim-note').textContent = `REFUSED · ${t.refused}`;
}

function wireSimbar() {
  $('sim-run').addEventListener('click', () => app.send({ cmd: 'toggle' }));
  $('sim-restart').addEventListener('click', () => { app.errors = []; $('sim-note').textContent = ''; app.send({ cmd: 'restart' }); });
  $('chips').addEventListener('click', e => {
    const b = e.target.closest('button[data-crew]');
    if (b) app.send({ cmd: 'input', input: { type: 'crew_change', injected: false, payload: { crew_aboard: Number(b.dataset.crew) } } });
  });
  $('simbar').addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.speed) app.send({ cmd: 'speed', value: Number(b.dataset.speed) });
    if (b.dataset.jump) app.send({ cmd: 'jump', t: Number(b.dataset.jump) });
    if (b.dataset.file) app.send({ cmd: 'mission', value: b.dataset.file });
  });
  document.addEventListener('keydown', e => {
    if (e.code !== 'Space' || !VIEWS[app.view].sim) return;
    if (e.target.closest('input, select, textarea')) return;
    e.preventDefault();
    app.send({ cmd: 'toggle' });
  });
}

// ------------------------------------------------------------------------------------------- stream

function connect(attempt = 0) {
  const q = new URLSearchParams({ mission: app.tick ? app.tick.mission : 'survey', t: app.tick ? app.tick.t_s : 0,
    speed: app.tick ? app.tick.speed : 12, run: app.tick && !app.tick.running ? '0' : '1' });
  const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws?${q}`);
  app.ws = ws;
  ws.onopen = () => { attempt = 0; link(true); };
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.type === 'error') {
      engineError(m);
      return;
    }
    app.tick = m;
    render();
  };
  ws.onclose = () => {
    link(false);
    setTimeout(() => connect(attempt + 1), Math.min(5000, 500 * 2 ** attempt));
  };
}

// An error frame: the engine failed on a tick or a command, the server held the run at that tick and kept the
// socket. One line in the event log and the SIM bar note, built from the frame; the run is not restarted.
function engineError(m) {
  const t = Math.max(0, Math.round(m.t_s || 0));
  const hh = String(Math.floor(t / 3600)).padStart(2, '0');
  const mm = String(Math.floor((t % 3600) / 60)).padStart(2, '0');
  const ss = String(t % 60).padStart(2, '0');
  app.errors.unshift({ t: `${hh}:${mm}:${ss}`, type: 'ALARM', tag: 'ENGINE', msg: `Run held at ${hh}:${mm}:${ss}. ${m.message}`, injected: false });
  if (app.tick) app.tick.running = false;
  $('sim-note').textContent = `ENGINE · ${m.message}`;
  render();
}

// The event log with the engine errors on top of the rows the server built.
function withErrors(v) {
  return app.errors.length ? { ...v, log: [...app.errors, ...v.log] } : v;
}

function link(up) {
  const el = $('link-state');
  el.textContent = up ? 'LINK UP' : 'LINK DOWN';
  el.classList.toggle('down', !up);
}

// ------------------------------------------------------------------------------------------- views

function render() {
  const v = app.tick && app.tick.view;
  if (v && app.view === 'ops') renderOps($('view-ops'), withErrors(v));
  if (v && app.view === 'ledger') renderLedger($('view-ledger'), v);
  if (app.view === 'compare') renderCompare($('view-compare'));
  if (app.view === 'build') builderTick($('view-build'));
  paintHeader();
  simbar();
}

function route() {
  const name = (location.hash || '#ops').slice(1);
  app.view = VIEWS[name] ? name : 'ops';
  app.header = null;
  for (const k of Object.keys(VIEWS)) {
    $(`view-${k}`).hidden = k !== app.view;
  }
  document.querySelectorAll('.views a').forEach(a => a.classList.toggle('on', a.dataset.view === app.view));
  $('simbar').hidden = !VIEWS[app.view].sim;
  if (app.view === 'admit') renderAdmit($('view-admit'));
  if (app.view === 'ref') renderReference($('view-ref'));
  if (app.view === 'build') renderBuilder($('view-build'));
  render();
}

async function start() {
  app.meta = await getJSON('/api/meta');
  wireSimbar();
  window.addEventListener('hashchange', route);
  route();
  connect();
}

start();
