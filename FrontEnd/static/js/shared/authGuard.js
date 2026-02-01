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
  var publicPaths = [
    "/",
    "/homepage.html",
    "/homepage",
    "/login.html",
    "/login",
    "/signup.html",
    "/signup"
  ];

  var path = window.location.pathname;
  // Normalize: ensure path consistency (trim trailing slash for root)
  var pathNormalized = path === "" ? "/" : path.replace(/\/$/, "") || "/";

  var isPublic = publicPaths.some(function (p) {
    var norm = p.replace(/\/$/, "") || "/";
    return pathNormalized === norm || path === p;
  });

  if (isPublic) {
    return;
  }

  var token = typeof localStorage !== "undefined" ? localStorage.getItem("auth_token") : null;
  if (!token) {
    var redirectParam = encodeURIComponent(path + (window.location.search || ""));
    window.location.replace("/login.html?redirect=" + redirectParam);
  }

  /* Load auth bar init - shows user email on all screens except court and lineup */
  var s = document.createElement("script");
  s.src = "/js/shared/authBarInit.js";
  document.head.appendChild(s);
})();
