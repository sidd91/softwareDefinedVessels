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

export const INJECTED = '<span class="injected">INJECTED</span>';

export function injected(flag) {
  return flag ? ' ' + INJECTED : '';
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
