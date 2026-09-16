/**
 * Stylesheet readiness — show UI only once the CSS that sizes it has applied.
 *
 * Why this exists: modules that inject their own stylesheet and then append their
 * DOM in the same tick paint UNSTYLED until the CSS request returns. Netlify serves
 * CSS with `max-age=0, must-revalidate`, so that is a network round trip on every
 * page load. Symptom: a 3000px Sammy portrait rendered at natural size inside a
 * 420px clipped modal box — an "extreme close-up" for ~1s.
 *
 * Contract:
 *   - Already applied (`link.sheet` present) → resolves immediately.
 *   - Otherwise resolves on `load`, on `error`, or after STYLESHEET_WAIT_MAX_MS,
 *     whichever comes first. It NEVER rejects: a failed or slow stylesheet
 *     degrades to the old flash, it never blocks the UI (or the FTE funnel).
 *
 * authBarInit.js (a classic script, cannot import) carries an inline copy of
 * this logic — keep the two in step.
 */

export const STYLESHEET_WAIT_MAX_MS = 2000;

const pending = new Map();

function isApplied(link) {
  try {
    return !!link.sheet;
  } catch (_) {
    return false;
  }
}

export function loadStylesheet(href) {
  let link = document.querySelector(`link[rel="stylesheet"][href="${href}"]`);
  if (link && isApplied(link)) return Promise.resolve();
  // Kept after resolving: a stylesheet that errored never gains `.sheet`, and it
  // must not cost every later caller another full wait.
  if (pending.has(href)) return pending.get(href);

  if (!link) {
    link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    document.head.appendChild(link);
  }

  const ready = new Promise((resolve) => {
    let timer = null;
    const done = () => {
      clearTimeout(timer);
      resolve();
    };
    timer = setTimeout(done, STYLESHEET_WAIT_MAX_MS);
    link.addEventListener('load', done, { once: true });
    link.addEventListener('error', done, { once: true });
  });
  pending.set(href, ready);
  return ready;
}

export function loadStylesheets(hrefs) {
  return Promise.all(hrefs.map(loadStylesheet));
}
