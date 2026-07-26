/**
 * Auth Bar Init - Shared top nav: logo (left) | Alpha badge (center) | YouTube, X, account (right).
 *
 * Shows on all screens EXCEPT gameplay (court, set-lineup) and training screens.
 *
 * - Injects auth bar HTML if not present
 * - Loads auth-bar.css
 * - Initializes auth state (email, logout)
 * - Alpha badge visibility via AlphaBanner or app config
 */
(function () {
  'use strict';

  var authMeDataCache = null;
  var musicControllerPromise = null;

  var PAGES_WITHOUT_AUTH_BAR = [
    // Gameplay / lineup
    'court.html',
    'set-lineup.html',
    // Training
    'training.html',
    'training-report.html',
    // Requested removals
    'box-score.html',
    'game-plan.html',
    'playbooks.html',
    // Plays screens
    'plays-builder.html',
    'play-builder.html',
    'play-builder-v2.html',
    'play-details.html',
    // FTE v2 tutorial funnel — immersive screens, no auth bar
    'tutorial-persona-intro.html',
    'tutorial-situation.html',
    // Optional non-.html route variants
    '/box-score',
    '/game-plan',
    '/playbooks',
    '/plays-builder',
    '/play-builder',
    '/play-builder-v2',
    '/play-details'
  ];

  function shouldShowAuthBar() {
    var path = window.location.pathname || '';
    if (PAGES_WITHOUT_AUTH_BAR.some(function (p) { return path.indexOf(p) !== -1; })) {
      return false;
    }
    // FTE v2: any page loaded with ?mode=tutorial is part of the immersive
    // onboarding funnel — suppress the auth bar across the whole flow
    // (team-select most notably; situation + set-lineup are already in
    // PAGES_WITHOUT_AUTH_BAR above).
    try {
      var urlMode = new URLSearchParams(window.location.search).get('mode');
      if (urlMode === 'tutorial') return false;
    } catch (_) {}
    return true;
  }

  function ensureAuthBarStyles() {
    if (document.getElementById('auth-bar-styles-link')) return;
    if (document.querySelector('link[href*="auth-bar.css"]')) return;
    var link = document.createElement('link');
    link.id = 'auth-bar-styles-link';
    link.rel = 'stylesheet';
    link.href = '/css/auth-bar.css';
    document.head.appendChild(link);
  }

  function getLogoDestination(isLoggedIn) {
    return isLoggedIn ? '/mode-select.html' : '/homepage.html';
  }

  function updateLogoDestination(isLoggedIn) {
    document.querySelectorAll('.logo-link').forEach(function (link) {
      link.setAttribute('href', getLogoDestination(isLoggedIn));
    });
  }

  function hasStoredAuthCredentials() {
    try {
      return !!(typeof localStorage !== 'undefined' && localStorage.getItem('auth_token') && localStorage.getItem('auth_user'));
    } catch (e) {
      return false;
    }
  }

  function loadScriptOnce(src) {
    return new Promise(function (resolve, reject) {
      if (document.querySelector('script[src="' + src + '"]')) {
        resolve();
        return;
      }
      var s = document.createElement('script');
      s.src = src;
      s.onload = function () { resolve(); };
      s.onerror = reject;
      document.body.appendChild(s);
    });
  }

  function ensureTutorialAlertExperience() {
    if (!document.getElementById('gob-tutorial-styles-link') && !document.querySelector('link[href*="gob-tutorial.css"]')) {
      var css = document.createElement('link');
      css.id = 'gob-tutorial-styles-link';
      css.rel = 'stylesheet';
      css.href = '/css/gob-tutorial.css';
      document.head.appendChild(css);
    }
    if (window.GOBTutorialAlerts) return Promise.resolve();
    var chain = window.GOB ? Promise.resolve() : loadScriptOnce('/js/shared/gobTutorialNav.js');
    return chain.then(function () {
      return loadScriptOnce('/js/shared/gobTutorialAlerts.js');
    }).catch(function (err) {
      console.warn('[authBarInit] tutorial alerts scripts failed to load', err);
    });
  }

  // FTE v2 replaces the old 4-modal welcome flow with a playable tutorial
  // game. The auth-bar entry decision now routes new users to the funnel
  // (franchise-select-team?mode=tutorial → username → tutorial-situation →
  // set-lineup?mode=tutorial → court?mode=tutorial). Grandfathered users
  // (fte_v2_complete=true) hit no routing at all.
  //
  // Username modal lives in /js/shared/usernameModal.js (FTE v2 chrome).
  // Loaded on demand via dynamic import — see openUsernameModal() below.

  // Account Settings — a Functional Modal (per Styleguide §Modal System).
  // Reuses the shared `.gob-modal-overlay/backdrop/box/accent/body` classes;
  // only the username/toggle/link rows add field-level CSS (see auth-bar.css).
  function ensureAccountSettingsModal() {
    if (document.getElementById('account-settings-overlay')) return;
    var overlay = document.createElement('div');
    overlay.id = 'account-settings-overlay';
    overlay.className = 'gob-modal-overlay account-modal-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-labelledby', 'account-settings-title');
    overlay.innerHTML = [
      '<div class="gob-modal-backdrop" data-account-dismiss></div>',
      '<div class="gob-modal-box account-modal-box">',
      // Orange accent — Account Settings is a non-gating settings surface.
      '  <div class="gob-modal-accent"></div>',
      '  <div class="account-modal-header">',
      '    <h3 id="account-settings-title" class="gob-modal-title">Username</h3>',
      '    <button type="button" id="account-settings-close" class="account-modal-close" aria-label="Close account settings">',
      '      <svg viewBox="0 0 16 16" width="16" height="16" fill="none" aria-hidden="true">',
      '        <path d="M3.5 3.5 L12.5 12.5 M12.5 3.5 L3.5 12.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
      '      </svg>',
      '    </button>',
      '  </div>',
      '  <div class="gob-modal-body account-modal-body">',
      // Field 1 — Username (display-only, intentionally locked)
      '    <div class="account-field account-field--first">',
      '      <div class="account-identity">',
      '        <div id="account-avatar" class="account-avatar" aria-hidden="true"></div>',
      '        <div class="account-identity-text">',
      '          <div class="account-username-row">',
      '            <span id="account-settings-username" class="account-username">-</span>',
      '            <span id="account-settings-badge" class="account-username-badge"></span>',
      '          </div>',
      '        </div>',
      '        <span class="account-locked">',
      '          <svg viewBox="0 0 12 12" width="12" height="12" fill="none" aria-hidden="true">',
      '            <rect x="2.25" y="5.25" width="7.5" height="5.25" rx="1" stroke="currentColor" stroke-width="1.1"/>',
      '            <path d="M4 5.25 V3.75 a2 2 0 0 1 4 0 V5.25" stroke="currentColor" stroke-width="1.1"/>',
      '          </svg>',
      '          LOCKED',
      '        </span>',
      '      </div>',
      '    </div>',
      // Field 2 — Scouting Ambience (instant-apply sliding switch)
      '    <div class="account-field account-toggle-row">',
      '      <div class="account-field-label">Scouting Ambience</div>',
      '      <button type="button" id="account-ambience-switch" class="account-switch" role="switch" aria-checked="true" aria-label="Scouting ambience">',
      '        <span class="account-switch-knob" aria-hidden="true"></span>',
      '      </button>',
      '    </div>',
      // Forward link to the full account page.
      '    <div class="account-field account-manage-row">',
      '      <a href="/account.html" id="account-manage-link" class="account-manage-link">Account Details<span class="account-manage-arrow" aria-hidden="true">&rarr;</span></a>',
      '    </div>',
      '  </div>',
      '</div>'
    ].join('');
    document.body.appendChild(overlay);
  }

  // Username modal: delegated to /js/shared/usernameModal.js (FTE v2 chrome).
  // Loaded on demand so this classic script doesn't need to be a module.
  // Signature preserved (positional `onSuccess` callback) so existing callers
  // continue to work unchanged.
  function openUsernameModal(onSuccess) {
    import('/js/shared/usernameModal.js')
      .then(function (mod) {
        mod.openUsernameModal({ onSuccess: onSuccess });
      })
      .catch(function (e) {
        console.error('[authBarInit] Failed to load usernameModal.js:', e);
      });
  }

  // FTE v2 entry decision. Called from initAuthState() once /api/auth/me
  // returns. Routes users whose fte_v2_complete is explicitly false to the
  // appropriate page in the tutorial funnel. Users whose flag is true (or
  // unknown — pre-migration) are left alone.
  //
  // Step → page mapping (per fte_implementation_plan.md §5.1):
  //   team_select / username → /franchise-select-team.html?mode=tutorial
  //   situation              → /tutorial-situation.html
  //   set_lineup / in_game   → /set-lineup.html?mode=tutorial&home=...&away=...
  //
  // in_game resumes at set-lineup per Coach Q4(iii): only pre-game steps
  // resume; if the engine ever started, the game restarts from tip.
  function routeToTutorial(meData) {
    if (!meData || meData.fte_v2_complete !== false) return;
    var state = (meData && meData.tutorial_state) || { step: 'persona_intro', team_pick: null };
    var step = state.step || 'persona_intro';
    var teamPick = state.team_pick;

    var PERSONA_INTRO_URL = '/tutorial-persona-intro.html';
    var TEAM_SELECT_URL = '/franchise-select-team.html?mode=tutorial';
    var SITUATION_URL = '/tutorial-situation.html';
    var currentPath = window.location.pathname;

    // FTE v2 tutorial "shoulder pages" — entered from the tutorial funnel but
    // not themselves a step. Treat as in-scope when ?mode=tutorial is set so
    // the user isn't bounced back to their current step (e.g. Scout opens
    // team-roster-view from team-select; we must let them stay there).
    var TUTORIAL_SHOULDER_PAGES = ['/team-roster-view.html'];
    var urlMode = new URLSearchParams(window.location.search).get('mode');
    if (urlMode === 'tutorial' && TUTORIAL_SHOULDER_PAGES.indexOf(currentPath) !== -1) return;

    var targetPath;
    var targetUrl;
    if (step === 'persona_intro') {
      targetPath = '/tutorial-persona-intro.html';
      targetUrl = PERSONA_INTRO_URL;
    } else if (step === 'team_select' || step === 'username') {
      targetPath = '/franchise-select-team.html';
      targetUrl = TEAM_SELECT_URL;
    } else if (step === 'situation') {
      targetPath = '/tutorial-situation.html';
      targetUrl = SITUATION_URL;
    } else if (step === 'set_lineup' || step === 'in_game') {
      if (!teamPick) {
        targetPath = '/franchise-select-team.html';
        targetUrl = TEAM_SELECT_URL;
      } else {
        targetPath = '/set-lineup.html';
        var opp = teamPick === 'Xavien' ? 'South Lancaster' : 'Xavien';
        var params = new URLSearchParams({
          mode: 'tutorial',
          home: teamPick,
          away: opp,
          my_team: 'home'
        });
        targetUrl = '/set-lineup.html?' + params.toString();
      }
    } else {
      // 'complete' (or unknown) — should not happen when flag is false, but
      // be defensive: send to mode-select so the user isn't stranded.
      return;
    }

    if (currentPath === targetPath) return;
    window.location.replace(targetUrl);
  }

  function createAuthBarHTML() {
    var bar = document.createElement('div');
    bar.id = 'auth-bar';
    bar.className = 'auth-bar';
    bar.innerHTML = [
      '<div class="auth-bar-left">',
      '  <a href="/homepage.html" class="logo-link"><img src="/images/geekedout_logo.png" alt="Geeked-Out Basketball logo" class="logo"></a>',
      '  <a href="/tutorial.html" class="nav-tutorials-link" aria-label="Tutorials">',
      '    <svg class="nav-tutorials-icon" width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">',
      '      <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.25"/>',
      '      <path d="M5.6 4.8 L9.4 7 L5.6 9.2 Z" fill="currentColor"/>',
      '    </svg>',
      '    <span class="nav-tutorials-label">Tutorials</span>',
      '  </a>',
      '</div>',
      '<img id="alpha-badge" class="alpha-badge visible" src="/images/alpha_badge_gold.png" alt="Alpha">',
      '<div class="auth-bar-right">',
      '  <button type="button" id="feedback-btn" class="feedback-btn"><span class="feedback-pulse" aria-hidden="true"></span>Send feedback</button>',
      '  <a href="https://www.youtube.com/@geeked-outbasketball765" target="_blank" rel="noopener noreferrer" class="nav-icon nav-icon-yt" aria-label="GOB on YouTube">',
      '    <img src="/images/yt_icon_red_digital.png" alt="" width="24" height="24">',
      '  </a>',
      '  <a href="https://x.com/geekedoutbball" target="_blank" rel="noopener noreferrer" class="nav-icon" aria-label="GOB on X">',
      '    <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z"/></svg>',
      '  </a>',
      '  <div id="auth-logged-out" class="auth-status">',
      '    <a href="/login.html" class="auth-link">Log In</a>',
      '    <span class="auth-divider">|</span>',
      '    <a href="/signup.html" class="auth-link">Sign Up</a>',
      '  </div>',
      '  <div id="auth-logged-in" class="auth-status" style="display: none;">',
      '    <button type="button" id="auth-settings-btn" class="auth-settings-btn" aria-label="Account settings" title="Account settings">',
      '      <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M19.14 12.94c.04-.31.06-.63.06-.94s-.02-.63-.06-.94l2.03-1.58a.5.5 0 0 0 .12-.64l-1.92-3.32a.5.5 0 0 0-.6-.22l-2.39.96a7.03 7.03 0 0 0-1.63-.94l-.36-2.54A.5.5 0 0 0 13.9 2h-3.8a.5.5 0 0 0-.49.42l-.36 2.54c-.58.22-1.13.53-1.63.94l-2.39-.96a.5.5 0 0 0-.6.22L2.71 8.48a.5.5 0 0 0 .12.64l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58a.5.5 0 0 0-.12.64l1.92 3.32c.13.22.39.31.6.22l2.39-.96c.5.41 1.05.72 1.63.94l.36 2.54c.04.24.25.42.49.42h3.8c.24 0 .45-.18.49-.42l.36-2.54c.58-.22 1.13-.53 1.63-.94l2.39.96c.22.09.47 0 .6-.22l1.92-3.32a.5.5 0 0 0-.12-.64l-2.03-1.58ZM12 15.5A3.5 3.5 0 1 1 12 8.5a3.5 3.5 0 0 1 0 7Z"/></svg>',
      '    </button>',
      '    <button type="button" id="logout-btn" class="auth-logout-btn">Log Out</button>',
      '  </div>',
      '</div>'
    ].join('');
    return bar;
  }

  function ensureFeedbackButton() {
    var right = document.querySelector('#auth-bar .auth-bar-right');
    if (!right) return;
    if (document.getElementById('feedback-btn')) return;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'feedback-btn';
    btn.className = 'feedback-btn';
    var pulse = document.createElement('span');
    pulse.className = 'feedback-pulse';
    pulse.setAttribute('aria-hidden', 'true');
    btn.appendChild(pulse);
    btn.appendChild(document.createTextNode('Send feedback'));
    right.insertBefore(btn, right.firstChild);
  }

  function ensureSettingsButton() {
    var loggedIn = document.getElementById('auth-logged-in');
    if (!loggedIn) return;
    var existing = document.getElementById('auth-settings-btn');
    if (!existing) {
      var settingsBtn = document.createElement('button');
      settingsBtn.type = 'button';
      settingsBtn.id = 'auth-settings-btn';
      settingsBtn.className = 'auth-settings-btn';
      settingsBtn.setAttribute('aria-label', 'Account settings');
      settingsBtn.setAttribute('title', 'Account settings');
      settingsBtn.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M19.14 12.94c.04-.31.06-.63.06-.94s-.02-.63-.06-.94l2.03-1.58a.5.5 0 0 0 .12-.64l-1.92-3.32a.5.5 0 0 0-.6-.22l-2.39.96a7.03 7.03 0 0 0-1.63-.94l-.36-2.54A.5.5 0 0 0 13.9 2h-3.8a.5.5 0 0 0-.49.42l-.36 2.54c-.58.22-1.13.53-1.63.94l-2.39-.96a.5.5 0 0 0-.6.22L2.71 8.48a.5.5 0 0 0 .12.64l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58a.5.5 0 0 0-.12.64l1.92 3.32c.13.22.39.31.6.22l2.39-.96c.5.41 1.05.72 1.63.94l.36 2.54c.04.24.25.42.49.42h3.8c.24 0 .45-.18.49-.42l.36-2.54c.58-.22 1.13-.53 1.63-.94l2.39.96c.22.09.47 0 .6-.22l1.92-3.32a.5.5 0 0 0-.12-.64l-2.03-1.58ZM12 15.5A3.5 3.5 0 1 1 12 8.5a3.5 3.5 0 0 1 0 7Z"/></svg>';
      var logoutBtn = document.getElementById('logout-btn');
      if (logoutBtn) loggedIn.insertBefore(settingsBtn, logoutBtn);
      else loggedIn.appendChild(settingsBtn);
    }
    var authUserEmail = document.getElementById('auth-user-email');
    if (authUserEmail) authUserEmail.style.display = 'none';
  }

  function playNavSound(filename) {
    try {
      var a = new Audio('/sounds/' + encodeURIComponent(filename));
      a.volume = 0.7;
      a.play().catch(function () {});
    } catch (e) {}
  }

  function injectAuthBar() {
    var existing = document.getElementById('auth-bar');
    if (existing) {
      ensureFeedbackButton();
      ensureSettingsButton();
      ensureTutorialsNavSound();
      updateLogoDestination(hasStoredAuthCredentials());
      document.body.classList.add('has-auth-bar');
      return;
    }
    var bar = createAuthBarHTML();
    document.body.insertBefore(bar, document.body.firstChild);
    document.body.classList.add('has-auth-bar');
    ensureSettingsButton();
    ensureTutorialsNavSound();
  }

  function getStoredAuthUser() {
    if (typeof localStorage === 'undefined') return null;
    try {
      var raw = localStorage.getItem('auth_user');
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function setStoredAuthUser(user) {
    if (typeof localStorage === 'undefined' || !user) return;
    try {
      localStorage.setItem('auth_user', JSON.stringify(user));
    } catch (e) {}
  }

  function normalizeAccountSettings(settings) {
    var displayColor = settings && settings.display_color === 'team_colors' ? 'team_colors' : 'default';
    return { display_color: displayColor };
  }

  var BRAND_DEFAULT_PRIMARY = '#27408E';
  var BRAND_DEFAULT_TOP = '#3551A5';
  var BRAND_DEFAULT_MID = '#1E3068';
  var BRAND_DEFAULT_DEEP = '#1C2D60';
  var CORE_TEAM_PRIMARY_COLORS = {
    'Bentley-Truman': '#4066B2',
    'Lancaster': '#D24A1B',
    'Four Corners': '#C0976A',
    'Ocean City': '#2A2168',
    'Morristown': '#EC1D28',
    'Little York': '#65308E',
    'Xavien': '#016837',
    'South Lancaster': '#7C2B24'
  };

  function normalizeHexColor(value) {
    var raw = String(value || '').trim();
    if (!/^#?[0-9a-fA-F]{6}$/.test(raw)) return null;
    return raw.charAt(0) === '#' ? raw.toUpperCase() : ('#' + raw.toUpperCase());
  }

  function blendHexColors(baseHex, targetHex, ratio) {
    var base = normalizeHexColor(baseHex);
    var target = normalizeHexColor(targetHex);
    if (!base || !target) return null;
    var clamped = Math.max(0, Math.min(1, Number(ratio) || 0));
    var baseInt = parseInt(base.slice(1), 16);
    var targetInt = parseInt(target.slice(1), 16);
    var r = Math.round(((baseInt >> 16) & 255) * (1 - clamped) + ((targetInt >> 16) & 255) * clamped);
    var g = Math.round(((baseInt >> 8) & 255) * (1 - clamped) + ((targetInt >> 8) & 255) * clamped);
    var b = Math.round((baseInt & 255) * (1 - clamped) + (targetInt & 255) * clamped);
    return '#' + [r, g, b].map(function (part) {
      return part.toString(16).padStart(2, '0');
    }).join('').toUpperCase();
  }

  function resolveStoredFranchiseTeamPrimaryColor() {
    if (typeof localStorage === 'undefined') return null;
    try {
      var fid = null;
      if (window.FranchiseLS && typeof window.FranchiseLS.resolveFranchiseIdFromUrl === 'function') {
        fid = window.FranchiseLS.resolveFranchiseIdFromUrl();
      } else {
        try {
          fid = new URLSearchParams(window.location.search).get('franchise_id');
        } catch (e2) {}
      }
      // Hybrid C: only paint franchise team chrome when URL has franchise_id
      if (!fid) return null;
      var ctx = window.FranchiseLS ? window.FranchiseLS.getTeamContext(fid) : null;
      var storedPrimary = normalizeHexColor(ctx && ctx.primaryColor);
      if (storedPrimary) return storedPrimary;
      var storedTeam = (ctx && ctx.teamName) || '';
      return normalizeHexColor(CORE_TEAM_PRIMARY_COLORS[storedTeam || '']);
    } catch (e) {
      return null;
    }
  }

  function applyGlobalDisplayColor(displayColor) {
    var root = document.documentElement;
    if (!root) return;
    var context = getDisplayContext();
    var teamPrimaryColor = normalizeHexColor(context && context.teamPrimaryColor) || resolveStoredFranchiseTeamPrimaryColor();
    var useTeamColor = displayColor === 'team_colors' && teamPrimaryColor;
    if (!useTeamColor) {
      root.style.setProperty('--fcc-primary', BRAND_DEFAULT_PRIMARY);
      root.style.setProperty('--fcc-primary-top', BRAND_DEFAULT_TOP);
      root.style.setProperty('--fcc-primary-mid', BRAND_DEFAULT_MID);
      root.style.setProperty('--fcc-primary-deep', BRAND_DEFAULT_DEEP);
      return;
    }
    var top = blendHexColors(teamPrimaryColor, '#FFFFFF', 0.18) || BRAND_DEFAULT_TOP;
    var mid = blendHexColors(teamPrimaryColor, '#000000', 0.14) || teamPrimaryColor;
    var deep = blendHexColors(teamPrimaryColor, '#000000', 0.34) || BRAND_DEFAULT_DEEP;
    root.style.setProperty('--fcc-primary', teamPrimaryColor);
    root.style.setProperty('--fcc-primary-top', top);
    root.style.setProperty('--fcc-primary-mid', mid);
    root.style.setProperty('--fcc-primary-deep', deep);
  }

  // Alpha feedback: until the survey is submitted (and once the coach has reached
  // the first prompt threshold of 2 games), the nav Feedback button reroutes to
  // the survey form and shows a pulsing violet aura instead of opening the bug modal.
  var alphaFeedbackRewire = false;
  function applyAlphaFeedbackState(me) {
    try {
      var games = me ? (parseInt(me.alpha_feedback_games, 10) || 0) : 0;
      alphaFeedbackRewire = !!(me && !me.alpha_feedback_submitted && games >= 4);
      var btn = document.getElementById('feedback-btn');
      if (btn) btn.classList.toggle('is-glowing', alphaFeedbackRewire);
    } catch (e) {}
  }

  function setAuthMeData(meData) {
    if (!meData) return;
    meData.account_settings = normalizeAccountSettings(meData.account_settings);
    authMeDataCache = meData;
    window.__gobAuthMeData = meData;
    applyAlphaFeedbackState(meData);
    applyGlobalDisplayColor(meData.account_settings.display_color);
    try {
      window.dispatchEvent(new CustomEvent('gob:auth-me-loaded', { detail: meData }));
    } catch (e) {}
    var stored = getStoredAuthUser() || {};
    stored.username = meData.username || stored.username || null;
    stored.email = meData.email || stored.email || null;
    stored.account_settings = meData.account_settings;
    setStoredAuthUser(stored);
  }

  function emitAccountSettingsUpdated(settings) {
    try {
      window.dispatchEvent(new CustomEvent('gob:account-settings-updated', {
        detail: { account_settings: normalizeAccountSettings(settings) }
      }));
    } catch (e) {}
  }

  function getDisplayContext() {
    try {
      if (typeof window.getGobDisplayColorContext === 'function') {
        return window.getGobDisplayColorContext() || {};
      }
      if (window.__gobDisplayColorContext) {
        return window.__gobDisplayColorContext;
      }
    } catch (e) {}
    return {
      mode: 'franchise',
      hasActiveFranchiseTeam: (function () {
        try {
          var fid = window.FranchiseLS
            ? window.FranchiseLS.resolveFranchiseIdFromUrl()
            : new URLSearchParams(window.location.search).get('franchise_id');
          if (!fid || !window.FranchiseLS) return false;
          var ctx = window.FranchiseLS.getTeamContext(fid);
          return !!(ctx && (ctx.teamName || ctx.teamId));
        } catch (e) {
          return false;
        }
      })(),
      teamPrimaryColor: resolveStoredFranchiseTeamPrimaryColor()
    };
  }

  function loadMusicController() {
    if (!musicControllerPromise) {
      musicControllerPromise = import('/js/musicController.js');
    }
    return musicControllerPromise;
  }

  function applyAmbienceSwitchVisual(switchEl, enabled) {
    if (!switchEl) return;
    // aria-checked drives the knob slide / on-state styling in CSS.
    switchEl.setAttribute('aria-checked', enabled ? 'true' : 'false');
  }

  function syncAmbienceSwitchFromController(switchEl, mc) {
    applyAmbienceSwitchVisual(switchEl, mc.isScoutingAmbienceEnabled());
  }

  function refreshAccountSettingsModal() {
    var usernameEl = document.getElementById('account-settings-username');
    var switchEl = document.getElementById('account-ambience-switch');
    if (!usernameEl || !switchEl) return;

    var meData = authMeDataCache || window.__gobAuthMeData || {};
    var displayName = meData.username || meData.email || 'Coach';
    usernameEl.textContent = displayName;

    var avatar = document.getElementById('account-avatar');
    if (avatar) {
      // First initial fallback (a real coach avatar image could replace this).
      avatar.textContent = displayName.charAt(0).toUpperCase();
    }

    renderAccountArchetypeBadge(meData);

    loadMusicController()
      .then(function (mc) {
        syncAmbienceSwitchFromController(switchEl, mc);
      })
      .catch(function (err) {
        console.warn('[account-settings] music controller import failed', err);
      });
  }

  // Load the shared archetype-badge module on demand (auth bar runs on many pages).
  function ensureArchetypeBadgeScript() {
    if (window.GOBArchetype) return Promise.resolve();
    if (window.__gobArchetypeBadgeLoading) return window.__gobArchetypeBadgeLoading;
    window.__gobArchetypeBadgeLoading = new Promise(function (resolve) {
      var s = document.createElement('script');
      s.src = '/js/shared/archetypeBadge.js';
      s.onload = function () { resolve(); };
      s.onerror = function () { resolve(); };
      document.head.appendChild(s);
    });
    return window.__gobArchetypeBadgeLoading;
  }

  // Coaching-archetype badge beside the username (reads lead_archetype, with
  // the shared fallback to derive from archetype counts on older docs).
  function renderAccountArchetypeBadge(meData) {
    var badgeEl = document.getElementById('account-settings-badge');
    if (!badgeEl) return;
    badgeEl.innerHTML = '';
    ensureArchetypeBadgeScript().then(function () {
      if (!window.GOBArchetype) return;
      var lead = window.GOBArchetype.leadFrom(meData);
      if (!lead) return;
      var badge = window.GOBArchetype.createBadge(lead, 22);
      if (badge) { badgeEl.innerHTML = ''; badgeEl.appendChild(badge); }
    });
  }

  function closeAccountSettingsModal() {
    var overlay = document.getElementById('account-settings-overlay');
    if (!overlay) return;
    overlay.classList.remove('is-visible');
    var box = overlay.querySelector('.account-modal-box');
    if (box) box.classList.remove('is-entered'); // reset so it re-animates next open
  }

  function openAccountSettingsModal() {
    refreshAccountSettingsModal();
    var overlay = document.getElementById('account-settings-overlay');
    if (!overlay) return;
    overlay.classList.add('is-visible');
    var box = overlay.querySelector('.account-modal-box');
    if (box) {
      // Reflow at the pre-entrance scale (overlay is now displayed) so the
      // scale 0.96 -> 1.0 transition actually runs.
      box.classList.remove('is-entered');
      void box.offsetWidth;
      box.classList.add('is-entered');
    }
  }

  // --- Save toast (shared Toast pattern, Styleguide §Toast Notifications) ---
  var accountToastTimer = null;

  function ensureAccountToast() {
    var existing = document.getElementById('account-toast');
    if (existing) return existing;
    var toast = document.createElement('div');
    toast.id = 'account-toast';
    toast.className = 'account-toast';
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');
    toast.hidden = true;
    toast.innerHTML = [
      '<span class="account-toast-icon" aria-hidden="true">',
      '  <svg viewBox="0 0 20 20" width="11" height="11" fill="none">',
      '    <path d="M5.1 10.4 8.3 13.6 14.9 7" stroke="#FFFFFF" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>',
      '  </svg>',
      '</span>',
      '<div class="account-toast-copy">',
      '  <div id="account-toast-message" class="account-toast-message"></div>',
      '</div>'
    ].join('');
    document.body.appendChild(toast);
    return toast;
  }

  // One toast at a time — a rapid second flip reuses it and resets the 3s timer.
  function showAccountToast(enabled) {
    var toast = ensureAccountToast();
    var message = document.getElementById('account-toast-message');
    if (message) {
      message.textContent = enabled ? 'Scouting ambience on.' : 'Scouting ambience off.';
    }
    if (accountToastTimer) {
      clearTimeout(accountToastTimer);
      accountToastTimer = null;
    }
    toast.hidden = false;
    // Force reflow so the entrance transition replays on a reused toast.
    void toast.offsetWidth;
    toast.classList.add('is-visible');
    accountToastTimer = setTimeout(function () {
      toast.classList.remove('is-visible');
      accountToastTimer = null;
    }, 3000);
  }

  function persistDisplayColor(displayColor) {
    if (typeof API_CONFIG === 'undefined' || !API_CONFIG.buildUrl || !API_CONFIG.getAuthHeaders) {
      return Promise.reject(new Error('API unavailable'));
    }
    return fetch(API_CONFIG.buildUrl('/api/auth/account-settings'), {
      method: 'PATCH',
      headers: Object.assign({ 'Content-Type': 'application/json' }, API_CONFIG.getAuthHeaders()),
      body: JSON.stringify({ display_color: displayColor })
    })
      .then(function (res) {
        if (!res.ok) throw new Error('Unable to save setting');
        return res.json();
      })
      .then(function (data) {
        var nextSettings = normalizeAccountSettings(data.account_settings);
        if (authMeDataCache) authMeDataCache.account_settings = nextSettings;
        emitAccountSettingsUpdated(nextSettings);
        setAuthMeData(Object.assign({}, authMeDataCache || {}, { account_settings: nextSettings }));
        refreshAccountSettingsModal();
        return data;
      });
  }

  function initAccountSettingsModal() {
    ensureAccountSettingsModal();
    var settingsBtn = document.getElementById('auth-settings-btn');
    var overlay = document.getElementById('account-settings-overlay');
    var closeBtn = document.getElementById('account-settings-close');
    if (settingsBtn && !settingsBtn.dataset.bound) {
      settingsBtn.dataset.bound = '1';
      settingsBtn.addEventListener('click', openAccountSettingsModal);
    }
    if (closeBtn && !closeBtn.dataset.bound) {
      closeBtn.dataset.bound = '1';
      closeBtn.addEventListener('click', closeAccountSettingsModal);
    }
    if (overlay && !overlay.dataset.bound) {
      overlay.dataset.bound = '1';
      // Backdrop click dismisses (Functional Modal rule).
      overlay.addEventListener('click', function (e) {
        if (e.target && e.target.hasAttribute('data-account-dismiss')) {
          closeAccountSettingsModal();
        }
      });
    }
    // ESC dismisses (Functional Modal rule). Bound once at the document level.
    if (!document.body.dataset.accountEscBound) {
      document.body.dataset.accountEscBound = '1';
      document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape' && e.key !== 'Esc') return;
        var open = document.getElementById('account-settings-overlay');
        if (open && open.classList.contains('is-visible')) {
          closeAccountSettingsModal();
        }
      });
    }
    var switchEl = document.getElementById('account-ambience-switch');
    if (switchEl && !switchEl.dataset.bound) {
      switchEl.dataset.bound = '1';
      switchEl.addEventListener('click', function () {
        var turningOn = switchEl.getAttribute('aria-checked') !== 'true';
        loadMusicController()
          .then(function (mc) {
            // Apply instantly — no Save button. setScoutingAmbienceEnabled is
            // the account's real persistence for this preference.
            mc.setScoutingAmbienceEnabled(turningOn);
            syncAmbienceSwitchFromController(switchEl, mc);
            if (turningOn) {
              mc.tryStartScoutingAmbienceForCurrentPage();
            } else {
              mc.clearFranchiseMusicState();
            }
            showAccountToast(turningOn);
          })
          .catch(function (err) {
            console.warn('[ambience-toggle] music controller import failed', err);
          });
      });
    }
  }

  function ensureTutorialsNavSound() {
    var bar = document.getElementById('auth-bar');
    if (!bar) return;
    var tutorialsBtn = bar.querySelector('.nav-tutorials-link');
    if (tutorialsBtn && !tutorialsBtn.dataset.soundBound) {
      tutorialsBtn.dataset.soundBound = '1';
      tutorialsBtn.addEventListener('click', function () { playNavSound('click-tiny.wav'); });
    }
  }

  function createFooterHTML() {
    var footer = document.createElement('footer');
    footer.id = 'site-footer';
    footer.className = 'site-footer';
    footer.innerHTML = '<a href="/faqs.html">FAQs</a>';
    return footer;
  }

  function injectFooter() {
    if (document.getElementById('site-footer')) return;
    var footer = createFooterHTML();
    document.body.appendChild(footer);
    document.body.classList.add('has-footer');
  }

  function initAuthState() {
    var authLoggedOut = document.getElementById('auth-logged-out');
    var authLoggedIn = document.getElementById('auth-logged-in');
    var logoutBtn = document.getElementById('logout-btn');
    if (!authLoggedOut && !authLoggedIn) return;

    var authToken = typeof localStorage !== 'undefined' ? localStorage.getItem('auth_token') : null;
    var authUser = typeof localStorage !== 'undefined' ? localStorage.getItem('auth_user') : null;
    updateLogoDestination(hasStoredAuthCredentials());

    if (authToken && authUser) {
      try {
        var user = JSON.parse(authUser);
        // Validate token before showing logged-in state
        if (typeof API_CONFIG !== 'undefined' && typeof API_CONFIG.buildUrl === 'function' && typeof API_CONFIG.getAuthHeaders === 'function') {
          fetch(API_CONFIG.buildUrl('/api/auth/me'), { headers: API_CONFIG.getAuthHeaders() })
            .then(function (res) {
              if (res.ok) {
                // Token valid - show logged-in state
                if (authLoggedOut) authLoggedOut.style.display = 'none';
                if (authLoggedIn) authLoggedIn.style.display = 'flex';
                updateLogoDestination(true);
                res.json().then(function (meData) {
                  setAuthMeData(meData);
                  refreshAccountSettingsModal();
                  routeToTutorial(meData);
                  ensureTutorialAlertExperience().then(function () {
                    /* Read the live global, not the closure's meData: the alerts
                       module patches dismissals into __gobAuthMeData (new object),
                       so the captured meData can be stale by the time this runs —
                       passing it would revert a local dismissal and re-show the
                       modal (see Tutorial_Alerts_System.md bug history). */
                    if (window.GOBTutorialAlerts) window.GOBTutorialAlerts.onAuthMeLoaded(window.__gobAuthMeData || meData);
                  });
                }).catch(function () {
                  setAuthMeData({
                    username: user.username || null,
                    email: user.email || null,
                    account_settings: user.account_settings || { display_color: 'default' }
                  });
                  refreshAccountSettingsModal();
                });
              } else {
                // Token invalid - clear and show logged-out state
                if (typeof localStorage !== 'undefined') {
                  localStorage.removeItem('auth_token');
                  localStorage.removeItem('auth_user');
                }
                if (authLoggedOut) authLoggedOut.style.display = 'flex';
                if (authLoggedIn) authLoggedIn.style.display = 'none';
                updateLogoDestination(false);
              }
            })
            .catch(function () {
              // Network error - clear token to be safe
              if (typeof localStorage !== 'undefined') {
                localStorage.removeItem('auth_token');
                localStorage.removeItem('auth_user');
              }
              if (authLoggedOut) authLoggedOut.style.display = 'flex';
              if (authLoggedIn) authLoggedIn.style.display = 'none';
              updateLogoDestination(false);
            });
        } else {
          // API_CONFIG not available - show from localStorage but don't validate
          if (authLoggedOut) authLoggedOut.style.display = 'none';
          if (authLoggedIn) authLoggedIn.style.display = 'flex';
          updateLogoDestination(true);
          setAuthMeData({
            username: user.username || null,
            email: user.email || null,
            account_settings: user.account_settings || { display_color: 'default' }
          });
          refreshAccountSettingsModal();
        }
      } catch (e) {
        if (typeof localStorage !== 'undefined') {
          localStorage.removeItem('auth_token');
          localStorage.removeItem('auth_user');
        }
        if (authLoggedOut) authLoggedOut.style.display = 'flex';
        if (authLoggedIn) authLoggedIn.style.display = 'none';
        updateLogoDestination(false);
      }
    } else {
      updateLogoDestination(false);
    }

    if (logoutBtn) {
      logoutBtn.addEventListener('click', function () {
        try {
          if (typeof API_CONFIG !== 'undefined') {
            fetch(API_CONFIG.buildUrl('/api/auth/logout'), { method: 'POST' }).catch(function () {});
          }
        } catch (e) {}
        if (typeof localStorage !== 'undefined') {
          localStorage.removeItem('auth_token');
          localStorage.removeItem('auth_user');
        }
        if (authLoggedOut) authLoggedOut.style.display = 'flex';
        if (authLoggedIn) authLoggedIn.style.display = 'none';
        updateLogoDestination(false);
        window.location.href = '/mode-select.html';
      });
    }
  }

  function ensureFeedbackModal() {
    if (document.getElementById('feedback-modal-backdrop')) return;
    var backdrop = document.createElement('div');
    backdrop.id = 'feedback-modal-backdrop';
    backdrop.className = 'feedback-modal-backdrop';
    backdrop.innerHTML = [
      '<div class="feedback-modal" role="dialog" aria-modal="true" aria-labelledby="feedback-modal-title">',
      '  <div class="feedback-modal-header">',
      '    <h3 id="feedback-modal-title" class="feedback-modal-title">Send Feedback</h3>',
      '    <button type="button" id="feedback-close-btn" class="feedback-modal-close" aria-label="Close">×</button>',
      '  </div>',
      '  <div class="feedback-modal-body">',
      '    <label>Type',
      '      <select id="feedback-category">',
      '        <option value="bug">Bug</option>',
      '        <option value="ux">UX</option>',
      '        <option value="balance">Balance</option>',
      '        <option value="content">Content</option>',
      '        <option value="general" selected>General</option>',
      '      </select>',
      '    </label>',
      '    <label>Message',
      '      <textarea id="feedback-message" maxlength="5000" placeholder="What should we improve?" required></textarea>',
      '    </label>',
      '    <label>Email (optional)',
      '      <input id="feedback-email" type="email" maxlength="254" placeholder="you@example.com">',
      '    </label>',
      '    <div id="feedback-status" class="feedback-modal-status"></div>',
      '  </div>',
      '  <div class="feedback-modal-footer">',
      '    <button type="button" id="feedback-cancel-btn" class="feedback-modal-btn">Cancel</button>',
      '    <button type="button" id="feedback-submit-btn" class="feedback-modal-btn primary">Send</button>',
      '  </div>',
      '</div>'
    ].join('');
    document.body.appendChild(backdrop);
  }

  function initFeedbackModal() {
    ensureFeedbackModal();
    var openBtn = document.getElementById('feedback-btn');
    var backdrop = document.getElementById('feedback-modal-backdrop');
    var closeBtn = document.getElementById('feedback-close-btn');
    var cancelBtn = document.getElementById('feedback-cancel-btn');
    var submitBtn = document.getElementById('feedback-submit-btn');
    var statusEl = document.getElementById('feedback-status');
    var messageEl = document.getElementById('feedback-message');
    var emailEl = document.getElementById('feedback-email');
    var categoryEl = document.getElementById('feedback-category');
    if (!openBtn || !backdrop || !closeBtn || !cancelBtn || !submitBtn || !statusEl || !messageEl || !emailEl || !categoryEl) {
      return;
    }

    var parsedUser = null;
    try {
      var authUser = typeof localStorage !== 'undefined' ? localStorage.getItem('auth_user') : null;
      parsedUser = authUser ? JSON.parse(authUser) : null;
    } catch (e) {
      parsedUser = null;
    }
    if (parsedUser && parsedUser.email && !emailEl.value) {
      emailEl.value = parsedUser.email;
    }

    function setStatus(text, isError) {
      statusEl.textContent = text || '';
      statusEl.style.color = isError ? '#b91c1c' : '#6b7280';
    }

    function playSound(filename) {
      try {
        var a = new Audio('/sounds/' + encodeURIComponent(filename));
        a.volume = 0.7;
        a.play().catch(function () {});
      } catch (e) {}
    }
    function openModal() {
      playSound('click-tiny.wav');
      // Until the alpha survey is submitted, the Feedback button routes to the
      // survey form instead of opening the general bug-report modal.
      if (alphaFeedbackRewire) {
        window.location.href = '/alpha-feedback.html';
        return;
      }
      setStatus('', false);
      backdrop.classList.add('open');
      messageEl.focus();
    }

    function closeModal() {
      backdrop.classList.remove('open');
    }

    openBtn.addEventListener('click', openModal);
    closeBtn.addEventListener('click', closeModal);
    cancelBtn.addEventListener('click', closeModal);
    backdrop.addEventListener('click', function (e) {
      if (e.target === backdrop) closeModal();
    });

    submitBtn.addEventListener('click', function () {
      var message = (messageEl.value || '').trim();
      if (message.length < 5) {
        setStatus('Please add a bit more detail (at least 5 characters).', true);
        return;
      }

      var url = (typeof API_CONFIG !== 'undefined' && API_CONFIG.buildUrl)
        ? API_CONFIG.buildUrl('/api/feedback')
        : '/api/feedback';
      var headers = { 'Content-Type': 'application/json' };
      if (typeof API_CONFIG !== 'undefined' && API_CONFIG.getAuthHeaders) {
        var authHeaders = API_CONFIG.getAuthHeaders() || {};
        for (var k in authHeaders) headers[k] = authHeaders[k];
      }

      var urlParams = new URLSearchParams(window.location.search || '');
      var payload = {
        category: categoryEl.value || 'general',
        message: message,
        reporter_email: (emailEl.value || '').trim(),
        page_url: window.location.href,
        page_path: window.location.pathname,
        mode: urlParams.get('mode') || '',
        user_label: parsedUser ? (parsedUser.username || parsedUser.email || '') : ''
      };

      submitBtn.disabled = true;
      setStatus('Sending feedback...', false);

      fetch(url, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload)
      })
        .then(function (res) {
          if (!res.ok) throw new Error('Unable to send feedback right now.');
          return res.json();
        })
        .then(function () {
          setStatus('Thanks. Feedback sent.', false);
          messageEl.value = '';
          setTimeout(closeModal, 700);
        })
        .catch(function (err) {
          setStatus(err.message || 'Unable to send feedback right now.', true);
        })
        .finally(function () {
          submitBtn.disabled = false;
        });
    });

  }

  function initAlphaBadge() {
    if (typeof AlphaBanner !== 'undefined' && typeof AlphaBanner.init === 'function') {
      AlphaBanner.init();
      return;
    }
    if (typeof API_CONFIG !== 'undefined' && typeof API_CONFIG.loadAppConfig === 'function') {
      API_CONFIG.loadAppConfig().then(function (config) {
        if (config && config.isAlpha) {
          var badge = document.getElementById('alpha-badge');
          if (badge) badge.classList.add('visible');
        }
      }).catch(function () {});
    }
  }

  function initAuthBar() {
    applyGlobalDisplayColor(normalizeAccountSettings((getStoredAuthUser() || {}).account_settings).display_color);
    if (!shouldShowAuthBar()) return;
    ensureAuthBarStyles();
    injectAuthBar();
    injectFooter();
    initAccountSettingsModal();
    initAuthState();
    ensureTutorialAlertExperience();
    initAlphaBadge();
    initFeedbackModal();
  }

  function run() {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', initAuthBar);
    } else {
      initAuthBar();
    }
  }

  run();
})();
