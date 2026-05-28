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
    return !PAGES_WITHOUT_AUTH_BAR.some(function (p) {
      return path.indexOf(p) !== -1;
    });
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

  function ensureFTEStyles() {
    if (document.getElementById('fte-styles-link')) return;
    if (document.querySelector('link[href*="fte.css"]')) return;
    var link = document.createElement('link');
    link.id = 'fte-styles-link';
    link.rel = 'stylesheet';
    link.href = '/css/fte.css';
    document.head.appendChild(link);
  }

  var FTE_STEPS = [
    { title: 'Hey Coach!', body: '<p>Welcome to Geeked-Out Basketball.</p>', showBack: false, primaryLabel: 'Next' },
    { title: 'We assume you know hoops.', body: '<p>Now learn GOB.</p>', showBack: true, primaryLabel: 'Next' },
    {
      title: 'The Tutorial button sits in the top nav.',
      body: '<div class="fte-tutorial-wrap fte-tutorial-wrap--full-width"><div class="fte-tutorial-preview" aria-hidden="true">Tutorials</div></div>',
      showBack: true,
      primaryLabel: 'Next'
    },
    {
      title: 'Deeper breakdowns live on our YouTube channel.',
      body: '<div class="fte-row-with-img"><span class="fte-content-text">Deeper breakdowns live on our YouTube channel.</span><img src="/images/yt_icon_red_digital.png" alt="YouTube" class="fte-yt-logo"></div>',
      showBack: true,
      primaryLabel: 'Done'
    }
  ];

  // Username modal lives in /js/shared/usernameModal.js (FTE v2 chrome).
  // Loaded on demand via dynamic import — see openUsernameModal() below.

  function ensureAccountSettingsModal() {
    if (document.getElementById('account-settings-backdrop')) return;
    var backdrop = document.createElement('div');
    backdrop.id = 'account-settings-backdrop';
    backdrop.className = 'account-settings-backdrop';
    backdrop.setAttribute('role', 'dialog');
    backdrop.setAttribute('aria-modal', 'true');
    backdrop.setAttribute('aria-labelledby', 'account-settings-title');
    backdrop.innerHTML = [
      '<div class="account-settings-modal">',
      '  <div class="account-settings-header">',
      '    <h3 id="account-settings-title" class="account-settings-title">Account Settings</h3>',
      '    <button type="button" id="account-settings-close" class="account-settings-close" aria-label="Close account settings">&times;</button>',
      '  </div>',
      '  <div class="account-settings-body">',
      '    <div class="account-settings-row">',
      '      <div class="account-settings-label">Username</div>',
      '      <div id="account-settings-username" class="account-settings-value">-</div>',
      '    </div>',
      '    <div class="account-settings-row">',
      '      <div class="account-settings-label">Scouting Ambience</div>',
      '      <button type="button" id="account-ambience-pill" class="account-display-pill" aria-label="Scouting ambience toggle" aria-pressed="true">',
      '        <span class="account-display-pill-thumb" aria-hidden="true"></span>',
      '        <span class="account-display-pill-option account-display-pill-option-left">On</span>',
      '        <span class="account-display-pill-option account-display-pill-option-right">Off</span>',
      '      </button>',
      '    </div>',
      '  </div>',
      '</div>'
    ].join('');
    document.body.appendChild(backdrop);
  }

  function ensureFTEModal() {
    if (document.getElementById('fte-backdrop')) return;
    var backdrop = document.createElement('div');
    backdrop.id = 'fte-backdrop';
    backdrop.className = 'fte-backdrop';
    backdrop.setAttribute('role', 'dialog');
    backdrop.setAttribute('aria-modal', 'true');
    backdrop.setAttribute('aria-labelledby', 'fte-content-main');
    backdrop.innerHTML = [
      '<div class="fte-modal">',
      '  <div class="fte-content">',
      '    <img src="/images/sammy_tutorial.png" alt="" class="fte-content-img">',
      '    <div id="fte-content-main" class="fte-content-main"></div>',
      '  </div>',
      '  <div class="fte-footer">',
      '    <button type="button" id="fte-btn-back" class="fte-btn fte-btn-back">Back</button>',
      '    <button type="button" id="fte-btn-primary" class="fte-btn fte-btn-next"></button>',
      '  </div>',
      '</div>'
    ].join('');
    document.body.appendChild(backdrop);
  }

  function showFTEStep(stepIndex) {
    var step = FTE_STEPS[stepIndex];
    var mainEl = document.getElementById('fte-content-main');
    var backBtn = document.getElementById('fte-btn-back');
    var primaryBtn = document.getElementById('fte-btn-primary');
    if (!mainEl || !backBtn || !primaryBtn) return;
    if (stepIndex === 3 && step.body) {
      mainEl.innerHTML = step.body;
    } else if (step.body) {
      mainEl.innerHTML = '<p>' + step.title + '</p>' + step.body;
    } else {
      mainEl.innerHTML = '<p>' + step.title + '</p>';
    }
    backBtn.style.display = step.showBack ? '' : 'none';
    primaryBtn.textContent = step.primaryLabel;
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

  function openFTESteps() {
    ensureFTEModal();
    var backdrop = document.getElementById('fte-backdrop');
    var backBtn = document.getElementById('fte-btn-back');
    var primaryBtn = document.getElementById('fte-btn-primary');
    if (!backdrop || !primaryBtn) return;

    var currentStep = 0;
    showFTEStep(currentStep);
    backdrop.classList.add('open');

    function closeFTE() {
      backdrop.classList.remove('open');
    }

    function completeFTE() {
      if (typeof API_CONFIG !== 'undefined' && typeof API_CONFIG.buildUrl === 'function' && typeof API_CONFIG.getAuthHeaders === 'function') {
        fetch(API_CONFIG.buildUrl('/api/auth/fte-complete'), {
          method: 'POST',
          headers: API_CONFIG.getAuthHeaders()
        }).then(function () {
          try {
            var authUser = localStorage.getItem('auth_user');
            if (authUser) {
              var user = JSON.parse(authUser);
              user.fte = false;
              localStorage.setItem('auth_user', JSON.stringify(user));
            }
          } catch (e) {}
          closeFTE();
        }).catch(function () {
          closeFTE();
        });
      } else {
        closeFTE();
      }
    }

    backBtn.addEventListener('click', function () {
      if (currentStep > 0) {
        currentStep -= 1;
        showFTEStep(currentStep);
      }
    });

    primaryBtn.addEventListener('click', function () {
      if (currentStep === 3 && FTE_STEPS[3].primaryLabel === 'Done') {
        completeFTE();
        return;
      }
      if (currentStep < FTE_STEPS.length - 1) {
        currentStep += 1;
        showFTEStep(currentStep);
      }
    });
  }

  function runFTE(meData) {
    if (!meData || meData.fte !== true) return;
    ensureFTEStyles();

    var hasUsername = meData.username && String(meData.username).trim().length > 0;
    if (!hasUsername) {
      var fteBackdrop = document.getElementById('fte-backdrop');
      if (fteBackdrop) fteBackdrop.classList.remove('open');
      openUsernameModal(function () {
        openFTESteps();
      });
      return;
    }
    openFTESteps();
  }

  function createAuthBarHTML() {
    var bar = document.createElement('div');
    bar.id = 'auth-bar';
    bar.className = 'auth-bar';
    bar.innerHTML = [
      '<div class="auth-bar-left">',
      '  <a href="/" class="logo-link"><img src="/images/geekedout_logo.png" alt="Geeked-Out Basketball logo" class="logo"></a>',
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
      var storedPrimary = normalizeHexColor(localStorage.getItem('franchise_user_team_primary_color'));
      if (storedPrimary) return storedPrimary;
      var storedTeam = localStorage.getItem('franchise_user_team');
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

  function setAuthMeData(meData) {
    if (!meData) return;
    meData.account_settings = normalizeAccountSettings(meData.account_settings);
    authMeDataCache = meData;
    window.__gobAuthMeData = meData;
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
      hasActiveFranchiseTeam: !!(typeof localStorage !== 'undefined' && (localStorage.getItem('franchise_user_team') || localStorage.getItem('franchise_user_team_id'))),
      teamPrimaryColor: resolveStoredFranchiseTeamPrimaryColor()
    };
  }

  function loadMusicController() {
    if (!musicControllerPromise) {
      musicControllerPromise = import('/js/musicController.js');
    }
    return musicControllerPromise;
  }

  function applyAmbiencePillVisual(pill, enabled) {
    if (!pill) return;
    // `is-off` slides the thumb right to the "Off" option.
    pill.classList.toggle('is-off', !enabled);
    pill.setAttribute('aria-pressed', enabled ? 'true' : 'false');
  }

  function syncAmbiencePillFromController(pill, mc) {
    applyAmbiencePillVisual(pill, mc.isScoutingAmbienceEnabled());
  }

  function refreshAccountSettingsModal() {
    var usernameEl = document.getElementById('account-settings-username');
    var pill = document.getElementById('account-ambience-pill');
    if (!usernameEl || !pill) return;

    var meData = authMeDataCache || window.__gobAuthMeData || {};
    usernameEl.textContent = meData.username || meData.email || 'Coach';

    loadMusicController()
      .then(function (mc) {
        syncAmbiencePillFromController(pill, mc);
      })
      .catch(function (err) {
        console.warn('[account-settings] music controller import failed', err);
      });
  }

  function closeAccountSettingsModal() {
    var backdrop = document.getElementById('account-settings-backdrop');
    if (backdrop) backdrop.classList.remove('open');
  }

  function openAccountSettingsModal() {
    refreshAccountSettingsModal();
    var backdrop = document.getElementById('account-settings-backdrop');
    if (backdrop) backdrop.classList.add('open');
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
    var backdrop = document.getElementById('account-settings-backdrop');
    var closeBtn = document.getElementById('account-settings-close');
    if (settingsBtn && !settingsBtn.dataset.bound) {
      settingsBtn.dataset.bound = '1';
      settingsBtn.addEventListener('click', openAccountSettingsModal);
    }
    if (closeBtn && !closeBtn.dataset.bound) {
      closeBtn.dataset.bound = '1';
      closeBtn.addEventListener('click', closeAccountSettingsModal);
    }
    if (backdrop && !backdrop.dataset.bound) {
      backdrop.dataset.bound = '1';
      backdrop.addEventListener('click', function (e) {
        if (e.target === backdrop) closeAccountSettingsModal();
      });
    }
    var pill = document.getElementById('account-ambience-pill');
    if (pill && !pill.dataset.bound) {
      pill.dataset.bound = '1';
      pill.addEventListener('click', function () {
        var turningOn = pill.classList.contains('is-off');
        loadMusicController()
          .then(function (mc) {
            mc.setScoutingAmbienceEnabled(turningOn);
            syncAmbiencePillFromController(pill, mc);
            if (turningOn) {
              mc.tryStartScoutingAmbienceForCurrentPage();
            } else {
              mc.clearFranchiseMusicState();
            }
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
                res.json().then(function (meData) {
                  setAuthMeData(meData);
                  refreshAccountSettingsModal();
                  if (meData.fte === true) runFTE(meData);
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
            });
        } else {
          // API_CONFIG not available - show from localStorage but don't validate
          if (authLoggedOut) authLoggedOut.style.display = 'none';
          if (authLoggedIn) authLoggedIn.style.display = 'flex';
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
      }
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
