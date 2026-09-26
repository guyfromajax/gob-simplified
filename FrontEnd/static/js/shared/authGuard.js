function franchiseCtx() {
  return typeof window !== 'undefined' ? window.FranchiseContext : null;
}
function liveParams() {
  var ctx = franchiseCtx();
  if (!ctx) return emptyParams();
  return ctx.toSearchParams();
}
function emptyParams() {
  var ctx = franchiseCtx();
  if (ctx) return ctx.createParams();
  return { toString: function () { return ''; }, get: function () { return null; }, set: function () {}, delete: function () {}, forEach: function () {} };
}
function currentSearch() {
  const s = liveParams().toString();
  return s ? '?' + s : '';
}
function shellFocusNavigation(pathname, search) {
  var path = pathname || '';
  var q = new URLSearchParams(search || '');
  if (path === '/box-score.html') return !q.get('return_url');
  if (path === '/recruiting.html' && q.get('action') === 'run') return true;
  return path === '/set-lineup.html'
    || path === '/training.html'
    || path === '/training-report.html'
    || path === '/training-squad-report.html'
    || path === '/training-playbooks.html'
    || path === '/cut-players.html'
    || path === '/game-plan.html'
    || path === '/playbooks.html'
    || path === '/playbook-report.html';
}

function cloneParams(params) {
  const out = emptyParams();
  if (params && typeof params.forEach === 'function') {
    params.forEach((value, key) => out.set(key, value));
  }
  return out;
}

/**
 * Auth Guard - Protects pages from unauthenticated access
 *
 * Include this script in the <head> of every HTML page.
 * Pages in the allowlist are public; all others require auth_token in localStorage.
 * If not authenticated, redirects to login with ?redirect=<current-path>
 *
 * Public pages: homepage, login, signup (and root /)
 */
(function () {
  (function loadClientStore() {
    try {
      var head = document.head || document.documentElement;
      if (!head || document.querySelector('script[src="/js/shared/gobStore.js"]')) return;
      var script = document.createElement('script');
      script.src = '/js/shared/gobStore.js';
      script.async = false;
      head.appendChild(script);
    } catch (e) {}
  })();

  (function loadGlobalButtonFont() {
    try {
      var head = document.head || document.getElementsByTagName("head")[0];
      if (!head) return;

      if (!document.getElementById("gob-bebas-neue-font")) {
        var fontLink = document.createElement("link");
        fontLink.id = "gob-bebas-neue-font";
        fontLink.rel = "stylesheet";
        fontLink.href = "/fonts/app-fonts.css";
        head.appendChild(fontLink);
      }

      if (!document.getElementById("gob-button-font-css")) {
        var styleLink = document.createElement("link");
        styleLink.id = "gob-button-font-css";
        styleLink.rel = "stylesheet";
        styleLink.href = "/css/button-font.css";
        head.appendChild(styleLink);
      }

      var shellPages = {
        "/recruiting.html": 1,
        "/rankings.html": 1,
        "/schedule.html": 1,
        "/practice-squad-standings.html": 1,
        "/practice-squad-bracket.html": 1,
        "/brackets.html": 1,
        "/awards.html": 1,
        "/news.html": 1,
        "/leaders.html": 1,
        "/standings.html": 1,
        "/team-stats.html": 1,
        "/stats.html": 1,
        "/player-detail.html": 1,
        "/team-roster-view.html": 1,
        "/set-lineup.html": 1,
        "/training.html": 1,
        "/training-report.html": 1,
        "/training-squad-report.html": 1,
        "/training-playbooks.html": 1,
        "/cut-players.html": 1,
        "/game-plan.html": 1,
        "/playbooks.html": 1,
        "/playbook-report.html": 1,
        "/box-score.html": 1
      };
      if (shellPages[window.location.pathname]) {
        ["/css/gob-tokens.css", "/css/gob-components.css", "/css/gob-shell.css"].forEach(function (href) {
          if (document.querySelector('link[href="' + href + '"]')) return;
          var link = document.createElement("link");
          link.rel = "stylesheet";
          link.href = href;
          head.appendChild(link);
        });
        if (shellFocusNavigation(window.location.pathname, window.location.search)) {
          var vtOff = document.createElement("style");
          vtOff.textContent = "@view-transition { navigation: none; }";
          head.appendChild(vtOff);
        }
        ["/js/shared/gobAdvance.js", "/js/shared/gobShell.js"].forEach(function (src) {
          if (document.querySelector('script[src="' + src + '"]')) return;
          var script = document.createElement("script");
          script.src = src;
          script.async = false;
          head.appendChild(script);
        });
      }
    } catch (e) {
      // ignore
    }
  })();

  // Always load the maintenance banner script (even on public pages).
  // authGuard early-returns on public paths, but we still want the banner everywhere.
  (function loadMaintenanceBanner() {
    try {
      var b = document.createElement("script");
      b.src = "/js/shared/maintenanceBanner.js";
      b.async = true;
      (document.head || document.getElementsByTagName("head")[0]).appendChild(b);
    } catch (e) {
      // ignore
    }
  })();

  var publicPaths = [
    "/",
    "/homepage.html",
    "/homepage",
    "/homepage-v3.html",
    "/homepage-v3",
    "/login.html",
    "/login",
    "/signup.html",
    "/signup",
    "/reset-password.html",
    "/reset-password",
    "/faqs.html",
    "/faqs",
    "/privacy.html",
    "/privacy",
    "/terms.html",
    "/terms"
  ];

  var path = window.location.pathname;
  // Normalize: ensure path consistency (trim trailing slash for root)
  var pathNormalized = path === "" ? "/" : path.replace(/\/$/, "") || "/";
  // Local dev can serve pages under /static/*; normalize to logical route path.
  var logicalPath = pathNormalized.indexOf("/static/") === 0
    ? (pathNormalized.slice("/static".length) || "/")
    : pathNormalized;

  var isPublic = publicPaths.some(function (p) {
    var norm = p.replace(/\/$/, "") || "/";
    return logicalPath === norm || pathNormalized === norm || path === p;
  });

  if (isPublic) {
    return;
  }

  // Desktop: the loopback engine injects a local principal server-side.
  // Login is always-remote, so sending the user there strands them offline.
  // window.GOB_BUILD_PROFILE is set by the Electron preload before any page
  // script runs. The web build never sets it, so this branch is dead there.
  var isDesktop = typeof window !== "undefined" && window.GOB_BUILD_PROFILE === "desktop";
  if (!isDesktop) {
    var token = typeof localStorage !== "undefined" ? localStorage.getItem("auth_token") : null;
    if (!token) {
      var redirectParam = encodeURIComponent(logicalPath + (currentSearch() || ""));
      window.location.replace("/login.html?redirect=" + redirectParam);
    }
  }

  /* Franchise LS helper before auth bar (multi-slot Phase 3). */
  var fls = document.createElement("script");
  fls.src = "/js/shared/franchiseLocalStorage.js";
  fls.onload = function () {
    var s = document.createElement("script");
    s.src = "/js/shared/authBarInit.js";
    document.head.appendChild(s);
  };
  fls.onerror = function () {
    var s = document.createElement("script");
    s.src = "/js/shared/authBarInit.js";
    document.head.appendChild(s);
  };
  document.head.appendChild(fls);
})();
