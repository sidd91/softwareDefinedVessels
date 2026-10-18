// Demo compare: the same inputs under two priority files, side by side, at the minute the bottom bar's run is on.
import { esc, chip, meter, panel, paint, getJSON } from './util.js';
import { app, setHeader } from './app.js';
import { recordRows, conflictTable } from './ops.js';

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
  paint(root, `<div class="row">${d.files.map(f => ship(f, d.ships[f])).join('')}</div>` + difference(d));
}

function header(d) {
  if (!app.tick || app.view !== 'compare') return;
  const h = app.tick.view.header;
  setHeader([chip(esc(h.crew)), chip(esc(h.sea)), chip(esc(h.sea_state)), chip(`SIM ×${esc(app.tick.speed)}`)].join(''), d.clock);
}

function timeline(t) {
  const btns = marks().map(m => {
    const on = m.t_s === t;
    return `<button type="button" class="tl-mark${on ? ' on' : ''}" data-t="${m.t_s}"><span class="mt">${esc(m.t)}</span><span class="ml">${esc(m.label)}</span></button>`;
  }).join('');
  const follow = `<button type="button" class="tl-mark${state.pinned == null ? ' on' : ''}" data-follow="1"><span class="mt">LIVE</span><span class="ml">FOLLOW REPLAY</span></button>`;
  return `<nav class="panel" aria-label="Timeline"><div class="strip"><span>TIMELINE</span></div><div class="marks">${btns}${follow}</div></nav>`;
}

function ship(f, s) {
  const d = s.decision;
  const hot = new Set(s.mimic.zones.filter(z => z.hot).map(z => z.guest.split(' ')[0]));
  const record = d
    ? `<p class="why" style="margin: 0; font-size: 17px; font-weight: 600" title="${esc(d.sentence)}">${esc(d.headline || d.sentence)}</p>${conflictTable({ ...d, conflicts: d.conflicts })}<div class="kv" style="padding: 0">${recordRows(d.rows.filter(r => r[0] !== 'RESPONSE'))}</div>`
    : '<div class="empty" style="padding: 0">NO DECISION</div>';
  const bars = s.bars.map(b => `<div><div class="bl"><b>${esc(b.name)}</b><span class="mono">${esc(b.value)}</span></div>
${meter(b.pct, b.mark, b.state === 'LIMITING' ? 'warn' : '')}</div>`).join('');
  const rows = s.guests.map(g => `<tr class="${hot.has(g.id) ? 'exec' : ''}"><td class="b">${esc(g.id)}</td><td>${esc(g.pos)}</td><td>${esc(g.mode)}</td><td class="num">${esc(g.kw)}</td><td class="num">${esc(g.cap)}</td></tr>`).join('');
  return `<section class="panel ship ${esc(f)}" aria-label="${esc(s.name)}">
<div class="strip"><span>${esc(s.name)}</span><span class="w">${esc(s.weights)}</span></div>
<div class="body">${record}<div class="bars">${bars}</div>
<table><thead><tr><th scope="col">ID</th><th scope="col">POS</th><th scope="col">MODE</th><th scope="col">kW</th><th scope="col">CAP</th></tr></thead><tbody>${rows}</tbody></table>
</div></section>`;
}

function difference(d) {
  const [a, b] = d.files;
  const rows = d.diff.map(x => `<tr><th scope="row" style="font-size: 13px; color: var(--muted); width: 160px">${esc(x.k)}</th><td class="num">${esc(x.a)}</td><td class="num">${esc(x.b)}</td></tr>`).join('');
  return panel(`DIFFERENCE · ${d.clock}`, `<div class="scroll-x"><table class="big diff" style="min-width: 640px">
<thead><tr><th scope="col"></th><th scope="col" class="${esc(a)}">${esc(d.ships[a].name.replace('MISSION ', ''))}</th><th scope="col" class="${esc(b)}">${esc(d.ships[b].name.replace('MISSION ', ''))}</th></tr></thead>
<tbody>${rows || '<tr><td colspan="3" class="empty">SAME</td></tr>'}</tbody></table></div>`, { strip: 'navy', note: 'SAME INPUTS · PRIORITY FILE ONLY' });
}
