/**
 * Sim broadcast moment copy — loader + template fill.
 *
 * Every line that appears on a card comes from `/sim-moment-copy.md`, fetched at runtime so
 * copy edits ship without touching code (brief §10; acceptance: zero copy in source). If that
 * fetch fails — offline, or a downloaded build with no server — we fall back to the data-only
 * `simMomentPack.js`. Nothing here, and nothing in the renderer, may contain a card string.
 *
 * The `.md` format is the one the design mockups read:
 *   `### <id> · tag <TAG> · color <COLOR>` then one `- ` line per copy variant.
 *   `### context` rows are pipe-delimited: SETTING | VALUE | STAT | NOW | your base | league base
 */

import { MOMENT_PACK } from './simMomentPack.js';

export const COPY_FILE = '/sim-moment-copy.md';

/**
 * Static assets live under /static locally and at the root in production, and the dev
 * middleware only rewrites a whitelist of extensions — `.md` is not on it. API_CONFIG owns
 * that difference, so ask it rather than hardcoding either form.
 */
export function copyUrl() {
  const cfg = (typeof window !== 'undefined') ? window.API_CONFIG : null;
  return (cfg && typeof cfg.buildStaticPath === 'function')
    ? cfg.buildStaticPath(COPY_FILE)
    : COPY_FILE;
}

/** A parse is only trusted if it actually carries a pack's worth of copy. */
const MIN_CATEGORIES = 8;

/** Slots the engine fills from emitted per-player deltas. */
const SLOT_RE = /\{([A-Z]+)\}/g;

/**
 * Parse the editable markdown into the pack shape.
 * Unknown `###` sections are kept — new card types can be added in the file alone.
 */
export function parseCopyMd(md) {
  const categories = {};
  const context = [];
  let cur = null;
  let isCtx = false;
  const ver = (String(md || '').match(/\*\*version:\s*([^*]+)\*\*/) || [])[1];

  String(md || '').split(/\r?\n/).forEach((raw) => {
    const line = raw.trim();
    if (line.startsWith('###')) {
      const parts = line.replace(/^#+\s*/, '').split('·').map((s) => s.trim());
      const id = parts[0];
      isCtx = id === 'context';
      if (isCtx) { cur = null; return; }
      const meta = { tag: id.toUpperCase(), color: 'green' };
      parts.slice(1).forEach((p) => {
        const t = p.match(/^tag\s+(.+)$/i);
        if (t) meta.tag = t[1].trim();
        const c = p.match(/^color\s+(\w+)$/i);
        if (c) meta.color = c[1].trim();
      });
      categories[id] = { tag: meta.tag, color: meta.color, lines: [] };
      cur = categories[id];
      return;
    }
    if (!line.startsWith('- ')) return;
    const value = line.slice(2).trim();
    if (isCtx) {
      const f = value.split('|').map((s) => s.trim());
      if (f.length >= 6) {
        context.push({ setting: f[0], value: f[1], stat: f[2], now: f[3], base: f[4], league: f[5] });
      }
    } else if (cur) {
      cur.lines.push(value);
    }
  });

  return { version: (ver || 'md').trim(), categories, context };
}

/** True when a parsed pack has enough in it to be worth preferring over the fallback. */
export function isUsablePack(pack) {
  return !!pack
    && !!pack.categories
    && Object.keys(pack.categories).length >= MIN_CATEGORIES
    && Object.values(pack.categories).every((c) => c && Array.isArray(c.lines) && c.lines.length > 0)
    && Array.isArray(pack.context)
    && pack.context.length > 0;
}

let cached = null;

/**
 * Resolve the copy pack once per session.
 * Always resolves — a failed fetch degrades to the bundled pack rather than killing playback.
 * @returns {Promise<{version:string, categories:object, context:Array, source:string}>}
 */
export function loadMomentCopy(opts = {}) {
  if (cached && !opts.force) return cached;
  const url = opts.url || copyUrl();
  const fallback = () => ({ ...MOMENT_PACK, source: 'simMomentPack.js (fallback)' });

  const fetchFn = (typeof fetch === 'function') ? fetch : null;
  if (!fetchFn) {
    cached = Promise.resolve(fallback());
    return cached;
  }

  cached = fetchFn(url)
    .then((res) => (res && res.ok ? res.text() : Promise.reject(new Error('copy fetch failed'))))
    .then((text) => {
      const parsed = parseCopyMd(text);
      if (!isUsablePack(parsed)) return fallback();
      return { ...parsed, source: `sim-moment-copy.md · v${parsed.version}` };
    })
    .catch(() => fallback());
  return cached;
}

/** Test seam — drop the memoised pack. */
export function resetMomentCopy() {
  cached = null;
}

/**
 * Fill `{SLOT}` placeholders from a values bag.
 * An unknown or empty slot collapses the line rather than printing a literal `{PTS}` on screen;
 * callers should pick a different variant when this returns null.
 */
export function fillLine(template, values) {
  const bag = values || {};
  let missing = false;
  const out = String(template || '').replace(SLOT_RE, (_, key) => {
    const v = bag[key];
    if (v === undefined || v === null || v === '') { missing = true; return ''; }
    return String(v);
  });
  return missing ? null : out.replace(/\s{2,}/g, ' ').trim();
}

/**
 * Choose a copy variant for a category, filling slots from `values`.
 * Variants that need a slot this event has no value for are skipped, so a template referencing
 * {AST} never appears on a card built from a rebound.
 * @param {object} pack   resolved copy pack
 * @param {string} id     category id (`bucket`, `board`, `run`, …)
 * @param {object} values slot bag
 * @param {() => number} rnd injectable RNG for deterministic tests
 */
export function pickLine(pack, id, values, rnd) {
  const cat = pack && pack.categories && pack.categories[id];
  if (!cat || !cat.lines || !cat.lines.length) return null;
  const usable = cat.lines.map((l) => fillLine(l, values)).filter((l) => l !== null && l !== '');
  if (!usable.length) return null;
  const r = typeof rnd === 'function' ? rnd() : Math.random();
  const idx = Math.min(usable.length - 1, Math.max(0, Math.floor(r * usable.length)));
  return { tag: cat.tag, color: cat.color, line: usable[idx] };
}
