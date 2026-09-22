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

  // Web only (desktop returns above). Sentry DSN lives on the hosted
  // /app-config; force the auth cell so this never follows a local franchise
  // onto loopback. Desktop loadAppConfig talks to loopback instead.
  function withApiConfig(done) {
    if (window.API_CONFIG) {
      done(window.API_CONFIG);
      return;
    }
    var script = document.createElement('script');
    script.src = '/js/config/api-config.js';
    script.onload = function () { done(window.API_CONFIG); };
    script.onerror = function () { /* same as fetch catch: skip Sentry */ };
    document.head.appendChild(script);
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
      }
    };
    document.head.appendChild(script);
  }

  withApiConfig(function (api) {
    if (!api) return;
    fetch(api.buildUrl('/app-config', { category: 'auth' }))
      .then(function (r) { return r.json(); })
      .then(function (config) {
        if (config && config.sentryDsn) initSentry(config.sentryDsn);
      })
      .catch(function () {});
  });

})();
