/**
 * Alpha feedback prompt — post-game Moment modal on the Franchise Command Center.
 *
 * Fires when an unsubmitted coach returns to the FCC after their 2nd non-tutorial
 * game (and once more after the 5th, copy swapped to "five games"). Gating reads
 * three /api/auth/me fields:
 *   - alpha_feedback_submitted  → true ends all prompts forever.
 *   - alpha_feedback_games      → FORWARD-ONLY count of games since launch (2 / 5 thresholds).
 *   - alpha_feedback_prompt_level→ highest threshold already shown (0 / 2 / 5).
 * On show we PATCH the prompt level (via $max) so each variant fires exactly once.
 * Dismissing (button / ✕ / backdrop) never marks feedback given — only a real
 * survey submission flips alpha_feedback_submitted (in /api/alpha-feedback).
 *
 * Mirrors archetypeReveal.js. Styling per Styleguide §Moment Modals; the primary
 * CTA uses the nav Feedback button's violet.
 */
(function () {
  'use strict';

  var shown = false;

  function injectStyles() {
    if (document.getElementById('afm-styles')) return;
    var css = [
      // Backdrop + the Command Center dim/blur behind (spec §4a chrome).
      '.afm-overlay{position:fixed;inset:0;z-index:10050;display:none;align-items:center;justify-content:center;}',
      '.afm-overlay.is-visible{display:flex;}',
      '.afm-backdrop{position:absolute;inset:0;background:rgba(6,8,12,0.72);backdrop-filter:blur(4px);opacity:0;transition:opacity 220ms ease;}',
      '.afm-overlay.is-entered .afm-backdrop{opacity:1;}',
      '#franchise-container.afm-dimmed{filter:blur(3px) brightness(0.6);transition:filter 220ms ease;}',
      // Dialog container.
      '.afm-box{position:relative;z-index:1;width:min(440px,calc(100vw - 48px));overflow:hidden;',
      'background:rgba(17,20,28,0.98);border:1px solid rgba(255,255,255,0.12);border-radius:18px;',
      'padding:28px 28px 24px;text-align:left;',
      'box-shadow:0 28px 70px rgba(0,0,0,0.6),inset 0 1px 0 rgba(255,255,255,0.06);',
      'transform:translateY(8px) scale(0.96);opacity:0;transition:transform 260ms cubic-bezier(0.22,1,0.36,1),opacity 260ms ease;}',
      '.afm-overlay.is-entered .afm-box{transform:translateY(0) scale(1);opacity:1;}',
      // Purple accent strip across the very top.
      '.afm-strip{position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#8B5CF6 0%,#A78BFA 60%,transparent 100%);}',
      '.afm-close{position:absolute;top:14px;right:14px;width:30px;height:30px;border:none;border-radius:8px;',
      'background:transparent;color:rgba(255,255,255,0.35);font-size:18px;cursor:pointer;line-height:1;}',
      '.afm-close:hover{color:#fff;background:rgba(255,255,255,0.06);}',
      // Rounded-square chat-bubble mark.
      '.afm-mark{width:46px;height:46px;border-radius:12px;display:flex;align-items:center;justify-content:center;',
      'background:rgba(139,92,246,0.16);border:1px solid rgba(139,92,246,0.4);margin:6px 0 16px;}',
      '.afm-mark svg{width:22px;height:22px;color:#A78BFA;}',
      '.afm-eyebrow{font-family:\'Inter\',sans-serif;font-size:11px;font-weight:700;letter-spacing:0.16em;',
      'text-transform:uppercase;color:#A78BFA;margin:0 0 8px;}',
      '.afm-headline{font-family:\'Bebas Neue Pro\',\'Bebas Neue\',sans-serif;font-weight:700;font-size:30px;',
      'letter-spacing:0.03em;color:#fff;margin:0 0 10px;}',
      '.afm-body{font-family:\'Inter\',sans-serif;font-size:14px;line-height:1.55;color:rgba(255,255,255,0.55);margin:0 0 22px;}',
      '.afm-actions{display:flex;gap:10px;}',
      '.afm-btn-primary,.afm-btn-secondary{appearance:none;height:46px;border-radius:10px;',
      'font-family:\'Bebas Neue Pro\',\'Bebas Neue\',sans-serif;font-size:17px;letter-spacing:0.04em;cursor:pointer;',
      'display:inline-flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;transition:background .14s ease;}',
      '.afm-btn-primary{flex:1.2;background:#7C3AED;border:1px solid rgba(167,139,250,0.55);color:#fff;',
      'box-shadow:0 8px 22px rgba(124,58,237,0.35);}',
      '.afm-btn-primary:hover{background:#8B5CF6;}',
      '.afm-btn-primary svg{width:17px;height:17px;}',
      '.afm-btn-secondary{flex:1;background:transparent;border:1px solid rgba(255,255,255,0.18);color:rgba(255,255,255,0.7);}',
      '.afm-btn-secondary:hover{background:rgba(255,255,255,0.06);color:#fff;}',
      '@media (prefers-reduced-motion: reduce){.afm-box,.afm-backdrop,#franchise-container.afm-dimmed{transition:none;}}',
    ].join('');
    var style = document.createElement('style');
    style.id = 'afm-styles';
    style.textContent = css;
    document.head.appendChild(style);
  }

  function markPromptSeen(level) {
    try {
      if (window.__gobAuthMeData) window.__gobAuthMeData.alpha_feedback_prompt_level = level;
      if (typeof API_CONFIG === 'undefined' || !API_CONFIG.buildUrl || !API_CONFIG.getAuthHeaders) return;
      fetch(API_CONFIG.buildUrl('/api/auth/alpha-feedback-prompt-seen'), {
        method: 'PATCH',
        headers: Object.assign({ 'Content-Type': 'application/json' }, API_CONFIG.getAuthHeaders()),
        body: JSON.stringify({ level: level }),
      }).catch(function () {});
    } catch (e) {}
  }

  function buildModal(bodyText) {
    injectStyles();
    var overlay = document.createElement('div');
    overlay.className = 'afm-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Share your feedback');

    var chatSvg = '<svg viewBox="0 0 24 24" fill="none"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    overlay.innerHTML = [
      '<div class="afm-backdrop" data-dismiss></div>',
      '<div class="afm-box">',
      '  <div class="afm-strip" aria-hidden="true"></div>',
      '  <button type="button" class="afm-close" data-dismiss aria-label="Close">&times;</button>',
      '  <div class="afm-mark" aria-hidden="true">' + chatSvg + '</div>',
      '  <div class="afm-eyebrow">We&rsquo;re Listening</div>',
      '  <h2 class="afm-headline">Help Us Make GOB Better</h2>',
      '  <p class="afm-body"></p>',
      '  <div class="afm-actions">',
      '    <a class="afm-btn-primary" href="/alpha-feedback.html">' + chatSvg + 'Feedback</a>',
      '    <button type="button" class="afm-btn-secondary" data-dismiss>Go to Locker Room</button>',
      '  </div>',
      '</div>'
    ].join('');

    overlay.querySelector('.afm-body').textContent = bodyText;

    var dimTarget = document.getElementById('franchise-container');
    if (dimTarget) dimTarget.classList.add('afm-dimmed');

    function close() {
      overlay.classList.remove('is-entered');
      if (dimTarget) dimTarget.classList.remove('afm-dimmed');
      setTimeout(function () { if (overlay.parentNode) overlay.parentNode.removeChild(overlay); }, 220);
    }
    overlay.addEventListener('click', function (e) {
      if (e.target && e.target.hasAttribute('data-dismiss')) {
        // Primary link navigates on its own; secondary / close / backdrop dismiss.
        if (e.target.classList.contains('afm-btn-secondary')
            || e.target.classList.contains('afm-close')
            || e.target.classList.contains('afm-backdrop')) {
          e.preventDefault();
          close();
        }
      }
    });
    document.addEventListener('keydown', function onEsc(e) {
      if (e.key === 'Escape') { document.removeEventListener('keydown', onEsc); close(); }
    });

    document.body.appendChild(overlay);
    overlay.classList.add('is-visible');
    void overlay.offsetWidth;
    overlay.classList.add('is-entered');
  }

  function maybeShow(me) {
    if (shown || !me) return;
    if (me.alpha_feedback_submitted) return;
    // Never stack on the one-time first-archetype reveal. If that's still pending
    // (seen === false → it will fire this visit since ≥2 games means a lead exists),
    // yield this visit; we'll prompt on the next FCC load once it's been seen.
    if (me.archetype_reveal_seen === false) return;
    var games = parseInt(me.alpha_feedback_games, 10) || 0;
    var level = parseInt(me.alpha_feedback_prompt_level, 10) || 0;

    var targetLevel, body;
    if (games >= 5 && level < 5) {
      targetLevel = 5;
      body = "Now that you've played five games, we'd love to get your feedback to make the game better.";
    } else if (games >= 2 && level < 2) {
      targetLevel = 2;
      body = "Now that you've played a couple of games, we'd love to get your feedback to make the game better.";
    } else {
      return;
    }

    shown = true;
    markPromptSeen(targetLevel); // persist immediately, however it's dismissed
    buildModal(body);
  }

  // Only on the Franchise Command Center.
  if ((window.location.pathname || '').indexOf('franchise-command-center') === -1) return;

  if (window.__gobAuthMeData) maybeShow(window.__gobAuthMeData);
  window.addEventListener('gob:auth-me-loaded', function (e) {
    maybeShow((e && e.detail) || window.__gobAuthMeData);
  });
})();
