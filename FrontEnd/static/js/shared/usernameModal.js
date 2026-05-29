/**
 * Username Modal — FTE v2 onboarding redesign.
 *
 * Implemented as the canonical Functional modal (`gob-modal-*` chrome,
 * 3px orange accent bar, Bebas Neue Pro title, Inter subtitle). Team-linked
 * Sammy portrait overlaps the top edge of the modal so the persona stays
 * warm without breaking the system box.
 *
 * Primary CTA is the canonical `.gob-btn--action` (orange) — per the
 * styleguide's Action Color rules, naming yourself is a non-gating action
 * (configures a preference; doesn't advance game state). Previously this
 * button was green, which was incorrect.
 *
 * Usage:
 *   import { openUsernameModal } from '/js/shared/usernameModal.js';
 *
 *   openUsernameModal({
 *     teamName: 'Bentley-Truman',           // optional — drives Sammy portrait
 *     mascot: 'Sterling Knights',           // optional — drives title
 *     onSuccess: () => navigate(...),
 *   });
 *
 * Legacy `prompt` field is no longer used (the new design swaps the
 * sentence-prompt for a structured Title + Subtitle). Callers that still
 * pass `prompt` are silently ignored — they'll get the default subtitle.
 */

import { getTeamSammyImage } from '/js/shared/teamCoachAsset.js';
import { mountTutorialProgress } from '/js/shared/tutorialProgressThread.js';

const USERNAME_HINT = '3–24 characters · letters, numbers, underscores';
const DEFAULT_SUBTITLE = "Every coach in GOB needs a username. What should the league call you?";
const STYLESHEET_HREFS = [
  // Canonical `.gob-modal-*` classes used by every Functional modal.
  '/resource-pages.css',
  '/css/gob-buttons.css',
  '/css/username-modal.css',
];


function validateUsername(value) {
  const v = (value || '').trim();
  if (v.length < 3) return 'Username must be at least 3 characters';
  if (v.length > 24) return 'Username must be at most 24 characters';
  if (/\s/.test(v)) return 'No spaces allowed';
  if (!/^[a-zA-Z0-9_]+$/.test(v)) return 'Only letters, numbers, and underscores';
  return null;
}


function persistUsernameLocally(username) {
  try {
    const raw = localStorage.getItem('auth_user');
    if (raw) {
      const user = JSON.parse(raw);
      user.username = username;
      localStorage.setItem('auth_user', JSON.stringify(user));
    }
  } catch (_) { /* best-effort */ }
  const emailDisplay = document.getElementById('auth-user-email');
  if (emailDisplay) emailDisplay.textContent = username;
}


function ensureStylesheets() {
  STYLESHEET_HREFS.forEach((href) => {
    if (document.querySelector(`link[href="${href}"]`)) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    document.head.appendChild(link);
  });
}


/**
 * @param {Object} opts
 * @param {string}   [opts.teamName]   — drives Sammy portrait variant
 * @param {string}   [opts.mascot]     — drives title ("YOU'RE COACHING THE …")
 * @param {Function} [opts.onSuccess]  — called after username is persisted server-side
 * @returns {{ close: Function }}
 */
export function openUsernameModal(opts = {}) {
  const onSuccess = typeof opts.onSuccess === 'function' ? opts.onSuccess : null;
  const mascotText = (opts.mascot || '').trim();
  const titleText = mascotText
    ? `YOU'RE COACHING THE ${mascotText.toUpperCase()}`
    : 'CHOOSE A USERNAME';
  const sammySrc = getTeamSammyImage(opts.teamName);

  ensureStylesheets();
  // Username step of the funnel — quiet progress thread updates.
  try { mountTutorialProgress('username'); } catch (_) { /* non-fatal */ }

  const overlay = document.createElement('div');
  overlay.className = 'gob-modal-overlay';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');

  overlay.innerHTML = `
    <div class="gob-modal-backdrop"></div>
    <div class="gob-modal-box username-modal-box">
      <div class="username-modal-portrait-wrap" aria-hidden="true">
        <img class="username-modal-portrait" src="${sammySrc}" alt="">
      </div>
      <div class="gob-modal-accent"></div>
      <div class="gob-modal-body username-modal-body">
        <div class="gob-modal-title">${titleText}</div>
        <p class="gob-modal-subtitle">${DEFAULT_SUBTITLE}</p>
        <div class="username-modal-field-wrap">
          <input
            type="text"
            class="username-modal-input"
            id="username-modal-input"
            placeholder="Username"
            autocomplete="off"
            spellcheck="false"
            maxlength="24"
            aria-label="Username"
          >
          <p class="username-modal-hint">${USERNAME_HINT}</p>
          <p class="username-modal-error" id="username-modal-error" aria-live="polite"></p>
        </div>
      </div>
      <div class="gob-modal-actions username-modal-actions">
        <button type="button" class="gob-btn gob-btn--action username-modal-cta" id="username-modal-cta">CONTINUE</button>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);
  // Force reflow so the .is-visible transition runs.
  // eslint-disable-next-line no-unused-expressions
  overlay.offsetHeight;
  overlay.classList.add('is-visible');

  const inputEl = overlay.querySelector('#username-modal-input');
  const errorEl = overlay.querySelector('#username-modal-error');
  const ctaBtn = overlay.querySelector('#username-modal-cta');

  function setError(msg) {
    if (errorEl) errorEl.textContent = msg || '';
  }

  function setBusy(busy) {
    if (ctaBtn) ctaBtn.disabled = !!busy;
    if (inputEl) inputEl.disabled = !!busy;
  }

  function close() {
    if (!overlay.parentNode) return;
    overlay.classList.remove('is-visible');
    setTimeout(() => {
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    }, 180);
  }

  async function submit() {
    const value = (inputEl?.value || '').trim();
    const err = validateUsername(value);
    if (err) {
      setError(err);
      inputEl?.focus();
      return;
    }
    setError('');

    // Public-only fallback — if API isn't loaded, just succeed locally.
    if (typeof API_CONFIG === 'undefined' ||
        typeof API_CONFIG.buildUrl !== 'function' ||
        typeof API_CONFIG.getAuthHeaders !== 'function') {
      close();
      if (onSuccess) onSuccess();
      return;
    }

    setBusy(true);
    let res;
    let data;
    try {
      res = await fetch(API_CONFIG.buildUrl('/api/auth/set-username'), {
        method: 'POST',
        headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: value }),
      });
      data = await res.json().catch(() => ({}));
    } catch (_) {
      setBusy(false);
      setError('Something went wrong. Try again.');
      return;
    }

    if (!res.ok) {
      setBusy(false);
      setError((data && data.detail) || 'This username is already taken');
      return;
    }

    persistUsernameLocally(data.username);
    close();
    if (onSuccess) onSuccess();
  }

  if (ctaBtn) ctaBtn.addEventListener('click', submit);
  if (inputEl) {
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        submit();
      }
    });
    setTimeout(() => inputEl.focus(), 0);
  }

  return { close };
}
