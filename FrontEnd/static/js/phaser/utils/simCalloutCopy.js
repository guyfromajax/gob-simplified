/**
 * Sim broadcast callout copy — loader + template fill.
 *
 * Every line on a worm callout comes from `/sim-callout-copy.md`. Zero callout strings in
 * rendering or cadence source. Falls back to a bundled pack if the fetch fails.
 */

export const COPY_FILE = '/sim-callout-copy.md';

const SLOT_RE = /\{([A-Z_]+)\}/g;
const MIN_CATEGORIES = 8;

/** Bundled fallback — kept in sync with FrontEnd/static/sim-callout-copy.md. */
export const CALLOUT_PACK = {
  version: '2026.08.d-fallback',
  categories: {
    gamewinner: { avatar: 'headshot', color: 'gold', lines: [
      '{NAME} — Game Winning Shot!',
    ] },
    milestone: { avatar: 'headshot', color: 'gold', lines: [
      '{NAME} has *{PTS}* now', "That's *{PTS}* for {NAME}", '{NAME} up to *{PTS}* points',
    ] },
    boards10: { avatar: 'headshot', color: 'gold', lines: [
      '{NAME} has *{REB}* boards', '*{REB}* rebounds for {NAME}',
    ] },
    doubleDouble: { avatar: 'headshot', color: 'gold', lines: [
      '{NAME} — double-double', 'Double-double for {NAME}', '{NAME} hits *{CATS}*',
    ] },
    streak: { avatar: 'headshot', color: 'orange', lines: [
      '{NAME} has the last *{STREAK}*', '*{STREAK}* straight for {NAME}',
    ] },
    run: { avatar: 'abbr', color: 'orange', lines: [
      '{TEAM} on a *{RUN}* run', '*{RUN}* unanswered for {TEAM}',
    ] },
    advantage: { avatar: 'abbr', color: 'blue', lines: [
      '*+{EDGE}* {STAT} advantage', '{TEAM} up *+{EDGE}* on {STAT}',
    ] },
    disadvantage: { avatar: 'abbr', color: 'red', lines: [
      '{TEAM} — *+{EDGE}* {STAT} disadvantage', '*+{EDGE}* {STAT} disadvantage for {TEAM}',
    ] },
    defense: { avatar: 'headshot', color: 'blue', lines: [
      '{NAME} — *{DEF}%* defense', '{NAME} locking up at *{DEF}%*',
    ] },
    clutch: { avatar: 'headshot', color: 'green', lines: [
      '{NAME} — go-ahead bucket!', '{NAME} puts them up!', '{NAME} ties it!',
    ] },
    fouledout: { avatar: 'headshot', color: 'red', lines: [
      '{NAME} fouls out', "That's five on {NAME}",
    ] },
  },
};

export function copyUrl() {
  const cfg = (typeof window !== 'undefined') ? window.API_CONFIG : null;
  return (cfg && typeof cfg.buildStaticPath === 'function')
    ? cfg.buildStaticPath(COPY_FILE)
    : COPY_FILE;
}

export function parseCalloutMd(md) {
  const categories = {};
  let cur = null;
  const ver = (String(md || '').match(/\*\*version:\s*([^*]+)\*\*/) || [])[1];

  String(md || '').split(/\r?\n/).forEach((raw) => {
    const line = raw.trim();
    if (line.startsWith('###')) {
      const parts = line.replace(/^#+\s*/, '').split('·').map((s) => s.trim());
      const id = parts[0];
      const meta = { avatar: 'headshot', color: 'green' };
      parts.slice(1).forEach((p) => {
        const a = p.match(/^avatar\s+(\w+)$/i);
        if (a) meta.avatar = a[1].toLowerCase();
        const c = p.match(/^color\s+(\w+)$/i);
        if (c) meta.color = c[1].trim().toLowerCase();
        else if (/^(gold|blue|orange|red|green)$/i.test(p)) meta.color = p.toLowerCase();
      });
      categories[id] = { avatar: meta.avatar, color: meta.color, lines: [] };
      cur = categories[id];
      return;
    }
    if (line.startsWith('- ') && cur) cur.lines.push(line.slice(2).trim());
  });

  return { version: (ver || 'md').trim(), categories };
}

export function isUsableCalloutPack(pack) {
  return !!pack
    && !!pack.categories
    && Object.keys(pack.categories).length >= MIN_CATEGORIES
    && Object.values(pack.categories).every((c) => c && Array.isArray(c.lines) && c.lines.length > 0);
}

let cached = null;

export function loadCalloutCopy(opts = {}) {
  if (cached && !opts.force) return cached;
  const url = opts.url || copyUrl();
  const fallback = () => ({ ...CALLOUT_PACK, source: 'simCalloutCopy.js (fallback)' });

  const fetchFn = (typeof fetch === 'function') ? fetch : null;
  if (!fetchFn) {
    cached = Promise.resolve(fallback());
    return cached;
  }

  cached = fetchFn(url)
    .then((res) => (res && res.ok ? res.text() : Promise.reject(new Error('callout copy fetch failed'))))
    .then((text) => {
      const parsed = parseCalloutMd(text);
      if (!isUsableCalloutPack(parsed)) return fallback();
      return { ...parsed, source: `sim-callout-copy.md · v${parsed.version}` };
    })
    .catch(() => fallback());
  return cached;
}

export function resetCalloutCopy() {
  cached = null;
}

export function fillCalloutLine(template, values) {
  const bag = values || {};
  let missing = false;
  const out = String(template || '').replace(SLOT_RE, (_, key) => {
    const v = bag[key];
    if (v === undefined || v === null || v === '') { missing = true; return ''; }
    return String(v);
  });
  return missing ? null : out.replace(/\s{2,}/g, ' ').trim();
}

export function pickCalloutLine(pack, id, values, rnd) {
  const cat = pack && pack.categories && pack.categories[id];
  if (!cat || !cat.lines || !cat.lines.length) return null;
  const usable = cat.lines.map((l) => fillCalloutLine(l, values)).filter((l) => l !== null && l !== '');
  if (!usable.length) return null;
  const r = typeof rnd === 'function' ? rnd() : Math.random();
  const idx = Math.min(usable.length - 1, Math.max(0, Math.floor(r * usable.length)));
  return {
    tier: id,
    avatar: cat.avatar || 'headshot',
    color: cat.color || 'green',
    line: usable[idx],
  };
}
