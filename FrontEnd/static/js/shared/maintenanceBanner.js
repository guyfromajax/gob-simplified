/**
 * Maintenance Warning Banner
 *
 * Fetches remote JSON config from /config/maintenance.json and shows a dismissible
 * banner when enabled. Dismissal is persisted in localStorage keyed by config `id`.
 *
 * starts_at_iso:
 * - With Z or a numeric offset (e.g. ...Z, +00:00, -05:00): parsed as an absolute instant (UTC / offset).
 * - Naive local time (e.g. 2026-02-17T15:00:00, no Z/offset): interpreted as wall clock in
 *   `starts_at_timezone` (default America/New_York — US Eastern, Philadelphia).
 *
 * This script is intentionally dependency-free and safe to include on every page.
 */
(function () {
  var CONFIG_URL = "/config/maintenance.json";
  var POLL_MS = 60 * 1000;
  var BANNER_ID = "maintenance-warning-banner";
  var DEFAULT_WALL_CLOCK_TZ = "America/New_York";

  function nowMs() {
    return Date.now();
  }

  function safeParseInt(v, fallback) {
    var n = parseInt(v, 10);
    return isNaN(n) ? fallback : n;
  }

  /** True if the string ends with Z or a numeric UTC offset (absolute ISO-8601 instant). */
  function hasExplicitIsoZone(iso) {
    var t = String(iso).trim();
    if (!t) return false;
    if (/Z$/i.test(t)) return true;
    return /[+-]\d{2}:\d{2}$/.test(t) || /[+-]\d{4}$/.test(t);
  }

  /**
   * Parse YYYY-MM-DDThh:mm[:ss] with no zone as wall time in `timeZone`, return UTC ms.
   * Uses Intl iteration so DST (America/New_York) is handled without extra dependencies.
   */
  function parseNaiveWallTimeToUtcMs(iso, timeZone) {
    var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(String(iso).trim());
    if (!m) return null;
    var y = +m[1];
    var mo = +m[2];
    var d = +m[3];
    var hh = +m[4];
    var mi = +m[5];
    var ss = m[6] != null ? +m[6] : 0;
    if (
      [y, mo, d, hh, mi, ss].some(function (n) {
        return isNaN(n);
      })
    ) {
      return null;
    }

    var fmt;
    try {
      fmt = new Intl.DateTimeFormat("en-US", {
        timeZone: timeZone,
        hour12: false,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch (e) {
      return null;
    }

    function partsAt(ms) {
      var parts = fmt.formatToParts(new Date(ms));
      var o = {};
      for (var i = 0; i < parts.length; i++) {
        if (parts[i].type !== "literal") o[parts[i].type] = parts[i].value;
      }
      return {
        y: +o.year,
        m: +o.month,
        d: +o.day,
        h: +o.hour,
        mi: +o.minute,
        s: o.second != null ? +o.second : 0,
      };
    }

    var instant = Date.UTC(y, mo - 1, d, hh, mi, ss);
    var maxIter = 12;
    for (var iter = 0; iter < maxIter; iter++) {
      var p = partsAt(instant);
      if (p.y === y && p.m === mo && p.d === d && p.h === hh && p.mi === mi && p.s === ss) {
        return instant;
      }
      var want = Date.UTC(y, mo - 1, d, hh, mi, ss);
      var got = Date.UTC(p.y, p.m - 1, p.d, p.h, p.mi, p.s);
      instant += want - got;
    }
    return null;
  }

  function safeParseTimeMs(iso, timeZone) {
    if (!iso || typeof iso !== "string") return null;
    var trimmed = iso.trim();
    if (!trimmed) return null;

    var tz = timeZone && typeof timeZone === "string" && timeZone.trim() ? timeZone.trim() : DEFAULT_WALL_CLOCK_TZ;

    if (hasExplicitIsoZone(trimmed)) {
      var t = Date.parse(trimmed);
      return isNaN(t) ? null : t;
    }

    var wall = parseNaiveWallTimeToUtcMs(trimmed, tz);
    if (wall != null) return wall;

    var fallback = Date.parse(trimmed);
    return isNaN(fallback) ? null : fallback;
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

    var startsAtMs = safeParseTimeMs(config.starts_at_iso, config.starts_at_timezone);
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

