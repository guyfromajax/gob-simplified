/**
 * Username Modal — FTE v2 design.
 *
 * Wraps showSammyModal() with username-specific config:
 *   - Validation: 3-24 chars, no spaces, [a-zA-Z0-9_] only
 *   - POST /api/auth/set-username
 *   - On success: update localStorage.auth_user, refresh auth-bar display, close
 *   - On failure: show inline error
 *
 * Replaces the inline username modal previously defined in authBarInit.js
 * (ensureUsernameModal + openUsernameModal). In PR 2b this is invoked by the
 * legacy FTE v1 entry path; in PR 2c it'll also be the username step of the
 * new tutorial funnel.
 *
 * Usage:
 *   import { openUsernameModal } from '/js/shared/usernameModal.js';
 *   openUsernameModal({ onSuccess: () => { ... } });
 */

import { showSammyModal } from '/js/shared/sammyModal.js';


const USERNAME_HINT = '3-24 characters. Letters, numbers, and underscores only — no spaces.';
const USERNAME_PROMPT = 'Choose a username, Coach.';


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
  } catch (_) {
    // Best-effort; ignore parse/storage failures.
  }
  const emailDisplay = document.getElementById('auth-user-email');
  if (emailDisplay) emailDisplay.textContent = username;
}


/**
 * Open the username modal.
 * @param {Object} opts
 * @param {Function} [opts.onSuccess]  - called after the username is persisted server-side
 * @returns {{ close: Function }}      - handle to dismiss the modal early if needed
 */
export function openUsernameModal(opts = {}) {
  const onSuccess = typeof opts.onSuccess === 'function' ? opts.onSuccess : null;

  const handle = showSammyModal({
    body: USERNAME_PROMPT,
    ctaLabel: 'Continue',
    dismissOnCta: false,  // we control dismissal — wait for API success
    input: {
      placeholder: 'Username',
      hint: USERNAME_HINT,
      validate: validateUsername,
    },
    onCta: async (username) => {
      const trimmed = (username || '').trim();

      // Fallback when API_CONFIG isn't loaded (e.g., on a public-only page) —
      // dismiss without making the request so the caller isn't stranded.
      if (typeof API_CONFIG === 'undefined' ||
          typeof API_CONFIG.buildUrl !== 'function' ||
          typeof API_CONFIG.getAuthHeaders !== 'function') {
        handle.close();
        if (onSuccess) onSuccess();
        return;
      }

      let res;
      let data;
      try {
        res = await fetch(API_CONFIG.buildUrl('/api/auth/set-username'), {
          method: 'POST',
          headers: Object.assign({ 'Content-Type': 'application/json' }, API_CONFIG.getAuthHeaders()),
          body: JSON.stringify({ username: trimmed }),
        });
        data = await res.json();
      } catch (_) {
        handle.setError('Something went wrong. Try again.');
        return;
      }

      if (!res.ok) {
        handle.setError((data && data.detail) || 'This username is already taken');
        return;
      }

      persistUsernameLocally(data.username);
      handle.close();
      if (onSuccess) onSuccess();
    },
  });

  return handle;
}
