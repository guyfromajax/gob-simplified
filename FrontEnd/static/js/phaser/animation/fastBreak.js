import * as Phaser from "https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.esm.js";
import { gridToPixels } from "../utils/gridToPixels.js";
import { attachBallToPlayer } from "./BallControllerAdapter.js";
import { tweenPlayerTo, runPass, detachBall, getBallDuration } from "./ballTween.js";
import { animateShotToRim } from "./ballAnimationSimple.js";
import animationConfig from "./animation_config.js";
import {
  HOME_RIM_COORDS,
  AWAY_RIM_COORDS,
  HOME_TOP_KEY,
  AWAY_TOP_KEY,
  getMadeShotSweetSpotGrid,
} from "./courtConstants.js";
import { States, safeTransition } from "../state/gameStateMachine.js";
import { getCurrentOwner } from "./BallControllerAdapter.js";
import { runInboundSetup, getPlayerDuration, horizontalGridUnitsForDurationMs } from "./turnAnimation.js";
import { pauseTweensOfPlayerSprites } from "../utils/playerSpriteTweenPause.js";
import { getAnimationEndGridForPlayer } from "../utils/animationEndFromTurn.js";
import { animationDebugLog, isAnimationDebugEnabled } from "../utils/debugFlags.js";
import { appendToTextScroll } from "../utils/textScroll.js";
import { enforceUnitCompletionContract } from "./unitCompletionContract.js";
import { CLAMP_BOUNDS } from "./courtClamp.js";
import * as fastBreakConstants from "../constants/fastBreakConstants.js";

const {
  REBOUNDER_X_MIN,
  REBOUNDER_X_MAX,
  REBOUNDER_Y_RANGE,
  SHOT_ATTEMPT_REBOUNDER_Y_RANGE,
  STEAL_ENTRY_MOVE_X_MIN,
  STEAL_ENTRY_MOVE_X_MAX,
  STEAL_ENTRY_MOVE_Y_RANGE,
  STEAL_ENTRY_Y_MIN,
  STEAL_ENTRY_Y_MAX,
  fastBreakShotDefenderGridVsShooter,
} = fastBreakConstants;
const fastBreakSecondaryShotDefenderGrid =
  fastBreakConstants.fastBreakSecondaryShotDefenderGrid ??
  function fallbackFastBreakSecondaryShotDefenderGrid(primaryX, primaryY, sourceY) {
    return {
      x: Phaser.Math.Clamp(primaryX, GRID_MIN_X, GRID_MAX_X),
      y: Phaser.Math.Clamp(
        primaryY + (sourceY > primaryY ? 3 : -3),
        GRID_MIN_Y,
        GRID_MAX_Y,
      ),
    };
  };


const GRID_MIN_X = CLAMP_BOUNDS.minX;
const GRID_MAX_X = CLAMP_BOUNDS.maxX;
const GRID_MIN_Y = CLAMP_BOUNDS.minY;
const GRID_MAX_Y = CLAMP_BOUNDS.maxY;

/**
 * Phase 2 resolution kind for fast break turns — mirrors Rim Runner payload contract
 * (`docs/To Do/FB_Playcall_Update.md`, `tests/fixtures/rim_runner_contract/`).
 *
 * @param {object} turnData
 * @param {{ isBlockingFoul: boolean }} opts
 * @returns {'fast_break_shot'|'fast_break_shot_foul'|'rim_runner_steal'|'rim_runner_bat_oob'|'rim_runner_hco_settle'|'generic_fb_stop'}
 */
function classifyFastBreakPhase2(turnData, { isBlockingFoul }) {
  const result = turnData.result_type;
  const isTriangleSeq =
    turnData.fast_break_play === "triangle" ||
    turnData.roles?.triangle_sequence === true ||
    Boolean(turnData.roles?.triangle_setup_phase);
  if (result === "MAKE" || result === "MISS" || result === "BLOCK") {
    return "fast_break_shot";
  }
  if (result === "CHARGE" || isBlockingFoul) {
    return "fast_break_shot_foul";
  }
  // Outlet-denied must route through RR denied settle, even for Triangle-tagged
  // possessions that share the same burst/denied handoff contract.
  if (turnData.rim_runner_outlet_failed) {
    return "rim_runner_hco_settle";
  }

  const isRimRunnerSeq =
    turnData.fast_break_play === "rim_runner" ||
    turnData.roles?.rim_runner_sequence === true;

  if (isRimRunnerSeq) {
    if (turnData.rim_runner_interception && result === "STEAL") {
      return "rim_runner_steal";
    }
    if (turnData.rim_runner_bat_oob && result === "DEAD BALL") {
      return "rim_runner_bat_oob";
    }
    if (result === "DEFENSIVE_STOP" || turnData.rim_runner_outlet_failed) {
      return "rim_runner_hco_settle";
    }
  }

  if (isTriangleSeq && (result === "DEFENSIVE_STOP" || turnData.triangle_enter_hco)) {
    return "triangle_hco_settle";
  }

  return "generic_fb_stop";
}

function deriveFbBranchKind(turnData, phase2Kind) {
  if (phase2Kind === "fast_break_shot" || phase2Kind === "fast_break_shot_foul") {
    return turnData.fast_break_play === "rim_runner" || turnData.roles?.rim_runner_sequence
      ? "rr_lane_shot"
      : "generic_fb_shot_stop";
  }
  if (phase2Kind === "rim_runner_steal") return "rr_interception";
  if (phase2Kind === "rim_runner_bat_oob") return "rr_bat_oob";
  if (phase2Kind === "rim_runner_hco_settle") {
    if (turnData.rim_runner_outlet_failed) return "rr_outlet_denied";
    return "rr_hold_up";
  }
  if (phase2Kind === "triangle_hco_settle") return "triangle_hco";
  return "generic_fb_shot_stop";
}

function initFbTelemetryContext(scene, { turnData, turnIndex, branchKind }) {
  scene.__fbTelemetry = {
    turnIndex,
    turnId: turnData?.turn_count ?? turnData?.id ?? null,
    resultType: turnData?.result_type ?? null,
    branchKind,
    offenseTeamId: turnData?.offense_team_id ?? scene?.offenseTeamId ?? null,
    gameClock: scene?.simData?.clock ?? null,
    quarter: turnData?.quarter ?? scene?.quarter ?? null,
    counters: {
      fbFallbackCount: 0,
      fbRequiredRoleCount: 0,
      fbClampCount: 0,
      fbSnapCount: 0,
      fbAwaitTimeoutCount: 0,
    },
  };
}

function getFbTelemetry(scene) {
  return scene?.__fbTelemetry ?? null;
}

function getFbContractGlobalScope() {
  return (
    (typeof window !== "undefined" && window) ||
    (typeof globalThis !== "undefined" && globalThis) ||
    null
  );
}

const FB_STRICT_DEFAULT_BRANCHES = [
  "rr_lane_shot",
  "rr_outlet_denied",
  "rr_hold_up",
  "generic_fb_shot_stop",
];

function isLocalDevFbContractDefault(scope) {
  const host = scope?.location?.hostname;
  return host === "localhost" || host === "127.0.0.1";
}

function isCriticalEventPatternEnabled() {
  const scope = getFbContractGlobalScope();
  const raw = scope?.UESS_FB_CRITICAL_EVENT_PATTERN;
  return raw === true || raw === "on";
}

function resolveFbStrictContractMode() {
  const scope = getFbContractGlobalScope();
  const raw = scope?.FB_STRICT_CONTRACT;
  if (raw === "throw") return "throw";
  if (raw === "warn" || raw === true) return "warn";
  if (raw === "off" || raw === false) return "off";
  // Local default is strict throw-mode for fail-fast contract checks.
  if (isLocalDevFbContractDefault(scope)) {
    return "throw";
  }
  // Non-local debug sessions default to warnings.
  if (scope?.DEBUG_FB_TELEMETRY === true || isAnimationDebugEnabled()) {
    return "warn";
  }
  return "off";
}

function resolveFbStrictBranches() {
  const defaults = FB_STRICT_DEFAULT_BRANCHES;
  const scope = getFbContractGlobalScope();
  const raw = scope?.FB_STRICT_BRANCHES;
  if (Array.isArray(raw)) {
    const cleaned = raw
      .map((v) => (v == null ? "" : String(v).trim()))
      .filter((v) => v.length > 0);
    return cleaned.length ? new Set(cleaned) : new Set(defaults);
  }
  if (typeof raw === "string") {
    const cleaned = raw
      .split(",")
      .map((v) => String(v).trim())
      .filter((v) => v.length > 0);
    return cleaned.length ? new Set(cleaned) : new Set(defaults);
  }
  return new Set(defaults);
}

function shouldEnforceFbContractForBranch(scene) {
  const t = getFbTelemetry(scene);
  const branch = t?.branchKind;
  if (!branch) return false;
  return resolveFbStrictBranches().has(branch);
}

function enforceFbContractGuardrail(scene, {
  playerId,
  role,
  requiredEndpointType,
  reason,
} = {}) {
  if (!shouldEnforceFbContractForBranch(scene)) return;
  const mode = resolveFbStrictContractMode();
  if (mode === "off") return;
  const t = getFbTelemetry(scene);
  const branch = t?.branchKind ?? "unknown_branch";
  const msg =
    `[FB contract] missing required endpoint in strict branch ` +
    `(branch=${branch}, playerId=${playerId ?? "?"}, role=${role ?? "?"}, ` +
    `required=${requiredEndpointType ?? "?"}, reason=${reason ?? "unknown"})`;
  if (mode === "throw") {
    throw new Error(msg);
  }
  console.warn(msg, {
    branch,
    playerId,
    role,
    requiredEndpointType,
    reason,
    turnIndex: t?.turnIndex ?? null,
    turnId: t?.turnId ?? null,
  });
}

function emitFbTelemetry(scene, event, payload = {}) {
  const t = getFbTelemetry(scene);
  if (!t) return;
  const envelope = {
    event,
    turnIndex: t.turnIndex,
    turnId: t.turnId,
    resultType: t.resultType,
    branchKind: t.branchKind,
    offenseTeamId: t.offenseTeamId,
    gameClock: t.gameClock,
    quarter: t.quarter,
    timestampMs: Date.now(),
  };
  const row = { ...envelope, ...payload };
  scene.events?.emit?.("animTelemetry", row);
  if (isAnimationDebugEnabled()) {
    animationDebugLog("FB telemetry", row);
  }
}

function startRebounderCatchMonitor({
  scene,
  rebounderTweens,
  rebounderSprite,
  ballGrid,
  width,
  height,
}) {
  if (!scene || !rebounderSprite || !Array.isArray(rebounderTweens) || rebounderTweens.length === 0) {
    return () => {};
  }
  const scope = (typeof window !== "undefined" && window) || globalThis;
  const maxMonitorMs = Math.max(
    0,
    Number(scope?.UESS_FB_REBOUND_MONITOR_MAX_MS ?? 450) || 450
  );
  const pollMs = Math.max(
    10,
    Number(scope?.UESS_FB_REBOUND_MONITOR_POLL_MS ?? 40) || 40
  );
  const startDelayMs = Math.max(
    0,
    Number(scope?.UESS_FB_REBOUND_MONITOR_START_DELAY_MS ?? 60) || 60
  );
  const ballBouncePx = gridToPixels(ballGrid.x, ballGrid.y, width, height);
  const monitorStartMs = Date.now();
  let monitoringActive = true;
  let handle = null;
  const stopAllRebounderTweens = () => {
    rebounderTweens.forEach((tween) => {
      if (tween && tween.isPlaying) {
        tween.stop();
      }
    });
  };
  const schedule = (fn, ms) => {
    if (scene.time?.delayedCall) {
      handle = scene.time.delayedCall(ms, fn);
    } else {
      handle = setTimeout(fn, ms);
    }
  };
  const clearScheduled = () => {
    if (!handle) return;
    if (scene.time?.delayedCall && typeof handle.remove === "function") {
      handle.remove(false);
    } else {
      clearTimeout(handle);
    }
    handle = null;
  };
  const checkRebounderReached = () => {
    if (!monitoringActive) return;
    const elapsedMs = Date.now() - monitorStartMs;
    if (elapsedMs >= maxMonitorMs) {
      // Deterministic fallback: stop rebounder drifts so they cannot leak into next boundary.
      stopAllRebounderTweens();
      monitoringActive = false;
      return;
    }
    const distanceToBall = Math.hypot(
      rebounderSprite.x - ballBouncePx.x,
      rebounderSprite.y - ballBouncePx.y
    );
    if (distanceToBall < 30) {
      stopAllRebounderTweens();
      monitoringActive = false;
      return;
    }
    if (rebounderTweens.some((t) => t && t.isPlaying)) {
      schedule(checkRebounderReached, pollMs);
    } else {
      monitoringActive = false;
    }
  };
  schedule(checkRebounderReached, startDelayMs);
  return () => {
    monitoringActive = false;
    clearScheduled();
  };
}

function resolveFbUnitContractMode() {
  const scope = getFbContractGlobalScope();
  const raw = String(scope?.UESS_FB_CONTRACT_MODE ?? "observe")
    .trim()
    .toLowerCase();
  if (raw === "off" || raw === "observe" || raw === "warn" || raw === "throw") return raw;
  return "observe";
}

function getFbUnitBudgetGameSeconds(kind = "phase") {
  const scope = getFbContractGlobalScope();
  const rawLeadIn = Number(scope?.UESS_FB_LEAD_IN_MAX_GAME_SECONDS);
  const rawPhase = Number(scope?.UESS_FB_PHASE_MAX_GAME_SECONDS);
  const rawOut = Number(scope?.UESS_FB_OUT_MAX_GAME_SECONDS);
  if (kind === "lead_in" && Number.isFinite(rawLeadIn) && rawLeadIn > 0) return rawLeadIn;
  if (kind === "out" && Number.isFinite(rawOut) && rawOut > 0) return rawOut;
  if (Number.isFinite(rawPhase) && rawPhase > 0) return rawPhase;
  if (kind === "lead_in") return 4;
  if (kind === "out") return 2;
  return 6;
}

function enforceFbUnitContract({
  scene,
  turnData,
  unitId,
  advanceTrigger,
  visualSettleTrigger,
  authorizingEventReceived,
  visualSettled,
  unitStartMs,
  budgetKind = "phase",
  context = {},
}) {
  const mode = resolveFbUnitContractMode();
  if (mode === "off") return;
  const clockSecondMs = scene?.gameClock?.getState?.().tickMs || 350;
  const elapsedMs = Math.max(0, Date.now() - Number(unitStartMs || Date.now()));
  const elapsedGameSeconds = elapsedMs / clockSecondMs;
  const maxWaitGameSeconds = getFbUnitBudgetGameSeconds(budgetKind);
  const overrun =
    Number.isFinite(maxWaitGameSeconds) &&
    maxWaitGameSeconds > 0 &&
    elapsedGameSeconds > maxWaitGameSeconds;
  const contractContext = {
    unitId,
    elapsedMs,
    elapsedGameSeconds: Number(elapsedGameSeconds.toFixed(2)),
    maxWaitGameSeconds,
    overrun,
    ...context,
  };
  if (overrun) {
    emitFbTelemetry(scene, "fb_phase_clock_overrun", contractContext);
  }
  const logger =
    mode === "observe"
      ? {
          warn: () => {},
        }
      : console;
  enforceUnitCompletionContract({
    contract: {
      unit_id: unitId,
      execution_mode: "dynamic_event",
      advance_trigger: advanceTrigger,
      visual_settle_trigger: visualSettleTrigger,
      failure_policy: mode === "throw" ? "throw" : "warn",
    },
    observed: {
      authorizingEventReceived: authorizingEventReceived === true,
      visualSettled: visualSettled === true && !overrun,
    },
    context: contractContext,
    emitTelemetry: (event, payload = {}) => emitFbTelemetry(scene, event, payload),
    logger,
  });
  if (mode === "throw" && overrun) {
    throw new Error(
      `[FB contract] clock overrun (unit=${unitId}, elapsedGameSeconds=${elapsedGameSeconds.toFixed(2)}, maxWaitGameSeconds=${maxWaitGameSeconds})`
    );
  }
}

function incrementFbCounter(scene, key, n = 1) {
  const t = getFbTelemetry(scene);
  if (!t) return;
  if (!Object.prototype.hasOwnProperty.call(t.counters, key)) return;
  t.counters[key] += Number(n) || 0;
}

function getPlayerAnimationRecord(turnData, playerId) {
  const want = playerId != null ? String(playerId) : null;
  if (!want || !Array.isArray(turnData?.animations)) return null;
  return turnData.animations.find((a) => String(a?.playerId) === want) ?? null;
}

function reportMissingEndpoint(scene, turnData, {
  playerId,
  role,
  requiredEndpointType = "animations_end",
  hasRoleCoord = false,
  reason = "missing_endpoint",
} = {}) {
  const rec = getPlayerAnimationRecord(turnData, playerId);
  emitFbTelemetry(scene, "fb_contract_missing_endpoint", {
    playerId,
    role,
    requiredEndpointType,
    availableAuthority: {
      hasAnimations: Array.isArray(turnData?.animations) && turnData.animations.length > 0,
      hasPlayerAnimation: !!rec,
      hasAnimEnd: !!(rec?.end && Number.isFinite(rec.end.x) && Number.isFinite(rec.end.y)),
      hasRoleCoord,
    },
    reason,
  });
  enforceFbContractGuardrail(scene, {
    playerId,
    role,
    requiredEndpointType,
    reason,
  });
}

function reportFallback(scene, {
  playerId,
  role,
  fallbackPolicy,
  missingAuthority = ["animations_end"],
  source,
  target,
} = {}) {
  incrementFbCounter(scene, "fbFallbackCount", 1);
  emitFbTelemetry(scene, "fb_fallback_used", {
    playerId,
    role,
    fallbackPolicy,
    missingAuthority,
    source,
    target,
  });
}

function finalizeFbTelemetry(scene) {
  const t = getFbTelemetry(scene);
  if (!t) return;
  const req = t.counters.fbRequiredRoleCount || 0;
  const rate = req > 0 ? t.counters.fbFallbackCount / req : 0;
  scene.events?.emit?.("animTelemetry", {
    event: "fb_telemetry_summary",
    turnIndex: t.turnIndex,
    turnId: t.turnId,
    resultType: t.resultType,
    branchKind: t.branchKind,
    offenseTeamId: t.offenseTeamId,
    gameClock: t.gameClock,
    quarter: t.quarter,
    timestampMs: Date.now(),
    fbFallbackCount: t.counters.fbFallbackCount,
    fbRequiredRoleCount: req,
    fbFallbackRate: rate,
    fbClampCount: t.counters.fbClampCount,
    fbSnapCount: t.counters.fbSnapCount,
  });
  scene.__fbTelemetry = null;
}

async function awaitWithTimeout(promise, timeoutMs, label) {
  const ms = Number.isFinite(timeoutMs) && timeoutMs > 0 ? timeoutMs : 2500;
  let timer = null;
  try {
    const timeoutPromise = new Promise((resolve) => {
      timer = setTimeout(() => resolve("__timeout__"), ms);
    });
    const result = await Promise.race([promise, timeoutPromise]);
    if (result === "__timeout__") {
      const expectedSettleTimeout = label === "rim_runner_burst_secondary_settle";
      if (!expectedSettleTimeout || isAnimationDebugEnabled()) {
        console.warn(`[FB animation] timeout while awaiting ${label}`, { timeoutMs: ms });
      }
      return false;
    }
    return true;
  } finally {
    if (timer) clearTimeout(timer);
  }
}

/**
 * Rim Runner lane pass (BH / outlet receiver → rim runner), spec ~6 grid toward basket from RR post-burst.
 * Runs after burst/outlet when the sim attempted the lane pass (not hold-up, not outlet denied).
 */
function shouldAnimateRimRunnerLanePass(turnData, phase2Kind) {
  if (turnData.rim_runner_outlet_failed) return false;
  const seq =
    turnData.fast_break_play === "rim_runner" ||
    turnData.roles?.rim_runner_sequence === true;
  if (!seq) return false;
  if (!turnData.roles?.rim_runner_burst_phase && turnData.roles?.rim_runner_id == null) {
    return false;
  }
  // Completion-to-shot only: steal / bat OOB use their own lane-style sequences
  const laneKinds =
    phase2Kind === "fast_break_shot" || phase2Kind === "fast_break_shot_foul";
  if (!laneKinds) return false;

  const sid = (id) => (id != null ? String(id) : null);
  const bh = sid(
    turnData.roles?.ball_handler_id ??
      turnData.roles?.ball_handler?.player_id ??
      turnData.roles?.passer?.player_id
  );
  const rr = sid(turnData.roles?.rim_runner_id ?? turnData.roles?.shooter?.player_id);
  if (!bh || !rr || bh === rr) return false;
  return true;
}

function getRimRunnerDecisionPillMeta(turnData) {
  const explicitGood = turnData?.rim_runner_decision_good;
  const passAttempted = Boolean(turnData?.rim_runner_pass_attempted);
  const fbOpen = Boolean(turnData?.rim_runner_fb_open);
  const isGoodDecision =
    typeof explicitGood === "boolean" ? explicitGood : passAttempted === fbOpen;
  return {
    decisionPillText: isGoodDecision ? "Good Decision" : "Bad Decision",
    decisionPillTone: isGoodDecision ? "good" : "bad",
  };
}

async function animateRimRunnerLanePass(scene, turnData, playerSprites, ballSprite, width, height) {
  const roles = turnData.roles || {};
  const phase = roles.rim_runner_burst_phase;
  const sid = (id) => (id != null ? String(id) : null);
  const passerId = sid(
    roles.ball_handler_id ?? roles.ball_handler?.player_id ?? roles.passer?.player_id
  );
  const rrId = sid(roles.rim_runner_id ?? roles.shooter?.player_id);
  const passerSprite = playerSprites[passerId];
  const rrSprite = playerSprites[rrId];
  if (!passerSprite || !rrSprite) return;

  const { showAnnouncement, getSecondaryColorForTeam } = await import("../utils/announcements.js");
  const offenseSide = passerSprite.team === "home" ? "home" : "away";
  const passerTeamId = passerSprite.team_id;
  const homeTeamField = scene.simData?.home_team;
  const awayTeamField = scene.simData?.away_team;
  const homeTeamName = typeof homeTeamField === "object" ? homeTeamField?.name : homeTeamField;
  const awayTeamName = typeof awayTeamField === "object" ? awayTeamField?.name : awayTeamField;
  const passerTeamName = passerTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
  const passerInfo = scene.playerInfo?.[passerId];
  const passerPlayerData = passerInfo
    ? {
        playerId: passerId,
        photo: passerSprite.photo || null,
        teamName: passerTeamName,
        secondaryColor: getSecondaryColorForTeam(scene, passerTeamId),
      }
    : null;
  showAnnouncement("Fast Break!", offenseSide, passerPlayerData, getRimRunnerDecisionPillMeta(turnData));

  const away = Boolean(phase?.is_away_offense ?? roles.is_away_offense);
  const towardBasket = away ? -1 : 1;

  let rrGridX =
    typeof rrSprite.gridX === "number"
      ? rrSprite.gridX
      : phase?.rr_to?.x ?? 50;
  let rrGridY =
    typeof rrSprite.gridY === "number"
      ? rrSprite.gridY
      : phase?.rr_to?.y ?? 25;

  const catchGrid = {
    x: Phaser.Math.Clamp(rrGridX + 6 * towardBasket, GRID_MIN_X, GRID_MAX_X),
    y: Phaser.Math.Clamp(rrGridY, GRID_MIN_Y, GRID_MAX_Y),
  };
  const catchPx = gridToPixels(catchGrid.x, catchGrid.y, width, height);

  attachBallToPlayer(scene, ballSprite, passerSprite);

  const rrDur = getPlayerDuration(rrSprite, catchPx.x, catchPx.y, true);

  const rrTween = tweenPlayerTo(scene, rrSprite, catchPx, {
    duration: rrDur,
    easing: "Linear",
  });

  const passPromise = runPass(scene, {
    fromId: passerId,
    toId: rrId,
    endCoords: { x: catchPx.x, y: catchPx.y },
    duration: rrDur,
    easing: "Sine.easeInOut",
  });

  await Promise.all([passPromise, rrTween]);

  rrSprite.gridX = catchGrid.x;
  rrSprite.gridY = catchGrid.y;

  await new Promise((resolve) => {
    if (scene.time?.delayedCall) scene.time.delayedCall(50, resolve);
    else setTimeout(resolve, 50);
  });
  const { getBallController, synchronizeBallState } = await import("./BallControllerAdapter.js");
  const ballController = getBallController();
  synchronizeBallState(scene, { clearPassState: true, allowAttachment: true });
  if (!ballController?.isAttached || ballController.currentOwner !== rrSprite) {
    attachBallToPlayer(scene, ballSprite, rrSprite, { reason: "rim_runner_lane_pass" });
  }
}

function rimRunnerSpriteGrid(sprite, width, height) {
  if (sprite && typeof sprite.gridX === "number" && typeof sprite.gridY === "number") {
    return { x: sprite.gridX, y: sprite.gridY };
  }
  if (!sprite) return { x: 50, y: 25 };
  return {
    x: Phaser.Math.Clamp((sprite.x / width) * 100, GRID_MIN_X, GRID_MAX_X),
    y: Phaser.Math.Clamp(50 - (sprite.y / height) * 50, GRID_MIN_Y, GRID_MAX_Y),
  };
}

function rimRunnerLiveSpriteGrid(sprite, width, height) {
  if (!sprite) return { x: 50, y: 25 };
  return {
    x: Phaser.Math.Clamp((sprite.x / width) * 100, GRID_MIN_X, GRID_MAX_X),
    y: Phaser.Math.Clamp(50 - (sprite.y / height) * 50, GRID_MIN_Y, GRID_MAX_Y),
  };
}

function setRimRunnerSpriteGrid(sprite, gx, gy) {
  if (!sprite) return;
  sprite.gridX = gx;
  sprite.gridY = gy;
}

function commitRrLiveSpriteGrid(playerSprites, width, height) {
  for (const sprite of Object.values(playerSprites || {})) {
    if (!sprite) continue;
    const gx = Phaser.Math.Clamp((sprite.x / width) * 100, GRID_MIN_X, GRID_MAX_X);
    const gy = Phaser.Math.Clamp(50 - (sprite.y / height) * 50, GRID_MIN_Y, GRID_MAX_Y);
    setRimRunnerSpriteGrid(sprite, gx, gy);
  }
}

function captureRrLiveSnapshot(playerSprites, width, height) {
  const snapshot = {};
  for (const [pid, sprite] of Object.entries(playerSprites || {})) {
    if (!sprite) continue;
    snapshot[String(pid)] = {
      x: Phaser.Math.Clamp((sprite.x / width) * 100, GRID_MIN_X, GRID_MAX_X),
      y: Phaser.Math.Clamp(50 - (sprite.y / height) * 50, GRID_MIN_Y, GRID_MAX_Y),
    };
  }
  return snapshot;
}

function resolveFbPassEndpointGrid(targetGrid, sprite, width, height) {
  if (
    targetGrid &&
    Number.isFinite(targetGrid.x) &&
    Number.isFinite(targetGrid.y)
  ) {
    return {
      x: Phaser.Math.Clamp(targetGrid.x, GRID_MIN_X, GRID_MAX_X),
      y: Phaser.Math.Clamp(targetGrid.y, GRID_MIN_Y, GRID_MAX_Y),
    };
  }
  return rimRunnerSpriteGrid(sprite, width, height);
}

function resolveFbInterceptionContactGrid({
  passerTarget,
  passerSprite,
  receiverTarget,
  receiverSprite,
  width,
  height,
}) {
  const passerGrid = resolveFbPassEndpointGrid(passerTarget, passerSprite, width, height);
  const receiverGrid = resolveFbPassEndpointGrid(receiverTarget, receiverSprite, width, height);

  const x =
    passerGrid.x > receiverGrid.x
      ? receiverGrid.x + 3
      : receiverGrid.x - 3;

  let y = receiverGrid.y;
  if (passerGrid.y >= receiverGrid.y + 3) {
    y = receiverGrid.y + 3;
  } else if (passerGrid.y <= receiverGrid.y - 3) {
    y = receiverGrid.y - 3;
  }

  return {
    x: Phaser.Math.Clamp(x, GRID_MIN_X, GRID_MAX_X),
    y: Phaser.Math.Clamp(y, GRID_MIN_Y, GRID_MAX_Y),
    passerGrid,
    receiverGrid,
  };
}

function resolveNearestOutOfBoundsGrid(interceptorGrid) {
  const candidates = [
    { edge: "left_sideline", x: GRID_MIN_X, y: interceptorGrid.y, distance: Math.abs(interceptorGrid.x - GRID_MIN_X) },
    { edge: "right_sideline", x: GRID_MAX_X, y: interceptorGrid.y, distance: Math.abs(GRID_MAX_X - interceptorGrid.x) },
    { edge: "top_baseline", x: interceptorGrid.x, y: GRID_MIN_Y, distance: Math.abs(interceptorGrid.y - GRID_MIN_Y) },
    { edge: "bottom_baseline", x: interceptorGrid.x, y: GRID_MAX_Y, distance: Math.abs(GRID_MAX_Y - interceptorGrid.y) },
  ];
  candidates.sort((a, b) => a.distance - b.distance);
  const winner = candidates[0];
  return {
    x: Phaser.Math.Clamp(winner.x, GRID_MIN_X, GRID_MAX_X),
    y: Phaser.Math.Clamp(winner.y, GRID_MIN_Y, GRID_MAX_Y),
    edge: winner.edge,
  };
}

function isTriangleSequence(turnData) {
  return (
    turnData?.fast_break_play === "triangle" ||
    turnData?.roles?.triangle_sequence === true ||
    Boolean(turnData?.roles?.triangle_setup_phase)
  );
}

function getTriangleSetupPayload(turnData) {
  return turnData?.roles?.triangle_setup_phase || null;
}

async function tweenTriangleSpriteToGrid(scene, sprite, grid, width, height, { burst = false } = {}) {
  if (!sprite || !grid || typeof grid.x !== "number" || typeof grid.y !== "number") return null;
  if (scene.tweens) scene.tweens.killTweensOf(sprite);
  const px = gridToPixels(
    Phaser.Math.Clamp(grid.x, GRID_MIN_X, GRID_MAX_X),
    Phaser.Math.Clamp(grid.y, GRID_MIN_Y, GRID_MAX_Y),
    width,
    height
  );
  const duration = getPlayerDuration(sprite, px.x, px.y, burst);
  return tweenPlayerTo(scene, sprite, px, {
    duration,
    easing: "Linear",
  });
}

async function animateTriangleSetupPhase(scene, turnData, playerSprites, ballSprite, width, height) {
  const payload = getTriangleSetupPayload(turnData);
  if (!payload) return { payload: null, snapshot: captureRrLiveSnapshot(playerSprites, width, height) };
  const sid = (id) => (id != null ? String(id) : null);
  console.log("[TRIANGLE SETUP][OWNER]", {
    turnId: turnData?.turn_count ?? turnData?.id ?? null,
    resultType: turnData?.result_type ?? null,
    triangleBranch:
      turnData?.triangle_branch ?? turnData?.roles?.triangle_branch ?? payload?.triangle_branch ?? null,
    liveOwnerId: getCurrentOwner(scene),
    triangleBallHandlerId: sid(payload.ball_handler_id),
    outletPasserId: sid(turnData?.roles?.outlet_passer),
    outletReceiverId: sid(turnData?.roles?.outlet_receiver),
    burstOutletPasserId: sid(turnData?.roles?.rim_runner_burst_phase?.outlet_passer_id),
    burstOutletReceiverId: sid(turnData?.roles?.rim_runner_burst_phase?.outlet_receiver_id),
    skipOutletPass:
      turnData?.roles?.rim_runner_burst_phase?.skip_outlet_pass === true,
  });
  const moved = [];
  const promises = [];
  const queueMove = (playerId, target, opts = {}) => {
    const pid = sid(playerId);
    if (!pid || moved.includes(pid)) return;
    const sprite = playerSprites?.[pid];
    if (!sprite || !target) return;
    moved.push(pid);
    const promise = tweenTriangleSpriteToGrid(scene, sprite, target, width, height, opts);
    if (promise) promises.push(Promise.resolve(promise).then(() => setRimRunnerSpriteGrid(sprite, target.x, target.y)));
  };

  queueMove(payload.ball_handler_id, payload.ball_handler_to, { burst: false });
  queueMove(payload.rim_runner_id, payload.rim_runner_to, { burst: false });
  queueMove(payload.trailer_id, payload.trailer_to, { burst: false });
  for (const corner of payload.corner_players || []) {
    queueMove(corner.player_id, corner.to, { burst: Boolean(corner.burst) });
  }
  queueMove(payload.rr_defender_id, payload.rr_defender_to, { burst: false });
  queueMove(payload.bh_defender_id, payload.bh_defender_to, { burst: false });
  for (const helper of payload.helper_defenders || []) {
    queueMove(helper.player_id, helper.to, { burst: Boolean(helper.burst) });
  }

  const bhSprite = playerSprites?.[sid(payload.ball_handler_id)];
  if (bhSprite) attachBallToPlayer(scene, ballSprite, bhSprite, { reason: "triangle_setup" });

  await Promise.all(promises);
  commitRrLiveSpriteGrid(playerSprites, width, height);
  return { payload, snapshot: captureRrLiveSnapshot(playerSprites, width, height) };
}

async function animateTriangleDecisionLeadIn(scene, turnData, playerSprites, ballSprite, width, height) {
  const payload = getTriangleSetupPayload(turnData);
  if (!payload) return;
  const sid = (id) => (id != null ? String(id) : null);
  const branch = turnData?.triangle_branch ?? turnData?.roles?.triangle_branch ?? payload?.triangle_branch;
  const bhId = sid(payload.ball_handler_id);
  const rrId = sid(payload.rim_runner_id);
  const sameCornerId = sid(payload.same_side_corner_id);
  const bhSprite = bhId ? playerSprites?.[bhId] : null;
  const rrSprite = rrId ? playerSprites?.[rrId] : null;
  const sameCornerSprite = sameCornerId ? playerSprites?.[sameCornerId] : null;

  if (bhSprite) attachBallToPlayer(scene, ballSprite, bhSprite, { reason: "triangle_decision" });

  const runOptionalPass = async (fromId, toId, target) => {
    if (!fromId || !toId || fromId === toId) return;
    if (!playerSprites?.[String(toId)] || !target) return;
    await runPass(scene, {
      fromId: String(fromId),
      toId: String(toId),
      endCoords: gridToPixels(target.x, target.y, width, height),
      easing: "Sine.easeInOut",
    });
    await new Promise((resolve) => {
      if (scene.time?.delayedCall) scene.time.delayedCall(45, resolve);
      else setTimeout(resolve, 45);
    });
    attachBallToPlayer(scene, ballSprite, playerSprites[String(toId)], { reason: "triangle_branch_pass" });
  };

  if (branch === "triangle_rr_post") {
    await runOptionalPass(bhId, rrId, payload.rim_runner_to);
  } else if (branch === "triangle_corner_three") {
    await runOptionalPass(bhId, sameCornerId, payload.same_side_corner_to);
  } else if (branch === "triangle_bh_wing_three") {
    return;
  } else if (branch === "triangle_bh_drive" || branch === "triangle_drive_rr_feed" || branch === "triangle_drive_corner_kick") {
    const movers = [];
    if (bhSprite && payload.triangle_drive_to) {
      movers.push(
        tweenTriangleSpriteToGrid(scene, bhSprite, payload.triangle_drive_to, width, height, { burst: false }).then(() => {
          setRimRunnerSpriteGrid(bhSprite, payload.triangle_drive_to.x, payload.triangle_drive_to.y);
        })
      );
    }
    if (rrSprite && payload.triangle_rr_drive_to) {
      movers.push(
        tweenTriangleSpriteToGrid(scene, rrSprite, payload.triangle_rr_drive_to, width, height, { burst: false }).then(() => {
          setRimRunnerSpriteGrid(rrSprite, payload.triangle_rr_drive_to.x, payload.triangle_rr_drive_to.y);
        })
      );
    }
    await Promise.all(movers);
    if (branch === "triangle_drive_rr_feed") {
      await runOptionalPass(bhId, rrId, payload.triangle_rr_drive_to);
    } else if (branch === "triangle_drive_corner_kick") {
      await runOptionalPass(bhId, sameCornerId, payload.same_side_corner_to);
    }
  }

  commitRrLiveSpriteGrid(playerSprites, width, height);
}

async function animateTriangleHcoSettle(scene, turnData, playerSprites, ballSprite, width, height) {
  appendToTextScroll("Triangle flow into half court.");
  await finalizeRimRunnerNonShotTurn(scene, turnData, playerSprites);
}

function logRrDenied(scene, stage, payload = {}) {
  const telemetry = getFbTelemetry(scene);
  console.log(`[RR DENIED][${stage}]`, {
    branchKind: telemetry?.branchKind ?? null,
    turnId: telemetry?.turnId ?? null,
    turnIndex: telemetry?.turnIndex ?? null,
    resultType: telemetry?.resultType ?? null,
    ...payload,
  });
}

/** Shared wall time for RR AG-drift beats (outlet denied + hold-up); floors snap/warp from tiny primary moves. */
function clampRrAgSharedPhaseDurationMs(ms) {
  const raw = Number(ms);
  const base = Number.isFinite(raw) ? raw : 500;
  const minMs = animationConfig.fastBreak?.agDriftSharedPhaseMinMs ?? 520;
  return Math.max(minMs, base);
}

/**
 * Parallel horizontal drifts toward the offense basket: same duration for all, per-sprite distance
 * from AG (`horizontalGridUnitsForDurationMs`), Y fixed, grid X clamped 4–97. Skips `excludeIds`.
 */
function rimRunnerAgHorizontalDriftPromises(
  scene,
  playerSprites,
  width,
  height,
  sid,
  excludeIds,
  towardBasket,
  phaseDurationMs
) {
  const skip = excludeIds instanceof Set ? excludeIds : new Set();
  const promises = [];
  const edgeInsetGrid = Math.max(0, Number(animationConfig.fastBreak?.agDriftEdgeInsetGrid ?? 2));
  const minDriftX = 4 + edgeInsetGrid;
  const maxDriftX = 97 - edgeInsetGrid;
  for (const [pidRaw, sprite] of Object.entries(playerSprites)) {
    if (!sprite) continue;
    const pid = sid(pidRaw);
    if (!pid || skip.has(pid)) continue;
    if (scene.tweens) {
      scene.tweens.killTweensOf(sprite);
    }
    const g = rimRunnerSpriteGrid(sprite, width, height);
    const stride = horizontalGridUnitsForDurationMs(sprite, phaseDurationMs, width, { scene });
    const direction = towardBasket >= 0 ? 1 : -1;
    const startX = Phaser.Math.Clamp(g.x, GRID_MIN_X, GRID_MAX_X);
    const strideAbs = Math.abs(stride);
    const boundedStartX = Phaser.Math.Clamp(startX, minDriftX, maxDriftX);
    const maxStrideToward =
      direction > 0
        ? Math.max(0, maxDriftX - boundedStartX)
        : Math.max(0, boundedStartX - minDriftX);
    const usedStride = Math.min(strideAbs, maxStrideToward) * direction;
    const proposedEndX = startX + stride * direction;
    const endX = Phaser.Math.Clamp(boundedStartX + usedStride, GRID_MIN_X, GRID_MAX_X);
    const endY = Phaser.Math.Clamp(g.y, GRID_MIN_Y, GRID_MAX_Y);
    if (getFbTelemetry(scene)?.branchKind === "rr_outlet_denied") {
      logRrDenied(scene, "DRIFT PLAN", {
        playerId: pid,
        start: { x: startX, y: g.y },
        stride,
        proposedEndX,
        end: { x: endX, y: endY },
        phaseDurationMs,
      });
    }
    if (Math.abs(strideAbs - Math.abs(usedStride)) > 0.001) {
      incrementFbCounter(scene, "fbClampCount", 1);
      const speedPxPerSec = phaseDurationMs > 0
        ? ((Math.abs(stride) * width) / 100) / (phaseDurationMs / 1000)
        : null;
      emitFbTelemetry(scene, "fb_clamp_destination", {
        playerId: pid,
        role: "ag_drift",
        sourceX: startX,
        proposedEndX,
        clampedEndX: endX,
        clampEdge: direction > 0 ? "max_x" : "min_x",
        edgeInsetGrid,
        phaseDurationMs,
        speedPxPerSec,
      });
    }
    const px = gridToPixels(endX, endY, width, height);
    promises.push(
      tweenPlayerTo(scene, sprite, px, {
        duration: phaseDurationMs,
        easing: "Linear",
        debugTag:
          getFbTelemetry(scene)?.branchKind === "rr_outlet_denied"
            ? `rr_denied_drift_${pid}`
            : null,
      })
    );
  }
  return promises;
}

async function finalizeRimRunnerNonShotTurn(scene, turnData, playerSprites = null) {
  if (scene.skipToEnd) return;
  if (scene.stateMachine?.state !== States.HalfCourt) {
    safeTransition(scene.stateMachine, States.HalfCourt);
  }

  let pre = null;
  if (turnData.next_play_type === "HCO" && playerSprites) {
    pre = Object.fromEntries(
      Object.entries(playerSprites)
        .filter(([, s]) => !!s)
        .map(([pid, s]) => [String(pid), { x: Number(s.x), y: Number(s.y) }])
    );
    if (turnData.rim_runner_outlet_failed) {
      logRrDenied(scene, "HCO HANDOFF", {
        preSnapshot: pre,
      });
    }
  }

  if (
    turnData.next_play_type === "HCO" &&
    typeof scene.startNextHalfCourtOffense === "function"
  ) {
    scene.startNextHalfCourtOffense();
  }

  if (pre && playerSprites) {
    const check = () => {
      for (const [pid, sprite] of Object.entries(playerSprites)) {
        if (!sprite || !pre[pid]) continue;
        const dx = Number(sprite.x) - pre[pid].x;
        const dy = Number(sprite.y) - pre[pid].y;
        const deltaPx = Math.hypot(dx, dy);
        if (deltaPx < 20) continue;
        incrementFbCounter(scene, "fbSnapCount", 1);
        emitFbTelemetry(scene, "fb_transition_snap", {
          playerId: pid,
          role: "player",
          fromTurnType: "FAST_BREAK",
          toTurnType: "HCO",
          preTransition: pre[pid],
          postTransition: { x: Number(sprite.x), y: Number(sprite.y) },
          deltaPx,
          deltaGridApprox: {
            x: (dx / (scene.game.config.width || 1)) * 100,
            y: (-dy / (scene.game.config.height || 1)) * 50,
          },
        });
      }
      if (turnData.rim_runner_outlet_failed) {
        const post = Object.fromEntries(
          Object.entries(playerSprites)
            .filter(([, s]) => !!s)
            .map(([pid, s]) => [String(pid), { x: Number(s.x), y: Number(s.y) }])
        );
        logRrDenied(scene, "HCO HANDOFF POST", { postSnapshot: post });
      }
    };
    if (scene.time?.delayedCall) {
      scene.time.delayedCall(0, check);
    } else {
      setTimeout(check, 0);
    }
  }
}

function resolvePlayerSpriteById(playerSprites, rawId) {
  if (!playerSprites || rawId == null) return { id: null, sprite: null };
  const sid = String(rawId);
  if (playerSprites[sid]) return { id: sid, sprite: playerSprites[sid] };
  if (playerSprites[rawId]) return { id: rawId, sprite: playerSprites[rawId] };
  const num = Number(rawId);
  if (Number.isFinite(num) && playerSprites[num]) return { id: num, sprite: playerSprites[num] };
  return { id: sid, sprite: null };
}

function appendUniqueIdCandidate(list, seen, rawId, source) {
  if (rawId == null) return;
  const sid = String(rawId).trim();
  if (!sid || seen.has(sid)) return;
  seen.add(sid);
  list.push({ rawId, sid, source });
}

function collectFastBreakDefenderCandidates(turnData) {
  const list = [];
  const seen = new Set();
  appendUniqueIdCandidate(list, seen, turnData?.defender_id, "turnData.defender_id");
  appendUniqueIdCandidate(list, seen, turnData?.defenderId, "turnData.defenderId");

  const defenderObj = turnData?.defender ?? turnData?.roles?.defender;
  if (defenderObj && typeof defenderObj === "object") {
    appendUniqueIdCandidate(list, seen, defenderObj.player_id, "defender.player_id");
    appendUniqueIdCandidate(list, seen, defenderObj.playerId, "defender.playerId");
  } else {
    appendUniqueIdCandidate(list, seen, defenderObj, "defender");
  }

  if (Array.isArray(turnData?.roles?.defense)) {
    turnData.roles.defense.forEach((d, i) => {
      if (d && typeof d === "object") {
        appendUniqueIdCandidate(list, seen, d.player_id, `roles.defense[${i}].player_id`);
        appendUniqueIdCandidate(list, seen, d.playerId, `roles.defense[${i}].playerId`);
      } else {
        appendUniqueIdCandidate(list, seen, d, `roles.defense[${i}]`);
      }
    });
  }

  return list;
}

function resolveFastBreakDefenderSprite(playerSprites, turnData, { excludeIds = [] } = {}) {
  const excluded = new Set(
    (excludeIds || [])
      .filter((id) => id != null)
      .map((id) => String(id))
  );
  const candidates = collectFastBreakDefenderCandidates(turnData);
  for (const candidate of candidates) {
    if (excluded.has(candidate.sid)) continue;
    const ref = resolvePlayerSpriteById(playerSprites, candidate.rawId);
    if (ref?.sprite) {
      return {
        id: ref.id,
        sprite: ref.sprite,
        source: candidate.source,
        candidates: candidates.map((c) => ({ id: c.sid, source: c.source })),
      };
    }
  }
  return {
    id: candidates[0]?.sid ?? null,
    sprite: null,
    source: null,
    candidates: candidates.map((c) => ({ id: c.sid, source: c.source })),
  };
}

/**
 * Rim Runner outlet denied: defender two grid steps toward the pass direction (same as backend
 * `outlet_defender_to`), announcement + headshot, receiver cuts to passer x and y±6, then pass.
 *
 * While the outlet receiver tweens to the catch spot, all other players move horizontally toward
 * the offense basket for the same phase duration (AG-scoped distance each, X clamped 4–97), excluding
 * outlet passer, receiver, and outlet defender. Burst-phase tweens on those players are stopped first;
 * see `animateRimRunnerBurstPhase` + `Promise.allSettled` when denied.
 */
async function animateRimRunnerOutletDeniedBeat(
  scene,
  turnData,
  playerSprites,
  ballSprite,
  width,
  height,
  phase,
  passerSprite,
  recvSprite
) {
  const sid = (id) => (id != null ? String(id) : null);
  const spriteIdFor = (targetSprite) => {
    if (!targetSprite) return null;
    for (const [pid, sprite] of Object.entries(playerSprites || {})) {
      if (sprite === targetSprite) return sid(pid);
    }
    return null;
  };
  if (!passerSprite || !recvSprite) {
    return { branch: "outlet_denied", snapshot: captureRrLiveSnapshot(playerSprites, width, height) };
  }

  const defId = sid(phase?.outlet_defender_id);
  const defSprite = defId ? playerSprites[defId] : null;
  const rawPasserFallback = turnData.roles?.outlet_passer;
  const spriteDerivedPasserId = spriteIdFor(passerSprite);
  const phasePasserId = sid(phase?.outlet_passer_id);
  const rolesPasserId = sid(
    rawPasserFallback != null && typeof rawPasserFallback === "object"
      ? rawPasserFallback.player_id ?? rawPasserFallback.playerId
      : rawPasserFallback
  );
  let passerId = spriteDerivedPasserId;
  if (
    spriteDerivedPasserId &&
    ((phasePasserId && phasePasserId !== spriteDerivedPasserId) ||
      (rolesPasserId && rolesPasserId !== spriteDerivedPasserId))
  ) {
    logRrDenied(scene, "PASSER MISMATCH", {
      spriteDerivedPasserId,
      phasePasserId,
      rolesPasserId,
    });
  }
  if (!passerId && phasePasserId) {
    passerId = phasePasserId;
    logRrDenied(scene, "PASSER RECOVERY", {
      mode: "phase_payload",
      passerId,
    });
  }
  if (!passerId && rolesPasserId) {
    passerId = rolesPasserId;
    logRrDenied(scene, "PASSER RECOVERY", {
      mode: "roles_payload",
      passerId,
    });
  }
  if (!passerId) {
    passerId = sid(getCurrentOwner(scene));
    if (passerId) {
      logRrDenied(scene, "PASSER RECOVERY", {
        mode: "ball_owner",
        passerId,
      });
    }
  }
  const recvId = sid(phase?.outlet_receiver_id);
  const away = Boolean(phase?.is_away_offense);
  const towardBasket = away ? -1 : 1;

  attachBallToPlayer(scene, ballSprite, passerSprite);

  // Derive the denied-outlet beat from the visible on-court locations, not the
  // cached logical burst endpoints. This branch forks immediately after the burst
  // receiver reaches the trigger spot, so cached gridX/gridY can get ahead of
  // what is actually on screen and make the defender step / receiver cutback
  // appear skipped.
  const pg = rimRunnerLiveSpriteGrid(passerSprite, width, height);
  const receiverLiveGrid = rimRunnerLiveSpriteGrid(recvSprite, width, height);
  const defenderLiveGrid = defSprite ? rimRunnerLiveSpriteGrid(defSprite, width, height) : null;
  const defenderTarget = {
    x: Phaser.Math.Clamp(pg.x + 2 * towardBasket, GRID_MIN_X, GRID_MAX_X),
    y: Phaser.Math.Clamp(pg.y, GRID_MIN_Y, GRID_MAX_Y),
  };
  logRrDenied(scene, "ENTRY", {
    passerId,
    receiverId: recvId,
    defenderId: defId,
    passerGrid: pg,
    receiverGrid: receiverLiveGrid,
    defenderGrid: defenderLiveGrid,
    defenderTarget,
  });

  if (defSprite && scene.tweens) {
    scene.tweens.killTweensOf(defSprite);
  }

  if (defSprite) {
    const defTargetPx = gridToPixels(defenderTarget.x, defenderTarget.y, width, height);
    await tweenPlayerTo(scene, defSprite, defTargetPx, {
      duration: getPlayerDuration(defSprite, defTargetPx.x, defTargetPx.y, true),
      easing: "Linear",
      debugTag: "rr_denied_defender_closeout",
    });
    setRimRunnerSpriteGrid(defSprite, defenderTarget.x, defenderTarget.y);
  }

  const defenseTeam = passerSprite.team === "home" ? "away" : "home";
  const { showAnnouncement, getSecondaryColorForTeam } = await import("../utils/announcements.js");
  // Freeze ongoing burst tweens (RR, other_players, etc.) during callout + hold — same universal px/s, no motion on screen.
  pauseTweensOfPlayerSprites(scene, playerSprites);
  if (defSprite) {
    const stopperInfo = scene.playerInfo?.[defId];
    const stopperTeamId = defSprite.team_id;
    const homeTeamField = scene.simData?.home_team;
    const awayTeamField = scene.simData?.away_team;
    const homeTeamName = typeof homeTeamField === "object" ? homeTeamField?.name : homeTeamField;
    const awayTeamName = typeof awayTeamField === "object" ? awayTeamField?.name : awayTeamField;
    const stopperTeamName = stopperTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
    const stopperPlayerData = stopperInfo
      ? {
          playerId: defId,
          photo: defSprite.photo || null,
          teamName: stopperTeamName,
          secondaryColor: getSecondaryColorForTeam(scene, defSprite.team_id),
        }
      : null;
    showAnnouncement("FB Outlet Pass Denied!", defenseTeam, stopperPlayerData);
  } else {
    showAnnouncement("FB Outlet Pass Denied!", defenseTeam, null);
  }

  const stopHoldMs = animationConfig.fastBreak?.defensiveStopHoldMs ?? 1000;
  await new Promise((resolve) => {
    if (scene.time?.delayedCall) scene.time.delayedCall(stopHoldMs, resolve);
    else setTimeout(resolve, stopHoldMs);
  });

  const recvTarget = {
    x: Phaser.Math.Clamp(pg.x, GRID_MIN_X, GRID_MAX_X),
    y: Phaser.Math.Clamp(pg.y < 25 ? pg.y + 6 : pg.y - 6, GRID_MIN_Y, GRID_MAX_Y),
  };

  const recvTargetPx = gridToPixels(recvTarget.x, recvTarget.y, width, height);
  const phaseDurationMs = clampRrAgSharedPhaseDurationMs(
    getPlayerDuration(recvSprite, recvTargetPx.x, recvTargetPx.y, true)
  );

  const driftExclude = new Set([passerId, recvId, defId].filter(Boolean));
  logRrDenied(scene, "ENTRY", {
    driftExclude: Array.from(driftExclude),
    driftMoverCount: Object.keys(playerSprites || {}).filter((pid) => !driftExclude.has(String(pid))).length,
  });
  const driftPromises = rimRunnerAgHorizontalDriftPromises(
    scene,
    playerSprites,
    width,
    height,
    sid,
    driftExclude,
    towardBasket,
    phaseDurationMs
  );
  // Denied branch advances on receiver cutback, not drift completion. Drift tweens
  // can be stopped at handoff, so consume outcomes to avoid unhandled stop errors.
  void Promise.allSettled(driftPromises);

  const recvPromise = tweenPlayerTo(scene, recvSprite, recvTargetPx, {
    duration: phaseDurationMs,
    easing: "Linear",
    debugTag: "rr_denied_receiver_cutback",
  });

  const recvCutbackCompleted = await awaitWithTimeout(
    recvPromise,
    phaseDurationMs + 2000,
    "rim_runner_outlet_denied_receiver_cutback"
  );
  if (!recvCutbackCompleted) {
    incrementFbCounter(scene, "fbAwaitTimeoutCount", 1);
    emitFbTelemetry(scene, "fb_await_timeout", {
      label: "rim_runner_outlet_denied_receiver_cutback",
      timeoutMs: phaseDurationMs + 2000,
    });
  }
  logRrDenied(scene, "TRIGGER", {
    trigger: "receiver_cutback_reached",
    receiverTarget: recvTarget,
    receiverLive: rimRunnerLiveSpriteGrid(recvSprite, width, height),
    snapshotAtTrigger: captureRrLiveSnapshot(playerSprites, width, height),
  });

  setRimRunnerSpriteGrid(recvSprite, recvTarget.x, recvTarget.y);
  for (const [pidRaw, sprite] of Object.entries(playerSprites)) {
    if (!sprite || !scene.tweens) continue;
    const pid = sid(pidRaw);
    if (pid === passerId || pid === recvId || pid === defId) continue;
    scene.tweens.killTweensOf(sprite);
  }
  commitRrLiveSpriteGrid(playerSprites, width, height);

  if (passerId && recvId && passerId !== recvId) {
    logRrDenied(scene, "PASS START", {
      fromId: passerId,
      toId: recvId,
    });
    await runPass(scene, {
      fromId: passerId,
      toId: recvId,
      easing: "Sine.easeInOut",
    });
    await new Promise((resolve) => {
      if (scene.time?.delayedCall) scene.time.delayedCall(50, resolve);
      else setTimeout(resolve, 50);
    });
    const { synchronizeBallState } = await import("./BallControllerAdapter.js");
    synchronizeBallState(scene, { clearPassState: true, allowAttachment: true });
    attachBallToPlayer(scene, ballSprite, recvSprite, { reason: "rim_runner_outlet_denied_pass" });
    logRrDenied(scene, "PASS END", {
      receiverLive: rimRunnerLiveSpriteGrid(recvSprite, width, height),
      snapshotAfterPass: captureRrLiveSnapshot(playerSprites, width, height),
    });
  } else {
    attachBallToPlayer(scene, ballSprite, recvSprite, {
      reason: "rim_runner_outlet_denied_pass_recovery_failed",
    });
    logRrDenied(scene, "PASS END", {
      receiverLive: rimRunnerLiveSpriteGrid(recvSprite, width, height),
      mode: "pass_recovery_failed",
      passerId,
      receiverId: recvId,
      snapshotAfterPass: captureRrLiveSnapshot(playerSprites, width, height),
    });
  }

  commitRrLiveSpriteGrid(playerSprites, width, height);
  const finalSnapshot = captureRrLiveSnapshot(playerSprites, width, height);
  logRrDenied(scene, "FINAL SNAPSHOT", {
    snapshot: finalSnapshot,
  });
  return { branch: "outlet_denied", snapshot: finalSnapshot };
}

/**
 * RR hold-up (no lane pass): the ball handler settle is the branch advance trigger.
 * Everyone else drifts toward the offense basket only until the ball handler reaches
 * that hold-up spot, then their drift is stopped and the branch hands off to HCO.
 */
async function animateRimRunnerHoldUpLeadIn(
  scene,
  turnData,
  playerSprites,
  ballSprite,
  width,
  height
) {
  const roles = turnData.roles || {};
  const phase = roles.rim_runner_burst_phase;
  const sid = (id) => (id != null ? String(id) : null);
  const bhId = sid(
    roles.ball_handler_id ?? roles.ball_handler?.player_id ?? roles.passer?.player_id
  );
  const bh = playerSprites[bhId];
  if (!bh) {
    return { branch: "hold_up", snapshot: captureRrLiveSnapshot(playerSprites, width, height) };
  }

  if (turnData.rim_runner_no_lane_pass && !isTriangleSequence(turnData)) {
    const { showAnnouncement, getSecondaryColorForTeam } = await import("../utils/announcements.js");
    const offenseSide = bh.team === "home" ? "home" : "away";
    const bhTeamId = bh.team_id;
    const homeTeamField = scene.simData?.home_team;
    const awayTeamField = scene.simData?.away_team;
    const homeTeamName = typeof homeTeamField === "object" ? homeTeamField?.name : homeTeamField;
    const awayTeamName = typeof awayTeamField === "object" ? awayTeamField?.name : awayTeamField;
    const bhTeamName = bhTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
    const bhInfo = scene.playerInfo?.[bhId];
    const bhPlayerData = bhInfo
      ? {
          playerId: bhId,
          photo: bh.photo || null,
          teamName: bhTeamName,
          secondaryColor: getSecondaryColorForTeam(scene, bhTeamId),
        }
      : null;
    const decisionMeta = getRimRunnerDecisionPillMeta(turnData);
    showAnnouncement("No Fast Break", offenseSide, bhPlayerData, decisionMeta);
  }

  attachBallToPlayer(scene, ballSprite, bh);
  const away = Boolean(phase?.is_away_offense ?? roles.is_away_offense);
  const towardBasket = away ? -1 : 1;

  const bhg = rimRunnerSpriteGrid(bh, width, height);
  const settleBh = {
    x: Phaser.Math.Clamp(bhg.x + 6 * towardBasket, GRID_MIN_X, GRID_MAX_X),
    y: Phaser.Math.Clamp(bhg.y < 25 ? bhg.y + 8 : bhg.y - 8, GRID_MIN_Y, GRID_MAX_Y),
  };
  const bhTargetPx = gridToPixels(settleBh.x, settleBh.y, width, height);
  const phaseDurationMs = clampRrAgSharedPhaseDurationMs(
    getPlayerDuration(bh, bhTargetPx.x, bhTargetPx.y)
  );

  const driftPromises = rimRunnerAgHorizontalDriftPromises(
    scene,
    playerSprites,
    width,
    height,
    sid,
    new Set([bhId]),
    towardBasket,
    phaseDurationMs
  );

  const bhPromise = tweenPlayerTo(scene, bh, bhTargetPx, {
    duration: phaseDurationMs,
    easing: "Linear",
  });

  const bhSettleCompleted = await awaitWithTimeout(
    bhPromise,
    phaseDurationMs + 2000,
    "rim_runner_hold_up_ball_handler_settle"
  );
  if (!bhSettleCompleted) {
    incrementFbCounter(scene, "fbAwaitTimeoutCount", 1);
    emitFbTelemetry(scene, "fb_await_timeout", {
      label: "rim_runner_hold_up_ball_handler_settle",
      timeoutMs: phaseDurationMs + 2000,
    });
  }

  for (const [pid, sprite] of Object.entries(playerSprites)) {
    if (sid(pid) === bhId || !sprite || !scene.tweens) continue;
    scene.tweens.killTweensOf(sprite);
  }

  setRimRunnerSpriteGrid(bh, settleBh.x, settleBh.y);
  for (const [pid, sprite] of Object.entries(playerSprites)) {
    if (sid(pid) === bhId || !sprite) continue;
    const gx = Phaser.Math.Clamp((sprite.x / width) * 100, GRID_MIN_X, GRID_MAX_X);
    const gy = Phaser.Math.Clamp(50 - (sprite.y / height) * 50, GRID_MIN_Y, GRID_MAX_Y);
    setRimRunnerSpriteGrid(sprite, gx, gy);
  }

  const raw = turnData.text || "";
  const msg = raw.toLowerCase().includes("holding") ? raw.replace(/^Fast Break! /, "") : "Holding up — settling.";
  appendToTextScroll(msg);
  return { branch: "hold_up", snapshot: captureRrLiveSnapshot(playerSprites, width, height) };
}

async function animateRimRunnerInterception(
  scene,
  turnData,
  playerSprites,
  ballSprite,
  width,
  height
) {
  const roles = turnData.roles || {};
  const phase = roles.rim_runner_burst_phase;
  const sid = (id) => (id != null ? String(id) : null);
  const victimId = sid(
    turnData.victim_id ?? roles.ball_handler_id ?? roles.ball_handler?.player_id
  );
  const stealerId = sid(turnData.stealer_id);
  const rrId = sid(roles.rim_runner_id ?? roles.shooter?.player_id);
  const victim = playerSprites[victimId];
  const stealer = playerSprites[stealerId];
  const rr = rrId ? playerSprites[rrId] : null;
  if (!victim || !stealer) {
    await animateDefensiveStop(scene, turnData, playerSprites, ballSprite, width, height);
    return { branch: "interception", snapshot: captureRrLiveSnapshot(playerSprites, width, height) };
  }

  attachBallToPlayer(scene, ballSprite, victim);
  const away = Boolean(phase?.is_away_offense ?? roles.is_away_offense);
  const towardBasket = away ? -1 : 1;

  let rrGx =
    rr && typeof rr.gridX === "number"
      ? rr.gridX
      : phase?.rr_to?.x ?? 50;
  let rrGy =
    rr && typeof rr.gridY === "number"
      ? rr.gridY
      : phase?.rr_to?.y ?? 25;
  const catchGx = Phaser.Math.Clamp(rrGx + 6 * towardBasket, GRID_MIN_X, GRID_MAX_X);
  const catchGy = Phaser.Math.Clamp(rrGy, GRID_MIN_Y, GRID_MAX_Y);

  const contactGrid = resolveFbInterceptionContactGrid({
    passerSprite: victim,
    receiverTarget: { x: catchGx, y: catchGy },
    receiverSprite: rr,
    width,
    height,
  });
  const lanePx = gridToPixels(contactGrid.x, contactGrid.y, width, height);

  const partialGx = Phaser.Math.Clamp(rrGx + 3 * towardBasket, GRID_MIN_X, GRID_MAX_X);
  const partialPx = gridToPixels(partialGx, catchGy, width, height);

  const tw = [
    tweenPlayerTo(scene, stealer, lanePx, {
      duration: getPlayerDuration(stealer, lanePx.x, lanePx.y, true),
      easing: "Quad.easeOut",
    }),
  ];
  if (rr) {
    tw.push(
      tweenPlayerTo(scene, rr, partialPx, {
        duration: getPlayerDuration(rr, partialPx.x, partialPx.y, true),
        easing: "Linear",
      })
    );
  }
  await Promise.all(tw);
  if (rr) setRimRunnerSpriteGrid(rr, partialGx, catchGy);
  setRimRunnerSpriteGrid(stealer, contactGrid.x, contactGrid.y);

  await runPass(scene, {
    fromId: victimId,
    toId: stealerId,
    endCoords: { x: stealer.x, y: stealer.y },
    easing: "Sine.easeIn",
  });
  await new Promise((resolve) => {
    if (scene.time?.delayedCall) scene.time.delayedCall(45, resolve);
    else setTimeout(resolve, 45);
  });
  const { synchronizeBallState } = await import("./BallControllerAdapter.js");
  synchronizeBallState(scene, { clearPassState: true, allowAttachment: true });
  attachBallToPlayer(scene, ballSprite, stealer, { reason: "rim_runner_interception" });

  const { showAnnouncement, getSecondaryColorForTeam } = await import("../utils/announcements.js");
  const stealerInfo = scene.playerInfo?.[stealerId];
  const stealerTeamId = stealer?.team_id;
  const homeTeamField = scene.simData?.home_team;
  const awayTeamField = scene.simData?.away_team;
  const homeTeamName = typeof homeTeamField === "object" ? homeTeamField?.name : homeTeamField;
  const awayTeamName = typeof awayTeamField === "object" ? awayTeamField?.name : awayTeamField;
  const stealerTeamName = stealerTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
  const stealerPlayerData = stealerInfo
    ? {
        playerId: stealerId,
        photo: stealer?.photo || null,
        teamName: stealerTeamName,
        secondaryColor: getSecondaryColorForTeam(scene, stealerTeamId),
      }
    : null;
  const defenseSide = stealer?.team === "home" ? "home" : "away";
  showAnnouncement("Interception!", defenseSide, stealerPlayerData);
  const holdMs = animationConfig.fastBreak?.defensiveStopHoldMs ?? 1000;
  await new Promise((resolve) => {
    if (scene.time?.delayedCall) scene.time.delayedCall(holdMs, resolve);
    else setTimeout(resolve, holdMs);
  });

  await finalizeRimRunnerNonShotTurn(scene, turnData, playerSprites);
  return { branch: "interception", snapshot: captureRrLiveSnapshot(playerSprites, width, height) };
}

async function animateRimRunnerBatOob(
  scene,
  turnData,
  playerSprites,
  ballSprite,
  width,
  height
) {
  const { animateBallToPosition } = await import("./ballAnimationSimple.js");
  const roles = turnData.roles || {};
  const phase = roles.rim_runner_burst_phase;
  const sid = (id) => (id != null ? String(id) : null);
  const bhId = sid(
    roles.ball_handler_id ?? roles.ball_handler?.player_id ?? roles.passer?.player_id
  );
  const rrId = sid(roles.rim_runner_id ?? roles.shooter?.player_id);
  const bh = playerSprites[bhId];
  const rr = rrId ? playerSprites[rrId] : null;

  let defId = sid(turnData.defender_id ?? turnData.defenderId);
  const defObj = roles.defender;
  if (!defId && defObj && typeof defObj === "object") {
    defId = sid(defObj.player_id ?? defObj.playerId);
  }
  if (!defId && Array.isArray(roles.defense) && roles.defense[0]) {
    const d0 = roles.defense[0];
    defId = sid(typeof d0 === "string" ? d0 : d0.player_id ?? d0.playerId);
  }
  const defSp = defId ? playerSprites[defId] : null;

  if (!bh) {
    await animateDefensiveStop(scene, turnData, playerSprites, ballSprite, width, height);
    return { branch: "bat_oob", snapshot: captureRrLiveSnapshot(playerSprites, width, height) };
  }

  attachBallToPlayer(scene, ballSprite, bh);
  const away = Boolean(phase?.is_away_offense ?? roles.is_away_offense);
  const towardBasket = away ? -1 : 1;
  const bg = rimRunnerSpriteGrid(bh, width, height);
  const rg = rr ? rimRunnerSpriteGrid(rr, width, height) : { x: phase?.rr_to?.x ?? bg.x, y: phase?.rr_to?.y ?? bg.y };
  const catchGx = Phaser.Math.Clamp(rg.x + 6 * towardBasket, GRID_MIN_X, GRID_MAX_X);
  const catchGy = Phaser.Math.Clamp(rg.y, GRID_MIN_Y, GRID_MAX_Y);
  const contactGrid = resolveFbInterceptionContactGrid({
    passerTarget: bg,
    passerSprite: bh,
    receiverTarget: { x: catchGx, y: catchGy },
    receiverSprite: rr,
    width,
    height,
  });

  const movers = [];
  if (rr) {
    const pc = gridToPixels(
      Phaser.Math.Clamp(rg.x + 4 * towardBasket, GRID_MIN_X, GRID_MAX_X),
      catchGy,
      width,
      height
    );
    movers.push(
      tweenPlayerTo(scene, rr, pc, {
        duration: getPlayerDuration(rr, pc.x, pc.y, true),
        easing: "Linear",
      })
    );
  }
  if (defSp) {
    const defLanePx = gridToPixels(contactGrid.x, contactGrid.y, width, height);
    movers.push(
      tweenPlayerTo(scene, defSp, defLanePx, {
        duration: getPlayerDuration(defSp, defLanePx.x, defLanePx.y, true),
        easing: "Quad.easeOut",
      })
    );
  }
  if (movers.length) await Promise.all(movers);

  if (defSp) {
    setRimRunnerSpriteGrid(defSp, contactGrid.x, contactGrid.y);
  }
  const contactPx = gridToPixels(contactGrid.x, contactGrid.y, width, height);
  detachBall(scene, ballSprite);
  await animateBallToPosition(scene, contactPx, {
    duration: getBallDuration(ballSprite, contactPx.x, contactPx.y),
    easing: "Sine.easeInOut",
  });

  const oobGrid = resolveNearestOutOfBoundsGrid(contactGrid);
  const oobPx = gridToPixels(oobGrid.x, oobGrid.y, width, height);
  await animateBallToPosition(scene, oobPx, {
    duration: getBallDuration(ballSprite, oobPx.x, oobPx.y),
    easing: "Quad.easeOut",
  });

  appendToTextScroll("Batted out of bounds.");
  const { showAnnouncement } = await import("../utils/announcements.js");
  showAnnouncement("Out of bounds!", "neutral", null);
  await new Promise((resolve) => {
    if (scene.time?.delayedCall) scene.time.delayedCall(650, resolve);
    else setTimeout(resolve, 650);
  });

  await finalizeRimRunnerNonShotTurn(scene, turnData, playerSprites);
  return { branch: "bat_oob", snapshot: captureRrLiveSnapshot(playerSprites, width, height) };
}

/**
 * Simplified Fast Break Animation System
 * 
 * Flow:
 * 1. Outlet Pass (if outlet_passer exists)
 * 2. Fast Break Resolution (shot, stop, foul, turnover, steal)
 * 3. Outcome handling and state transitions
 */

export async function runFastBreakSequence({
  scene,
  turnData,
  playerSprites,
  ballSprite,
  turnIndex = null,
}) {
  if (!scene || !turnData || scene.skipToEnd) {
    return;
  }
  if (!scene.ballSprite) scene.ballSprite = ballSprite;
  
  const width = scene.game.config.width;
  const height = scene.game.config.height;
  const debugEnabled = isAnimationDebugEnabled();
  
  // Stop any existing timeline/tweens
  if (scene.__activeTimeline) {
    scene.__activeTimeline.stop();
    scene.__activeTimeline = null;
  }
  
  const currentState = scene.stateMachine?.state;
  const hasRimRunnerBurst = Boolean(turnData.roles?.rim_runner_burst_phase);
  const hasStandardOutlet =
    turnData.roles?.outlet_passer && turnData.roles?.outlet_receiver;
  let rrBurstResult = null;
  let leadInUnit = null;
  const leadInStartMs = Date.now();

  // ✅ Check current state before transitioning - avoid invalid transitions
  // For defensive stops after HCO, we're already in HalfCourt, so transition to FastBreak directly
  // For Fast Break from DREB, we should be in Rebound/OutletSetup, so can transition to FastBreakOutlet
  if (
    (hasStandardOutlet || hasRimRunnerBurst) &&
    currentState !== States.FastBreak &&
    currentState !== States.FastBreakOutlet
  ) {
    if (currentState === States.Rebound || currentState === States.OutletSetup) {
      safeTransition(scene.stateMachine, States.FastBreakOutlet);
    } else {
      safeTransition(scene.stateMachine, States.FastBreak);
    }
  } else if (currentState !== States.FastBreak && currentState !== States.FastBreakOutlet) {
    safeTransition(scene.stateMachine, States.FastBreak);
  }
  
  scene.events?.emit("fb:start");
  
  // ============================================================================
  // PHASE 1: Rim Runner burst + outlet (or standard Covert-style outlet)
  // ============================================================================
  if (hasRimRunnerBurst) {
    rrBurstResult = await animateRimRunnerBurstPhase(
      scene,
      turnData,
      playerSprites,
      ballSprite,
      width,
      height
    );
    leadInUnit = turnData.roles?.is_steal_entry
      ? "fb.lead_in.from_hco_steal"
      : "fb.lead_in.from_dreb_release";
    enforceFbUnitContract({
      scene,
      turnData,
      unitId: "fb.phase.entry_burst",
      advanceTrigger: "required movers reach burst targets",
      visualSettleTrigger: "burst tweens settled",
      authorizingEventReceived: true,
      visualSettled: true,
      unitStartMs: leadInStartMs,
      budgetKind: "phase",
      context: { phase: "entry_burst" },
    });
    if (scene.stateMachine?.state !== States.FastBreak) {
      safeTransition(scene.stateMachine, States.FastBreak);
    }
  } else if (hasStandardOutlet) {
    await animateOutletPhase(scene, turnData, playerSprites, ballSprite, width, height);
    leadInUnit = "fb.lead_in.from_dreb_release";
    enforceFbUnitContract({
      scene,
      turnData,
      unitId: "fb.phase.outlet",
      advanceTrigger: "outlet pass received",
      visualSettleTrigger: "passer/receiver movement + pass settled",
      authorizingEventReceived: true,
      visualSettled: true,
      unitStartMs: leadInStartMs,
      budgetKind: "phase",
      context: { phase: "outlet" },
    });
    if (scene.stateMachine?.state !== States.FastBreak) {
      safeTransition(scene.stateMachine, States.FastBreak);
    }
  } else if (turnData.roles?.is_steal_entry || (!turnData.roles?.outlet_passer && !turnData.roles?.outlet_receiver)) {
    // ============================================================================
    // PHASE 1b: STEAL ENTRY (for steal-initiated Fast Breaks)
    // ============================================================================
    // Check is_steal_entry flag OR if there's no outlet pass (steal-initiated)
    await animateStealEntry(scene, turnData, playerSprites, ballSprite, width, height);
    leadInUnit = "fb.lead_in.from_hco_steal";
    
    // Transition to FastBreak state after steal entry
    if (scene.stateMachine?.state !== States.FastBreak) {
      safeTransition(scene.stateMachine, States.FastBreak);
    }
  }
  if (leadInUnit) {
    const leadInAdvanceTrigger =
      leadInUnit === "fb.lead_in.from_hco_steal"
        ? "FB route committed + entry owner resolved"
        : "DREB committed + FB route committed";
    const leadInVisualSettleTrigger =
      leadInUnit === "fb.lead_in.from_hco_steal"
        ? "steal handoff visuals settled"
        : "rebound secure + release setup settled";
    enforceFbUnitContract({
      scene,
      turnData,
      unitId: leadInUnit,
      advanceTrigger: leadInAdvanceTrigger,
      visualSettleTrigger: leadInVisualSettleTrigger,
      authorizingEventReceived: true,
      visualSettled: true,
      unitStartMs: leadInStartMs,
      budgetKind: "lead_in",
      context: { phase: "lead_in", leadInUnit },
    });
  }
  
  if (scene.skipToEnd) {
    return;
  }
  
  // ============================================================================
  // PHASE 2: FAST BREAK RESOLUTION — contract-ordered routing (Rim Runner + generic FB)
  // ============================================================================
  const result = turnData.result_type;
  const isBlockingFoul =
    result === "FOUL" &&
    turnData.foul_team === "DEFENSE" &&
    turnData.text?.toLowerCase().includes("blocking foul");

  const phase2Kind = classifyFastBreakPhase2(turnData, { isBlockingFoul });
  const branchKind = deriveFbBranchKind(turnData, phase2Kind);
  initFbTelemetryContext(scene, { turnData, turnIndex, branchKind });
  if (branchKind === "rr_outlet_denied") {
    logRrDenied(scene, "ROUTE", {
      phase2Kind,
      branchKind,
      rim_runner_outlet_failed: Boolean(turnData.rim_runner_outlet_failed),
      fast_break_play: turnData.fast_break_play ?? null,
      resultType: turnData.result_type ?? null,
    });
  }

  try {
    const resolutionStartMs = Date.now();
    const triangleSetupRequired =
      isTriangleSequence(turnData) &&
      !turnData.rim_runner_outlet_failed &&
      Boolean(getTriangleSetupPayload(turnData));

    if (triangleSetupRequired) {
      await animateTriangleSetupPhase(scene, turnData, playerSprites, ballSprite, width, height);
    }

    if (shouldAnimateRimRunnerLanePass(turnData, phase2Kind)) {
      await animateRimRunnerLanePass(scene, turnData, playerSprites, ballSprite, width, height);
    }

    if (phase2Kind === "fast_break_shot") {
      if (triangleSetupRequired) {
        await animateTriangleDecisionLeadIn(scene, turnData, playerSprites, ballSprite, width, height);
      }
      if (turnData.roles?.ball_handler_beats_defender && turnData.stopper_id) {
        await animateFastBreakShotWithStopper(scene, turnData, playerSprites, ballSprite, width, height);
      } else {
        await animateFastBreakShot(scene, turnData, playerSprites, ballSprite, width, height);
      }
      enforceFbUnitContract({
        scene,
        turnData,
        unitId: "fb.phase.shot_attempt",
        advanceTrigger: "shot release/result committed",
        visualSettleTrigger: "shot visuals settled",
        authorizingEventReceived: true,
        visualSettled: true,
        unitStartMs: resolutionStartMs,
        budgetKind: "phase",
        context: { phase2Kind },
      });
    } else if (phase2Kind === "fast_break_shot_foul") {
      if (triangleSetupRequired) {
        await animateTriangleDecisionLeadIn(scene, turnData, playerSprites, ballSprite, width, height);
      }
      await animateFastBreakShot(scene, turnData, playerSprites, ballSprite, width, height, { foulOnly: true });
      enforceFbUnitContract({
        scene,
        turnData,
        unitId: "fb.phase.shot_attempt",
        advanceTrigger: "shot release/result committed",
        visualSettleTrigger: "shot visuals settled",
        authorizingEventReceived: true,
        visualSettled: true,
        unitStartMs: resolutionStartMs,
        budgetKind: "phase",
        context: { phase2Kind },
      });
    } else if (phase2Kind === "rim_runner_steal") {
      await animateRimRunnerInterception(
        scene,
        turnData,
        playerSprites,
        ballSprite,
        width,
        height
      );
      enforceFbUnitContract({
        scene,
        turnData,
        unitId: "fb.phase.defensive_stop",
        advanceTrigger: "ball attaches to intercepting player's sprite",
        visualSettleTrigger: "stop visuals settled",
        authorizingEventReceived: true,
        visualSettled: true,
        unitStartMs: resolutionStartMs,
        budgetKind: "phase",
        context: { phase2Kind },
      });
    } else if (phase2Kind === "rim_runner_bat_oob") {
      await animateRimRunnerBatOob(scene, turnData, playerSprites, ballSprite, width, height);
      enforceFbUnitContract({
        scene,
        turnData,
        unitId: "fb.phase.defensive_stop",
        advanceTrigger: "ball reaches out-of-bounds destination",
        visualSettleTrigger: "stop visuals settled",
        authorizingEventReceived: true,
        visualSettled: true,
        unitStartMs: resolutionStartMs,
        budgetKind: "phase",
        context: { phase2Kind },
      });
    } else if (phase2Kind === "rim_runner_hco_settle") {
      if (turnData.rim_runner_outlet_failed) {
        await animateRimRunnerOutletDeniedBeat(
          scene,
          turnData,
          playerSprites,
          ballSprite,
          width,
          height,
          rrBurstResult?.phase ?? turnData.roles?.rim_runner_burst_phase,
          rrBurstResult?.passerSprite ??
            playerSprites[
              String(
                turnData.roles?.rim_runner_burst_phase?.outlet_passer_id ??
                  turnData.roles?.outlet_passer ??
                  ""
              )
            ],
          rrBurstResult?.recvSprite ??
            playerSprites[
              String(turnData.roles?.rim_runner_burst_phase?.outlet_receiver_id ?? "")
            ]
        );
      } else {
        await animateRimRunnerHoldUpLeadIn(
          scene,
          turnData,
          playerSprites,
          ballSprite,
          width,
          height
        );
      }
      await finalizeRimRunnerNonShotTurn(scene, turnData, playerSprites);
      enforceFbUnitContract({
        scene,
        turnData,
        unitId: "fb.phase.defensive_stop",
        advanceTrigger: "stop result committed",
        visualSettleTrigger: "stop visuals settled",
        authorizingEventReceived: true,
        visualSettled: true,
        unitStartMs: resolutionStartMs,
        budgetKind: "phase",
        context: { phase2Kind },
      });
    } else if (phase2Kind === "triangle_hco_settle") {
      await animateTriangleHcoSettle(scene, turnData, playerSprites, ballSprite, width, height);
      enforceFbUnitContract({
        scene,
        turnData,
        unitId: "triangle.phase.finish",
        advanceTrigger: "same-side corner reached HCO trigger spot",
        visualSettleTrigger: "Triangle HCO settle visuals settled",
        authorizingEventReceived: true,
        visualSettled: true,
        unitStartMs: resolutionStartMs,
        budgetKind: "phase",
        context: { phase2Kind },
      });
    } else {
      await animateDefensiveStop(scene, turnData, playerSprites, ballSprite, width, height);
      enforceFbUnitContract({
        scene,
        turnData,
        unitId: "fb.phase.defensive_stop",
        advanceTrigger: "stop result committed",
        visualSettleTrigger: "stop visuals settled",
        authorizingEventReceived: true,
        visualSettled: true,
        unitStartMs: resolutionStartMs,
        budgetKind: "phase",
        context: { phase2Kind },
      });
    }
    if (
      (phase2Kind === "fast_break_shot" || phase2Kind === "fast_break_shot_foul") &&
      (String(turnData?.result_type || "").toUpperCase() === "MISS" ||
        String(turnData?.result_type || "").toUpperCase() === "BLOCK")
    ) {
      enforceFbUnitContract({
        scene,
        turnData,
        unitId: "fb.phase.rebound_resolution",
        advanceTrigger: "rebound outcome committed",
        visualSettleTrigger: "rebound attach + settle complete",
        authorizingEventReceived: true,
        visualSettled: true,
        unitStartMs: resolutionStartMs,
        budgetKind: "phase",
        context: { phase2Kind, reboundType: turnData?.rebound_type ?? null },
      });
    }
    
    if (scene.skipToEnd) {
      return;
    }
    
    // ============================================================================
    // PHASE 3: CLEANUP & STATE TRANSITIONS
    // ============================================================================
    const outStartMs = Date.now();
    const route = String(turnData?.next_play_type || turnData?.next_turn || "").toUpperCase();
    enforceFbUnitContract({
      scene,
      turnData,
      unitId: "fb.out.to_*",
      advanceTrigger: "route committed",
      visualSettleTrigger: "final FB settle complete",
      authorizingEventReceived: !!route || turnData?.quarter_ends_after === true,
      visualSettled: true,
      unitStartMs: outStartMs,
      budgetKind: "out",
      context: { route: route || null, quarterEndsAfter: turnData?.quarter_ends_after === true },
    });
    scene.events?.emit("fb:end");
  } finally {
    finalizeFbTelemetry(scene);
  }
}

/**
 * Rim Runner: simultaneous setup tweens (RR sprint, outlet contest defender, role players),
 * then outlet pass only after the outlet receiver's tween completes (others may still be moving).
 *
 * Each burst target uses one tween at universal speed (`getPlayerDuration` = distance ÷ AG×game-speed px/s).
 */
async function animateRimRunnerBurstPhase(scene, turnData, playerSprites, ballSprite, width, height) {
  const phase = turnData.roles?.rim_runner_burst_phase;
  if (!phase) return { branch: "none", snapshot: captureRrLiveSnapshot(playerSprites, width, height) };

  const sid = (id) => (id != null ? String(id) : null);
  const rrSprite = playerSprites[sid(phase.rr_id)];
  const recvSprite = playerSprites[sid(phase.outlet_receiver_id)];
  if (!rrSprite || !recvSprite) {
    return { branch: "none", snapshot: captureRrLiveSnapshot(playerSprites, width, height) };
  }

  const secondary = [];
  const secondarySprites = [];
  const startTween = (sprite, grid) => {
    if (!sprite || grid == null || grid.x == null || grid.y == null) return;
    const px = gridToPixels(grid.x, grid.y, width, height);
    const dur = getPlayerDuration(sprite, px.x, px.y, true);
    secondary.push(
      tweenPlayerTo(scene, sprite, px, { duration: dur, easing: "Linear" })
    );
    secondarySprites.push(sprite);
  };

  startTween(rrSprite, phase.rr_to);
  if (phase.outlet_defender_id != null && phase.outlet_defender_to) {
    startTween(playerSprites[sid(phase.outlet_defender_id)], phase.outlet_defender_to);
  }
  for (const row of phase.other_players || []) {
    startTween(playerSprites[sid(row.player_id)], { x: row.to_x, y: row.to_y });
  }
  // These movers can be stopped by downstream branch handoff logic; consume their
  // eventual outcomes to avoid unhandled promise rejections on expected stop().
  void Promise.allSettled(secondary);

  const recvTargetPx = gridToPixels(phase.receiver_to.x, phase.receiver_to.y, width, height);
  const recvDur = getPlayerDuration(recvSprite, recvTargetPx.x, recvTargetPx.y, true);
  const receiverPromise = tweenPlayerTo(scene, recvSprite, recvTargetPx, {
    duration: recvDur,
    easing: "Linear",
  });

  const passerSprite = phase.skip_outlet_pass
    ? recvSprite
    : playerSprites[sid(phase.outlet_passer_id ?? turnData.roles?.outlet_passer)];
  if (passerSprite) {
    attachBallToPlayer(scene, ballSprite, passerSprite);
  }

  await receiverPromise;

  const outletDenied = Boolean(turnData.rim_runner_outlet_failed);
  if (outletDenied) {
    // RR burst only owns the fork into outlet-denied. Once receiver reaches the
    // fork point, the dedicated denied branch becomes the sole owner.
    if (isCriticalEventPatternEnabled()) {
      for (const sprite of secondarySprites) {
        if (sprite && scene.tweens) scene.tweens.killTweensOf(sprite);
      }
    }
    logRrDenied(scene, "BURST FORK", {
      receiverLive: rimRunnerLiveSpriteGrid(recvSprite, width, height),
      rrLive: rimRunnerLiveSpriteGrid(rrSprite, width, height),
      outletDefenderId: sid(phase.outlet_defender_id),
      snapshot: captureRrLiveSnapshot(playerSprites, width, height),
    });
    return {
      branch: "outlet_denied",
      snapshot: captureRrLiveSnapshot(playerSprites, width, height),
      phase,
      passerSprite,
      recvSprite,
    };
  }

  const shouldPass = !outletDenied && !phase.skip_outlet_pass && passerSprite;

  if (shouldPass) {
    await runPass(scene, {
      fromId: sid(phase.outlet_passer_id ?? turnData.roles?.outlet_passer),
      toId: sid(phase.outlet_receiver_id),
      easing: "Sine.easeInOut",
    });
    await new Promise((resolve) => {
      if (scene.time?.delayedCall) {
        scene.time.delayedCall(50, resolve);
      } else {
        setTimeout(resolve, 50);
      }
    });
    const { getBallController, synchronizeBallState } = await import("./BallControllerAdapter.js");
    const ballController = getBallController();
    synchronizeBallState(scene, {
      clearPassState: true,
      allowAttachment: true,
    });
    if (ballController && recvSprite) {
      const isAttachedToReceiver =
        ballController.isAttached && ballController.currentOwner === recvSprite;
      const isInFlight = ballController.isInFlight;
      const wrongOwner =
        ballController.isAttached && ballController.currentOwner !== recvSprite;
      if (!isAttachedToReceiver || isInFlight || wrongOwner) {
        if (isInFlight) {
          ballController.onPassEnd(recvSprite, { reason: "rim_runner_burst_pass_fix" });
        } else {
          attachBallToPlayer(scene, ballSprite, recvSprite, {
            reason: "rim_runner_burst_pass_verify",
            debugInfo: { reason: "rim_runner_burst_pass_verify", wasInFlight: isInFlight },
          });
        }
      }
      if (!ballController.isAttached || ballController.currentOwner !== recvSprite) {
        synchronizeBallState(scene, { clearPassState: true, allowAttachment: true });
        attachBallToPlayer(scene, ballSprite, recvSprite, {
          reason: "rim_runner_burst_pass_retry",
          debugInfo: { reason: "rim_runner_burst_pass_retry" },
        });
      }
    }
  }

  if (isCriticalEventPatternEnabled()) {
    // Critical event has fired (receiver has the ball). Stop parallel secondary
    // tweens so they don't continue running into the next phase. Sprites hold at
    // their interrupted positions; downstream phases spawn fresh tweens if needed.
    for (const sprite of secondarySprites) {
      if (sprite && scene.tweens) scene.tweens.killTweensOf(sprite);
    }
    // Logical grid = live position for all sprites. Destination-based commits
    // would diverge from visual positions when secondary tweens are killed mid-flight.
    commitRrLiveSpriteGrid(playerSprites, width, height);
  } else {
    if (secondary.length) {
      await Promise.all(secondary);
    }
    // Commit burst endpoints into logical grid state before branch-specific follow-up
    // uses `rimRunnerSpriteGrid(...)`. Without this, stale gridX/gridY from a prior
    // sequence can skew RR lane-pass, interception, or bat-OOB geometry.
    if (phase.rr_to && rrSprite) {
      setRimRunnerSpriteGrid(rrSprite, phase.rr_to.x, phase.rr_to.y);
    }
    if (phase.receiver_to && recvSprite) {
      setRimRunnerSpriteGrid(recvSprite, phase.receiver_to.x, phase.receiver_to.y);
    }
    if (phase.outlet_defender_id != null && phase.outlet_defender_to) {
      const outletDefenderSprite = playerSprites[sid(phase.outlet_defender_id)];
      if (outletDefenderSprite) {
        setRimRunnerSpriteGrid(
          outletDefenderSprite,
          phase.outlet_defender_to.x,
          phase.outlet_defender_to.y
        );
      }
    }
    for (const row of phase.other_players || []) {
      const sprite = playerSprites[sid(row.player_id)];
      if (!sprite) continue;
      setRimRunnerSpriteGrid(sprite, row.to_x, row.to_y);
    }
  }
  return {
    branch: "outlet_completed",
    snapshot: captureRrLiveSnapshot(playerSprites, width, height),
    phase,
    passerSprite,
    recvSprite,
  };
}

/**
 * Phase 1: Outlet Pass Animation
 * - Outlet receiver moves to target spot
 * - Defenders chase (move toward basket)
 * - All other players hold position
 */
async function animateOutletPhase(scene, turnData, playerSprites, ballSprite, width, height) {
  const passerId = turnData.roles.outlet_passer;
  const receiverId = turnData.roles.outlet_receiver;
  const passerSprite = playerSprites[passerId];
  const receiverSprite = playerSprites[receiverId];
  
  if (!passerSprite || !receiverSprite) return;
  
  // Attach ball to rebounder/passer
  attachBallToPlayer(scene, ballSprite, passerSprite);
  
  // Determine offense team and basket
  const isHomeOffense = receiverSprite.team === "home";
  const targetBasket = isHomeOffense ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
  const newOffenseTeam = isHomeOffense ? "home" : "away";
  
  // Find the original MISS turn to get offense_getback list
  let missTurn = null;
  const currentIndex = scene.currentTurn || 0;
  const previousTurn = scene.simData?.turns?.[currentIndex - 1];
  const currentTurn = scene.simData?.turns?.[currentIndex];
  
  if (previousTurn?.result_type === "MISS" || previousTurn?.result_type === "BLOCK") {
    missTurn = previousTurn;
  } else if (currentTurn?.result_type === "MISS" || currentTurn?.result_type === "BLOCK") {
    missTurn = currentTurn;
  }
  
  const getBackList = missTurn?.offense_getback || [];
  
  // ✅ Outlet receiver receives pass at current position (NO MOVEMENT during outlet pass)
  // Ball handler will only move during defensive stop/shot attempt step
  const receiverCurrentGrid = {
    x: (receiverSprite.x / width) * 100,
    y: 50 - (receiverSprite.y / height) * 50
  };
  
  // Outlet receiver stays at current position (no movement)
  const outletTarget = receiverCurrentGrid;
  const outletPx = gridToPixels(outletTarget.x, outletTarget.y, width, height);
  
  const promises = [];
  
  // Outlet receiver receives pass at current position (no movement animation needed)
  // Note: Ball will still animate from passer to receiver, but receiver doesn't move
  
  // ✅ Defenders stay at current position during outlet pass (NO MOVEMENT)
  // Defenders will only move during defensive stop/shot attempt step
  // Note: No animation needed for defenders during outlet pass
  
  // ✅ TEMPORARILY COMMENTED OUT: Advance other players during outlet step
  // For now, only animate the outlet pass - other players stay where they are
  // TODO: May want to re-enable this in the future for more organic fast break feel
  /*
  // ✅ SIMULTANEOUSLY advance all other players (except get-back, outlet passer, and outlet receiver)
  // This moves players up the court at the same time as the outlet pass
  let playersAdvanced = 0;
  for (const [id, sprite] of Object.entries(playerSprites)) {
    const info = scene.playerInfo?.[id];
    const isGetBackPlayer = getBackList.includes(id);
    const isOutletPasser = id === passerId;
    const isOutletReceiver = id === receiverId;
    const isDefender = defendersSet.has(id);
    
    // Skip: get-back players, outlet passer/receiver, defenders (already handled above)
    if (!info || isGetBackPlayer || isOutletPasser || isOutletReceiver || isDefender) {
      continue;
    }
    
    // Calculate movement toward new offense basket
    const currentGridX = (sprite.x / width) * 100;
    const currentGridY = 50 - (sprite.y / height) * 50;
    
    // Move 20-30 grid spots toward new offense basket
    const distance = Phaser.Math.Between(20, 30);
    const directionAdvance = newOffenseTeam === "home" ? 1 : -1;
    
    const targetGrid = {
      x: Phaser.Math.Clamp(
        currentGridX + directionAdvance * distance,
        4,
        97
      ),
      y: Phaser.Math.Clamp(
        currentGridY + Phaser.Math.Between(-10, 10),
        10,
        40
      )
    };
    
    const targetPx = gridToPixels(targetGrid.x, targetGrid.y, width, height);
    const playerDuration = getPlayerDuration(sprite, targetPx.x, targetPx.y, true);
    
    promises.push(
      tweenPlayerTo(scene, sprite, targetPx, {
        duration: playerDuration,
        easing: "Linear"
      })
    );
    playersAdvanced++;
  }
  */
  
  // Wait for receiver and defenders to complete (outlet pass happens after)
  await Promise.all(promises);
  
  // THEN outlet pass (happens after all players are in position, but visually flows with the movement)
  await runPass(scene, {
    fromId: passerId,
    toId: receiverId,
    easing: "Sine.easeInOut",
  });
  
  // ✅ PHASE 2.8: Defensive attachment verification for fast breaks
  // Wait a small delay to ensure pass animation is fully complete
  // Then verify and fix attachment if needed
  await new Promise(resolve => {
    if (scene.time?.delayedCall) {
      scene.time.delayedCall(50, resolve); // Small delay to ensure pass completes
    } else {
      setTimeout(resolve, 50);
    }
  });
  
  const { getBallController, synchronizeBallState } = await import('./BallControllerAdapter.js');
  const ballController = getBallController();
  
  // ✅ PHASE 2.9: Synchronize state to ensure consistency
  synchronizeBallState(scene, {
    clearPassState: true,
    allowAttachment: true
  });
  
  if (ballController && receiverSprite) {
    // ✅ DEFENSIVE: Multiple checks to ensure ball is properly attached
    const isAttachedToReceiver = ballController.isAttached && 
                                  ballController.currentOwner === receiverSprite;
    const isInFlight = ballController.isInFlight;
    const wrongOwner = ballController.isAttached && 
                       ballController.currentOwner !== receiverSprite;
    
    // Fix attachment if needed
    if (!isAttachedToReceiver || isInFlight || wrongOwner) {
      // Clear any in-flight state first
      if (isInFlight) {
        ballController.onPassEnd(receiverSprite, { reason: 'fast_break_outlet_fix' });
      } else {
        // Direct attachment if not in flight
        attachBallToPlayer(scene, ballSprite, receiverSprite, { 
          reason: 'fast_break_outlet_verify',
          debugInfo: { reason: 'fast_break_outlet_verify', wasInFlight: isInFlight }
        });
      }
    }
    
    // ✅ DEFENSIVE: Verify attachment succeeded with retry
    if (!ballController.isAttached || ballController.currentOwner !== receiverSprite) {
      console.warn('Fast break: Ball attachment verification failed, retrying...', {
        isAttached: ballController.isAttached,
        currentOwner: ballController.currentOwner?.playerId,
        expectedReceiver: receiverId,
        isInFlight: ballController.isInFlight,
        reason: ballController.reason
      });
      // Retry attachment with state sync
      synchronizeBallState(scene, { clearPassState: true, allowAttachment: true });
      attachBallToPlayer(scene, ballSprite, receiverSprite, { 
        reason: 'fast_break_outlet_retry',
        debugInfo: { reason: 'fast_break_outlet_retry' }
      });
    }
  }
}

/**
 * Phase 1b: Steal Entry Animation (for steal-initiated Fast Breaks)
 * - Stealer (ball handler) moves 5-10 x spots toward basket
 * - Stealer moves ±4 y spots (clamped to 3-47)
 * - Ball is already attached to stealer from the steal turn
 */
async function animateStealEntry(scene, turnData, playerSprites, ballSprite, width, height) {
  // Get ball handler ID from roles (backend stores player object, frontend gets ID)
  const ballHandlerId = turnData.roles?.ball_handler_id ||
                        turnData.roles?.ball_handler?.player_id || 
                        turnData.ball_handler_id ||
                        turnData.stealer_id; // Fallback to stealer_id for steals
  const ballHandlerSprite = ballHandlerId ? playerSprites[ballHandlerId] : null;
  
  if (!ballHandlerSprite) {
    console.warn("Steal Entry: Ball handler sprite not found", { 
      ballHandlerId, 
      roles: turnData.roles,
      stealer_id: turnData.stealer_id 
    });
    return;
  }
  
  // Ball should already be attached to stealer from the steal turn
  // Verify attachment
  const { getBallController } = await import('./BallControllerAdapter.js');
  const ballController = getBallController();
  
  if (!ballController?.isAttached || ballController.currentOwner !== ballHandlerSprite) {
    // Attach ball to stealer if not already attached
    attachBallToPlayer(scene, ballSprite, ballHandlerSprite, {
      reason: 'steal_entry_verify'
    });
  }
  
  // Get stealer's current position
  const currentGrid = {
    x: ballHandlerSprite.gridX || 50,
    y: ballHandlerSprite.gridY || 25
  };
  
  // ✅ DETAILED LOGGING: Track frontend Steal Entry calculation
  console.warn("🏀 [FRONTEND STEAL ENTRY] Entry:", {
    ballHandlerId,
    currentSpritePosition: { x: ballHandlerSprite.gridX, y: ballHandlerSprite.gridY },
    roles: turnData.roles,
    backendOutletX: turnData.roles?.ball_handler_outlet_x,
    backendOutletY: turnData.roles?.ball_handler_outlet_y,
    backendMoveX: turnData.roles?.ball_handler_move_x,
    backendMoveY: turnData.roles?.ball_handler_move_y
  });
  
  // Determine offense team and direction
  const isHomeOffense = ballHandlerSprite.team === "home";
  const direction = isHomeOffense ? 1 : -1; // +1 for home (toward x=90), -1 for away (toward x=10)
  
  // Calculate steal entry movement (matches backend calculation)
  // Backend sends ball_handler_move_x and ball_handler_move_y in turnData.roles
  const moveX = turnData.roles?.ball_handler_move_x || 
                Phaser.Math.Between(STEAL_ENTRY_MOVE_X_MIN, STEAL_ENTRY_MOVE_X_MAX);
  const moveY = turnData.roles?.ball_handler_move_y || 
                Phaser.Math.Between(-STEAL_ENTRY_MOVE_Y_RANGE, STEAL_ENTRY_MOVE_Y_RANGE);
  
  // ✅ FIX: Use backend-provided final coordinates if available (more accurate)
  // Otherwise, calculate from current position
  let targetGrid;
  if (turnData.roles?.ball_handler_outlet_x !== undefined && turnData.roles?.ball_handler_outlet_y !== undefined) {
    // Use backend-calculated final position (for steals, outlet_x/y is the position after steal entry)
    targetGrid = {
      x: turnData.roles.ball_handler_outlet_x,
      y: turnData.roles.ball_handler_outlet_y
    };
    console.warn("🏀 [FRONTEND STEAL ENTRY] Using backend final coordinates:", targetGrid);
  } else {
    // Fallback: Calculate from current position (shouldn't happen if backend is correct)
    targetGrid = {
      x: currentGrid.x + (direction * moveX),
      y: Phaser.Math.Clamp(
        currentGrid.y + moveY,
        STEAL_ENTRY_Y_MIN,
        STEAL_ENTRY_Y_MAX
      )
    };
    console.warn("⚠️ [FRONTEND STEAL ENTRY] Calculated target (backend coords missing):", targetGrid);
  }
  
  console.warn("🏀 [FRONTEND STEAL ENTRY] Movement Details:", {
    startingPosition: currentGrid,
    direction,
    moveX,
    moveY,
    targetPosition: targetGrid,
    calculation: `${currentGrid.x} + (${direction} * ${moveX}) = ${targetGrid.x}`
  });
  
  // Convert to pixel coordinates
  const targetPx = gridToPixels(targetGrid.x, targetGrid.y, width, height);
  
  // Get animation duration
  const playerDuration = getPlayerDuration(ballHandlerSprite, targetPx.x, targetPx.y, true);
  
  // Animate stealer movement
  await tweenPlayerTo(scene, ballHandlerSprite, targetPx, {
    duration: playerDuration,
    easing: "Linear"
  });
  
  // Update sprite grid coordinates
  ballHandlerSprite.gridX = targetGrid.x;
  ballHandlerSprite.gridY = targetGrid.y;
  
  // Verify ball remains attached after movement
  if (ballController && (!ballController.isAttached || ballController.currentOwner !== ballHandlerSprite)) {
    attachBallToPlayer(scene, ballSprite, ballHandlerSprite, {
      reason: 'steal_entry_post_movement'
    });
  }
}

/**
 * Phase 2a: Fast Break Shot Attempt
 * - Ball handler moves near rim
 * - Defender follows
 * - All others move to standard positions
 */
/**
 * Animate Fast Break shot when ball handler beats defender (skill check won).
 * Stopper + trail defender use the unified FB shot-contest spots derived from the shooter final.
 */
async function animateFastBreakShotWithStopper(scene, turnData, playerSprites, ballSprite, width, height) {
  // ✅ FIX: Import showAnnouncement/showAndOneAnnouncement at the start of the function (AND-1 / shooting foul in Fast Break path)
  const { showAnnouncement, showAndOneAnnouncement, getSecondaryColorForTeam } = await import('../utils/announcements.js');
  
  const shooterRawId =
    turnData.roles?.shooter?.player_id ||
    turnData.shooter_id ||
    turnData.roles?.ball_handler?.player_id ||
    getCurrentOwner(scene);
  const shooterRef = resolvePlayerSpriteById(playerSprites, shooterRawId);
  const shooterId = shooterRef.id;
  const shooterSprite = shooterRef.sprite;
  
  if (!shooterSprite) return;
  
  const isHomeOffense = shooterSprite.team === "home";
  const basket = getFastBreakAttackingBasket(isHomeOffense);
  
  let shotSpot;
  if (turnData.shot_spot && typeof turnData.shot_spot.x === "number" && typeof turnData.shot_spot.y === "number") {
    shotSpot = {
      x: Phaser.Math.Clamp(turnData.shot_spot.x, GRID_MIN_X, GRID_MAX_X),
      y: Phaser.Math.Clamp(turnData.shot_spot.y, GRID_MIN_Y, GRID_MAX_Y),
    };
  } else {
    shotSpot = {
      x: isHomeOffense
        ? basket.x - Phaser.Math.Between(1, 4)
        : basket.x + Phaser.Math.Between(1, 4),
      y: basket.y + Phaser.Math.Between(-3, 3),
    };
    shotSpot.x = Phaser.Math.Clamp(shotSpot.x, GRID_MIN_X, GRID_MAX_X);
    shotSpot.y = Phaser.Math.Clamp(shotSpot.y, GRID_MIN_Y, GRID_MAX_Y);
  }
  
  const shotPx = gridToPixels(shotSpot.x, shotSpot.y, width, height);
  
  const promises = [];
  
  // Move shooter (ball handler) past stopper to shot spot
  attachBallToPlayer(scene, ballSprite, shooterSprite);
  const shooterDuration = getPlayerDuration(shooterSprite, shotPx.x, shotPx.y);
  const shooterPromise = tweenPlayerTo(scene, shooterSprite, shotPx, {
    duration: shooterDuration,
    easing: "Linear"
  });
  promises.push(shooterPromise);
  
  // Move stopper to stopper position (between ball handler start and basket)
  const stopperRef = resolvePlayerSpriteById(playerSprites, turnData.stopper_id);
  const stopperId = stopperRef.id;
  const stopperSprite = stopperRef.sprite;
  let stopperPromise = null;
  
  if (stopperSprite) {
    const stopperAnimEnd = getAnimationEndGridForPlayer(turnData, stopperId);
    incrementFbCounter(scene, "fbRequiredRoleCount", 1);
    const stopperSpot =
      stopperAnimEnd ??
      fastBreakShotDefenderGridVsShooter(shotSpot.x, shotSpot.y, isHomeOffense);
    if (!stopperAnimEnd) {
      const source = rimRunnerSpriteGrid(stopperSprite, width, height);
      reportMissingEndpoint(scene, turnData, {
        playerId: stopperId,
        role: "stopper",
        requiredEndpointType: "animations_end",
        hasRoleCoord: false,
        reason: "missing_stopper_animation_end",
      });
      reportFallback(scene, {
        playerId: stopperId,
        role: "stopper",
        fallbackPolicy: "defender_vs_shooter_grid",
        missingAuthority: ["animations_end"],
        source,
        target: stopperSpot,
      });
    }
    const stopperPx = gridToPixels(stopperSpot.x, stopperSpot.y, width, height);
    const stopperDuration = getPlayerDuration(stopperSprite, stopperPx.x, stopperPx.y);
    stopperPromise = tweenPlayerTo(scene, stopperSprite, stopperPx, {
      duration: stopperDuration,
      easing: "Linear"
    });
    promises.push(stopperPromise);
  }
  
  // Move primary defender (if different from stopper/shooter)
  const defenderRef = resolveFastBreakDefenderSprite(playerSprites, turnData, {
    excludeIds: [stopperId, shooterId],
  });
  const defenderId = defenderRef.id;
  const defenderSprite = defenderRef.sprite;
  
  if (defenderSprite) {
    let defenderSpot;
    if (
      turnData.defender_spot &&
      typeof turnData.defender_spot.x === "number" &&
      typeof turnData.defender_spot.y === "number"
    ) {
      defenderSpot = {
        x: Phaser.Math.Clamp(turnData.defender_spot.x, GRID_MIN_X, GRID_MAX_X),
        y: Phaser.Math.Clamp(turnData.defender_spot.y, GRID_MIN_Y, GRID_MAX_Y),
      };
    } else {
      const defenderAnimEnd = getAnimationEndGridForPlayer(turnData, defenderId);
      incrementFbCounter(scene, "fbRequiredRoleCount", 1);
      defenderSpot =
        defenderAnimEnd ??
        fastBreakSecondaryShotDefenderGrid(
          stopperSpot.x,
          stopperSpot.y,
          rimRunnerSpriteGrid(defenderSprite, width, height).y,
        );
      if (!defenderAnimEnd) {
        const source = rimRunnerSpriteGrid(defenderSprite, width, height);
        reportMissingEndpoint(scene, turnData, {
          playerId: defenderId,
          role: "defender",
          requiredEndpointType: "animations_end",
          hasRoleCoord: false,
          reason: "missing_defender_animation_end",
        });
        reportFallback(scene, {
          playerId: defenderId,
          role: "defender",
          fallbackPolicy: "defender_vs_shooter_grid",
          missingAuthority: ["animations_end"],
          source,
          target: defenderSpot,
        });
      }
    }
    const defenderPx = gridToPixels(defenderSpot.x, defenderSpot.y, width, height);
    const defenderDuration = getPlayerDuration(defenderSprite, defenderPx.x, defenderPx.y);
    promises.push(
      tweenPlayerTo(scene, defenderSprite, defenderPx, {
        duration: defenderDuration,
        easing: "Linear"
      })
    );
  } else if (defenderId) {
    console.warn("🏀 FB Shot (with stopper) - No trail defender sprite found!", {
      defenderId,
      source: defenderRef.source,
      candidates: defenderRef.candidates,
      stopperId,
      shooterId,
      availableSprites: Object.keys(playerSprites),
    });
  }
  
  // Move all other players to standard positions
  const rebounderTweens = await moveOtherPlayersToStandardPositions(
    scene,
    playerSprites,
    shooterId,
    defenderId || stopperId,
    turnData,
    width,
    height,
    promises
  );
  
  // Wait for shooter to reach shot spot
  await shooterPromise;
  
  // Shoot the ball
  safeTransition(scene.stateMachine, States.ShotAttempt);
  
  const isBlockWithStopper = turnData.result_type === "BLOCK";
  const hasBlockSpotWithStopper = isBlockWithStopper && typeof turnData.ball_bounce_x === "number" && typeof turnData.ball_bounce_y === "number";
  let shotTargetPxWithStopper;
  if (hasBlockSpotWithStopper) {
    shotTargetPxWithStopper = gridToPixels(turnData.ball_bounce_x, turnData.ball_bounce_y, width, height);
  } else {
    const endGrid =
      turnData.result_type === "MAKE"
        ? getMadeShotSweetSpotGrid(isHomeOffense)
        : basket;
    shotTargetPxWithStopper = gridToPixels(endGrid.x, endGrid.y, width, height);
  }
  await animateShotToRim(scene, shotTargetPxWithStopper, {
    duration: animationConfig.fastBreak?.shotMs ?? 350,
    easing: "Sine.easeInOut",
    arc: { height: 50 }
  });
  
  // Stop rebounder animations when ball hits rim (made shot)
  if (turnData.result_type === "MAKE") {
    rebounderTweens.forEach(tween => {
      if (tween && tween.isPlaying) {
        tween.stop();
      }
    });
  }
  
  // Handle outcome (same as normal shot)
  if (turnData.result_type === "MAKE") {
    // Show announcement with shooter headshot
    const shooterInfo = scene.playerInfo?.[shooterId];
    const shooterTeamId = shooterSprite?.team_id;
    // ✅ UNIFIED STRUCTURE: Get team names from unified structure (with backward compatibility)
    const homeTeamId = scene.simData?.home_team_id;
    const awayTeamId = scene.simData?.away_team_id;
    const teamsObj = scene.simData?.teams || {};
    const homeTeamName = (homeTeamId && teamsObj[homeTeamId]?.name) || 
                         scene.simData?.home_team?.name || 
                         "Home";
    const awayTeamName = (awayTeamId && teamsObj[awayTeamId]?.name) || 
                         scene.simData?.away_team?.name || 
                         "Away";
    const shooterTeamName = shooterTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
    
    const hasFoulPlayer = !!(turnData?.foul_player_id || turnData?.foul_player?.player_id);
    const isAndOne = turnData?.text?.includes('AND-1') || (hasFoulPlayer && turnData?.result_type === "MAKE" && turnData?.foul_team === "DEFENSE");
    if (shooterInfo) {
      const shooterPlayerData = {
        playerId: shooterId,
        photo: shooterSprite?.photo || null,
        teamName: shooterTeamName,
        secondaryColor: getSecondaryColorForTeam(scene, shooterTeamId)
      };
      const teamStyle = shooterTeamId === scene.homeTeamId ? "home" : "away";
      if (isAndOne) {
        const foulPlayerId = turnData.foul_player_id || turnData.foul_player?.player_id;
        if (foulPlayerId) {
          const foulPlayerSprite = scene.playerSprites?.[foulPlayerId];
          const foulPlayerTeamId = foulPlayerSprite?.team_id;
          const foulPlayerTeamName = foulPlayerTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
          const foulPlayerData = { playerId: foulPlayerId, photo: foulPlayerSprite?.photo || null, teamName: foulPlayerTeamName, secondaryColor: getSecondaryColorForTeam(scene, foulPlayerTeamId) };
          showAndOneAnnouncement(teamStyle, shooterPlayerData, foulPlayerData);
        } else {
          showAnnouncement("It's Good! And 1!", teamStyle, shooterPlayerData);
        }
      } else {
        showAnnouncement("Fast Break Score!", teamStyle, shooterPlayerData);
      }
    } else if (isAndOne) {
      showAnnouncement("It's Good! And 1!", shooterTeamId === scene.homeTeamId ? "home" : "away", null);
    }
  } else if (turnData.result_type === "MISS" || turnData.result_type === "BLOCK") {
    // Handle MISS/BLOCK → rebound transition
    if (turnData.result_type === "BLOCK") {
      const { announceGameEvent } = await import('../utils/gameAnnouncements.js');
      const blockerId = turnData.blocker_id ?? turnData.defenderId ?? turnData.defender_id ?? stopperId;
      announceGameEvent('BLOCK', turnData, scene, { blockerId });
      appendToTextScroll("Blocked!");
    } else {
      // Shooting foul on miss (Fast Break path; ballManager not used)
      const hasFreeThrowsRemaining = (turnData?.free_throws_remaining ?? 0) > 0;
      const nextPlayTypeIsFreeThrow = turnData?.next_play_type === 'FREE_THROW';
      const isShootingFoulOnMiss = hasFreeThrowsRemaining || nextPlayTypeIsFreeThrow;
      if (isShootingFoulOnMiss) {
        const { triggerFoulEffect } = await import('./negativeActionEffects.js');
        const foulPlayerId = turnData.foul_player_id || turnData.foul_player?.player_id;
        if (foulPlayerId && scene) {
          const foulPlayerSprite = scene.playerSprites?.[foulPlayerId];
          if (foulPlayerSprite) {
            triggerFoulEffect(scene, foulPlayerId);
            const { announceGameEvent } = await import('../utils/gameAnnouncements.js');
            announceGameEvent('FOUL_SHOOTING', turnData, scene, { foulerId: foulPlayerId });
          } else {
            triggerFoulEffect(scene, foulPlayerId);
            const { announceGameEvent } = await import('../utils/gameAnnouncements.js');
            announceGameEvent('FOUL_SHOOTING', turnData, scene, { foulerId: foulPlayerId });
          }
        } else {
          const { announceGameEvent } = await import('../utils/gameAnnouncements.js');
          announceGameEvent('FOUL_SHOOTING', turnData, scene, {});
        }
      }
      appendToTextScroll("Missed!");
    }
    // ✅ FIX: Check all possible field names (matching animateFastBreakShot pattern)
    const rebounderId = turnData.rebounderId || turnData.rebounder_id || turnData.rebounder_player_id || turnData.roles?.rebounder?.player_id;
    
    if (!rebounderId) {
      console.error('⚠️ [FAST BREAK MISS WITH STOPPER] Missing rebounderId in turnData, cannot animate rebound', {
        turnDataKeys: Object.keys(turnData),
        hasRebounderId: !!turnData.rebounderId,
        hasRebounderIdUnderscore: !!turnData.rebounder_id,
        hasRebounderPlayerId: !!turnData.rebounder_player_id,
        hasRolesRebounder: !!turnData.roles?.rebounder?.player_id,
        fullTurnData: turnData
      });
      // Return early - rebound will be handled by next turn
      return;
    }
    
    const rebounderRef = resolvePlayerSpriteById(playerSprites, rebounderId);
    const rebounderSprite = rebounderRef.sprite;
    const rebounderIdResolved = rebounderRef.id;
    
    if (!rebounderSprite) {
      console.error('⚠️ [FAST BREAK MISS WITH STOPPER] Rebounder sprite not found', {
        rebounderId,
        rebounderIdResolved,
        availableSprites: Object.keys(playerSprites)
      });
      // Return early - rebound will be handled by next turn
      return;
    }
    
    // ✅ FIX: Use same rebound animation pattern as animateFastBreakShot
    safeTransition(scene.stateMachine, States.Rebound);
    
    const { bounceFromRim, animateRebound } = await import('./ballManager.js');
    const bounceOriginGrid = (turnData.result_type === "BLOCK" && hasBlockSpotWithStopper)
      ? { x: turnData.ball_bounce_x, y: turnData.ball_bounce_y }
      : basket;
    const miss = await bounceFromRim(scene, ballSprite, bounceOriginGrid, isHomeOffense, 300);
    
    // ✅ Stop rebounder animations when rebounder grabs ball (missed shot)
    // Monitor rebounder position and stop tweens when rebounder gets close to ball bounce spot
    const stopReboundMonitor = startRebounderCatchMonitor({
      scene,
      rebounderTweens,
      rebounderSprite,
      ballGrid: miss.grid,
      width,
      height,
    });
    
    // Animate rebound
    await animateRebound({
      scene,
      ballSprite,
      playerSprites,
      animations: [],
      rebounderId: rebounderIdResolved ?? rebounderId,
      ballSpot: miss.grid,
      shooterId,
      turnData: turnData
    });
    stopReboundMonitor();
    
    // ✅ FIX: Use runDefensiveReboundSetup for DREB (matching animateFastBreakShot pattern)
    if (turnData.rebound_type === "DREB") {
      const { runDefensiveReboundSetup } = await import('./turnAnimation.js');
      await runDefensiveReboundSetup({
        scene,
        ballSprite,
        playerSprites,
        rebounderId,
        nextPlayType: turnData.next_play_type || "HCO",
        turnData: turnData,
        suppressFastBreakReceiverAuthority: true,
      });
    }
  }
}

async function animateFastBreakShot(scene, turnData, playerSprites, ballSprite, width, height, options = {}) {
  const shooterRawId = turnData.roles?.shooter?.player_id || turnData.shooter_id || getCurrentOwner(scene);
  const shooterRef = resolvePlayerSpriteById(playerSprites, shooterRawId);
  const shooterId = shooterRef.id;
  const shooterSprite = shooterRef.sprite;
  
  if (!shooterSprite) return;
  
  const isHomeOffense = shooterSprite.team === "home";
  const basket = getFastBreakAttackingBasket(isHomeOffense);

  // ✅ SS&S: Backend is single source of truth for shot spot (and defender spot)
  // Use turnData.shot_spot when present (grid coords, HOME orientation); else fallback to local random
  let shotSpot;
  if (turnData.shot_spot && typeof turnData.shot_spot.x === "number" && typeof turnData.shot_spot.y === "number") {
    shotSpot = {
      x: Phaser.Math.Clamp(turnData.shot_spot.x, GRID_MIN_X, GRID_MAX_X),
      y: Phaser.Math.Clamp(turnData.shot_spot.y, GRID_MIN_Y, GRID_MAX_Y)
    };
  } else {
    shotSpot = {
      x: isHomeOffense ? basket.x - Phaser.Math.Between(1, 4) : basket.x + Phaser.Math.Between(1, 4),
      y: basket.y + Phaser.Math.Between(-3, 3)
    };
    shotSpot.x = Phaser.Math.Clamp(shotSpot.x, GRID_MIN_X, GRID_MAX_X);
    shotSpot.y = Phaser.Math.Clamp(shotSpot.y, GRID_MIN_Y, GRID_MAX_Y);
  }

  const shotPx = gridToPixels(shotSpot.x, shotSpot.y, width, height);
  
  const promises = [];
  
  // Move shooter
  attachBallToPlayer(scene, ballSprite, shooterSprite);
  // Use distance-based duration for consistent speed
  const shooterDuration = getPlayerDuration(shooterSprite, shotPx.x, shotPx.y);
  // ✅ Store shooter promise separately - we'll wait only for this before shooting
  const shooterPromise = tweenPlayerTo(scene, shooterSprite, shotPx, {
    duration: shooterDuration,
    easing: "Linear" // Match HCO step movements
  });
  promises.push(shooterPromise);
  
  // ✅ SS&S: Resolve defender from all supported payload shapes.
  const defenderRef = resolveFastBreakDefenderSprite(playerSprites, turnData, {
    excludeIds: [shooterId],
  });
  let defenderId = defenderRef.id;
  const defenderSprite = defenderRef.sprite;

  if (defenderSprite) {
    // ✅ SS&S: Use backend defender_spot when present (grid coords, HOME orientation); else fallback to spot between shooter and basket
    let defenderSpot;
    if (turnData.defender_spot && typeof turnData.defender_spot.x === "number" && typeof turnData.defender_spot.y === "number") {
      defenderSpot = {
        x: Phaser.Math.Clamp(turnData.defender_spot.x, GRID_MIN_X, GRID_MAX_X),
        y: Phaser.Math.Clamp(turnData.defender_spot.y, GRID_MIN_Y, GRID_MAX_Y)
      };
    } else {
      const defenderAnimEnd = getAnimationEndGridForPlayer(turnData, defenderId);
      incrementFbCounter(scene, "fbRequiredRoleCount", 1);
      defenderSpot =
        defenderAnimEnd ??
        fastBreakShotDefenderGridVsShooter(shotSpot.x, shotSpot.y, isHomeOffense);
      if (!defenderAnimEnd) {
        const source = rimRunnerSpriteGrid(defenderSprite, width, height);
        reportMissingEndpoint(scene, turnData, {
          playerId: defenderId,
          role: "defender",
          requiredEndpointType: "animations_end",
          hasRoleCoord: false,
          reason: "missing_defender_animation_end",
        });
        reportFallback(scene, {
          playerId: defenderId,
          role: "defender",
          fallbackPolicy: "defender_vs_shooter_grid",
          missingAuthority: ["animations_end"],
          source,
          target: defenderSpot,
        });
      }
    }

    const defenderPx = gridToPixels(defenderSpot.x, defenderSpot.y, width, height);
    const defenderDuration = getPlayerDuration(defenderSprite, defenderPx.x, defenderPx.y);
    promises.push(
      tweenPlayerTo(scene, defenderSprite, defenderPx, {
        duration: defenderDuration,
        easing: "Linear"
      })
    );
  } else if (defenderId) {
    console.warn("🏀 FB Shot - No defender sprite found!", {
      defenderId,
      source: defenderRef.source,
      candidates: defenderRef.candidates,
      turnDataDefenderId: turnData.defender_id ?? turnData.defenderId,
      availableSprites: Object.keys(playerSprites)
    });
  }
  
  // Move all other players to standard positions (same as defensive stop)
  // ✅ Capture rebounder tween references for early termination
  const rebounderTweens = await moveOtherPlayersToStandardPositions(
    scene,
    playerSprites,
    shooterId,
    defenderId,
    turnData,
    width,
    height,
    promises
  );

  // Charge / blocking foul: animate to shot spot only, then return. No shot; announcement in finalizeTurnAfterAnimation.
  if (options.foulOnly) {
    await Promise.all(promises);
    return;
  }
  
  // ✅ Wait only for shooter to reach basket - shoot immediately when he arrives
  // Defender and rebounders continue animating in parallel
  await shooterPromise;
  
  // Shoot the ball
  safeTransition(scene.stateMachine, States.ShotAttempt);
  
  // ✅ BLOCK: Use block spot as shot target when result is BLOCK (ball gets blocked before rim)
  const isBlock = turnData.result_type === "BLOCK";
  const hasBlockSpot = isBlock && typeof turnData.ball_bounce_x === "number" && typeof turnData.ball_bounce_y === "number";
  let shotTargetPx;
  if (hasBlockSpot) {
    const blockSpotGrid = { x: turnData.ball_bounce_x, y: turnData.ball_bounce_y };
    shotTargetPx = gridToPixels(blockSpotGrid.x, blockSpotGrid.y, width, height);
  } else {
    const endGrid =
      turnData.result_type === "MAKE"
        ? getMadeShotSweetSpotGrid(isHomeOffense)
        : basket;
    shotTargetPx = gridToPixels(endGrid.x, endGrid.y, width, height);
  }
  // ✅ STEP 3 MIGRATION: Use new animateShotToRim() helper instead of manual detach + animate
  await animateShotToRim(scene, shotTargetPx, {
    duration: animationConfig.fastBreak?.shotMs ?? 350,
    easing: "Sine.easeInOut",
    arc: { height: 50 }
  });
  
  // ✅ Stop rebounder animations when ball hits rim (made shot)
  if (turnData.result_type === "MAKE") {
    rebounderTweens.forEach(tween => {
      if (tween && tween.isPlaying) {
        tween.stop();
      }
    });
  }
  
  // Handle outcome
  if (turnData.result_type === "MAKE") {
    // Show announcement with shooter headshot (AND-1 handled here; ballManager path not used for Fast Break)
    const { showAnnouncement, showAndOneAnnouncement, getSecondaryColorForTeam } = await import('../utils/announcements.js');
    const shooterInfo = scene.playerInfo?.[shooterId];
    const shooterTeamId = shooterSprite?.team_id;
    
    // Handle both new nested structure (object) and old flat structure (string)
    const homeTeamField = scene.simData?.home_team;
    const awayTeamField = scene.simData?.away_team;
    const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
    const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
    const shooterTeamName = shooterTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
    
    const shooterPlayerData = shooterInfo ? {
      playerId: shooterId,
      photo: shooterSprite?.photo || null,
      teamName: shooterTeamName,
      secondaryColor: getSecondaryColorForTeam(scene, shooterTeamId)
    } : null;

    const teamStyle = isHomeOffense ? 'home' : 'away';
    const hasFoulPlayer = !!(turnData?.foul_player_id || turnData?.foul_player?.player_id);
    const isAndOne = turnData?.text?.includes('AND-1') || (hasFoulPlayer && turnData?.result_type === "MAKE" && turnData?.foul_team === "DEFENSE");
    if (isAndOne) {
      const foulPlayerId = turnData.foul_player_id || turnData.foul_player?.player_id;
      if (foulPlayerId && shooterPlayerData) {
        const foulPlayerSprite = scene.playerSprites?.[foulPlayerId];
        const foulPlayerTeamId = foulPlayerSprite?.team_id;
        const foulPlayerTeamName = foulPlayerTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
        const foulPlayerData = { playerId: foulPlayerId, photo: foulPlayerSprite?.photo || null, teamName: foulPlayerTeamName, secondaryColor: getSecondaryColorForTeam(scene, foulPlayerTeamId) };
        showAndOneAnnouncement(teamStyle, shooterPlayerData, foulPlayerData);
      } else {
        showAnnouncement("It's Good! And 1!", teamStyle, shooterPlayerData);
      }
    } else {
      showAnnouncement("It's Good!", teamStyle, shooterPlayerData);
    }
    
    const makeHoldMs = animationConfig.fastBreak?.makeAnnouncementHoldMs ?? 1000;
    await new Promise(resolve => scene.time.delayedCall(makeHoldMs, resolve));
    
    // ✅ OPTION 1 FIX: Ensure onShotEnd() is called before transitioning to inbound pass
    // This ensures ball state is cleared before inbound setup
    const { getBallController } = await import('./BallControllerAdapter.js');
    const ballController = getBallController();
    if (ballController && ballController.isInFlight) {
      ballController.onShotEnd();
    }
    
    // ✅ FIX: Don't call runInboundSetup() here if next play is BASELINE_INBOUND or FREE_THROW
    // BASELINE_INBOUND: the next turn will handle the inbound via AnimationEngine.handleBaselineInbound()
    // FREE_THROW (AND-1): no inbound — same team shoots the free throw; FREE_THROW turn handles transition
    if (turnData.next_play_type === "BASELINE_INBOUND" || turnData.next_play_type === "FREE_THROW") {
      return;
    }
    
    // Inbound setup (only for non-BASELINE_INBOUND cases)
    const newOffenseSide = isHomeOffense ? "away" : "home";
    const skipRetreat = turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT";
    const pressureType = skipRetreat ? turnData.next_defensive_setup : null;
    
    // ✅ SS&S: Possession flip removed from frontend (Fix 2 - Pattern A)
    // Backend now flips possession before creating BASELINE_INBOUND turn
    // Frontend just reads offense_team_id from turnData (handled by universal transition)
    
    await runInboundSetup({ 
      scene, 
      ballSprite, 
      playerSprites, 
      newOffenseSide,
      homeTeamId: scene.simData?.home_team_id,
      awayTeamId: scene.simData?.away_team_id,
      skipRetreat,
      pressureType
    });
  } else if (turnData.result_type === "BLOCK") {
    // Block - announce, bounce from block spot, then same rebound flow as miss
    const { announceGameEvent } = await import('../utils/gameAnnouncements.js');
    const blockerId = turnData.blocker_id ?? turnData.defenderId ?? defenderId;
    announceGameEvent('BLOCK', turnData, scene, { blockerId });
    appendToTextScroll("Blocked!");
    safeTransition(scene.stateMachine, States.Rebound);

    const { bounceFromRim, animateRebound } = await import('./ballManager.js');
    const blockSpotGrid = hasBlockSpot
      ? { x: turnData.ball_bounce_x, y: turnData.ball_bounce_y }
      : basket;
    const miss = await bounceFromRim(scene, ballSprite, blockSpotGrid, isHomeOffense, 300);

    // Reuse same rebound / DREB setup as MISS (below)
    const currentIndex = scene.currentTurn || 0;
    const previousTurn = scene.simData?.turns?.[currentIndex - 1];
    const currentTurn = scene.simData?.turns?.[currentIndex];
    const missTurnForGetback = (previousTurn?.result_type === "MISS" || previousTurn?.result_type === "BLOCK") ? previousTurn : null;
    const rebounderId = turnData.rebounderId || turnData.rebounder_id || turnData.rebounder_player_id || turnData.roles?.rebounder?.player_id;

    if (rebounderId) {
      const rebounderRef = resolvePlayerSpriteById(playerSprites, rebounderId);
      const rebounderSprite = rebounderRef.sprite;
      const rebounderIdResolved = rebounderRef.id;
      if (rebounderSprite) {
        const stopReboundMonitor = startRebounderCatchMonitor({
          scene,
          rebounderTweens,
          rebounderSprite,
          ballGrid: miss.grid,
          width,
          height,
        });
        await animateRebound({
          scene,
          ballSprite,
          playerSprites,
          animations: [],
          rebounderId: rebounderIdResolved ?? rebounderId,
          ballSpot: miss.grid,
          shooterId,
          turnData: missTurnForGetback
        });
        stopReboundMonitor();
        if (turnData.rebound_type === "DREB") {
          const { runDefensiveReboundSetup } = await import('./turnAnimation.js');
          await runDefensiveReboundSetup({
            scene,
            ballSprite,
            playerSprites,
            rebounderId: rebounderIdResolved ?? rebounderId,
            nextPlayType: turnData.next_play_type || "HCO",
            turnData,
            suppressFastBreakReceiverAuthority: true,
          });
        }
      }
    }
  } else {
    // Miss - shooting foul announcement (Fast Break path; ballManager not used)
    const hasFreeThrowsRemaining = (turnData?.free_throws_remaining ?? 0) > 0;
    const nextPlayTypeIsFreeThrow = turnData?.next_play_type === 'FREE_THROW';
    const isShootingFoulOnMiss = hasFreeThrowsRemaining || nextPlayTypeIsFreeThrow;
    if (isShootingFoulOnMiss) {
      const { triggerFoulEffect } = await import('./negativeActionEffects.js');
      const { announceGameEvent } = await import('../utils/gameAnnouncements.js');
      const foulPlayerId = turnData.foul_player_id || turnData.foul_player?.player_id;
      if (foulPlayerId && scene) {
        const foulPlayerSprite = scene.playerSprites?.[foulPlayerId];
        if (foulPlayerSprite) {
          triggerFoulEffect(scene, foulPlayerId);
          announceGameEvent('FOUL_SHOOTING', turnData, scene, { foulerId: foulPlayerId });
        } else {
          triggerFoulEffect(scene, foulPlayerId);
          announceGameEvent('FOUL_SHOOTING', turnData, scene, { foulerId: foulPlayerId });
        }
      } else {
        announceGameEvent('FOUL_SHOOTING', turnData, scene, {});
      }
    }
    appendToTextScroll("Missed!");
    safeTransition(scene.stateMachine, States.Rebound);
    
    const { bounceFromRim, animateRebound } = await import('./ballManager.js');
    const miss = await bounceFromRim(scene, ballSprite, basket, isHomeOffense, 300);
    
    // Find the original MISS turn that led to this Fast Break (for offense_getback list)
    // Also need the current Fast Break MISS turn (for animations)
    const currentIndex = scene.currentTurn || 0;
    const previousTurn = scene.simData?.turns?.[currentIndex - 1];
    const currentTurn = scene.simData?.turns?.[currentIndex];
    
    // The current turnData is the Fast Break MISS turn - use it for animations
    // The previous HCO MISS turn is needed for offense_getback list
    // runDefensiveReboundSetup will use turnData for animations, and can find offense_getback
    // from the previous turn if needed
    const missTurnForGetback = (previousTurn?.result_type === "MISS" || previousTurn?.result_type === "BLOCK") ? previousTurn : null;
    
    // ✅ Get rebounderId - must be present for rebound animation
    // Check all possible field names: rebounderId (camelCase), rebounder_id (underscore), rebounder_player_id
    const rebounderId = turnData.rebounderId || turnData.rebounder_id || turnData.rebounder_player_id || turnData.roles?.rebounder?.player_id;
    
    console.log('🏀 [FAST BREAK MISS] Checking rebounderId', {
      rebounderId,
      fromRebounderId: turnData.rebounderId,
      fromRebounderIdUnderscore: turnData.rebounder_id,
      fromRebounderPlayerId: turnData.rebounder_player_id,
      fromRolesRebounder: turnData.roles?.rebounder?.player_id,
      exists: !!rebounderId
    });
    
    if (!rebounderId) {
      console.error('⚠️ [FAST BREAK MISS] Missing rebounderId in turnData, cannot animate rebound', {
        turnDataKeys: Object.keys(turnData),
        hasRebounderId: !!turnData.rebounderId,
        hasRebounderIdUnderscore: !!turnData.rebounder_id,
        hasRebounderPlayerId: !!turnData.rebounder_player_id,
        hasRolesRebounder: !!turnData.roles?.rebounder?.player_id,
        fullTurnData: turnData
      });
      // Return early - rebound will be handled by next turn
      return;
    }
    
    const rebounderRef = resolvePlayerSpriteById(playerSprites, rebounderId);
    const rebounderSprite = rebounderRef.sprite;
    const rebounderIdResolved = rebounderRef.id;
    
    if (!rebounderSprite) {
      console.error('⚠️ [FAST BREAK MISS] Rebounder sprite not found', {
        rebounderId,
        rebounderIdResolved,
        availableSprites: Object.keys(playerSprites)
      });
      // Return early - rebound will be handled by next turn
      return;
    }
    
    // ✅ Stop rebounder animations when rebounder grabs ball (missed shot)
    // Monitor rebounder position and stop tweens when rebounder gets close to ball bounce spot
    const stopReboundMonitor = startRebounderCatchMonitor({
      scene,
      rebounderTweens,
      rebounderSprite,
      ballGrid: miss.grid,
      width,
      height,
    });
    
    await animateRebound({
      scene,
      ballSprite,
      playerSprites,
      animations: [],
      rebounderId: rebounderIdResolved ?? rebounderId,
      ballSpot: miss.grid,
      shooterId,
      turnData: missTurnForGetback // ✅ FIX: Pass previous HCO MISS turn (has offense_getback) so get-back players can be excluded
    });
    stopReboundMonitor();
    
    // Defensive rebound setup if needed
    if (turnData.rebound_type === "DREB") {
      const { runDefensiveReboundSetup } = await import('./turnAnimation.js');
      await runDefensiveReboundSetup({
        scene,
        ballSprite,
        playerSprites,
        rebounderId: rebounderIdResolved ?? rebounderId,
        nextPlayType: turnData.next_play_type || "HCO", // Use turnData.next_play_type instead of hardcoded "HCO"
        turnData: turnData, // ✅ FIX: Pass current Fast Break MISS turn (has animations), not previous HCO MISS turn
        suppressFastBreakReceiverAuthority: true,
        // runDefensiveReboundSetup will find offense_getback from previous turn if needed
      });
    }
  }
}

/**
 * Phase 2b: Defensive Stop / Foul / Turnover / Steal
 * - Ball handler moves to top of key
 * - Stopper defends ball handler
 * - Other defenders move closer to basket
 * - All other players scatter to half court
 */
async function animateDefensiveStop(scene, turnData, playerSprites, ballSprite, width, height) {
  
  // ✅ Use backend animation end coords for positioning (matches other transitions like DREB -> HCO)
  // This ensures frontend sprite positions match backend player.coords for accurate distance calculations
  const animations = turnData.animations || [];
  const promises = [];
  
  // ⚠️ CRITICAL CHECK: For DEFENSIVE_STOP, we should NOT use backend animations if they move ball handler toward basket
  // Instead, force ball handler to top of key (defensive stop position)
  const ballHandlerId = turnData.roles?.ball_handler?.player_id || turnData.roles?.ball_handler || getCurrentOwner(scene);
  const ballHandlerSprite = playerSprites[ballHandlerId];
  const isDefensiveStop = turnData.result_type === "DEFENSIVE_STOP" || turnData.fast_break === true;
  let gotoStateTransition = false; // Flag to skip fallback logic if we've already handled positioning
  
  if (animations.length > 0 && isDefensiveStop && ballHandlerSprite) {
    // For defensive stops, check if backend animation would move ball handler toward basket incorrectly
    const ballHandlerAnim = animations.find(a => a.playerId === ballHandlerId);
    if (ballHandlerAnim && ballHandlerAnim.movement && ballHandlerAnim.movement.length >= 2) {
      const endStep = ballHandlerAnim.movement[ballHandlerAnim.movement.length - 1];
      const startStep = ballHandlerAnim.movement[0];
      
      if (endStep?.coords && startStep?.coords) {
        const ballHandlerSprite = playerSprites[ballHandlerId];
        const isHomeOffense = ballHandlerSprite?.team === "home";
        const basket = isHomeOffense ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
        const topKey = isHomeOffense ? HOME_TOP_KEY : AWAY_TOP_KEY;
        
        // Check if end coords are closer to basket than top of key (indicating incorrect animation)
        const distanceToBasket = Math.abs(endStep.coords.x - basket.x);
        const distanceToTopKey = Math.abs(endStep.coords.x - topKey.x);
        
        // For away offense, coordinates in animation data are in HOME orientation
        // Flip them for display to match what the user sees
        let displayStartCoords = startStep.coords;
        let displayEndCoords = endStep.coords;
        if (!isHomeOffense) {
          // Away offense: flip coordinates for display
          displayStartCoords = { x: 100 - startStep.coords.x, y: startStep.coords.y };
          displayEndCoords = { x: 100 - endStep.coords.x, y: endStep.coords.y };
        }
        
        // ✅ REMOVED: Defensive stop animation check logging (cluttering console)
        
        if (distanceToBasket < distanceToTopKey) {
          // Backend animation incorrectly moves ball handler toward basket - use manual positioning instead
          console.warn("⚠️ Defensive Stop - Backend animation moves ball handler toward basket! Using manual positioning instead.");
          
          // Skip backend animations for ball handler, but use them for other players
          for (const anim of animations) {
            const sprite = playerSprites[anim.playerId];
            if (!sprite || !anim.movement || anim.movement.length < 2) continue;
            
            // Skip ball handler - we'll position manually to top of key
            if (anim.playerId === ballHandlerId) continue;
            
            const endStep = anim.movement[anim.movement.length - 1];
            if (!endStep || !endStep.coords) continue;
            
            const endPixels = gridToPixels(endStep.coords.x, endStep.coords.y, width, height);
            const duration = getPlayerDuration(sprite, endPixels.x, endPixels.y);
            
            promises.push(
              tweenPlayerTo(scene, sprite, endPixels, {
                duration,
                easing: "Linear"
              })
            );
          }
          
          // Manually position ball handler to top of key (override incorrect backend animation)
          attachBallToPlayer(scene, ballSprite, ballHandlerSprite);
          const topKeyPx = gridToPixels(topKey.x, topKey.y, width, height);
          const handlerDuration = getPlayerDuration(ballHandlerSprite, topKeyPx.x, topKeyPx.y);
          promises.push(
            tweenPlayerTo(scene, ballHandlerSprite, topKeyPx, {
              duration: handlerDuration,
              easing: "Linear"
            })
          );
          
          // Move stopper (if exists)
          const stopperId = turnData.stopper_id;
          const stopperSprite = stopperId ? playerSprites[stopperId] : null;
          if (stopperSprite) {
            const stopperSpot = {
              x: isHomeOffense ? topKey.x + 2 : topKey.x - 2,
              y: topKey.y
            };
            stopperSpot.x = Phaser.Math.Clamp(stopperSpot.x, GRID_MIN_X, GRID_MAX_X);
            const stopperPx = gridToPixels(stopperSpot.x, stopperSpot.y, width, height);
            const stopperDuration = getPlayerDuration(stopperSprite, stopperPx.x, stopperPx.y);
            promises.push(
              tweenPlayerTo(scene, stopperSprite, stopperPx, {
                duration: stopperDuration,
                easing: "Linear"
              })
            );
          }
          
          // Move other players to standard positions
          // ✅ Capture rebounder tween references for early termination
          const rebounderTweens = await moveOtherPlayersToStandardPositions(
            scene,
            playerSprites,
            ballHandlerId,
            turnData.stopper_id,
            turnData,
            width,
            height,
            promises
          );
          
          // ✅ Track ball handler and stopper promises for early termination
          const ballHandlerPromise = promises[promises.length - rebounderTweens.length - (stopperSprite ? 2 : 1)];
          const stopperPromise = stopperSprite ? promises[promises.length - rebounderTweens.length - 1] : null;
          
          // ✅ Stop rebounder animations when both ball handler and stopper reach their spots
          let handlerComplete = false;
          let stopperComplete = !stopperSprite; // If no stopper, consider it "complete"
          
          const checkAndStopRebounders = () => {
            if (handlerComplete && stopperComplete) {
              if (isCriticalEventPatternEnabled()) {
                stopAllNonBhStopperTweens(scene, playerSprites, ballHandlerId, turnData.stopper_id);
              } else {
                rebounderTweens.forEach(tween => {
                  if (tween && tween.isPlaying) {
                    tween.stop();
                  }
                });
              }
            }
          };
          
          // Set up completion handlers
          if (ballHandlerPromise && typeof ballHandlerPromise.then === 'function') {
            ballHandlerPromise.then(() => {
              handlerComplete = true;
              checkAndStopRebounders();
            });
          } else {
            handlerComplete = true;
            checkAndStopRebounders();
          }
          
          if (stopperPromise && typeof stopperPromise.then === 'function') {
            stopperPromise.then(() => {
              stopperComplete = true;
              checkAndStopRebounders();
            });
          } else if (stopperSprite) {
            stopperComplete = true;
            checkAndStopRebounders();
          }
          
          // Wait for all animations to complete (rebounders will stop early)
          await Promise.all(promises);
          // Skip to announcement/state transition (avoid fallback logic)
          gotoStateTransition = true;
        } else {
          // Backend animation looks correct (top of key or neutral) - use it
          // ✅ REMOVED: Defensive stop backend animations logging (cluttering console)

          let backendBhPromise = null;
          let backendStopperPromise = null;
          const backendStopperId = turnData.stopper_id;
          for (const anim of animations) {
            const sprite = playerSprites[anim.playerId];
            if (!sprite || !anim.movement || anim.movement.length < 2) continue;

            const endStep = anim.movement[anim.movement.length - 1];
            if (!endStep || !endStep.coords) continue;

            const endPixels = gridToPixels(endStep.coords.x, endStep.coords.y, width, height);
            const duration = getPlayerDuration(sprite, endPixels.x, endPixels.y);

            const hasBall = anim.hasBallAtStep?.[anim.movement.length - 1] || false;
            if (hasBall) {
              attachBallToPlayer(scene, ballSprite, sprite);
            }

            const tweenPromise = tweenPlayerTo(scene, sprite, endPixels, {
              duration,
              easing: "Linear"
            });
            promises.push(tweenPromise);
            if (String(anim.playerId) === String(ballHandlerId)) backendBhPromise = tweenPromise;
            if (backendStopperId && String(anim.playerId) === String(backendStopperId)) backendStopperPromise = tweenPromise;
          }

          // Critical-event cleanup: when BH (and stopper if present) reach their
          // backend-given destinations, stop all remaining parallel tweens so far-end
          // destinations on offensive teammates don't continue past the stop.
          if (isCriticalEventPatternEnabled() && backendBhPromise) {
            let bhDone = false;
            let stopperDone = !backendStopperPromise;
            const killOthers = () => {
              if (!bhDone || !stopperDone) return;
              stopAllNonBhStopperTweens(scene, playerSprites, ballHandlerId, backendStopperId);
            };
            backendBhPromise.then(() => { bhDone = true; killOthers(); });
            if (backendStopperPromise) {
              backendStopperPromise.then(() => { stopperDone = true; killOthers(); });
            }
          }
        }
      } else {
        // No valid animation coords - fall through to manual positioning
        console.warn("⚠️ Defensive Stop - Invalid animation coords, using manual positioning");
      }
    } else {
      // No ball handler animation found - fall through to manual positioning
      console.warn("⚠️ Defensive Stop - No ball handler animation found, using manual positioning");
    }
  } else if (animations.length > 0 && !isDefensiveStop) {
    // Not a defensive stop - use backend animations as normal
    // ✅ REMOVED: Using backend animations logging (cluttering console)
    for (const anim of animations) {
      const sprite = playerSprites[anim.playerId];
      if (!sprite || !anim.movement || anim.movement.length < 2) continue;
      
      const endStep = anim.movement[anim.movement.length - 1];
      if (!endStep || !endStep.coords) continue;
      
      const endPixels = gridToPixels(endStep.coords.x, endStep.coords.y, width, height);
      const duration = getPlayerDuration(sprite, endPixels.x, endPixels.y);
      
      const hasBall = anim.hasBallAtStep?.[anim.movement.length - 1] || false;
      if (hasBall) {
        attachBallToPlayer(scene, ballSprite, sprite);
      }
      
      promises.push(
        tweenPlayerTo(scene, sprite, endPixels, {
          duration,
          easing: "Linear"
        })
      );
    }
  }
  
  // Manual positioning fallback (if animations are missing or incorrect)
  if (!gotoStateTransition && promises.length === 0 && (animations.length === 0 || isDefensiveStop)) {
    // Fallback to manual positioning if animations are missing or incorrect (backwards compatibility)
    
    const ballHandlerData = turnData.roles?.ball_handler;
    const ballHandlerId = ballHandlerData?.player_id || ballHandlerData || getCurrentOwner(scene);
    const ballHandlerSprite = playerSprites[ballHandlerId];
    
    if (!ballHandlerSprite) {
      console.error("❌ animateDefensiveStop - EARLY RETURN: ballHandlerSprite not found!", {
        ballHandlerId,
        availableIds: Object.keys(playerSprites),
        ballHandlerData,
        fallbackOwner: getCurrentOwner(scene)
      });
      return;
    }
    
    const isHomeOffense = ballHandlerSprite.team === "home";
    const topKey = isHomeOffense ? HOME_TOP_KEY : AWAY_TOP_KEY;
    
    // Move ball handler to top of key
    attachBallToPlayer(scene, ballSprite, ballHandlerSprite);
    const topKeyPx = gridToPixels(topKey.x, topKey.y, width, height);
    const handlerDuration = getPlayerDuration(ballHandlerSprite, topKeyPx.x, topKeyPx.y);
    const ballHandlerPromise = tweenPlayerTo(scene, ballHandlerSprite, topKeyPx, {
      duration: handlerDuration,
      easing: "Linear"
    });
    promises.push(ballHandlerPromise);
    
    // Move stopper (if exists)
    const stopperId = turnData.stopper_id;
    const stopperSprite = stopperId ? playerSprites[stopperId] : null;
    let stopperPromise = null;
    
    if (stopperSprite) {
      // ✅ Position stopper DIRECTLY in front of ball handler (between ball handler and basket they're defending)
      // Home offense (attacking right): stopper x GREATER than ball handler (toward basket)
      // Away offense (attacking left): stopper x LESS than ball handler (toward basket)
      const stopperSpot = {
        x: isHomeOffense ? topKey.x + 2 : topKey.x - 2,  // 2 spots in front, directly between ball handler and basket
        y: topKey.y  // Same Y as ball handler (directly in front)
      };
      stopperSpot.x = Phaser.Math.Clamp(stopperSpot.x, GRID_MIN_X, GRID_MAX_X);
      
      const stopperPx = gridToPixels(stopperSpot.x, stopperSpot.y, width, height);
      const stopperDuration = getPlayerDuration(stopperSprite, stopperPx.x, stopperPx.y);
      stopperPromise = tweenPlayerTo(scene, stopperSprite, stopperPx, {
        duration: stopperDuration,
        easing: "Linear"
      });
      promises.push(stopperPromise);
    }
    
    // Move other defenders and non-involved players
    // ✅ Capture rebounder tween references for early termination
    const rebounderTweens = await moveOtherPlayersToStandardPositions(
      scene,
      playerSprites,
      ballHandlerId,
      stopperId,
      turnData,
      width,
      height,
      promises
    );
    
    // ✅ Stop rebounder animations when both ball handler and stopper reach their spots
    let handlerComplete = false;
    let stopperComplete = !stopperSprite; // If no stopper, consider it "complete"
    
    const checkAndStopRebounders = () => {
      if (handlerComplete && stopperComplete) {
        if (isCriticalEventPatternEnabled()) {
          stopAllNonBhStopperTweens(scene, playerSprites, ballHandlerId, stopperId);
        } else {
          rebounderTweens.forEach(tween => {
            if (tween && tween.isPlaying) {
              tween.stop();
            }
          });
        }
      }
    };
    
    // Set up completion handlers
    if (ballHandlerPromise && typeof ballHandlerPromise.then === 'function') {
      ballHandlerPromise.then(() => {
        handlerComplete = true;
        checkAndStopRebounders();
      });
    } else {
      handlerComplete = true;
      checkAndStopRebounders();
    }
    
    if (stopperPromise && typeof stopperPromise.then === 'function') {
      stopperPromise.then(() => {
        stopperComplete = true;
        checkAndStopRebounders();
      });
    } else if (stopperSprite) {
      stopperComplete = true;
      checkAndStopRebounders();
    }
  }
  
  // Only wait for promises if we haven't already awaited them (manual positioning case)
  if (!gotoStateTransition) {
    await Promise.all(promises);
  }
  
  // ✅ "Great Stop!" after Fast Break defensive stops (stopper headshot; outlet denial = text only, no headshot)
  const ballHandlerDataForStop = turnData.roles?.ball_handler;
  const ballHandlerIdForStop =
    ballHandlerDataForStop?.player_id || ballHandlerDataForStop || getCurrentOwner(scene);
  const ballHandlerSpriteForStop = playerSprites[ballHandlerIdForStop];
  const isHomeOffenseForStop = ballHandlerSpriteForStop?.team === 'home';
  const defenseTeamForStop = isHomeOffenseForStop ? 'away' : 'home';

  // Rim Runner outlet denied: handled in animateRimRunnerOutletDeniedBeat + finalizeRimRunnerNonShotTurn (no Great Stop! here).
  if (turnData.fast_break === true && turnData.stopper_id) {
    const stopperId = turnData.stopper_id;
    const stopperSprite = playerSprites[stopperId];
    
    if (stopperSprite) {
      const { showAnnouncement, getSecondaryColorForTeam } = await import('../utils/announcements.js');
      const stopperInfo = scene.playerInfo?.[stopperId];
      const stopperTeamId = stopperSprite?.team_id;
      
      // Handle both new nested structure (object) and old flat structure (string)
      const homeTeamField = scene.simData?.home_team;
      const awayTeamField = scene.simData?.away_team;
      const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
      const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
      const stopperTeamName = stopperTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
      
      const stopperPlayerData = stopperInfo ? {
        playerId: stopperId,
        photo: stopperSprite?.photo || null,
        teamName: stopperTeamName,
        secondaryColor: getSecondaryColorForTeam(scene, stopperSprite?.team_id)
      } : null;

      showAnnouncement('Great Stop!', defenseTeamForStop, stopperPlayerData);
      
      const stopHoldMs = animationConfig.fastBreak?.defensiveStopHoldMs ?? 1000;
      await new Promise(resolve => scene.time.delayedCall(stopHoldMs, resolve));
    }
  } else {
    // Display outcome text for non-Fast Break stops
    if (turnData.hold_up) {
      appendToTextScroll("Defensive stop!");
    }
  }
  
  // Transition to HalfCourt for next possession
  // This is critical - if we don't transition, playTurnAnimation will return early
  // because it checks if state is FastBreak and skips animation
  const currentState = scene.stateMachine?.state;
  if (currentState !== States.HalfCourt) {
    safeTransition(scene.stateMachine, States.HalfCourt);
    
    // Verify transition succeeded
    const newState = scene.stateMachine?.state;
    if (newState !== States.HalfCourt) {
      console.error("❌ Fast Break Defensive Stop - State transition FAILED:", {
        expected: States.HalfCourt,
        actual: newState,
        current_state: currentState
      });
    }
  }
  
  // ✅ Ensure HCO setup is triggered after defensive stop transitions to HCO
  // This ensures players are properly positioned for the next HCO turn
  if (turnData.next_play_type === "HCO") {
    if (typeof scene.startNextHalfCourtOffense === "function") {
      scene.startNextHalfCourtOffense();
    }
  }
}

/**
 * Animate rebounders (players who stayed near rim for shot attempt) to their target positions
 * - Prefer `turn.animations[].end` per player when present (SS&S with sim).
 * - Defensive Stop fallback: x=40-60, y=starting_y ± 6 (clamped 1-49)
 * - Shot Attempt fallback: x=random 5-20 spots out from basket, y=rim_y ± 10 (clamped 1-49)
 * 
 * @param {Phaser.Scene} scene - Phaser scene
 * @param {Object} playerSprites - Dictionary of player sprites
 * @param {string} ballHandlerId - ID of ball handler (to skip)
 * @param {string} primaryDefenderId - ID of primary defender (to skip)
 * @param {Object} turnData - Turn data with result_type and roles
 * @param {number} width - Scene width
 * @param {number} height - Scene height
 * @param {Set} getbackPlayerIdsSet - Set of get-back player IDs (to skip)
 * @param {Set} releasePlayerIdsSet - Set of release player IDs (to skip)
 * @returns {Array} Array of tween references for rebounder animations (for early termination)
 */
function animateRebounders(
  scene,
  playerSprites,
  ballHandlerId,
  primaryDefenderId,
  turnData,
  width,
  height,
  getbackPlayerIdsSet,
  releasePlayerIdsSet
) {
  const rebounderTweens = [];
  const isDefensiveStop = turnData.result_type === "DEFENSIVE_STOP";
  
  // Determine which basket is being attacked
  const shooterSprite = playerSprites[ballHandlerId];
  const isHomeOffense = shooterSprite?.team === "home";
  const basket = isHomeOffense ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
  
  // Convert sprite positions to grid for starting y calculation
  const pixelsToGrid = (pixelX, pixelY) => {
    const gridX = (pixelX / width) * 100;
    const gridY = 50 - (pixelY / height) * 50;
    return { x: gridX, y: gridY };
  };
  
  for (const [id, sprite] of Object.entries(playerSprites)) {
    // Skip shooter, primary defender, get-back players, and release players (outlet passer uses same tween path)
    if (
      id === ballHandlerId ||
      id === primaryDefenderId ||
      getbackPlayerIdsSet.has(id) ||
      releasePlayerIdsSet.has(id)
    ) {
      continue;
    }
    
    // ✅ This is a rebounder (stayed near rim for shot attempt)
    // Get starting y coordinate from current sprite position
    const startingGrid = pixelsToGrid(sprite.x, sprite.y);
    const startingY = startingGrid.y;
    
    let targetSpot;
    const animEnd = getAnimationEndGridForPlayer(turnData, id);
    incrementFbCounter(scene, "fbRequiredRoleCount", 1);
    if (animEnd) {
      targetSpot = animEnd;
    } else if (isDefensiveStop) {
      // ✅ Defensive Stop: x=40-60, y=starting_y ± 6 (clamped 1-49)
      targetSpot = {
        x: Phaser.Math.Between(REBOUNDER_X_MIN, REBOUNDER_X_MAX),
        y: Phaser.Math.Clamp(startingY + Phaser.Math.Between(-REBOUNDER_Y_RANGE, REBOUNDER_Y_RANGE), GRID_MIN_Y, GRID_MAX_Y)
      };
    } else {
      // ✅ Shot Attempt: x=random 5-20 spots out from basket, y=rim_y ± 10 (clamped 1-49)
      // Home basket (x=91): 5-20 spots less = 71-86
      // Away basket (x=9): 5-20 spots more = 14-29
      const distanceFromBasket = Phaser.Math.Between(5, 20);
      const targetX = isHomeOffense
        ? basket.x - distanceFromBasket // Home: move left (toward center court)
        : basket.x + distanceFromBasket; // Away: move right (toward center court)

      targetSpot = {
        x: Phaser.Math.Clamp(targetX, GRID_MIN_X, GRID_MAX_X), // Clamp to court bounds
        y: Phaser.Math.Clamp(
          basket.y + Phaser.Math.Between(-SHOT_ATTEMPT_REBOUNDER_Y_RANGE, SHOT_ATTEMPT_REBOUNDER_Y_RANGE),
          GRID_MIN_Y,
          GRID_MAX_Y
        ),
      };
    }
    if (!animEnd) {
      const source = rimRunnerSpriteGrid(sprite, width, height);
      reportMissingEndpoint(scene, turnData, {
        playerId: id,
        role: "rebounder",
        requiredEndpointType: "animations_end",
        hasRoleCoord: false,
        reason: "missing_rebounder_animation_end",
      });
      reportFallback(scene, {
        playerId: id,
        role: "rebounder",
        fallbackPolicy: isDefensiveStop ? "defensive_stop_band" : "shot_attempt_rebound_band",
        missingAuthority: ["animations_end"],
        source,
        target: targetSpot,
      });
    }

    const targetPx = gridToPixels(targetSpot.x, targetSpot.y, width, height);
    // ✅ Use distance-based duration for consistent speed
    // Players will stop at their current position if shot happens before they reach their spot
    // (Made shot: stops when ball hits rim; Missed shot: stops when rebounder grabs ball)
    const playerDuration = getPlayerDuration(sprite, targetPx.x, targetPx.y);
    
    // ✅ Create tween directly (not using tweenPlayerTo) so we can store reference for early termination
    const tween = scene.tweens.add({
      targets: sprite,
      x: targetPx.x,
      y: targetPx.y,
      duration: playerDuration,
      ease: "Linear",
      onComplete: () => {
        // Tween completed naturally (player reached destination)
      }
    });
    rebounderTweens.push(tween);
  }
  
  return rebounderTweens;
}

/**
 * Same rim convention as `animateFastBreakShot` / `animateFastBreakShotWithStopper` (HOME grid).
 */
function getFastBreakAttackingBasket(isHomeOffense) {
  return isHomeOffense ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
}

// Critical-event cleanup helper. When the defensive-stop critical event fires
// (BH at top-of-key, stopper at their spot), all other parallel tweens should
// stop wherever they are — preventing far-end runaways like offensive teammates
// continuing to the basket.
function stopAllNonBhStopperTweens(scene, playerSprites, ballHandlerId, stopperId) {
  if (!scene?.tweens) return;
  for (const [id, sprite] of Object.entries(playerSprites)) {
    if (id === String(ballHandlerId) || id === String(stopperId)) continue;
    if (!sprite) continue;
    scene.tweens.killTweensOf(sprite);
  }
}

/**
 * X band for get-back defenders to sprint toward the hoop the fast-break offense is attacking.
 * Must match offense direction used for shot spots — do not hardcode one rim; away FB attacks low x.
 */
function getGetBackRetreatXRange(isHomeOffense) {
  const basket = getFastBreakAttackingBasket(isHomeOffense);
  if (isHomeOffense) {
    return {
      minX: 50,
      maxX: Phaser.Math.Clamp(basket.x - 2, GRID_MIN_X, GRID_MAX_X),
    };
  }
  return {
    minX: Phaser.Math.Clamp(basket.x + 2, GRID_MIN_X, GRID_MAX_X),
    maxX: 50,
  };
}

function resolveFastBreakOffenseIsHome(playerSprites, ballHandlerId, turnData, scene) {
  const bhSprite = ballHandlerId != null ? playerSprites[ballHandlerId] : null;
  if (bhSprite?.team === "home") return true;
  if (bhSprite?.team === "away") return false;
  const oid =
    turnData?.offense_team_id ??
    turnData?.possession_team_id ??
    scene?.offenseTeamId;
  const hid = scene?.simData?.home_team_id;
  if (oid != null && hid != null) {
    return String(oid) === String(hid);
  }
  return true;
}

/**
 * Helper: Move all non-involved players to their positions
 * - Get-back players: prefer `turn.animations[].end` (SS&S with sim); else retreat band toward rim, Y: 15–35
 * - Outlet passer & other trail players: same targets/tweens as animateRebounders (incl. early stop)
 * - Distance-based animation - stops when ball hits rim (made) or rebounder grabs ball (missed)
 * - Rebounders stop early when defensive stop is made (ball handler and stopper reach their spots)
 *
 * @returns {Array} Array of tween references for rebounder animations (for early termination)
 */
async function moveOtherPlayersToStandardPositions(
  scene,
  playerSprites,
  ballHandlerId,
  primaryDefenderId,
  turnData,
  width,
  height,
  promises
) {
  // ✅ Find the most recent MISS/MAKE turn to get get-back and release player lists
  let getbackPlayerIds = [];
  let releasePlayerIds = [];
  const currentIndex = scene.currentTurn || 0;
  const previousTurn = scene.simData?.turns?.[currentIndex - 1];
  const currentTurn = scene.simData?.turns?.[currentIndex];
  
  if (previousTurn?.result_type === "MISS" || previousTurn?.result_type === "BLOCK" || previousTurn?.result_type === "MAKE") {
    getbackPlayerIds = previousTurn?.offense_getback || [];
    releasePlayerIds = previousTurn?.defense_release || [];
  } else if (currentTurn?.result_type === "MISS" || currentTurn?.result_type === "BLOCK" || currentTurn?.result_type === "MAKE") {
    getbackPlayerIds = currentTurn?.offense_getback || [];
    releasePlayerIds = currentTurn?.defense_release || [];
  }
  
  const getbackPlayerIdsSet = new Set(getbackPlayerIds);
  const releasePlayerIdsSet = new Set(releasePlayerIds);
  
  for (const [id, sprite] of Object.entries(playerSprites)) {
    // Skip shooter and primary defender (already animated)
    if (id === ballHandlerId || id === primaryDefenderId) {
      continue;
    }
    
    // ✅ Skip release players (they're the ball handler, already animated)
    if (releasePlayerIdsSet.has(id)) {
      continue;
    }
    
    // ✅ Only animate get-back players as defenders (not all players in defense list)
    // Rebounders are handled separately by animateRebounders() function
    if (getbackPlayerIdsSet.has(id)) {
      const isHomeOffense = resolveFastBreakOffenseIsHome(
        playerSprites,
        ballHandlerId,
        turnData,
        scene
      );
      const { minX, maxX } = getGetBackRetreatXRange(isHomeOffense);
      const lo = Math.min(minX, maxX);
      const hi = Math.max(minX, maxX);
      const animEnd = getAnimationEndGridForPlayer(turnData, id);
      incrementFbCounter(scene, "fbRequiredRoleCount", 1);
      const targetSpot = animEnd ?? {
        x: Phaser.Math.Between(lo, hi),
        y: Phaser.Math.Between(15, 35),
      };
      if (!animEnd) {
        const source = rimRunnerSpriteGrid(sprite, width, height);
        reportMissingEndpoint(scene, turnData, {
          playerId: id,
          role: "getback_defender",
          requiredEndpointType: "animations_end",
          hasRoleCoord: false,
          reason: "missing_getback_animation_end",
        });
        reportFallback(scene, {
          playerId: id,
          role: "getback_defender",
          fallbackPolicy: "random_band",
          missingAuthority: ["animations_end"],
          source,
          target: targetSpot,
        });
      }

      const targetPx = gridToPixels(targetSpot.x, targetSpot.y, width, height);
      const playerDuration = getPlayerDuration(sprite, targetPx.x, targetPx.y);
      
      promises.push(
        tweenPlayerTo(scene, sprite, targetPx, {
          duration: playerDuration,
          easing: "Linear"
        })
      );
    }
    // Note: Rebounders are handled by animateRebounders() function (called after this loop)
  }
  
  // ✅ Animate rebounders using extracted function
  const rebounderTweens = animateRebounders(
    scene,
    playerSprites,
    ballHandlerId,
    primaryDefenderId,
    turnData,
    width,
    height,
    getbackPlayerIdsSet,
    releasePlayerIdsSet
  );
  
  // Add rebounder tween promises for awaiting
  rebounderTweens.forEach(tween => {
    promises.push(
      new Promise((resolve) => {
        tween.once('complete', resolve);
        tween.once('stop', resolve);
      })
    );
  });
  
  return rebounderTweens; // Return tween references for early termination
}

// Export for backwards compatibility
export default function runFastBreakSequenceWrapper(scene, { playerSprites, ballSprite, turnData }) {
  return runFastBreakSequence({ scene, playerSprites, ballSprite, turnData });
}

export { HOME_RIM_COORDS, AWAY_RIM_COORDS, HOME_TOP_KEY, AWAY_TOP_KEY } from "./courtConstants.js";
