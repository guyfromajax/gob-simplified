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
  (function loadGlobalButtonFont() {
    try {
      var head = document.head || document.getElementsByTagName("head")[0];
      if (!head) return;

      if (!document.getElementById("gob-bebas-neue-font")) {
        var fontLink = document.createElement("link");
        fontLink.id = "gob-bebas-neue-font";
        fontLink.rel = "stylesheet";
        fontLink.href = "https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap";
        head.appendChild(fontLink);
      }

      if (!document.getElementById("gob-button-font-css")) {
        var styleLink = document.createElement("link");
        styleLink.id = "gob-button-font-css";
        styleLink.rel = "stylesheet";
        styleLink.href = "/css/button-font.css";
        head.appendChild(styleLink);
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
    "/login.html",
    "/login",
    "/signup.html",
    "/signup",
    "/reset-password.html",
    "/reset-password",
    "/faqs.html",
    "/faqs"
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

  var token = typeof localStorage !== "undefined" ? localStorage.getItem("auth_token") : null;
  if (!token) {
    var redirectParam = encodeURIComponent(logicalPath + (window.location.search || ""));
    window.location.replace("/login.html?redirect=" + redirectParam);
  }

  /* Load auth bar init - shows user email on all screens except court and lineup */
  var s = document.createElement("script");
  s.src = "/js/shared/authBarInit.js";
  document.head.appendChild(s);
})();
