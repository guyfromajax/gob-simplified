/**
 * Step 12.4: Admin-only pages (production only).
 * Include after authGuard.js on builder pages. In production, redirects non-admins to mode-select.
 */
(function () {
  var path = window.location.pathname;
  var builderPaths = [
    "/play-builder.html",
    "/play-builder-v2.html",
    "/plays-builder.html",
    "/fcp-skeletons.html",
    "/hct-skeletons.html"
  ];
  var isBuilderPage = builderPaths.some(function (p) {
    return path === p || path.indexOf(p) === 0;
  });
  var host = window.location.hostname;
  var isProduction = host === "www.geekedoutbasketball.com" || host === "geekedoutbasketball.com";
  console.log("[adminGuard] path=" + path + " host=" + host + " isBuilderPage=" + isBuilderPage + " isProduction=" + isProduction);
  if (!isBuilderPage || !isProduction) return;

  var token = typeof localStorage !== "undefined" ? localStorage.getItem("auth_token") : null;
  if (!token) return; // Auth guard will have redirected to login
  console.log("[adminGuard] token present, fetching /api/auth/me");

  function redirectToModeSelect() {
    window.location.replace("/mode-select.html");
  }
  // Auth is always-remote. Resolve through the routing table, not a local copy
  // of the hostname sniff. adminGuard loads before api-config on builder pages,
  // so pull it in if needed (same host/path as API_CONFIG.getBaseUrl()).
  function withApiConfig(done) {
    if (window.API_CONFIG) {
      done(window.API_CONFIG);
      return;
    }
    var script = document.createElement("script");
    script.src = "/js/config/api-config.js";
    script.onload = function () { done(window.API_CONFIG); };
    script.onerror = function () { redirectToModeSelect(); };
    document.head.appendChild(script);
  }
  withApiConfig(function (api) {
    var url = api.buildUrl("/api/auth/me", { category: "auth" });
    fetch(url, { headers: { "Authorization": "Bearer " + token } })
    .then(function (r) {
      if (!r.ok) return null;
      return r.json();
    })
    .then(function (me) {
      console.log("[adminGuard] me=" + (me ? JSON.stringify(me) : "null") + " role=" + (me ? me.role : "N/A"));
      if (!me || me.role !== "admin") {
        console.log("[adminGuard] redirecting to mode-select");
        redirectToModeSelect();
      } else {
        console.log("[adminGuard] admin OK, not redirecting");
      }
    })
    .catch(function (err) {
      console.log("[adminGuard] fetch error", err);
      redirectToModeSelect();
    });
  });
})();
