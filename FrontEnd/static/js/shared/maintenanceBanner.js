/**
 * Maintenance Warning Banner
 *
 * Fetches remote JSON config from /config/maintenance.json and shows a dismissible
 * banner when enabled. Dismissal is persisted in localStorage keyed by config `id`.
 *
 * This script is intentionally dependency-free and safe to include on every page.
 */
(function () {
  var CONFIG_URL = "/config/maintenance.json";
  var POLL_MS = 60 * 1000;
  var BANNER_ID = "maintenance-warning-banner";

  function nowMs() {
    return Date.now();
  }

  function safeParseInt(v, fallback) {
    var n = parseInt(v, 10);
    return isNaN(n) ? fallback : n;
  }

  function safeParseTimeMs(iso) {
    if (!iso || typeof iso !== "string") return null;
    var t = Date.parse(iso);
    return isNaN(t) ? null : t;
  }

  function getDismissedIdKey() {
    return "maintenance_banner_dismissed_id";
  }

  function getDismissedId() {
    try {
      return typeof localStorage !== "undefined" ? localStorage.getItem(getDismissedIdKey()) : null;
    } catch (e) {
      return null;
    }
  }

  function setDismissedId(id) {
    try {
      if (typeof localStorage === "undefined") return;
      localStorage.setItem(getDismissedIdKey(), id);
    } catch (e) {
      // ignore (private mode / disabled storage)
    }
  }

  function removeBanner() {
    var existing = document.getElementById(BANNER_ID);
    if (existing && existing.parentNode) existing.parentNode.removeChild(existing);
  }

  /** Pages where we defer the banner so users in an active game are not interrupted. */
  function isDeferredPage() {
    try {
      var path = (typeof window !== "undefined" && window.location && window.location.pathname) ? window.location.pathname : "";
      return /court\.html|set-lineup\.html|game-plan\.html/.test(path);
    } catch (e) {
      return false;
    }
  }

  function shouldShow(config) {
    if (!config || config.enabled !== true) return false;
    if (isDeferredPage()) return false;

    var startsAtMs = safeParseTimeMs(config.starts_at_iso);
    if (startsAtMs == null) {
      // Manual override: enabled=true and no starts_at_iso means "show immediately".
      return true;
    }

    var minutesBefore = safeParseInt(config.show_minutes_before, 60);
    var windowStart = startsAtMs - minutesBefore * 60 * 1000;
    return nowMs() >= windowStart;
  }

  function buildBanner(config) {
    var container = document.createElement("div");
    container.id = BANNER_ID;

    var topOffsetPx = document.body && document.body.classList && document.body.classList.contains("has-auth-bar") ? 56 : 12;

    container.style.position = "fixed";
    container.style.top = topOffsetPx + "px";
    container.style.right = "12px";
    container.style.maxWidth = "420px";
    container.style.background = "#b00020";
    container.style.color = "#fff";
    container.style.border = "2px solid rgba(255,255,255,0.35)";
    container.style.borderRadius = "10px";
    container.style.padding = "12px 40px 12px 12px";
    container.style.fontFamily = "system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif";
    container.style.fontSize = "14px";
    container.style.lineHeight = "1.25";
    container.style.boxShadow = "0 10px 30px rgba(0,0,0,0.35)";
    container.style.zIndex = "99999";

    var msg = document.createElement("div");
    msg.textContent = (config && config.message) ? String(config.message) : "Maintenance is scheduled soon.";
    msg.style.marginRight = "6px";
    container.appendChild(msg);

    if (config && config.details_url) {
      var url = String(config.details_url).trim();
      if (url) {
        var link = document.createElement("a");
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "Details";
        link.style.display = "inline-block";
        link.style.marginTop = "8px";
        link.style.color = "#fff";
        link.style.textDecoration = "underline";
        container.appendChild(link);
      }
    }

    var closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.setAttribute("aria-label", "Dismiss maintenance warning");
    closeBtn.textContent = "X";
    closeBtn.style.position = "absolute";
    closeBtn.style.top = "8px";
    closeBtn.style.right = "10px";
    closeBtn.style.width = "24px";
    closeBtn.style.height = "24px";
    closeBtn.style.borderRadius = "6px";
    closeBtn.style.border = "1px solid rgba(255,255,255,0.5)";
    closeBtn.style.background = "rgba(0,0,0,0.15)";
    closeBtn.style.color = "#fff";
    closeBtn.style.cursor = "pointer";
    closeBtn.style.fontWeight = "700";
    closeBtn.style.lineHeight = "22px";
    closeBtn.style.padding = "0";
    closeBtn.addEventListener("click", function () {
      var id = (config && config.id) ? String(config.id) : "unknown";
      setDismissedId(id);
      removeBanner();
    });
    container.appendChild(closeBtn);

    return container;
  }

  function applyConfig(config) {
    if (!shouldShow(config)) {
      removeBanner();
      return;
    }

    var currentId = (config && config.id) ? String(config.id) : "unknown";
    if (getDismissedId() === currentId) {
      removeBanner();
      return;
    }

    var existing = document.getElementById(BANNER_ID);
    if (existing) return;

    var banner = buildBanner(config);
    (document.body || document.documentElement).appendChild(banner);
  }

  function fetchConfig() {
    var url = CONFIG_URL + "?t=" + nowMs();
    return fetch(url, { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("maintenance.json fetch failed: " + res.status);
        return res.json();
      });
  }

  function tick() {
    fetchConfig()
      .then(function (cfg) {
        applyConfig(cfg);
      })
      .catch(function () {
        // Fail closed: if config can't be fetched, don't show anything.
        removeBanner();
      });
  }

  function start() {
    if (typeof window === "undefined" || typeof document === "undefined") return;
    tick();
    window.setInterval(tick, POLL_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();

