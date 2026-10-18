// Small rendering helpers shared by the views. Every string from the server goes through esc().

export function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// "NEAR LIMIT" -> "t-NEAR-LIMIT"; the class names in argos.css follow the status words.
export function tagClass(word) {
  return 't-' + String(word || '-').replace(/[^A-Za-z0-9]+/g, '-').replace(/-+$/, '') || 't--';
}

export function tag(word, lg = false) {
  return `<span class="tag${lg ? ' lg' : ''} ${tagClass(word)}">${esc(word)}</span>`;
}

// Scenario faults show exactly as plant faults do: no marker on screen.
export function injected() {
  return '';
}

export function stateWord(word) {
  const warn = ['LIMITING', 'DEGRADED', 'NEAR LIMIT', 'REDUCED'].includes(word);
  const bad = ['OVER', 'LATE', 'DOWN'].includes(word);
  return `<span class="state-word${warn ? ' warn' : ''}${bad ? ' bad' : ''}">${esc(word)}</span>`;
}

export function chip(text, cls = '') {
  return `<span class="chip ${cls}">${text}</span>`;
}

export function meter(pct, mark, tone = '') {
  const m = mark == null ? '' : `<div class="mark" style="left: calc(${mark}% - 1px)"></div>`;
  return `<div class="meter"><div class="fill ${tone}" style="width: ${pct}%"></div>${m}</div>`;
}

export function panel(title, inner, { cls = '', strip = '', note = '', label = title } = {}) {
  const n = note ? `<span class="note">${note}</span>` : '';
  return `<section class="panel ${cls}" aria-label="${esc(label)}"><div class="strip ${strip}"><span>${esc(title)}</span>${n}</div>${inner}</section>`;
}

export async function getJSON(url) {
  const r = await fetch(url, { cache: 'no-store' });
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

// Render into an element only when the markup changed, so a 12 Hz stream does not rebuild the DOM every tick.
export function paint(el, html) {
  if (el.__last !== html) {
    el.innerHTML = html;
    el.__last = html;
  }
}

// Render a row of single-element fragments, each into its own slot and only when that fragment changed, so a button in
// one slot (the crew chip) outlives the ticks that move the text of its neighbours. Empty fragments take no slot.
export function paintEach(el, parts) {
  const items = parts.filter(Boolean);
  while (el.children.length > items.length) el.lastElementChild.remove();
  items.forEach((html, i) => {
    const slot = el.children[i];
    if (slot && slot.__last === html) return;
    const tpl = document.createElement('template');
    tpl.innerHTML = html;
    const node = tpl.content.firstElementChild;
    node.__last = html;
    if (slot) slot.replaceWith(node); else el.append(node);
  });
  el.__last = undefined; // a later paint() of the whole element must not skip its first repaint
}
