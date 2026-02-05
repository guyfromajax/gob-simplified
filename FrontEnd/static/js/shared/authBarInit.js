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

  var PAGES_WITHOUT_AUTH_BAR = ['court.html', 'set-lineup.html', 'training.html', 'training-report.html'];

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

  function createAuthBarHTML() {
    var bar = document.createElement('div');
    bar.id = 'auth-bar';
    bar.className = 'auth-bar';
    bar.innerHTML = [
      '<div class="auth-bar-left">',
      '  <a href="/" class="logo-link"><img src="/images/geekedout_logo.png" alt="Geeked-Out Basketball logo" class="logo"></a>',
      '</div>',
      '<img id="alpha-badge" class="alpha-badge visible" src="/images/alpha_badge_gold.png" alt="Alpha">',
      '<div class="auth-bar-right">',
      '  <a href="https://www.youtube.com/@geeked-outbasketball765" target="_blank" rel="noopener noreferrer" class="nav-icon" aria-label="GOB on YouTube">',
      '    <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>',
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

  function injectAuthBar() {
    var existing = document.getElementById('auth-bar');
    if (existing) {
      document.body.classList.add('has-auth-bar');
      return;
    }
    var bar = createAuthBarHTML();
    document.body.insertBefore(bar, document.body.firstChild);
    document.body.classList.add('has-auth-bar');
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
        if (authLoggedOut) authLoggedOut.style.display = 'none';
        if (authLoggedIn) authLoggedIn.style.display = 'flex';
        if (authUserEmail) authUserEmail.textContent = user.username || user.email;
      } catch (e) {
        if (typeof localStorage !== 'undefined') {
          localStorage.removeItem('auth_token');
          localStorage.removeItem('auth_user');
        }
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
    initAuthState();
    initAlphaBadge();
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
