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
  if (!isBuilderPage || !isProduction) return;

  var token = typeof localStorage !== "undefined" ? localStorage.getItem("auth_token") : null;
  if (!token) return; // Auth guard will have redirected to login

  function getApiBase() {
    if (window.API_BASE_URL) return window.API_BASE_URL;
    var h = window.location.hostname;
    if (h === "www.geekedoutbasketball.com" || h === "geekedoutbasketball.com") return "https://api.geekedoutbasketball.com";
    if (h === "staging.geekedoutbasketball.com") return "https://api-staging.geekedoutbasketball.com";
    if (h.indexOf("netlify.app") !== -1 && h.indexOf("staging") !== -1) return "https://gob-simplified-staging.up.railway.app";
    return "http://localhost:8000";
  }
  function redirectToModeSelect() {
    window.location.replace("/mode-select.html");
  }
  var url = getApiBase() + "/api/auth/me";
  fetch(url, { headers: { "Authorization": "Bearer " + token } })
    .then(function (r) {
      if (!r.ok) return null;
      return r.json();
    })
    .then(function (me) {
      if (!me || me.role !== "admin") {
        redirectToModeSelect();
      }
    })
    .catch(function () {
      redirectToModeSelect();
    });
})();
