/**
 * Sentry Frontend Error Tracking
 * Fetches app-config for sentryDsn, then loads and initializes Sentry browser SDK if present.
 * Runs asynchronously and does not block page load.
 */
(function () {
  'use strict';

  function isDesktopProfile() {
    if (window.GOB_BUILD_PROFILE === 'desktop') return true;
    return /(?:^|; )GOB_BUILD_PROFILE=desktop(?:;|$)/.test(document.cookie || '');
  }
  if (isDesktopProfile()) {
    return;
  }

  // The SDK loads async (api-config → /app-config → CDN). Errors thrown by
  // later classic <script> tags — including before DOMContentLoaded — must
  // still reach Sentry. Queue them until init, then flush.
  var queued = [];
  function onEarlyError(e) {
    if (window.Sentry) return;
    queued.push(e.error || e.message);
  }
  function onEarlyRejection(e) {
    if (window.Sentry) return;
    queued.push(e.reason);
  }
  window.addEventListener('error', onEarlyError);
  window.addEventListener('unhandledrejection', onEarlyRejection);

  function flushQueued() {
    window.removeEventListener('error', onEarlyError);
    window.removeEventListener('unhandledrejection', onEarlyRejection);
    if (!window.Sentry) return;
    queued.forEach(function (err) {
      try {
        window.Sentry.captureException(err instanceof Error ? err : new Error(String(err)));
      } catch (ignore) {}
    });
    queued = [];
  }

  function setUserContext() {
    try {
      var authUser = typeof localStorage !== 'undefined' && localStorage.getItem('auth_user');
      if (authUser && window.Sentry) {
        var user = JSON.parse(authUser);
        window.Sentry.setUser({ id: user.user_id || user.email, email: user.email });
      }
    } catch (e) {}
  }

  function initSentry(dsn) {
    var script = document.createElement('script');
    script.src = 'https://browser.sentry-cdn.com/8.34.0/bundle.min.js';
    script.crossOrigin = 'anonymous';
    script.async = true;
    script.onload = function () {
      if (window.Sentry && dsn) {
        window.Sentry.init({
          dsn: dsn,
          tracesSampleRate: 0.1,
        });
        setUserContext();
        flushQueued();
      }
    };
    document.head.appendChild(script);
  }

  // Web only (desktop returns above). Sentry DSN lives on the hosted
  // /app-config; force the auth cell so this never follows a local franchise
  // onto loopback. Desktop loadAppConfig talks to loopback instead.
  function startSentry(api) {
    if (!api) return;
    fetch(api.buildUrl('/app-config', { category: 'auth' }))
      .then(function (r) { return r.json(); })
      .then(function (config) {
        if (config && config.sentryDsn) initSentry(config.sentryDsn);
      })
      .catch(function () {});
  }

  function injectApiConfig(done) {
    var script = document.createElement('script');
    script.src = '/js/config/api-config.js';
    script.onload = function () { done(window.API_CONFIG); };
    script.onerror = function () { /* same as fetch catch: skip Sentry */ };
    document.head.appendChild(script);
  }

  if (window.API_CONFIG) {
    startSentry(window.API_CONFIG);
  } else {
    // Reuse the page's own api-config.js when it is the next blocking
    // <script> (court / FCC / tutorials). Poll — do not wait for
    // DOMContentLoaded — so the DSN fetch starts as soon as that tag
    // evaluates. Inject only if the document finishes without it.
    var tries = 0;
    var poll = setInterval(function () {
      tries += 1;
      if (window.API_CONFIG) {
        clearInterval(poll);
        startSentry(window.API_CONFIG);
        return;
      }
      if (document.readyState !== 'loading' || tries > 200) {
        clearInterval(poll);
        if (window.API_CONFIG) startSentry(window.API_CONFIG);
        else injectApiConfig(startSentry);
      }
    }, 10);
  }

})();
