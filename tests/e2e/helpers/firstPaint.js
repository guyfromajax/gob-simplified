// @ts-check
/**
 * First-paint sweep helpers.
 *
 * Jamie's rule: no screen is ever shown half-built. With every API response held back,
 * a screen must show nothing, a designed skeleton or its loading overlay until the data
 * is in: never bare titles, placeholder dashes, "NR" / "0-0" / "undefined" / "null", a
 * layout that jumps when data lands, or an old panel that is then replaced.
 *
 * `delayApi` holds every API response. `probe` reads what is actually visible (text that
 * is on screen and not covered), and `compare` reports what moved or vanished between the
 * first paint and the settled page.
 */

const STATIC_PREFIXES = ['/images/', '/js/', '/css/', '/fonts/', '/sounds/', '/media/', '/config/'];
const STATIC_EXT = /\.(?:js|mjs|css|html|png|jpe?g|gif|svg|webp|ico|woff2?|otf|ttf|wav|mp3|ogg|mp4|webm|map)$/i;

function isApiRequest(request) {
  const type = request.resourceType();
  if (type !== 'fetch' && type !== 'xhr') return false;
  let pathname = '';
  try { pathname = new URL(request.url()).pathname; } catch (err) { return false; }
  if (STATIC_EXT.test(pathname)) return false;
  if (STATIC_PREFIXES.some((prefix) => pathname.startsWith(prefix))) return false;
  return true;
}

/**
 * Hold every API response for `ms`. Returns a tracker: `inFlight()` and `idleFor()` say
 * when the page has stopped asking for data, `seen` lists what it asked for.
 * `fulfil(request)` may return a `{status, body}` to answer from a recording instead of
 * the network (the online pass replays the offline pass's real data).
 */
async function delayApi(page, ms, fulfil) {
  const state = { pending: 0, lastChange: Date.now(), seen: [] };
  await page.route('**/*', async (route) => {
    const request = route.request();
    if (!isApiRequest(request)) return route.continue();
    state.pending += 1;
    state.lastChange = Date.now();
    state.seen.push(request.method() + ' ' + new URL(request.url()).pathname);
    try {
      await new Promise((resolve) => setTimeout(resolve, ms));
      const canned = fulfil ? await fulfil(request) : null;
      if (canned) {
        await route.fulfill({
          status: canned.status || 200,
          contentType: 'application/json',
          body: typeof canned.body === 'string' ? canned.body : JSON.stringify(canned.body),
        });
      } else {
        await route.continue();
      }
    } catch (err) {
      /* the page navigated away while the response was held */
    } finally {
      state.pending -= 1;
      state.lastChange = Date.now();
    }
  });
  return {
    seen: state.seen,
    inFlight: () => state.pending,
    idleFor: () => (state.pending === 0 ? Date.now() - state.lastChange : 0),
  };
}

/** Wait until no API call has been in flight for `quiet` ms (or `cap` ms pass). */
async function settle(page, tracker, quiet, cap) {
  const started = Date.now();
  while (Date.now() - started < (cap || 20000)) {
    if (tracker.idleFor() >= (quiet || 1200)) return true;
    await page.waitForTimeout(150);
  }
  return false;
}

/** Runs in the page. What a person can actually see right now. */
function probeInPage() {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const shown = (el) => {
    for (let node = el; node && node.nodeType === 1; node = node.parentElement) {
      const cs = getComputedStyle(node);
      if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return false;
    }
    return true;
  };
  const onTop = (el, x, y) => {
    const hit = document.elementFromPoint(x, y);
    return !!hit && (hit === el || el.contains(hit) || hit.contains(el));
  };
  const overlay = document.getElementById('page-load-overlay');
  const overlayOn = !!overlay && shown(overlay) && overlay.getClientRects().length > 0;

  const texts = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  while (node) {
    const text = (node.nodeValue || '').replace(/\s+/g, ' ').trim();
    const parent = node.parentElement;
    if (text && parent && !/^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(parent.tagName) && shown(parent)) {
      const range = document.createRange();
      range.selectNodeContents(node);
      const rect = range.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < vh && rect.right > 0 && rect.left < vw) {
        const cx = Math.min(vw - 1, Math.max(0, rect.left + rect.width / 2));
        const cy = Math.min(vh - 1, Math.max(0, rect.top + rect.height / 2));
        if (onTop(parent, cx, cy)) {
          const inOverlay = !!(overlay && overlay.contains(parent));
          const chrome = !!parent.closest('.top, nav.rail, .rail, #gob-top, .gob-top, header.top, .auth-bar, .site-footer');
          texts.push({
            t: text.slice(0, 80), x: Math.round(rect.left), y: Math.round(rect.top),
            tag: parent.tagName.toLowerCase(), inOverlay, chrome,
            heading: !!parent.closest('h1, h2, h3, h4, .pg-head, th'),
          });
        }
      }
    }
    node = walker.nextNode();
  }
  const PLACEHOLDER = /(^|[\s:])(--|—|–)($|[\s%])|\bNR\b|(^|\s)0-0($|\s)|undefined|\bnull\b|\bNaN\b/;
  const flagged = texts.filter((entry) => !entry.inOverlay && PLACEHOLDER.test(entry.t));
  const skeleton = [...document.querySelectorAll('[class*="skel"], [class*="skeleton"], .rsk, .gob-sk')]
    .filter((el) => shown(el) && el.getClientRects().length > 0).length;
  const headings = [...document.querySelectorAll('h1, h2, h3')]
    .filter((el) => shown(el) && el.getClientRects().length > 0 && (el.textContent || '').trim())
    .map((el) => {
      const r = el.getBoundingClientRect();
      const cx = Math.min(vw - 1, Math.max(0, r.left + Math.min(r.width, 40) / 2));
      const cy = Math.min(vh - 1, Math.max(0, r.top + r.height / 2));
      return {
        t: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60),
        x: Math.round(r.left), y: Math.round(r.top), seen: r.bottom > 0 && r.top < vh && onTop(el, cx, cy),
        chrome: !!el.closest('.top, nav.rail, .rail, .pg-head'),
        inOverlay: !!(overlay && overlay.contains(el)),
      };
    })
    .filter((h) => h.seen && !h.inOverlay);
  const content = texts.filter((entry) => !entry.inOverlay && !entry.chrome);
  return {
    overlayOn,
    skeleton,
    flagged: flagged.map((entry) => ({ t: entry.t, x: entry.x, y: entry.y, chrome: entry.chrome })),
    headings,
    contentCount: content.length,
    sample: content.slice(0, 40).map((entry) => entry.t).join(' | ').slice(0, 700),
    scrollH: document.documentElement.scrollHeight,
  };
}

async function probe(page) {
  try {
    return await page.evaluate(probeInPage);
  } catch (err) {
    return { error: String(err && err.message || err).slice(0, 120) };
  }
}

/** What changed between a pre-data probe and the settled page. */
function compare(first, final) {
  if (!first || !final || first.error || final.error) return { moved: [], vanished: [] };
  const byText = new Map(final.headings.map((h) => [h.t, h]));
  const moved = [];
  const vanished = [];
  first.headings.forEach((h) => {
    if (h.chrome) return;
    const later = byText.get(h.t);
    if (!later) vanished.push(h.t);
    else if (Math.abs(later.y - h.y) > 6 || Math.abs(later.x - h.x) > 6) {
      moved.push({ t: h.t, dy: later.y - h.y, dx: later.x - h.x });
    }
  });
  return { moved, vanished };
}

/**
 * Open one screen with the API held back and record what it shows on the way in.
 *
 *   first       ~1.1 s: before any data can have arrived (the first paint)
 *   mid         ~2.3 s: after the first response, before the calls it triggers
 *   post        the moment the page-load overlay lifts (if the screen uses it)
 *   post2       0.8 s after that: what stands in while the view's own data loads
 *   final       settled
 *
 * `shot(suffix)` saves a screenshot. `before(page)` runs after navigation commits
 * (the Settings panel opens itself there). `action(page)` replaces the navigation: a
 * transition is swept from the click that starts it (`overlayCap` ms for a long loader).
 */
async function sweepScreen(page, tracker, url, shot, opts) {
  const options = opts || {};
  const overlayOn = () => page.evaluate(() => {
    const el = document.getElementById('page-load-overlay');
    return !!el && getComputedStyle(el).display !== 'none' && el.getClientRects().length > 0;
  }).catch(() => false);
  let started = Date.now();
  const at = async (ms) => { const wait = ms - (Date.now() - started); if (wait > 0) await page.waitForTimeout(wait); };
  if (options.action) await options.action(page);
  else await page.goto(url, { waitUntil: 'commit' }).catch(() => {});
  if (options.before) {
    await options.before(page, tracker);
    started = Date.now();
  }
  await at(500);
  const p500 = await probe(page);
  await at(1100);
  const first = await probe(page);
  await shot('first');
  await at(2300);
  const mid = await probe(page);
  await shot('mid');
  let post = null;
  let post2 = null;
  if (first.overlayOn || mid.overlayOn) {
    const deadline = Date.now() + (options.overlayCap || 30000);
    while (Date.now() < deadline && await overlayOn()) await page.waitForTimeout(100);
    await page.waitForTimeout(120);
    post = await probe(page);
    await shot('post');
    await page.waitForTimeout(800);
    post2 = await probe(page);
    await shot('post2');
  }
  const settled = await settle(page, tracker, 1500, options.settleCap || 30000);
  await page.waitForTimeout(700);
  const final = await probe(page);
  await shot('final');
  return {
    url: page.url().replace(/^https?:\/\/[^/]+/, ''), settled, calls: tracker.seen.length,
    p500, first, mid, post, post2, final,
    firstVsFinal: compare(first, final), midVsFinal: compare(mid, final),
    postVsFinal: compare(post, final), post2VsFinal: compare(post2, final),
  };
}

module.exports = { delayApi, settle, probe, compare, isApiRequest, sweepScreen };
