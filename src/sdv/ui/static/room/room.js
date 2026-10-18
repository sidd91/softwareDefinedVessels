// ArgOS room map (/room): the ship as room (each position a cell: what is there, what is free, how it may change), the
// eight budgets as FREE capacity with the binding one in the warm tone, and the decision as text with its verdict word.
//
// It reads the same stream and routes as the console and changes none of them: /ws (the live run, same commands as
// static/js/app.js), /api/meta, /api/reference, /api/compare, /api/admit, and one route of its own, /api/room, for the
// cells' geometry (slot limits, part masses, mutability). Everything dynamic (modes, activities, the eight numbers, the
// decision) comes from the /ws payload the console renders, so both screens agree on the same tick.
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const num = s => { const m = String(s ?? '').match(/-?\d+(?:\.\d+)?/); return m ? Number(m[0]) : NaN; };
  const g = (x, nd = 1) => Number.isFinite(x) ? String(Number(x.toFixed(nd))) : '—';
  const low = s => String(s ?? '').toLowerCase();
  const words = s => low(s).replace(/_/g, ' ');
  const cap = s => (s ? s[0].toUpperCase() + s.slice(1) : s);
  // Lower-case a console string, keeping the ids and units that are names: G3, kW, CHW, FD, SATCOM, LOS.
  const soft = s => low(s).replace(/\bg(\d)\b/g, 'G$1').replace(/\bkw\b/g, 'kW').replace(/\bchw\b/g, 'CHW').replace(/\bfd\b/g, 'FD')
    .replace(/\bsatcom\b/g, 'SATCOM').replace(/\blos\b/g, 'LOS').replace(/\brsv\b/g, 'reserved').replace(/\bmbit\/s\b/g, 'Mbit/s');
  const pct = x => `${Math.round(x * 100)}`;
  function clock(t) {
    t = Math.max(0, Math.round(t || 0));
    const p = n => String(n).padStart(2, '0');
    return `${p(Math.floor(t / 3600))}:${p(Math.floor((t % 3600) / 60))}:${p(t % 60)}`;
  }
  function paint(el, html) { if (el.__last !== html) { el.innerHTML = html; el.__last = html; } }
  async function getJSON(url) {
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) throw new Error(`${url}: ${r.status}`);
    return r.json();
  }
  function store(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private window: fine */ } }
  function recall(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }

  const WEIGHT_NAMES = { 'SEABED INSPECTION': 'seabed', 'SAR AIR': 'uav', 'COASTAL CONNECTIVITY': 'comms', 'OCEAN DATA': 'ocean',
    'PASSIVE RF DETECTION': 'rf', 'FRESH WATER': 'water' };
  const SIGNALS = { speed_kn: 'speed', deck_machinery: 'deck machinery', heading_free: 'heading', noise: 'noise', course: 'course',
    deck_flight_deck: 'flight deck', ramp: 'ramp', emission: 'emission' };
  const CREW_NEXT = { 14: 6, 6: 0, 0: 14 };

  const state = {
    meta: null, ref: null, geo: null, geoKey: null, tick: null, ws: null, link: false, engineNote: '',
    preset: recall('argos-room-preset') || 'operate', tab: 'decision',
    compare: { t: null, data: null, loading: null },
    admit: { caseId: null, cases: null, edits: {}, good: {}, data: null, room: null, refused: null, seq: 0, base: {} },
    theme: recall('argos-room-theme') || 'auto',
  };
  const send = msg => { if (state.ws && state.ws.readyState === 1) state.ws.send(JSON.stringify(msg)); };

  // ------------------------------------------------------------------------------------------- stream (as app.js)

  function connect(attempt = 0) {
    const t = state.tick;
    const q = new URLSearchParams({ mission: t ? t.mission : 'survey', t: t ? t.t_s : 0, speed: t ? t.speed : 12, run: t && !t.running ? '0' : '1' });
    const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws?${q}`);
    state.ws = ws;
    ws.onopen = () => { attempt = 0; state.link = true; render(); };
    ws.onmessage = e => {
      const m = JSON.parse(e.data);
      if (m.type === 'error') {   // the engine failed on a tick: the server holds the run there and keeps the socket
        state.engineNote = `engine: run held at ${clock(m.t_s)} · ${m.message}`;
        if (state.tick) state.tick.running = false;
        render();
        return;
      }
      state.tick = m;
      if (m.refused) state.engineNote = `refused: ${m.refused}`;
      ensureGeo(m);
      render();
    };
    ws.onclose = () => { state.link = false; render(); setTimeout(() => connect(attempt + 1), Math.min(5000, 500 * 2 ** attempt)); };
  }

  // The cells' geometry depends on who is aboard, not on the tick: fetched once per installed set.
  function ensureGeo(m) {
    const key = Object.keys(m.snapshot.guests).sort().join(',');
    if (key === state.geoKey) return;
    state.geoKey = key;
    const mission = state.meta && state.meta.missions.some(x => x.id === m.mission) ? m.mission : 'survey';
    getJSON(`/api/room?mission=${encodeURIComponent(mission)}&t=${m.t_s}`).then(geo => { state.geo = geo; render(); })
      .catch(() => { state.geoKey = null; });
  }

  // ------------------------------------------------------------------------------------------- names

  function missionName(id) {
    const m = state.meta && state.meta.missions.find(x => x.id === id);
    if (m) return cap(low(m.name));
    const h = state.tick && state.tick.view.header;
    return h && h.mission_id === id ? cap(low(h.mission)) : id;
  }
  function weightsOf(id) {
    const m = state.ref && state.ref.missions.find(x => x.id === id);
    if (!m) return '';
    const ws = m.weights.split(' · ').map(s => { const i = s.lastIndexOf(' '); return [s.slice(0, i), Number(s.slice(i + 1))]; })
      .filter(([k]) => k in WEIGHT_NAMES && ['SEABED INSPECTION', 'SAR AIR', 'COASTAL CONNECTIVITY'].includes(k))
      .sort((a, b) => b[1] - a[1]);
    return ws.map(([k, v]) => `${WEIGHT_NAMES[k]} ${v.toFixed(1)}`).join(' · ');
  }
  function marks() {
    const t = state.tick;
    if (!state.meta) return [];
    const id = t && state.meta.marks[t.mission] ? t.mission : state.meta.missions[0].id;
    return state.meta.marks[id] || [];
  }
  function currentMark() {
    const t = state.tick ? state.tick.t_s : 0;
    const ms = marks().filter(m => m.t_s <= t);
    return ms.length ? ms[ms.length - 1] : { t_s: 0, at: 0, t: '00:00', label: 'START' };
  }

  // ------------------------------------------------------------------------------------------- records

  function latest(records, kinds, pred = () => true) {
    const rs = records.filter(r => kinds.includes(r.kind) && pred(r));
    return rs.length ? rs.reduce((a, b) => (b.tick > a.tick || (b.tick === a.tick && b.seq > a.seq) ? b : a)) : null;
  }
  function latestShed(t) {
    return latest(t.records, ['D4'], r => r.verdict === 'shed' && (r.applies_at_tick ?? r.tick + 1) <= t.t_s);
  }
  function responseText(d) {
    const row = d && d.rows.find(r => r[0] === 'RESPONSE');
    if (!row) return '';
    const [a, b] = String(row[1]).split(' / ');
    return `${a} of ${g(num(b))} s`;
  }

  // ------------------------------------------------------------------------------------------- header, controls

  function renderHeader(t) {
    const v = t.view, h = v.header, snap = t.snapshot;
    const faults = (snap.faults || []).filter(f => f.state === 'confirmed').map(f =>
      `<span class="warm">${esc(words(f.subject).replace('genset', 'gen').replace('chw pump', 'CHW pump'))} ${f.fault === 'genset_trip' ? 'tripped' : 'down'}${f.injected ? ' (injected)' : ''}</span>`);
    const parts = [
      `${esc(h.speed.replace('SPEED ', ''))}${state.meta.location ? ` · ${esc(state.meta.location)}` : ''}`,
      `${esc(g(num(h.sea)))} °C`,
      `<b>${esc(missionName(t.mission))}</b> profile${h.priority_file.includes('AT SEA') ? ' (applied at sea)' : ''}`,
      `crew ${esc(num(h.crew))}`,
      ...faults,
      state.link ? '' : '<span class="warm">link down · reconnecting</span>',
      state.engineNote ? `<span class="warm">${esc(state.engineNote)}</span>` : '',
    ].filter(Boolean);
    paint($('status'), parts.join(' · '));
    $('clock').textContent = h.clock;
    const builtin = state.meta.missions.some(m => m.id === t.mission);
    paint($('profile'), state.meta.missions.map(m =>
      `<button type="button" data-profile="${esc(m.id)}" aria-pressed="${builtin && m.id === t.mission}">${esc(cap(low(m.name)))}</button>`).join(''));
    document.querySelectorAll('#presets button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.preset === state.preset)));
    document.body.className = `preset-${state.preset}`;

    const jumps = marks().filter(m => m.t_s > 0).map(m =>
      `<button type="button" data-jump="${Math.max(0, m.at - 3)}" title="${esc(m.label)}">${esc(m.t.slice(3))}</button>`).join('');
    const crew = t.source === 'live'
      ? `<span class="grp"><span class="gl">crew</span><button type="button" data-crew="${CREW_NEXT[snap.crew.crew_aboard.value] ?? 14}" title="Next crew level">${esc(snap.crew.crew_aboard.value)} → ${CREW_NEXT[snap.crew.crew_aboard.value] ?? 14}</button></span>` : '';
    paint($('ops'), [
      `<button type="button" data-cmd="toggle" class="${t.running ? '' : 'primary'}" title="Space">${t.running ? 'Hold' : 'Run'}</button>`,
      `<span class="grp"><span class="gl">pace</span>${state.meta.speeds.map(s => `<button type="button" data-speed="${s}" class="${s === t.speed ? 'on' : ''}">×${s}</button>`).join('')}</span>`,
      `<span class="grp"><span class="gl">jump</span>${jumps}</span>`,
      `<button type="button" data-cmd="restart">Restart</button>`,
      crew,
      `<span class="track" aria-hidden="true"><i style="width:${Math.round(100 * t.t_s / t.end_t_s)}%"></i></span>`,
      `<span class="gl">${esc(t.source === 'live' ? `live · ${t.sim || 'simulator'}` : 'replay')}${h.standby ? ` · standby ${esc(low(h.standby))}` : ''}</span>`,
    ].join(''));
    paint($('foot-live'), `${t.source === 'live' ? 'Live' : 'Replay'} · <b>${esc(t.sim || 'scripted plant')}, A.6</b>`);
    paint($('foot-source'), `<span class="verify-only">snapshot tick ${esc(v.snapshot_tick)} · records ${esc(v.records_seen)} · ${esc(low(h.priority_file))}</span>`);
  }

  // ------------------------------------------------------------------------------------------- the step strip

  const STEPS = [
    { id: 'pick', label: 'Jury picks a profile', title: 'Restart the run and hold at T+0' },
    { id: 'm8', label: 'Minute 8 · right of way', title: 'Jump to the minute-8 mark and run' },
    { id: 'swap', label: 'Jury swaps the profile', title: 'Hold and open the two-ships comparison; the switch above swaps the file' },
    { id: 'm12', label: 'Minute 12 · genset trips', title: 'Jump to the minute-12 mark and run' },
    { id: 'm19', label: 'Minute 19 · pump fault', title: 'Jump to the minute-19 mark and run' },
    { id: 'card', label: 'Jury’s card · Scenario A', title: 'Open the admission panel' },
    { id: 'edit', label: 'Jury changes one number', title: 'Open the admission panel on its editable numbers' },
  ];
  function currentStep(t) {
    if (state.tab === 'admit') return Object.keys(state.admit.edits).length ? 'edit' : 'card';
    if (state.tab === 'compare') return 'swap';
    const ms = marks().filter(m => m.t_s > 0).map(m => Math.max(0, m.at - 3));
    if (ms.length < 3) return t.t_s === 0 ? 'pick' : 'm8';
    if (t.t_s < ms[0]) return 'pick';
    if (t.t_s < ms[1]) return 'm8';
    if (t.t_s < ms[2]) return 'm12';
    return 'm19';
  }
  function renderSteps(t) {
    const cur = currentStep(t);
    paint($('steps'), STEPS.map((s, i) => `${i ? '<span class="sep">›</span>' : ''}<button type="button" role="listitem" data-step="${s.id}" title="${esc(s.title)}" aria-current="${s.id === cur ? 'step' : 'false'}">${i + 1} · ${esc(s.label)}</button>`).join(''));
  }
  function goStep(id) {
    const ms = marks().filter(m => m.t_s > 0).map(m => Math.max(0, m.at - 3));
    const jumpRun = i => { if (ms[i] != null) { send({ cmd: 'jump', t: ms[i] }); send({ cmd: 'run' }); } };
    if (id === 'pick') { send({ cmd: 'restart' }); send({ cmd: 'hold' }); setTab('decision'); }
    else if (id === 'm8') { jumpRun(0); setTab('decision'); }
    else if (id === 'swap') { send({ cmd: 'hold' }); setTab('compare'); }
    else if (id === 'm12') { jumpRun(1); setTab('decision'); }
    else if (id === 'm19') { jumpRun(2); setTab('decision'); }
    else if (id === 'card') setTab('admit');
    else if (id === 'edit') { setTab('admit'); state.admit.focus = 'peak'; }
    render();
  }

  // ------------------------------------------------------------------------------------------- cells

  function cellHTML(c) {
    const cls = `cell ${c.cls || ''}${c.held ? ' held' : ''}${c.changed ? ' changed' : ''}`;
    // at sea a port-mutable cell carries PORT ONLY where its tag was; the tag (its line, its slots) moves to the what-line
    const tag = c.portOnly ? '<span class="portonly">PORT ONLY</span>' : esc(c.tag || '');
    const what = c.portOnly && c.tag && !String(c.what).includes(c.tag) ? `${c.tag} · ${c.what}` : c.what;
    return `<div class="${cls}" data-cell="${esc(c.id)}"><div class="where"><span>${esc(c.where)}</span><span>${tag}</span></div>` +
      `<div class="who${c.free ? ' free' : ''}" title="${esc(c.whoTitle || '')}">${esc(c.who)}</div><div class="what">${esc(what || '')}</div>` +
      `<div class="rule" title="${esc(c.ruleDetail || '')}">${esc(c.rule || '')}</div>` +
      `<div class="room"><span>${esc(c.roomK)}</span><b class="${esc(c.roomCls || '')}">${esc(c.roomV)}</b></div></div>`;
  }

  function g3State(snap, gs) {
    const b = snap.guests.G3 || {};
    const leg = b.leg_state ? words(b.leg_state.value) : '';
    const act = words(gs.activity);
    if (act === 'surveying') return `at depth · surveying · ${gs.kw} kW`;
    if (act === 'holding depth') return `holding depth · leg ${leg || 'paused'}`;
    if (act === 'holding at sea') return `holding at sea · leg ${leg || 'aborted'}`;
    if (act === 'launch recovery') return 'recovery over the ramp';
    return `${act} · ${words(gs.mode.split(' · ')[0])} ${gs.kw} kW`;
  }

  function liveCells(t, geo) {
    const v = t.view, snap = t.snapshot;
    const guests = Object.fromEntries(v.guests.map(x => [x.id, x]));
    const hot = new Set(v.mimic.zones.filter(z => z.hot).map(z => z.guest.split(' ')[0]));
    const armed = v.shed_order.rows.find(r => r.state === 'ARMED');
    const armedFirst = armed ? armed.g : null;
    const shed = latestShed(t);
    const losses = shed ? shed.losses || {} : {};
    const atSea = geo.situation !== 'alongside';
    return geo.cells.map(c => {
      const gid = c.guests[0];
      const gs = gid && (c.primary || []).includes(gid) ? guests[gid] : null;   // a secondary part (the antenna) carries no draw
      const mode = gs ? words(gs.mode.split(' · ')[0]) : '';
      const lost = gid && losses[gid] && losses[gid].mode_before !== losses[gid].mode_after ? losses[gid] : null;
      const first = gid && armedFirst === gid;
      const marks_ = (first ? ' · first armed step' : '') + (lost ? ` · shed ${pct(lost.capability_before - lost.capability_after)} %` : '');
      const out = { id: c.id, cls: c.mutability, held: c.held, changed: !!gs && hot.has(gid), where: c.where, tag: c.tag,
        portOnly: c.port_only && atSea, who: c.who, whoTitle: c.who_title, free: !gid, what: c.what, rule: c.rule, ruleDetail: c.rule_detail,
        roomK: c.free_k, roomV: c.free_v, roomCls: '' };
      if (!gs) {
        if (c.id === 'stern_ramp') {
          const ramp = snap.ship_state.ramp;
          if (ramp.value !== 'free') { out.who = `in use · ${(ramp.by || []).join(' ')}`.trim(); out.free = false; }
        }
        return out;
      }
      out.what = `${c.what} · ${gs.kw} kW`;
      if (gid === 'G3') {
        out.roomK = 'vehicle'; out.roomV = g3State(snap, gs) + marks_; out.roomCls = hot.has('G3') || first || lost ? 'hot' : '';
      } else if (gid === 'G4') {
        const b = snap.guests.G4 || {};
        const batt = b.battery_pct && b.battery_pct.value != null ? ` · batt ${Math.round(b.battery_pct.value)} %` : '';
        const landBy = b.land_by_t_s && b.land_by_t_s.value != null ? ` · land by ${clock(b.land_by_t_s.value)}` : '';
        const act = words(gs.activity);
        if (act === 'airborne') { out.roomK = 'drone'; out.roomV = `airborne · ${gs.kw} kW${batt}`; }
        else if (act === 'recovering' || act === 'launch recovery') { out.roomK = 'recovering'; out.roomV = `${batt.slice(3) || 'on approach'}${landBy}`; }
        else if (act === 'landed') { out.roomK = 'charging'; out.roomV = `${mode} ${gs.kw} kW`; }
        else { out.roomK = act; out.roomV = `${mode} ${gs.kw} kW`; }
        out.roomV += (gs.rsv && act !== 'landed' ? ` · ${gs.rsv} reserved` : '') + marks_;
        out.roomCls = hot.has('G4') || first || lost ? 'hot' : '';
      } else {
        out.roomK = 'mode'; out.roomV = `${mode}${gs.rsv ? ` · ${gs.rsv} reserved` : ''}${marks_}`; out.roomCls = first || lost ? 'hot' : '';
      }
      return out;
    });
  }

  function pierCells(room, d) {
    const lines = Object.fromEntries((d ? d.lines : []).map(l => [l.k, l]));
    const yes = d && d.verdict_raw === 'yes';
    return room.cells.map(c => {
      const out = { id: c.id, cls: c.mutability, held: c.held, changed: false, where: c.where, tag: c.tag, portOnly: false,
        who: c.who, whoTitle: c.who_title, free: !c.guests.length, what: c.what, rule: c.rule, ruleDetail: c.rule_detail, roomK: c.free_k, roomV: c.free_v, roomCls: '' };
      if (c.held) {
        out.who = `${c.who.split(' ')[0]} held here`;
        const stbd = lines['LINE STBD'], port = lines['LINE PORT'], drone = lines['HANGAR DRONE'];
        const line = c.line === 'port' ? port : stbd;
        const slotOk = !drone || drone.s === 'OK';
        out.roomK = 'fits';
        if (d && yes) { const [lu, lc] = line ? String(line.v).split(' / ') : []; out.roomV = `yes${line ? ` · ${c.line} line ${g(num(lu))} of ${g(num(lc))} kW` : ''}`; out.roomCls = 'ok'; }
        else if (d) { out.roomV = `slot ${slotOk ? 'yes' : 'no'} · ${soft(d.binding).split(' ')[0]} binds`; out.roomCls = 'hot'; }
        else out.roomV = '…';
      } else if (c.free_n != null && c.free_n <= 0 && c.id !== 'mast_free') out.roomCls = 'hot';
      return out;
    });
  }

  function renderMap(t) {
    const geo = state.geo;
    const pier = state.tab === 'admit' && state.admit.room;
    if (pier) {
      const r = state.admit.room;
      $('maptitle').textContent = `Room alongside · Scenario A · ${r.card} onto ${r.installed.join(', ')}`;
      paint($('hull'), pierCells(r, state.admit.data).map(cellHTML).join(''));
    } else {
      $('maptitle').textContent = 'Room aboard';
      paint($('hull'), geo ? liveCells(t, geo).map(cellHTML).join('') : '<div class="cell"><div class="who free">loading the room…</div></div>');
    }
    const ab = (pier ? state.admit.room : geo) && (pier ? state.admit.room : geo).as_built;
    if (ab) {
      paint($('asbuilt'), `<span>As built: <b>${esc(ab.gensets)}</b> gensets</span><span>loop <b>${esc(ab.loop)}</b></span><span>lines <b>${esc(ab.lines)}</b></span>` +
        `<span>mass <b>${esc(ab.mass_t)} t</b> · stability <b>${esc(ab.stability_t_eq)} t-eq</b></span><span>mast <b>${esc(ab.mast_natives.join(', '))}</b></span>`);
    }
  }

  // ------------------------------------------------------------------------------------------- the eight free numbers

  function gaugeHTML(x) {
    const p = Math.max(0, Math.min(100, Number.isFinite(x.pct) ? x.pct : 0));
    return `<div class="g${x.bind ? ' bind' : ''}"><span class="label">${esc(x.label)}${x.injected ? '<span class="inj">injected</span>' : ''}</span>` +
      `<div class="v">${esc(x.v)}<small>${esc(x.u)}</small></div><div class="bar"><i style="width:${p}%"></i></div><div class="of">${esc(x.of)}</div>` +
      `<div class="src verify-only">source: ${esc(x.src || 'snapshot')}</div></div>`;
  }

  function liveGauges(t, geo) {
    const v = t.view, snap = t.snapshot;
    const rows = Object.fromEntries(v.ledger.rows.map(r => [r.name, r]));
    const tiles = Object.fromEntries(v.tiles.map(r => [r.name, r]));
    const capc = k => (snap.capacity[k] && snap.capacity[k].value) || {};
    const src = geo ? geo.sources : {};
    const ab = geo ? geo.as_built : {};
    const bind = s => ['LIMITING', 'OVER', 'LATE'].includes(s);
    const gens = v.plant.filter(p => p.tag.startsWith('GEN') && p.state === 'RUN').length;
    const pumpsDown = v.plant.filter(p => p.tag.startsWith('CHW P') && p.state !== 'RUN').map(p => p.tag.replace('CHW P', 'pump '));
    const sw = snap.environment.seawater_c.value;
    const rsv = v.guests.filter(x => x.rsv).map(x => `${x.rsv} reserved for ${x.id}`);
    const P = rows.POWER, C = rows['COOLING CHW'], M = rows.MASS, S = rows.STABILITY, D = rows['DATA SATCOM'], L = rows['DATA LOS'], A = rows['DATA ACOUSTIC'], K = rows.COMPUTE;
    const shed = latestShed(t);
    const resp = tiles.RESPONSE;
    const [ra, rb] = String(resp.value).split(' / ');
    const respV = ra.trim() === '--' ? '—' : ra.trim().split(' ')[0];
    const respU = ra.trim() === '--' ? '' : ra.trim().split(' ')[1] || '';
    const geoMast = geo ? geo.mast : null, geoDeck = geo ? geo.deck : null;
    const halfBay = geo ? geo.cells.filter(c => (c.id === 'bay1' || c.id === 'bay2') && c.limits.halves_free > 0).map(c => `${c.where.split(' · ')[0]} half free`) : [];
    return [
      { label: 'Power', v: g(num(P.free)), u: 'kW', pct: 100 * num(P.used) / num(P.lim), bind: bind(P.state),
        of: `${g(num(P.used))} of ${g(num(P.lim))} kW · ${gens} genset${gens === 1 ? '' : 's'}${rsv.length ? ' · ' + rsv.join(' · ') : ''}`,
        src: (capc('power').degraded_by || [])[0] || `${src.power || 'brief'} · limit = reserve − ${ab.headroom_kw ?? 5} kW headroom (${src.headroom || 'assumed'})` },
      { label: 'Cooling', v: g(num(C.free)), u: 'kW', pct: 100 * num(C.used) / num(C.lim), bind: bind(C.state), injected: tiles['COOLING CHW'].injected,
        of: `${g(num(C.used))} of ${g(num(C.lim))} kW at ${g(sw)} °C · ${pumpsDown.length ? pumpsDown.join(', ') + ' down' : '2 pumps'}${shed && bind(C.state) ? ` · was ${g(shed.load_kw)}` : ''}`,
        src: (capc('heat').degraded_by || [])[0] || `${src.heat || 'brief'} · loop ${ab.loop || ''}` },
      { label: 'Mass', v: g(num(M.free), 3), u: 't', pct: 100 * num(M.used) / num(M.cap), bind: bind(M.state),
        of: `${g(num(M.used), 3)} of ${g(num(M.cap))} t · ${g(num(S.used), 3)} of ${g(num(S.cap))} t-eq`, src: `${src.mass || 'brief'} · cards (parts)` },
      { label: 'Mast', v: geoMast ? String(geoMast.slots_free) : rows.MAST.free, u: 'slots', pct: geoMast ? 100 * (3 - geoMast.slots_free) / 3 : 100, bind: false,
        of: geoMast ? `${3 - geoMast.slots_free} of 3 · ${geoMast.natives.join(', ')}${geoMast.guest ? ', ' + geoMast.guest : ''}` : soft(rows.MAST.used),
        src: `${src.positions || 'brief'} · D2 placement` },
      { label: 'Deck', v: geoDeck ? String(geoDeck.halves_free) : rows.DECK.free, u: geoDeck && geoDeck.halves_free === 1 ? 'half' : 'halves',
        pct: geoDeck ? 100 * (geoDeck.halves_total - geoDeck.halves_free) / geoDeck.halves_total : 75, bind: false,
        of: `${halfBay.length ? halfBay.join(' · ') : 'bays full'} · ramp ${words(snap.ship_state.ramp.value)}`, src: `${src.positions || 'brief'} · D2 placement` },
      { label: 'Data', v: D.state === 'DOWN' ? '—' : g(num(D.free)), u: 'Mbit/s', pct: 100 * num(D.used) / num(D.cap), bind: bind(D.state),
        of: `SATCOM ${g(num(D.used))} of ${g(num(D.cap))} · LOS ${g(num(L.used))} of ${g(num(L.cap))}${A.state === 'DOWN' ? ' · acoustic down' : ''}`,
        src: (capc('acoustic').degraded_by || [])[0] || `${src.data || 'brief'} · links measured` },
      { label: 'Compute', v: String(num(K.free)), u: 'cores', pct: 100 * num(K.used) / num(K.cap), bind: false,
        of: `${num(K.used)} of ${num(K.cap)}`, src: `${src.compute || 'brief'} · cores per card (assumed)` },
      { label: 'Response', v: respV, u: respU, pct: 1, bind: bind(resp.state),
        of: `of ${g(num(rb))} s · ${soft(resp.sub).replace('d3', 'D3').replace('d4', 'D4').replace('d5', 'D5')}`,
        src: `${src.response || 'brief'} · ${/COMPUTE/.test(resp.sub) ? 'timing log' : 'ship time'}` },
    ];
  }

  function pierGauges(d, room) {
    const L = Object.fromEntries(d.lines.map(l => [l.k, l]));
    const sp = l => { const [a, b] = String(l.v).split(' / '); return [num(a), num(b)]; };
    const over = l => l && (l.s === 'OVER' || (l.binding && d.verdict_raw !== 'yes'));
    const heat = L['CHW AT 30 °C'], power = L.POWER, mass = L.MASS, stab = L.STABILITY, sat = L.SATCOM, los = L['LOS RADIO'], comp = L.COMPUTE;
    const port = L['LINE PORT'], stbd = L['LINE STBD'];
    const halfBay = room.cells.filter(c => (c.id === 'bay1' || c.id === 'bay2') && c.limits.halves_free > 0).map(c => `${c.where.split(' · ')[0]} half free`);
    const src = room.sources || {};
    const gg = (l, nd = 1) => { const [a, b] = sp(l); return { used: a, cap: b, free: num(l.free), pct: 100 * a / b, nd }; };
    const H = gg(heat), P = gg(power), M = gg(mass, 3), St = gg(stab, 3), Dd = gg(sat), Lo = gg(los), K = gg(comp);
    return [
      { label: 'Cooling', v: g(H.free), u: 'kW', pct: H.pct, bind: over(heat), of: `${g(H.used)} of ${g(H.cap)} at ${room.as_built.judge_cooling_at_c} °C · ${heat.binding ? (over(heat) ? 'binding' : 'tightest') : 'holds'}`,
        src: `${src.heat || 'brief'} · judged at ${room.as_built.judge_cooling_at_c} °C (${src.envelope || 'brief A.10'})` },
      { label: 'Power', v: g(P.free), u: 'kW', pct: P.pct, bind: over(power), of: `${g(P.used)} of ${g(P.cap)} · lines ${g(sp(port)[0])} / ${g(sp(stbd)[0])}`,
        src: `${src.power || 'brief'} · envelope reserve, peaks not credited` },
      { label: 'Mass', v: g(M.free, 3), u: 't', pct: M.pct, bind: over(mass) || over(stab), of: `${g(M.used, 3)} of ${g(M.cap)} · ${g(St.used, 3)} of ${g(St.cap)} t-eq`, src: `${src.mass || 'brief'} · cards (parts)` },
      { label: 'Mast', v: String(room.mast.slots_free), u: 'slots', pct: 100 * (3 - room.mast.slots_free) / 3, bind: over(L['MAST SLOT MASS']) || over(L['MAST SLOT AREA']) || over(L['MAST AIR COOLING']),
        of: `${3 - room.mast.slots_free} of 3 · ${room.mast.natives.join(', ')}${room.mast.guest ? ', ' + room.mast.guest : ''}`, src: `${src.positions || 'brief'} · D2 placement` },
      { label: 'Deck', v: String(room.deck.halves_free), u: room.deck.halves_free === 1 ? 'half' : 'halves', pct: 100 * (room.deck.halves_total - room.deck.halves_free) / room.deck.halves_total,
        bind: room.unplaced && room.unplaced.length > 0, of: room.unplaced && room.unplaced.length ? `no position for ${room.unplaced.map(u => `${u.guest} ${u.part}`).join(', ')}` : (halfBay.length ? halfBay.join(' · ') : 'bays full'),
        src: `${src.positions || 'brief'} · D2 placement` },
      { label: 'Data', v: g(Dd.free), u: 'Mbit/s', pct: Dd.pct, bind: over(sat) || over(los), of: `${g(Dd.used)} of ${g(Dd.cap)} SATCOM at minimums · LOS ${g(Lo.used)} of ${g(Lo.cap)}`, src: `${src.data || 'brief'} · guests' minimum rates (DEC-38)` },
      { label: 'Compute', v: g(K.free), u: 'cores', pct: K.pct, bind: over(comp), of: `${g(K.used)} of ${g(K.cap)}`, src: `${src.compute || 'brief'} · cores per card (assumed)` },
      { label: 'Response', v: d.latency_ms.toFixed(1), u: 'ms', pct: 1, bind: d.latency_ms > d.ceiling_s * 1000, of: `of ${g(d.ceiling_s)} s · D1`, src: `${src.response || 'brief'} · measured on this request` },
    ];
  }

  function renderGauges(t) {
    const pier = state.tab === 'admit' && state.admit.data && state.admit.room;
    if (pier) {
      const d = state.admit.data, r = state.admit.room;
      $('gtitle').textContent = 'Free at the mission envelope';
      $('gsub').textContent = `${r.as_built.judge_cooling_at_c} °C · ${r.as_built.reserve_kw.cruise} kW reserve · one genset down checked`;
      paint($('gauges'), pierGauges(d, r).map(gaugeHTML).join(''));
      return;
    }
    const v = t.view;
    const limiting = v.tiles.filter(x => ['LIMITING', 'OVER'].includes(x.state)).map(x => low(x.name).replace(' chw', ''));
    const gens = v.plant.filter(p => p.tag.startsWith('GEN') && p.state === 'RUN').length;
    $('gtitle').textContent = 'Free now';
    $('gsub').textContent = `against the shed limit · ${gens === 2 ? 'both gensets' : 'one genset down'}${limiting.length ? ` · ${limiting.join(', ')} binds` : ''}`;
    paint($('gauges'), liveGauges(t, state.geo).map(gaugeHTML).join(''));
  }

  // ------------------------------------------------------------------------------------------- decision as text

  const facts = rows => `<div class="facts">${rows.map(r => `<span class="k">${esc(r[0])}</span><span class="v${r[2] ? ' ' + r[2] : ''}">${esc(r[1])}</span>`).join('')}</div>`;
  const opts = rows => `<div class="opts">${rows.map(o => `<div class="opt ${o.cls || ''}"><span class="t">${esc(o.t)}</span><span class="cost">${esc(o.cost)}</span><span class="d">${esc(o.d)}</span></div>`).join('')}</div>`;
  const sechead = (h, label) => `<div class="sechead"><h2>${esc(h)}</h2><span class="label num">${esc(label)}</span></div>`;
  const verdict = (word, cls, lat) => `<div class="verdict"><span class="word ${cls}">${esc(word)}</span>${lat ? `<span class="lat">${esc(lat)}</span>` : ''}</div>`;
  const r3line = x => (x ? `<div class="r3">R3 · <b>${esc(x.crew)} aboard</b> · ${esc(low(x.verdict))} · ${esc(x.sentence)}</div>` : '');
  const verify = (t, rec) => `<div class="verify verify-only">record seq ${esc(rec.seq)} · kind ${esc(rec.kind)} · tick ${esc(rec.tick)} · applies ${esc(rec.applies_at_tick ?? rec.tick + 1)} · inputs ${esc(rec.inputs_hash || '—')} · snapshot tick ${esc(t.view.snapshot_tick)} · records seen ${esc(t.view.records_seen)}</div>`;

  function condVal(signal, v) {
    if (v && typeof v === 'object') {
      const unit = signal.endsWith('_kn') ? ' kn' : '';
      return v.min != null && v.max != null ? `${v.min}–${v.max}${unit}` : v.min != null ? `≥ ${v.min}${unit}` : `≤ ${v.max}${unit}`;
    }
    if (signal === 'heading_free') return v ? 'free' : 'steady';
    if (typeof v === 'boolean') return v ? 'on' : 'off';
    if (signal.endsWith('_kn')) return `${v} kn`;
    return words(v);
  }
  function lossText(rec) {
    return Object.entries(rec.losses || {}).sort().map(([gid, l]) => l.mode_before === l.mode_after ? `${gid} none`
      : `${gid} ${words(l.mode_before)} → ${words(l.mode_after)} · ${pct(l.capability_before)} → ${pct(l.capability_after)} %`).join(' · ') || 'none';
  }

  function decisionHTML(t) {
    const v = t.view, d = v.decision, snap = t.snapshot, geo = state.geo;
    if (!d) {
      const quiet = v.tiles.every(x => ['NORMAL', 'NEAR LIMIT', 'FULL'].includes(x.state));
      const who = v.guests.map(x => `${x.id} ${words(x.activity)}, ${words(x.mode.split(' · ')[0])} ${x.kw} kW`).join('; ');
      const last = v.shed_order.rows.filter(r => r.state === 'LAST').map(r => `${r.g} · mission critical · ${low(r.tier)} class`);
      const r3 = latest(t.records, ['D5']);
      return sechead('No decision pending', quiet ? 'eight budgets steady' : 'no record yet') +
        `<p class="sentence quiet">${esc(cap(who))}. No decision yet.</p>` +
        facts([['Profile', `${missionName(t.mission)} · ${weightsOf(t.mission) || 'weights in the file'}`], ['Goes last', last.join(' · ') || 'nothing declared mission critical'],
               ['Shed ladder', 'computed every tick from the profile; shown with the first load decision']]) +
        r3line(r3 && { crew: r3.crew_aboard, verdict: r3.verdict, sentence: r3.sentence });
    }
    const rec = t.records.find(r => r.seq === d.seq && r.kind === d.kind) || {};
    const lat = responseText(d);
    if (d.kind === 'D3') {
      const lim = rec.hard_limit || {}, when = lim.when || {}, cost = rec.cost_to_loser || {};
      const sig = String(when.signal || '').split('.').pop().replace('_pct', '').replace(/_/g, ' ');
      const conflict = (rec.conflicts || []).map(c => c.exclusion ? c.exclusion.replace(/\./g, ' ').replace(/_/g, ' ')
        : `${SIGNALS[c.signal] || words(c.signal)} ${condVal(c.signal, c[rec.yields])} vs ${condVal(c.signal, c[rec.proceeds])}`).join(' · ');
      const [lo, hi] = cost.minutes_lost || ['?', '?'];
      const rows = [
        ['Hard limit', `${lim.guest} ${sig} ${when.op} ${when.value} % · land within ${(lim.then || {}).within_min} min · by ${clock(rec.deadline_t_s)}`],
        ['Conflict', conflict, 'conflict'],
        [`Cost to ${cost.guest || rec.yields}`, `leg ${cost.leg} · ${lo}–${hi} survey minutes${cost.open_ended ? ', open-ended' : ''}${cost.holds ? ` · holds ${words(cost.holds)}` : ''}` +
          (cost.recovery ? ` · recovered via the ${words(cost.recovery.via)} after ${cost.recovery.after}` : '')],
        ['Reserved', rec.reserved && Object.keys(rec.reserved).length ? Object.entries(rec.reserved).map(([gid, kw]) => `${gid} ${kw} kW ahead of everything`).join(' · ') : 'nothing'],
      ];
      if (d.r3) rows.push(['Crew', `${d.r3.crew} aboard · ${d.r3.sentence}`]);
      return sechead(`Right of way · ${rec.proceeds} / ${rec.yields}`, `D3 · ${clock(rec.t_s)}`) + verdict(`${rec.proceeds} proceeds`, 'ok', lat) +
        `<p class="sentence">${esc(rec.sentence)}</p>` + facts(rows) +
        '<p class="aside-note">Hard limits are judged before weights; the profile decides what the loser gives up.</p>' + verify(t, rec);
    }
    if (d.kind === 'D4') {
      const b = rec.binding || {}, cls = b.class === 'heat' ? 'cooling' : words(b.class);
      const f = (snap.faults || []).find(x => x.fault === rec.trigger && x.raw_event_t_s === rec.raw_event_t_s);
      const subj = f ? words(f.subject).replace('genset', 'gen').replace('chw pump', 'CHW pump') : words(rec.trigger);
      let trig = `${subj} ${rec.trigger === 'cooling_degraded' ? 'fault' : 'trip'} ${clock(rec.raw_event_t_s)} · confirmed ${clock(rec.confirmed_t_s)}`;
      if (f && rec.trigger === 'genset_trip') trig += ` on ${f.votes.length} of ${geo ? geo.as_built.trip_signals : 3} signals`;
      if (f && rec.trigger === 'cooling_degraded') trig += ` by ${f.votes.map(x => x.replace(/_/g, ' ')).join(', ')}`;
      if (rec.injected) trig += ' · injected';
      const rows = [['Trigger', trig, rec.injected ? 'b' : ''], ['Limit', `${g(b.capacity)} − ${g(b.capacity - rec.limit_kw)} headroom = ${g(rec.limit_kw)} kW`]];
      let word = 'Holds', wcls = '', title = `Load management · ${cls} limit`;
      if (rec.verdict === 'shed') {
        word = 'Shed'; wcls = 'warm';
        const re = d.recheck ? (String(d.recheck).match(/\d\d:\d\d:\d\d/) || [])[0] : null;
        rows.push(['Binding', `${cls} · ${g(rec.load_kw)} of ${g(rec.limit_kw)} kW`, 'b']);
        rows.push(['Action', (rec.steps || []).map(s => `${s.guest} ${words(s.from_mode)} → ${words(s.to_mode)} · frees ${g(s.frees_kw)} kW`).join(' · ')]);
        rows.push(['After', `${g(rec.load_after_kw)} of ${g(rec.limit_kw)} kW${re ? ` · recheck ${re} holds` : ''}`]);
      } else {
        word = rec.verdict === 'hold' ? 'Holds' : cap(words(rec.verdict));
        rows.push(['Load', `${g(rec.load_kw)} kW · ${g(rec.limit_kw - rec.load_kw)} kW spare`]);
        const a = (rec.armed || [])[0];
        rows.push(['Next armed', a ? `${a.guest} ${words(a.from_mode)} → ${words(a.to_mode)} · frees ${g(a.frees_kw)} kW` : 'nothing armed']);
      }
      rows.push(['Loss', lossText(rec)]);
      const applied = d.applied && rec.verdict === 'shed' ? ` · applied ${clock(rec.applies_at_tick)}` : '';
      const note = rec.verdict === 'shed' ? '' : `<p class="aside-note">Nothing is shed now; ${(rec.armed || []).length} steps stay armed in order.</p>`;
      return sechead(title, `D4 · ${clock(rec.t_s)}`) + verdict(word, wcls, lat + applied) +
        `<p class="sentence${rec.sentence.length > 220 ? ' long' : ''}">${esc(rec.sentence)}</p>` + facts(rows) + note + r3line(d.r3) + verify(t, rec);
    }
    return sechead(d.title, `${d.kind} · ${d.t}`) + verdict(cap(low(d.tag)), '', lat) + `<p class="sentence">${esc(d.sentence)}</p>` + r3line(d.r3);
  }

  // ------------------------------------------------------------------------------------------- the two ships

  function compareHTML(t) {
    const mark = currentMark();
    const tm = mark.t_s;
    if (state.compare.t !== tm || !state.compare.data) {
      if (state.compare.loading !== tm) {
        state.compare.loading = tm;
        getJSON(`/api/compare?t=${tm}`).then(x => { state.compare = { t: tm, data: x, loading: null }; render(); }).catch(() => { state.compare.loading = null; });
      }
      if (!state.compare.data) return sechead('Two ships', 'loading…') + '<div class="empty">…</div>';
    }
    const d = state.compare.data;
    const cols = d.files.map(f => {
      const s = d.ships[f], dec = s.decision;
      const bars = Object.fromEntries(s.bars.map(b => [b.name, b]));
      const free = b => { const [a, c] = String(b.value).split(' / '); return g(num(c) - num(a)); };
      const keep = new Set(['COST', 'RESERVED', 'ACTION', 'RESULT', 'NEXT', 'FREED']);
      const nums = dec ? dec.rows.filter(r => keep.has(r[0])).map(r => `${low(r[0])} ${soft(r[1])}`) : [];
      nums.push(`power free ${free(bars.POWER)} kW`, `cooling free ${free(bars['COOLING CHW'])} kW`);
      return `<div class="${esc(f)}"><h3>${esc(missionName(f))} · ${esc(weightsOf(f))}</h3><p>${esc(dec ? dec.sentence : 'No decision yet.')}</p><span class="num">${esc(nums.join(' · '))}</span></div>`;
    }).join('');
    const diff = d.diff.length
      ? `<div class="diff"><span></span>${d.files.map(f => `<span class="h ${esc(f)}">${esc(missionName(f))}</span>`).join('')}` +
        d.diff.map(x => `<span class="k">${esc(low(x.k))}</span><span class="v">${esc(soft(x.a))}</span><span class="v">${esc(soft(x.b))}</span>`).join('') + '</div>'
      : '<p class="aside-note">Same under both files at this mark.</p>';
    const next = marks().find(m => m.t_s > tm);
    const ctl = `<div class="ctl">${next ? `<button type="button" class="primary" data-jump="${Math.max(0, next.at - 3)}" data-then="decision">Continue to ${esc(next.t.slice(3))} · ${esc(low(next.label))}</button>` : ''}` +
      `<button type="button" data-tab="decision">Back to the decision</button></div>`;
    return sechead(`Two ships · ${mark.t_s ? mark.t : 'start'}${mark.label && mark.t_s ? ` · ${soft(mark.label)}` : ''}`, 'same inputs · profile only') +
      `<div class="two">${cols}</div>${diff}` +
      '<p class="aside-note">Both ships read the same inputs; only the priority file differs. What is the same is a hard limit; what differs is what the loser gives up.</p>' + ctl;
  }

  // ------------------------------------------------------------------------------------------- the jury's card (D1)

  function admitCase() {
    const a = state.admit;
    if (a.caseId) return a.caseId;
    const file = state.tick && state.meta.missions.some(m => m.id === state.tick.mission) ? state.tick.mission : 'survey';
    return `A5-${file}`;
  }
  function switchAdmitFile(file) {
    const id = admitCase();
    const base = id.slice(0, id.indexOf('-'));
    const want = `${base}-${file}`;
    if (!state.admit.cases || state.admit.cases.some(c => c.id === want)) { state.admit.caseId = want; state.admit.edits = {}; state.admit.good = {}; state.admit.refused = null; }
  }
  async function loadAdmit() {
    const a = state.admit;
    const seq = ++a.seq;
    const q = new URLSearchParams({ case: admitCase() });
    for (const [k, v] of Object.entries(a.edits)) q.append('edit', `${k}=${v}`);
    for (const [k, v] of Object.entries(a.good)) q.append('keep', `${k}=${v}`);
    let d, room, body;
    try {
      const [r1, r2] = await Promise.all([fetch(`/api/admit?${q}`, { cache: 'no-store' }), fetch(`/api/room?${q}`, { cache: 'no-store' })]);
      body = await r1.json().catch(() => null);
      if (!r1.ok) throw Object.assign(new Error(`/api/admit: ${r1.status}`), { status: r1.status, body });
      d = body;
      room = r2.ok ? await r2.json() : null;
    } catch (err) {
      if (seq !== a.seq) return;
      if (err.status === 404 && a.caseId) { a.caseId = null; loadAdmit(); return; }
      a.refused = (err.body && err.body.refused) || { field: '', reason: err.message };
      render();   // the previous verdict stays; the refusal is shown on the edit line
      return;
    }
    if (seq !== a.seq) return;
    a.refused = null; a.data = d; a.room = room || a.room; a.cases = d.cases;
    if (!d.rejected) a.good = { ...a.edits };
    if (!Object.keys(a.edits).length && !d.rejected) a.base[d.case.id] = { verdict: d.verdict, sentence: d.sentence };
    render();
  }
  function admitLoadedFor() { return state.admit.data && state.admit.data.case.id; }

  function editLabel(d, field) {
    const p = d.parts.find(x => x.field === field);
    if (p) return [p.name, 't', p.base];
    const w = d.power.find(x => x.field === field);
    if (w) return [w.name === 'peak' ? `${low(w.mode)}` : 'nominal', 'kW', w.base];
    return [field, '', ''];
  }
  function numberInput(d, field, base, shown) {
    const a = state.admit, typed = a.edits[field];
    const bad = (d.rejected && d.rejected.field === field) || (a.refused && a.refused.field === field);
    const edited = typed != null && !bad;
    const value = typed != null ? (typed === 'blank' ? '' : typed) : shown;
    return `<input type="text" inputmode="decimal" class="${bad ? 'bad' : edited ? 'edited' : ''}" data-field="${esc(field)}" data-base="${esc(base)}" value="${esc(value)}" aria-label="${esc(field)}">`;
  }

  function admitHTML() {
    const a = state.admit, d = a.data;
    if (!d) return sechead('Admission', 'loading…') + '<div class="empty">running D1…</div>';
    const rec = d.record || {};
    const cases = `<label class="cfg-only">case <select data-case="1">${(d.cases || []).map(c => `<option value="${esc(c.id)}"${c.id === d.case.id ? ' selected' : ''}>${esc(soft(c.label))}</option>`).join('')}</select></label>`;
    const inputs = [...d.parts.map(p => `<label>${esc(p.name)} ${numberInput(d, p.field, p.base, Number(p.mass_t).toFixed(3))} t</label>`),
      ...d.power.map(p => `<label>${esc(p.name === 'peak' ? low(p.mode) : 'nominal')} ${numberInput(d, p.field, p.base, String(p.kw))} kW</label>`)].join('');
    const nEdits = Object.keys(a.edits).length;
    const base = a.base[d.case.id];
    let note;
    if (a.refused) note = `<span class="refused">edit refused · ${esc(a.refused.field.split('.').slice(1).join('.'))}: ${esc(a.refused.reason)} · previous verdict kept</span>`;
    else if (d.rejected) note = `<span class="refused">card rejected · ${esc(d.rejected.field.split('.').slice(1).join('.'))}: ${esc(d.rejected.problem)} · previous card kept</span>`;
    else if (nEdits) {
      const moves = Object.entries(d.edits).map(([f, val]) => { const [l, u, b] = editLabel(d, f); return `${l} <span class="num">${esc(b)} ${u}</span> → <span class="num to">${esc(val)} ${u}</span>`; }).join(' · ');
      const became = base ? (base.verdict === d.verdict ? `still ${low(d.verdict)}` : `${low(base.verdict)} became ${low(d.verdict)}`) : '';
      note = `<span>Jury’s edit · ${moves}${became ? ` · ${became}` : ''}</span>`;
    } else note = '<span>Jury may change one number; D1 re-decides on every change.</span>';
    const edit = `<div class="edit">${cases}${inputs}${nEdits ? '<button type="button" class="linklike" data-revert="1">revert</button>' : ''}</div><div class="edit">${note}</div>`;
    const wmap = { yes: ['Yes', 'ok'], 'yes-if': ['Yes-if', 'warm'], no: ['No', 'warm'], 'not-now': ['Not now', 'warm'], 'card-rejected': ['Card rejected', 'warm'] };
    const [word, wcls] = wmap[d.verdict_raw] || [cap(low(d.verdict)), ''];
    const b = rec.binding || {};
    const bindText = b.class ? `${low(b.label || b.class)} · ${g(b.demand, b.unit === 't' || b.unit === 't_eq' ? 3 : 1)} of ${g(b.capacity, b.unit === 't' || b.unit === 't_eq' ? 3 : 1)} ${String(b.unit).replace('t_eq', 't-eq')}${b.class === 'heat' ? ` at ${a.room ? a.room.as_built.judge_cooling_at_c : 30} °C` : ''}` : soft(d.binding);
    const placed = Object.entries(rec.placement || {}).filter(([k]) => k.startsWith(d.case.card + '.'));
    const slotName = s => ({ flight_deck: 'flight deck', bay1: 'Bay 1', bay1_half: 'half of Bay 1', bay2: 'Bay 2', mast_free: 'mast', hangar_roof: 'hangar roof' }[s] || (s ? words(s) : 'no position'));
    const bySlot = {};
    placed.forEach(([k, s]) => { (bySlot[slotName(s)] = bySlot[slotName(s)] || []).push(k.split('.')[1]); });
    const placement = Object.entries(bySlot).map(([s, ps]) => `${ps.join(' and ')} → ${s}`).join(' · ') || soft((d.checks.find(c => c.k === 'PLACEMENT') || {}).v || '');
    const gen = rec.genset || {};
    const gstate = { fits: 'fits', holds_by_throttling: 'holds by throttling', does_not_hold: 'does not hold' }[gen.state] || gen.state;
    const steps = (gen.steps || []).map(s => `${s.guest} ${words(s.from_mode)} → ${words(s.to_mode)}, ${g(s.frees_kw)} kW freed`).join(' · ');
    const tip = rec.seawater_tip_c;
    const env = a.room ? a.room.as_built.envelope_seawater_c[1] : 30;
    const route = a.room && a.room.route_seawater_c != null ? ` · route ${a.room.route_seawater_c} °C` : '';
    const rows = [
      [d.verdict_raw === 'yes' ? 'Tightest' : 'Binding', bindText, d.verdict_raw === 'yes' ? '' : 'b'],
      ['Placement', placement + (a.room && a.room.unplaced && a.room.unplaced.length ? ` · no position for ${a.room.unplaced.map(u => `${u.guest} ${u.part}`).join(', ')}` : '')],
      ['One genset down', `${g(gen.load_kw)} of ${g(gen.reserve_kw)} kW · gate ${g(gen.gate_kw)} · ${gstate}${steps ? ` · ${steps}` : ''}`, gen.state === 'does_not_hold' ? 'b' : ''],
      ['Tipping point', tip == null ? 'none in scan' : `cooling flips at ${g(tip)} °C${route} · envelope to ${env} °C`, tip != null && tip <= env ? 'b' : ''],
      ['Inputs', `hash ${rec.inputs_hash || '—'}${Object.entries(d.edits).map(([f, val]) => ` · edit ${f}=${val}`).join('')}`],
    ];
    const options = d.options.length ? opts(d.options.map((o, i) => ({ t: `${o.n} · ${o.remove} disembarks`, cost: `${o.value_lost} lost${o.mc ? ' · mission-critical' : ''}`,
      d: `mass after ${o.mass_after}${o.moves ? ` · ${soft(o.moves)}` : ''}`, cls: i === 0 ? 'pick' : '' }))) : '';
    const noteOpts = d.options.length ? '<p class="aside-note">Switch the profile above: the ranking follows the file; the room is identical, only who yields changes.</p>' : '';
    const heldCell = a.room && a.room.cells.find(c => c.held);
    return sechead(`Admission · ${heldCell ? heldCell.who : `${d.case.card} ${low(d.case.card_name)}`}`, `D1 · ${d.latency_ms.toFixed(1)} ms of ${g(d.ceiling_s)} s`) + edit +
      verdict(word, wcls, `${d.latency_ms.toFixed(1)} ms of ${g(d.ceiling_s)} s · ${low(d.case.mission)} file`) +
      `<p class="sentence${d.sentence.length > 220 ? ' long' : ''}">${esc(d.sentence)}</p>` + facts(rows) + options + noteOpts +
      `<div class="verify verify-only">case ${esc(d.case.id)} · installed ${esc(d.case.installed.join(' '))} · ${esc(d.envelope.toLowerCase())} · record seq ${esc(rec.seq)} · inputs ${esc(rec.inputs_hash || '—')}</div>`;
  }

  function renderDecision(t) {
    document.querySelectorAll('#tabs button').forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === state.tab)));
    const el = $('decision');
    const focused = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.field : null;
    if (state.tab === 'compare') paint(el, compareHTML(t));
    else if (state.tab === 'admit') {
      if (!state.admit.data || admitLoadedFor() !== admitCase()) { if (!state.admit.loading) { state.admit.loading = true; loadAdmit().finally(() => { state.admit.loading = false; }); } }
      paint(el, admitHTML());
      if (focused) { const i = el.querySelector(`input[data-field="${CSS.escape(focused)}"]`); if (i) i.focus(); }
      if (state.admit.focus === 'peak') { const i = el.querySelector('input[data-field$=".peak"]'); if (i) { i.focus(); i.select(); } state.admit.focus = null; }
    } else paint(el, decisionHTML(t));
  }

  // ------------------------------------------------------------------------------------------- wiring

  function setTab(tab) { state.tab = tab; }
  function render() {
    const t = state.tick;
    if (!t || !state.meta) return;
    renderHeader(t);
    renderSteps(t);
    renderMap(t);
    renderGauges(t);
    renderDecision(t);
  }
  function applyTheme() {
    const root = document.documentElement;
    if (state.theme === 'auto') root.removeAttribute('data-theme'); else root.setAttribute('data-theme', state.theme);
    $('theme').textContent = `Theme: ${state.theme}`;
  }

  document.addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.profile) {
      send({ cmd: 'mission', value: b.dataset.profile });
      switchAdmitFile(b.dataset.profile);
      if (state.tab === 'admit') loadAdmit();
    } else if (b.dataset.preset) { state.preset = b.dataset.preset; store('argos-room-preset', state.preset); }
    else if (b.dataset.tab) { setTab(b.dataset.tab); }
    else if (b.dataset.step) { goStep(b.dataset.step); return; }
    else if (b.dataset.cmd) { if (b.dataset.cmd === 'restart') state.engineNote = ''; send({ cmd: b.dataset.cmd }); }
    else if (b.dataset.speed) send({ cmd: 'speed', value: Number(b.dataset.speed) });
    else if (b.dataset.jump) { send({ cmd: 'jump', t: Number(b.dataset.jump) }); send({ cmd: 'run' }); if (b.dataset.then) setTab(b.dataset.then); }
    else if (b.dataset.crew) send({ cmd: 'input', input: { type: 'crew_change', injected: false, payload: { crew_aboard: Number(b.dataset.crew) } } });
    else if (b.dataset.revert) { state.admit.edits = {}; state.admit.good = {}; state.admit.refused = null; loadAdmit(); }
    else if (b.id === 'theme') { state.theme = { auto: 'dark', dark: 'light', light: 'auto' }[state.theme]; store('argos-room-theme', state.theme); applyTheme(); }
    render();
  });
  document.addEventListener('change', e => {
    const el = e.target;
    if (el.matches('select[data-case]')) { state.admit.caseId = el.value; state.admit.edits = {}; state.admit.good = {}; state.admit.refused = null; loadAdmit(); }
    else if (el.matches('input[data-field]')) {
      const base = Number(el.dataset.base), raw = el.value.trim();
      if (raw !== '' && Number(raw) === base) { delete state.admit.edits[el.dataset.field]; delete state.admit.good[el.dataset.field]; }
      else state.admit.edits[el.dataset.field] = raw === '' ? 'blank' : raw;
      loadAdmit();
    }
  });
  document.addEventListener('keydown', e => {
    if (e.target.closest('input, select, textarea')) {
      if (e.key === 'Enter' && e.target.matches('input[data-field]')) e.target.dispatchEvent(new Event('change', { bubbles: true }));
      return;
    }
    if (e.code === 'Space') { e.preventDefault(); send({ cmd: 'toggle' }); }
    else if (/^[1-3]$/.test(e.key)) {
      const ms = marks().filter(m => m.t_s > 0);
      const m = ms[Number(e.key) - 1];
      if (m) { send({ cmd: 'jump', t: Math.max(0, m.at - 3) }); send({ cmd: 'run' }); }
    }
  });

  async function start() {
    applyTheme();
    document.body.className = `preset-${state.preset}`;
    const [meta, ref] = await Promise.all([getJSON('/api/meta'), getJSON('/api/reference').catch(() => null)]);
    state.meta = meta; state.ref = ref;
    connect();
  }
  start();
})();
