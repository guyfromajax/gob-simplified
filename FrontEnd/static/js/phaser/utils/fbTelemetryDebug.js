const globalScope =
  (typeof window !== "undefined" && window) ||
  (typeof globalThis !== "undefined" && globalThis) ||
  undefined;

function isEnabled() {
  if (!globalScope) return false;
  if (typeof globalScope.DEBUG_FB_TELEMETRY !== "undefined") {
    return Boolean(globalScope.DEBUG_FB_TELEMETRY);
  }
  if (typeof globalScope.DEBUG_ANIM !== "undefined") {
    return Boolean(globalScope.DEBUG_ANIM);
  }
  return false;
}

function resolveThresholds() {
  const defaults = {
    fallbackWarnRate: 0.15,
    clampWarnCount: 1,
    snapWarnCount: 1,
  };
  const raw = globalScope?.FB_TELEMETRY_THRESHOLDS;
  if (!raw || typeof raw !== "object") return defaults;
  return {
    fallbackWarnRate:
      Number.isFinite(raw.fallbackWarnRate) && raw.fallbackWarnRate >= 0
        ? Number(raw.fallbackWarnRate)
        : defaults.fallbackWarnRate,
    clampWarnCount:
      Number.isFinite(raw.clampWarnCount) && raw.clampWarnCount >= 0
        ? Number(raw.clampWarnCount)
        : defaults.clampWarnCount,
    snapWarnCount:
      Number.isFinite(raw.snapWarnCount) && raw.snapWarnCount >= 0
        ? Number(raw.snapWarnCount)
        : defaults.snapWarnCount,
  };
}

function formatPct(v) {
  return `${(Number(v || 0) * 100).toFixed(1)}%`;
}

function resolveBufferMax() {
  const n = Number(globalScope?.FB_TELEMETRY_BUFFER_MAX);
  if (Number.isFinite(n) && n >= 10) return Math.floor(n);
  return 200;
}

function pushGlobalSummaryRow(row) {
  if (!globalScope) return;
  const key = "__FB_TELEMETRY__";
  if (!Array.isArray(globalScope[key])) {
    globalScope[key] = [];
  }
  const list = globalScope[key];
  list.push(row);
  const max = resolveBufferMax();
  if (list.length > max) {
    list.splice(0, list.length - max);
  }
}

function installGlobalHelpers() {
  if (!globalScope) return;
  if (!Array.isArray(globalScope.__FB_TELEMETRY__)) {
    globalScope.__FB_TELEMETRY__ = [];
  }
  if (typeof globalScope.getFbTelemetryLatest !== "function") {
    globalScope.getFbTelemetryLatest = (n = 10) => {
      const list = Array.isArray(globalScope.__FB_TELEMETRY__) ? globalScope.__FB_TELEMETRY__ : [];
      const count = Math.max(0, Math.floor(Number(n) || 0));
      return list.slice(-count);
    };
  }
  if (typeof globalScope.clearFbTelemetry !== "function") {
    globalScope.clearFbTelemetry = () => {
      if (!Array.isArray(globalScope.__FB_TELEMETRY__)) {
        globalScope.__FB_TELEMETRY__ = [];
      } else {
        globalScope.__FB_TELEMETRY__.length = 0;
      }
    };
  }
  if (typeof globalScope.dumpFbTelemetryByBranch !== "function") {
    globalScope.dumpFbTelemetryByBranch = () => {
      const list = Array.isArray(globalScope.__FB_TELEMETRY__) ? globalScope.__FB_TELEMETRY__ : [];
      const byBranch = {};
      for (const row of list) {
        const branch = row?.branchKind || "unknown";
        const agg = (byBranch[branch] ||= {
          turns: 0,
          fallback: 0,
          required: 0,
          clamp: 0,
          snap: 0,
        });
        agg.turns += 1;
        agg.fallback += Number(row?.fbFallbackCount || 0);
        agg.required += Number(row?.fbRequiredRoleCount || 0);
        agg.clamp += Number(row?.fbClampCount || 0);
        agg.snap += Number(row?.fbSnapCount || 0);
      }
      const rows = Object.entries(byBranch).map(([branch, v]) => ({
        branch,
        turns: v.turns,
        fallback: v.fallback,
        required: v.required,
        fallbackRate: formatPct(v.required > 0 ? v.fallback / v.required : 0),
        clamp: v.clamp,
        snap: v.snap,
      }));
      rows.sort((a, b) => b.turns - a.turns || a.branch.localeCompare(b.branch));
      if (rows.length) console.table(rows);
      else console.log("[FB telemetry] no rows collected yet");
      return rows;
    };
  }
  if (typeof globalScope.dumpFbTelemetryThresholdBreaches !== "function") {
    globalScope.dumpFbTelemetryThresholdBreaches = () => {
      const list = Array.isArray(globalScope.__FB_TELEMETRY__) ? globalScope.__FB_TELEMETRY__ : [];
      const t = resolveThresholds();
      const rows = [];
      for (const row of list) {
        const fallbackRate = Number(row?.fbFallbackRate || 0);
        const clamp = Number(row?.fbClampCount || 0);
        const snap = Number(row?.fbSnapCount || 0);
        const fallbackBreach = fallbackRate >= t.fallbackWarnRate;
        const clampBreach = clamp >= t.clampWarnCount;
        const snapBreach = snap >= t.snapWarnCount;
        if (!fallbackBreach && !clampBreach && !snapBreach) continue;
        rows.push({
          turnIndex: row?.turnIndex ?? null,
          turnId: row?.turnId ?? null,
          branchKind: row?.branchKind ?? "unknown",
          resultType: row?.resultType ?? null,
          gameClock: row?.gameClock ?? null,
          quarter: row?.quarter ?? null,
          fallbackRate: formatPct(fallbackRate),
          clamp,
          snap,
          fallbackBreach,
          clampBreach,
          snapBreach,
        });
      }
      if (rows.length) console.table(rows);
      else console.log("[FB telemetry] no threshold breaches");
      return rows;
    };
  }
  if (typeof globalScope.showFbStrictConfig !== "function") {
    globalScope.showFbStrictConfig = () => {
      const defaults = ["rr_outlet_denied", "rr_hold_up", "generic_fb_shot_stop"];
      const modeRaw = globalScope.FB_STRICT_CONTRACT;
      const mode =
        modeRaw === "throw" || modeRaw === "warn" || modeRaw === "off"
          ? modeRaw
          : modeRaw === true
            ? "warn"
            : modeRaw === false
              ? "off"
              : "(auto)";
      const branchesRaw = globalScope.FB_STRICT_BRANCHES;
      let branches = defaults;
      if (Array.isArray(branchesRaw)) {
        const clean = branchesRaw
          .map((v) => (v == null ? "" : String(v).trim()))
          .filter((v) => v.length > 0);
        if (clean.length) branches = clean;
      } else if (typeof branchesRaw === "string") {
        const clean = branchesRaw
          .split(",")
          .map((v) => v.trim())
          .filter((v) => v.length > 0);
        if (clean.length) branches = clean;
      }
      const thresholds = resolveThresholds();
      const config = {
        strictMode: mode,
        strictBranches: branches,
        thresholds,
        debugFlags: {
          DEBUG_FB_TELEMETRY: Boolean(globalScope.DEBUG_FB_TELEMETRY),
          DEBUG_ANIM: Boolean(globalScope.DEBUG_ANIM),
        },
      };
      console.log("[FB strict config]", config);
      return config;
    };
  }
}

function getSession(scene) {
  if (!scene.__fbTelemetryDebugSession) {
    scene.__fbTelemetryDebugSession = {
      eventsSeen: 0,
      summaries: 0,
      byBranch: {},
      totals: {
        fallback: 0,
        required: 0,
        clamp: 0,
        snap: 0,
      },
    };
  }
  return scene.__fbTelemetryDebugSession;
}

export function createFbTelemetryDebugListener(scene) {
  installGlobalHelpers();
  if (!isEnabled()) return null;
  const thresholds = resolveThresholds();

  return function onAnimTelemetry(payload = {}) {
    const event = payload?.event;
    if (!event || typeof event !== "string") return;
    if (!event.startsWith("fb_")) return;

    const session = getSession(scene);
    session.eventsSeen += 1;

    if (event !== "fb_telemetry_summary") return;

    session.summaries += 1;
    const branch = payload.branchKind || "unknown";
    const branchAgg = (session.byBranch[branch] ||= {
      turns: 0,
      fallback: 0,
      required: 0,
      clamp: 0,
      snap: 0,
    });

    const fallback = Number(payload.fbFallbackCount || 0);
    const required = Number(payload.fbRequiredRoleCount || 0);
    const clamp = Number(payload.fbClampCount || 0);
    const snap = Number(payload.fbSnapCount || 0);
    const fallbackRate = required > 0 ? fallback / required : 0;
    const summaryRow = {
      event: event,
      timestampMs: payload.timestampMs ?? Date.now(),
      turnIndex: payload.turnIndex ?? null,
      turnId: payload.turnId ?? null,
      resultType: payload.resultType ?? null,
      branchKind: branch,
      offenseTeamId: payload.offenseTeamId ?? null,
      gameClock: payload.gameClock ?? null,
      quarter: payload.quarter ?? null,
      fbFallbackCount: fallback,
      fbRequiredRoleCount: required,
      fbFallbackRate: fallbackRate,
      fbClampCount: clamp,
      fbSnapCount: snap,
    };
    pushGlobalSummaryRow(summaryRow);

    branchAgg.turns += 1;
    branchAgg.fallback += fallback;
    branchAgg.required += required;
    branchAgg.clamp += clamp;
    branchAgg.snap += snap;

    session.totals.fallback += fallback;
    session.totals.required += required;
    session.totals.clamp += clamp;
    session.totals.snap += snap;

    const prefix = `[FB telemetry] turn=${payload.turnIndex ?? "?"} branch=${branch}`;
    console.log(
      `${prefix} fallback=${fallback}/${required} (${formatPct(fallbackRate)}) clamp=${clamp} snap=${snap}`
    );

    if (fallbackRate >= thresholds.fallbackWarnRate) {
      console.warn(
        `${prefix} fallback rate warning: ${formatPct(fallbackRate)} >= ${formatPct(
          thresholds.fallbackWarnRate
        )}`
      );
    }
    if (clamp >= thresholds.clampWarnCount) {
      console.warn(`${prefix} clamp warning: ${clamp} >= ${thresholds.clampWarnCount}`);
    }
    if (snap >= thresholds.snapWarnCount) {
      console.warn(`${prefix} snap warning: ${snap} >= ${thresholds.snapWarnCount}`);
    }
  };
}

export function flushFbTelemetryDebugSummary(scene) {
  if (!isEnabled()) return;
  const s = scene?.__fbTelemetryDebugSession;
  if (!s || s.summaries === 0) return;

  const totalRate = s.totals.required > 0 ? s.totals.fallback / s.totals.required : 0;
  console.log(
    `[FB telemetry][session] turns=${s.summaries} events=${s.eventsSeen} fallback=${s.totals.fallback}/${s.totals.required} (${formatPct(
      totalRate
    )}) clamp=${s.totals.clamp} snap=${s.totals.snap}`
  );

  const branchRows = Object.entries(s.byBranch).map(([branch, v]) => ({
    branch,
    turns: v.turns,
    fallback: v.fallback,
    required: v.required,
    fallbackRate: formatPct(v.required > 0 ? v.fallback / v.required : 0),
    clamp: v.clamp,
    snap: v.snap,
  }));
  if (branchRows.length) {
    console.table(branchRows);
  }
}
