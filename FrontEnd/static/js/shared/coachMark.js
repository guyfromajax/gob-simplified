/**
 * Coach-mark — spotlight tooltip anchored to a DOM element.
 *
 * Per spec: distinct from the three modal types. Sits on the page, leaves
 * the underlying screen visible and interactive, points at the thing it's
 * talking about.
 *
 *   import { showCoachMark } from '/js/shared/coachMark.js';
 *
 *   const handle = showCoachMark({
 *     anchor: document.getElementById('roster-table-container'),
 *     side: 'left',                    // which edge of anchor to attach to
 *     offset: 24,                      // gap between anchor and bubble
 *     eyebrow: 'QUICK TIP',
 *     body: "I've set a solid lineup for you. ...",
 *     dismissLabel: 'GOT IT',
 *     onDismiss: () => {},             // optional
 *     portraitSrc: '/images/...png',   // optional Sammy headshot
 *     count: 'Tip 1 of 1',             // optional micro-text
 *   });
 *
 * Returned handle: { close, element }.
 */

import { GENERIC_SAMMY_IMAGE } from '/js/shared/teamCoachAsset.js';

const STYLESHEET_HREF = '/css/coach-mark.css';
const GOB_BUTTONS_HREF = '/css/gob-buttons.css';

function ensureStylesheets() {
  [STYLESHEET_HREF, GOB_BUTTONS_HREF].forEach((href) => {
    if (document.querySelector(`link[href="${href}"]`)) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    document.head.appendChild(link);
  });
}

function positionRelativeTo(bubble, anchor, side, offset) {
  if (!anchor) {
    // Fall back to centered placement near the top — better than off-screen.
    bubble.style.top = '120px';
    bubble.style.left = '50%';
    bubble.style.transform = 'translateX(-50%)';
    return;
  }
  const r = anchor.getBoundingClientRect();
  const scrollX = window.scrollX || 0;
  const scrollY = window.scrollY || 0;
  // Use a sensible anchor point on the chosen side of the target element.
  let top;
  let left;
  switch (side) {
    case 'right':
      top = r.top + scrollY + 12;
      left = r.right + scrollX + offset;
      break;
    case 'top':
      top = r.top + scrollY - offset;
      left = r.left + scrollX + 24;
      break;
    case 'bottom':
      top = r.bottom + scrollY + offset;
      left = r.left + scrollX + 24;
      break;
    case 'left':
    default:
      top = r.top + scrollY + 12;
      left = r.left + scrollX - offset - 360; // 360 = bubble max width
      break;
  }
  // Clamp into the viewport so the bubble never lands off-screen.
  const maxLeft = window.innerWidth - 380;
  if (left < 12) left = 12;
  if (left > maxLeft) left = maxLeft;
  bubble.style.top = `${Math.max(12, top)}px`;
  bubble.style.left = `${left}px`;
}

export function showCoachMark(opts = {}) {
  if (!opts.body) throw new Error('showCoachMark: body is required');
  if (!opts.dismissLabel) throw new Error('showCoachMark: dismissLabel is required');

  ensureStylesheets();

  const side = ['left', 'right', 'top', 'bottom'].includes(opts.side) ? opts.side : 'left';
  const offset = typeof opts.offset === 'number' ? opts.offset : 24;
  const portrait = opts.portraitSrc || GENERIC_SAMMY_IMAGE;

  const bubble = document.createElement('div');
  bubble.className = `gob-coachmark gob-coachmark--${side}`;
  bubble.setAttribute('role', 'dialog');
  bubble.setAttribute('aria-live', 'polite');

  // Two-column row keeps the portrait fixed-width and the text block flowing
  // to its right. All body copy stays left-aligned, including lines that
  // would wrap below the portrait under the older float-based layout.
  const row = document.createElement('div');
  row.className = 'gob-coachmark__row';

  const portraitImg = document.createElement('img');
  portraitImg.className = 'gob-coachmark__portrait';
  portraitImg.src = portrait;
  portraitImg.alt = '';
  row.appendChild(portraitImg);

  const textBlock = document.createElement('div');
  textBlock.className = 'gob-coachmark__text';

  if (opts.eyebrow) {
    const eyebrow = document.createElement('div');
    eyebrow.className = 'gob-coachmark__eyebrow';
    eyebrow.textContent = opts.eyebrow;
    textBlock.appendChild(eyebrow);
  }

  const body = document.createElement('p');
  body.className = 'gob-coachmark__body';
  body.textContent = opts.body;
  textBlock.appendChild(body);

  row.appendChild(textBlock);
  bubble.appendChild(row);

  const foot = document.createElement('div');
  foot.className = 'gob-coachmark__foot';

  const count = document.createElement('span');
  count.className = 'gob-coachmark__count';
  count.textContent = opts.count || '';
  foot.appendChild(count);

  const dismissBtn = document.createElement('button');
  dismissBtn.type = 'button';
  dismissBtn.className = 'gob-btn gob-btn--ghost';
  dismissBtn.style.height = '34px';
  dismissBtn.style.minWidth = 'auto';
  dismissBtn.style.fontSize = '14px';
  dismissBtn.style.padding = '0 14px';
  dismissBtn.textContent = opts.dismissLabel;
  foot.appendChild(dismissBtn);

  bubble.appendChild(foot);
  document.body.appendChild(bubble);

  positionRelativeTo(bubble, opts.anchor, side, offset);

  // Reposition on resize / scroll so the bubble tracks its anchor.
  const reposition = () => positionRelativeTo(bubble, opts.anchor, side, offset);
  window.addEventListener('resize', reposition);
  window.addEventListener('scroll', reposition, true);

  requestAnimationFrame(() => bubble.classList.add('is-visible'));

  function close() {
    if (!bubble.parentNode) return;
    window.removeEventListener('resize', reposition);
    window.removeEventListener('scroll', reposition, true);
    bubble.classList.remove('is-visible');
    setTimeout(() => {
      if (bubble.parentNode) bubble.parentNode.removeChild(bubble);
    }, 220);
  }

  dismissBtn.addEventListener('click', () => {
    try {
      if (typeof opts.onDismiss === 'function') opts.onDismiss();
    } finally {
      close();
    }
  });

  return { close, element: bubble };
}
