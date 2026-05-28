/**
 * Sammy Modal — reusable modal component for the FTE v2 tutorial flow.
 *
 * Design baseline: standard post-game modal (gameCompletionPopup). Single
 * vertical column, dark chrome, Sammy headshot at top. Stylesheet:
 * /css/sammy-modal.css (auto-loaded if missing).
 *
 * Used by: username, situation card, set-lineup intro, tutorial post-game.
 *
 * Usage:
 *   import { showSammyModal } from '/js/shared/sammyModal.js';
 *
 *   const handle = showSammyModal({
 *     eyebrow: 'Your Debut',                   // optional uppercase chip
 *     body: 'Ok Coach, let\'s play ball...',   // string or HTMLElement
 *     ctaLabel: 'Set Lineup',                  // primary button
 *     onCta: () => { ... },                    // primary click handler
 *     secondaryLabel: null,                    // optional secondary button
 *     onSecondary: null,                       // optional secondary handler
 *     dismissOnCta: true,                      // close after onCta (default true)
 *     input: null,                             // optional input config (see below)
 *     imageSrc: '/images/sammy_tutorial.png',  // override Sammy image if needed
 *   });
 *
 *   // Input config (used by username modal in PR 2b):
 *   input: {
 *     placeholder: 'CoachJamie',
 *     hint: '3-24 characters. Letters, numbers, underscores.',
 *     initialValue: '',
 *     validate: (value) => null | 'error message',  // sync validator
 *   }
 *   // When `input` is provided, onCta receives the input value as its first arg.
 *
 *   // Returned handle:
 *   handle.close();          // dismiss the modal
 *   handle.setError(msg);    // show an error under the input (input mode only)
 *   handle.setBusy(bool);    // disable buttons + input (e.g., during async submit)
 */

const STYLESHEET_HREF = '/css/sammy-modal.css';
const DEFAULT_IMAGE_SRC = '/images/sammy_tutorial.png';

function ensureStylesheetLoaded() {
  const existing = document.querySelector(`link[href="${STYLESHEET_HREF}"]`);
  if (existing) return;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = STYLESHEET_HREF;
  document.head.appendChild(link);
}

function buildBodyNode(body) {
  if (body instanceof HTMLElement) return body;
  const p = document.createElement('p');
  p.textContent = String(body ?? '');
  return p;
}

/**
 * @param {Object} opts
 * @param {string} [opts.eyebrow]
 * @param {string|HTMLElement} opts.body
 * @param {string} opts.ctaLabel
 * @param {Function} opts.onCta            - signature: (inputValue?) => void | Promise
 * @param {string} [opts.secondaryLabel]
 * @param {Function} [opts.onSecondary]
 * @param {boolean} [opts.dismissOnCta=true]
 * @param {Object} [opts.input]            - { placeholder, hint, initialValue, validate }
 * @param {string} [opts.imageSrc]
 * @returns {{ close: Function, setError: Function, setBusy: Function, element: HTMLElement }}
 */
export function showSammyModal(opts) {
  if (!opts || typeof opts.ctaLabel !== 'string' || typeof opts.onCta !== 'function') {
    throw new Error('showSammyModal: ctaLabel (string) and onCta (function) are required');
  }

  ensureStylesheetLoaded();

  const backdrop = document.createElement('div');
  backdrop.className = 'sammy-modal-backdrop';
  backdrop.setAttribute('role', 'presentation');

  const modal = document.createElement('div');
  modal.className = 'sammy-modal';
  modal.setAttribute('role', 'dialog');
  modal.setAttribute('aria-modal', 'true');

  // Eyebrow (optional).
  if (opts.eyebrow) {
    const eyebrow = document.createElement('div');
    eyebrow.className = 'sammy-modal-eyebrow';
    eyebrow.textContent = opts.eyebrow;
    modal.appendChild(eyebrow);
  }

  // Sammy image.
  const img = document.createElement('img');
  img.className = 'sammy-modal-image';
  img.src = opts.imageSrc || DEFAULT_IMAGE_SRC;
  img.alt = '';
  modal.appendChild(img);

  // Body.
  const bodyWrap = document.createElement('div');
  bodyWrap.className = 'sammy-modal-body';
  bodyWrap.appendChild(buildBodyNode(opts.body));
  modal.appendChild(bodyWrap);

  // Optional input area.
  let inputEl = null;
  let errorEl = null;
  if (opts.input && typeof opts.input === 'object') {
    const wrap = document.createElement('div');
    wrap.className = 'sammy-modal-input-wrap';

    inputEl = document.createElement('input');
    inputEl.type = 'text';
    inputEl.className = 'sammy-modal-input';
    inputEl.placeholder = opts.input.placeholder || '';
    inputEl.value = opts.input.initialValue || '';
    inputEl.autocomplete = 'off';
    wrap.appendChild(inputEl);

    if (opts.input.hint) {
      const hint = document.createElement('p');
      hint.className = 'sammy-modal-hint';
      hint.textContent = opts.input.hint;
      wrap.appendChild(hint);
    }

    errorEl = document.createElement('p');
    errorEl.className = 'sammy-modal-error';
    errorEl.textContent = '';
    wrap.appendChild(errorEl);

    modal.appendChild(wrap);
  }

  // Actions row.
  const actions = document.createElement('div');
  actions.className = 'sammy-modal-actions';

  let secondaryBtn = null;
  if (opts.secondaryLabel && typeof opts.onSecondary === 'function') {
    secondaryBtn = document.createElement('button');
    secondaryBtn.type = 'button';
    secondaryBtn.className = 'sammy-modal-btn sammy-modal-btn-secondary';
    secondaryBtn.textContent = opts.secondaryLabel;
    actions.appendChild(secondaryBtn);
  }

  const primaryBtn = document.createElement('button');
  primaryBtn.type = 'button';
  primaryBtn.className = 'sammy-modal-btn sammy-modal-btn-primary';
  primaryBtn.textContent = opts.ctaLabel;
  actions.appendChild(primaryBtn);

  modal.appendChild(actions);
  backdrop.appendChild(modal);
  document.body.appendChild(backdrop);

  // Force reflow so the entrance animation runs.
  // eslint-disable-next-line no-unused-expressions
  backdrop.offsetHeight;
  backdrop.classList.add('open');

  const dismissOnCta = opts.dismissOnCta !== false;

  function close() {
    if (!backdrop.parentNode) return;
    backdrop.parentNode.removeChild(backdrop);
  }

  function setError(msg) {
    if (!errorEl) return;
    errorEl.textContent = msg || '';
  }

  function setBusy(busy) {
    primaryBtn.disabled = !!busy;
    if (secondaryBtn) secondaryBtn.disabled = !!busy;
    if (inputEl) inputEl.disabled = !!busy;
  }

  async function handlePrimary() {
    let value;
    if (inputEl) {
      value = inputEl.value.trim();
      if (opts.input?.validate) {
        const err = opts.input.validate(value);
        if (err) {
          setError(err);
          inputEl.focus();
          return;
        }
      }
      setError('');
    }
    try {
      setBusy(true);
      await opts.onCta(value);
      if (dismissOnCta) close();
    } catch (e) {
      // onCta may set its own error message via the returned handle.
      // Re-throw so the caller can log if desired.
      throw e;
    } finally {
      setBusy(false);
    }
  }

  primaryBtn.addEventListener('click', () => {
    // Don't await — let promise rejections surface as unhandled if the caller
    // doesn't handle them. setBusy/finally still runs in handlePrimary.
    handlePrimary().catch((e) => console.error('[sammyModal] onCta threw:', e));
  });

  if (secondaryBtn) {
    secondaryBtn.addEventListener('click', () => {
      try {
        opts.onSecondary();
      } finally {
        if (dismissOnCta) close();
      }
    });
  }

  // Enter key submits primary action when an input is present.
  if (inputEl) {
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        primaryBtn.click();
      }
    });
    // Autofocus the input on next tick.
    setTimeout(() => inputEl.focus(), 0);
  }

  return {
    close,
    setError,
    setBusy,
    element: modal,
  };
}
