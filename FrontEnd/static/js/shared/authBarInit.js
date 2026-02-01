/**
 * Auth Bar Init - Shared top nav bar with user email and logout.
 *
 * Shows on all screens EXCEPT court.html and set-lineup.html.
 * Call initAuthBar() after DOMContentLoaded (or it runs when script loads if DOM ready).
 *
 * - Injects auth bar HTML if not present
 * - Loads auth-bar.css
 * - Initializes auth state (email, logout)
 * - Alpha badge visibility via AlphaBanner or app config
 */
(function () {
  'use strict';

  var PAGES_WITHOUT_AUTH_BAR = ['court.html', 'set-lineup.html'];

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
      '<div class="auth-bar-spacer"></div>',
      '<img id="alpha-badge" class="alpha-badge" src="/images/alpha_badge_gold.png" alt="Alpha">',
      '<div class="auth-bar-right">',
      '  <div id="auth-logged-out" class="auth-status">',
      '    <a href="/login.html" class="auth-link">Log In</a>',
      '    <span class="auth-divider">|</span>',
      '    <a href="/signup.html" class="auth-link">Sign Up</a>',
      '  </div>',
      '  <div id="auth-logged-in" class="auth-status" style="display: none;">',
      '    <span id="auth-user-email" class="auth-email"></span>',
      '    <button id="logout-btn" class="auth-logout-btn">Log Out</button>',
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
        if (authUserEmail) authUserEmail.textContent = user.email;
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
