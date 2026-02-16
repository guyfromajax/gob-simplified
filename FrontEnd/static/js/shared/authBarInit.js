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
      title: 'Tap the yellow Tutorial button in the nav bar.',
      body: '<div class="fte-tutorial-wrap fte-tutorial-wrap--full-width"><div class="fte-tutorial-preview" aria-hidden="true">Tutorials</div></div>',
      showBack: true,
      primaryLabel: 'Next'
    },
    {
      title: 'Want more?',
      body: '<p>Want more?</p><div class="fte-row-with-img"><span class="fte-content-text">Watch our YouTube breakdowns.</span><img src="/images/yt_icon_red_digital.png" alt="YouTube" class="fte-yt-logo"></div>',
      showBack: true,
      primaryLabel: 'Done'
    }
  ];

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

  function runFTE(meData) {
    if (!meData || meData.fte !== true) return;
    ensureFTEStyles();
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

  function createAuthBarHTML() {
    var bar = document.createElement('div');
    bar.id = 'auth-bar';
    bar.className = 'auth-bar';
    bar.innerHTML = [
      '<div class="auth-bar-left">',
      '  <a href="/" class="logo-link"><img src="/images/geekedout_logo.png" alt="Geeked-Out Basketball logo" class="logo"></a>',
      '  <a href="/tutorial.html" class="tutorials-nav-btn">Tutorials</a>',
      '</div>',
      '<img id="alpha-badge" class="alpha-badge visible" src="/images/alpha_badge_gold.png" alt="Alpha">',
      '<div class="auth-bar-right">',
      '  <button type="button" id="feedback-btn" class="feedback-btn">Feedback</button>',
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
      '    <span id="auth-user-email" class="auth-email"></span>',
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
    btn.textContent = 'Feedback';
    right.insertBefore(btn, right.firstChild);
  }

  function injectAuthBar() {
    var existing = document.getElementById('auth-bar');
    if (existing) {
      ensureFeedbackButton();
      document.body.classList.add('has-auth-bar');
      return;
    }
    var bar = createAuthBarHTML();
    document.body.insertBefore(bar, document.body.firstChild);
    document.body.classList.add('has-auth-bar');
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
    var authUserEmail = document.getElementById('auth-user-email');
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
                  if (authUserEmail) authUserEmail.textContent = meData.username || meData.email || user.email;
                  if (meData.fte === true) runFTE(meData);
                }).catch(function () {
                  if (authUserEmail) authUserEmail.textContent = user.username || user.email;
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
          if (authUserEmail) authUserEmail.textContent = user.username || user.email;
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

    function openModal() {
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
    if (!shouldShowAuthBar()) return;
    ensureAuthBarStyles();
    injectAuthBar();
    injectFooter();
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
