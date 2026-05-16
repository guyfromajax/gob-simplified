import { gridToPixels } from "../../utils/gridToPixels.js";
import { BALL_ATTACH_OFFSET } from "../../setup/markerConfig.js";
import animationConfig from "../animation_config.js";
import {
  safeTransition,
  States,
} from "../../state/gameStateMachine.js";
import {
  isAnimationDebugEnabled,
} from "../../utils/debugFlags.js";
import { getSceneStepLogger } from "../debugStepLogger.js";

function toNumber(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (value == null) return null;
  const coerced = Number(value);
  return Number.isFinite(coerced) ? coerced : null;
}

function findOwnerFromFrame(frame) {
  if (!frame || typeof frame !== "object") return null;
  const players = frame.players || {};
  for (const [playerId, payload] of Object.entries(players)) {
    if (payload?.hasBall) return playerId;
  }
  return null;
}

function normalizeActionName(action) {
  if (typeof action !== "string") return null;
  return action.trim().toLowerCase();
}

function isShotAction(action) {
  const normalized = normalizeActionName(action);
  return normalized === "shoot" || normalized === "shot";
}

function isReboundAction(action) {
  return normalizeActionName(action) === "rebound";
}

function buildStepPayload({
  frame,
  frameIndex,
  possessionId,
  turnId,
  resolvedDuration,
  rawDuration,
  durationScale,
  scalePass,
}) {
  const normalizePass = (pass) => {
    const raw = toNumber(pass?.duration);
    return {
      fromId: pass?.fromId ?? null,
      toId: pass?.toId ?? null,
      duration: raw,
      scaledDuration:
        typeof scalePass === "function" && raw != null
          ? scalePass(raw)
          : null,
    };
  };
  return {
    frameIndex,
    timestamp: frame?.timestamp ?? null,
    duration: resolvedDuration ?? frame?.duration ?? null,
    rawDuration: rawDuration ?? frame?.duration ?? null,
    durationScale: durationScale ?? null,
    possessionId: possessionId ?? null,
    turnId: turnId ?? null,
    actions: Array.isArray(frame?.actions)
      ? frame.actions.map((action) => ({
          playerId: action?.playerId ?? null,
          action: action?.action ?? null,
        }))
      : [],
    passes: Array.isArray(frame?.passes)
      ? frame.passes.map((pass) => normalizePass(pass))
      : [],
  };
}

export class PossessionRunner {
  constructor({
    scene,
    ballSprite,
    playerSprites,
    graph,
    config = {},
  } = {}) {
    this.scene = scene || null;
    this.ballSprite = ballSprite || scene?.ballSprite || null;
    this.playerSprites = playerSprites || scene?.playerSprites || {};
    this.graph = graph || null;
    this.config = config || {};
    this.helpers = {
      attachBallToPlayer: this.config.helpers?.attachBallToPlayer || null,
      runPass: this.config.helpers?.runPass || null,
      animateRebound: this.config.helpers?.animateRebound || null,
      shootBall: this.config.helpers?.shootBall || null,
    };
    this.helpersLoaded = Boolean(
      this.helpers.attachBallToPlayer &&
        this.helpers.runPass &&
        this.helpers.animateRebound &&
        this.helpers.shootBall
    );
    this.helperLoadPromise = null;
    this.pendingPromises = [];
    this.frameSummaries = new Map();
    this.currentOwnerId = this.graph?.setup?.ball?.ownerId ?? null;
    this.lastMissLocation = null;
    this.lastShotOutcome = null;
    this.stepLogger = scene ? getSceneStepLogger(scene, "ANIM") : null;
    this.timelineFactoryPromise = null;
    this.activePendingCount = 0;
    this.targetFrameDurationMs =
      toNumber(this.config?.targetFrameDurationMs) ??
      toNumber(animationConfig?.possession?.targetFrameMs) ??
      320;
    this.minFrameDurationMs =
      toNumber(this.config?.minFrameDurationMs) ??
      toNumber(animationConfig?.possession?.minFrameMs) ??
      120;
    if (!this.minFrameDurationMs || this.minFrameDurationMs < 0) {
      this.minFrameDurationMs = 120;
    }
    const resolvedMaxFrame =
      toNumber(this.config?.maxFrameDurationMs) ??
      toNumber(animationConfig?.possession?.maxFrameMs) ??
      null;
    this.maxFrameDurationMs =
      resolvedMaxFrame && resolvedMaxFrame > 0
        ? Math.max(resolvedMaxFrame, this.minFrameDurationMs)
        : null;
    this.minPassDurationMs =
      toNumber(this.config?.minPassDurationMs) ??
      toNumber(animationConfig?.possession?.minPassDurationMs) ??
      toNumber(animationConfig?.pass?.duration) ??
      150;
    if (!this.minPassDurationMs || this.minPassDurationMs <= 0) {
      this.minPassDurationMs = 150;
    }
    const resolvedMaxPass =
      toNumber(this.config?.maxPassDurationMs) ??
      toNumber(animationConfig?.possession?.maxPassDurationMs) ??
      null;
    this.maxPassDurationMs =
      resolvedMaxPass && resolvedMaxPass > 0
        ? Math.max(resolvedMaxPass, this.minPassDurationMs)
        : null;
    this.minDurationScale =
      toNumber(this.config?.minDurationScale) ??
      toNumber(animationConfig?.possession?.minDurationScale) ??
      0.35;
    if (!this.minDurationScale || this.minDurationScale <= 0) {
      this.minDurationScale = 0.35;
    }
    this.maxDurationScale =
      toNumber(this.config?.maxDurationScale) ??
      toNumber(animationConfig?.possession?.maxDurationScale) ??
      6;
    if (!this.maxDurationScale || this.maxDurationScale < this.minDurationScale) {
      this.maxDurationScale = Math.max(this.minDurationScale, 6);
    }
    this.durationScale = 1;
  }

  getDebugContext(additional = {}) {
    return {
      turnIndex:
        this.config?.turnIndex ?? this.graph?.context?.turnIndex ?? null,
      possessionId: this.graph?.context?.possessionId ?? null,
      turnId: this.graph?.context?.turnId ?? null,
      ...additional,
    };
  }

  emitDebug(event, payload = {}) {
    if (!isAnimationDebugEnabled()) return;
    this.scene?.events?.emit?.(event, {
      ...this.getDebugContext(payload),
      timestamp: Date.now(),
    });
  }

  emitPendingSummary(reason, extra = {}) {
    this.emitDebug("possessionRunner:pending", {
      reason,
      pendingCount: this.activePendingCount,
      ...extra,
    });
  }

  emitPossessionChange(teamId, payload = {}) {
    if (!this.scene || teamId == null) return;
    const previous = this.scene.offenseTeamId;
    const nextId = String(teamId);
    if (previous != null && String(previous) === nextId) return;
    this.scene.offenseTeamId = teamId;
    this.scene.events?.emit?.("possessionChange", {
      offenseTeamId: teamId,
      ...payload,
    });
  }

  resolveDurationScale(frames = []) {
    const durations = [];
    let totalRaw = 0;
    for (const frame of frames) {
      const value = toNumber(frame?.duration);
      if (!value || value <= 0) continue;
      durations.push(value);
      totalRaw += value;
    }
    if (!durations.length || totalRaw <= 0) {
      return 1;
    }

    let scale = 1;
    const contextDuration = toNumber(this.graph?.context?.timeElapsed);
    if (contextDuration && contextDuration > 0) {
      const minTotal = this.minFrameDurationMs * durations.length * 0.5;
      if (!minTotal || contextDuration >= minTotal) {
        const contextScale = contextDuration / totalRaw;
        if (Number.isFinite(contextScale) && contextScale > 0) {
          scale = contextScale;
        }
      }
    }

    if (scale === 1) {
      const averageRaw = totalRaw / durations.length;
      const target =
        (this.targetFrameDurationMs && this.targetFrameDurationMs > 0)
          ? this.targetFrameDurationMs
          : 320;
      if (averageRaw > 0 && target > 0) {
        const baselineScale = target / averageRaw;
        if (Number.isFinite(baselineScale) && baselineScale > 0) {
          scale = baselineScale;
        }
      }
    }

    if (!Number.isFinite(scale) || scale <= 0) {
      scale = 1;
    }
    if (this.minDurationScale && scale < this.minDurationScale) {
      scale = this.minDurationScale;
    }
    if (this.maxDurationScale && scale > this.maxDurationScale) {
      scale = this.maxDurationScale;
    }
    return scale;
  }

  clampDuration(value, min, max) {
    let resolved = Number.isFinite(value) ? value : 0;
    const resolvedMin = toNumber(min);
    if (resolvedMin != null && resolvedMin > 0 && (resolved <= 0 || resolved < resolvedMin)) {
      resolved = resolvedMin;
    }
    const resolvedMax = toNumber(max);
    if (resolvedMax != null && resolvedMax > 0 && resolved > resolvedMax) {
      resolved = resolvedMax;
    }
    if (!Number.isFinite(resolved) || resolved < 0) {
      resolved = resolvedMin != null ? resolvedMin : 0;
    }
    return Math.round(resolved);
  }

  scaleFrameDuration(rawDuration) {
    const base = toNumber(rawDuration);
    if (!base || base <= 0) {
      return this.clampDuration(
        this.minFrameDurationMs,
        this.minFrameDurationMs,
        this.maxFrameDurationMs
      );
    }
    const scaled = base * (this.durationScale || 1);
    return this.clampDuration(scaled, this.minFrameDurationMs, this.maxFrameDurationMs);
  }

  scalePassDuration(rawDuration) {
    const base = toNumber(rawDuration);
    if (!base || base <= 0) {
      return this.clampDuration(
        this.minPassDurationMs,
        this.minPassDurationMs,
        this.maxPassDurationMs
      );
    }
    const scaled = base * (this.durationScale || 1);
    return this.clampDuration(scaled, this.minPassDurationMs, this.maxPassDurationMs);
  }

  async run() {
    if (!this.scene || !this.graph) return null;
    await this.ensureHelpersLoaded();
    this.preloadSprites();
    const timeline = await this.resolveTimeline();
    const frames = Array.isArray(this.graph?.timeline?.frames)
      ? this.graph.timeline.frames
      : [];

    if (!timeline || frames.length === 0) {
      await this.handleTerminalState();
      return null;
    }

    this.durationScale = this.resolveDurationScale(frames);
    if (isAnimationDebugEnabled()) {
      this.scene?.events?.emit?.("possessionRunner:timing", {
        scale: this.durationScale,
        targetFrameMs: this.targetFrameDurationMs,
        minFrameMs: this.minFrameDurationMs,
        maxFrameMs: this.maxFrameDurationMs,
      });
    }

    frames.forEach((frame, index) => {
      this.enqueueFrame(timeline, frame, index);
    });

    const completion = new Promise((resolve, reject) => {
      timeline.once?.("complete", resolve);
      timeline.once?.("stop", () => reject(new Error("timeline stopped")));
    });

    this.emitDebug("possessionRunner:timelinePlay", {
      frameCount: frames.length,
      durationScale: this.durationScale,
    });

    timeline.play?.();

    try {
      await completion;
      this.emitDebug("possessionRunner:timelineResolved", {
        pendingCount: this.activePendingCount,
      });
    } catch (error) {
      if (isAnimationDebugEnabled()) {
        this.scene?.events?.emit?.("possessionRunner:error", { error });
      }
    }

    await Promise.all(this.pendingPromises)
      .catch(() => {})
      .finally(() => {
        this.emitDebug("possessionRunner:helpersSettled", {
          pendingCount: this.activePendingCount,
        });
        this.pendingPromises = [];
        this.activePendingCount = 0;
      });
    await this.handleTerminalState();
    return null;
  }

  preloadSprites() {
    const setup = this.graph?.setup;
    if (!setup) return;

    const players = setup.players || {};
    const order = Array.isArray(setup.order) ? setup.order : Object.keys(players);

    const offenseTeamId =
      this.graph?.context?.offenseTeamId ?? setup.offenseTeamId ?? null;
    if (offenseTeamId != null) {
      this.scene.offenseTeamId = offenseTeamId;
    }

    order.forEach((playerId) => {
      const payload = players[playerId];
      if (!payload) return;
      const sprite = this.playerSprites?.[playerId];
      if (!sprite) return;
      if (payload.x == null || payload.y == null) return;
      const { x, y } = this.toPixels(payload.x, payload.y);
      if (typeof sprite.setPosition === "function") {
        sprite.setPosition(x, y);
      } else {
        sprite.x = x;
        sprite.y = y;
      }
    });

    if (this.ballSprite && setup.ball?.coords) {
      const coords = setup.ball.coords;
      if (coords?.x != null && coords?.y != null) {
        const { x, y } = this.toPixels(coords.x, coords.y);
        // When the ball is attached to an owner at setup, anchor at the hip
        // (BALL_ATTACH_OFFSET); loose / opening-tip placements stay on the spot.
        const hasOwner = !!setup.ball?.ownerId;
        const ax = x + (hasOwner ? BALL_ATTACH_OFFSET.x : 0);
        const ay = y + (hasOwner ? BALL_ATTACH_OFFSET.y : 0);
        if (typeof this.ballSprite.setPosition === "function") {
          this.ballSprite.setPosition(ax, ay);
        } else {
          this.ballSprite.x = ax;
          this.ballSprite.y = ay;
        }
        this.ballSprite.setVisible?.(true);
      }
    }

    if (setup.ball?.ownerId && this.ballSprite) {
      const sprite = this.playerSprites?.[setup.ball.ownerId];
      if (sprite) {
        this.helpers.attachBallToPlayer?.(this.scene, this.ballSprite, sprite);
        this.currentOwnerId = setup.ball.ownerId;
      }
    }

    if (this.scene?.stateMachine?.is?.(States.Inbound)) {
      const ctx = {
        event: "possessionSetup",
        possessionId: this.graph?.context?.possessionId ?? null,
        turnId: this.graph?.context?.turnId ?? null,
      };
      this.transitionTo(States.HalfCourt, ctx);
    }
  }

  enqueueFrame(timeline, frame, frameIndex) {
    const tracker = { progress: 0 };
    const rawDuration = Math.max(0, toNumber(frame?.duration) ?? 0);
    const duration = this.scaleFrameDuration(rawDuration);

    this.emitDebug("possessionRunner:timelineEnqueue", {
      frameIndex,
      rawDuration,
      duration,
    });

    timeline.add?.({
      targets: tracker,
      progress: 1,
      duration,
      ease: "Linear",
      onStart: () => this.onFrameStart(frame, frameIndex, duration, rawDuration),
      onComplete: () => this.onFrameComplete(frame, frameIndex),
    });
  }

  onFrameStart(frame, frameIndex, duration, rawDuration) {
    const debugEnabled = isAnimationDebugEnabled();
    if (debugEnabled) {
      this.scene?.events?.emit?.(
        "possessionRunner:step",
        buildStepPayload({
          frame,
          frameIndex,
          possessionId: this.graph?.context?.possessionId,
          turnId: this.graph?.context?.turnId,
          resolvedDuration: duration,
          rawDuration,
          durationScale: this.durationScale,
          scalePass: (value) => this.scalePassDuration(value),
        })
      );
    }

    if (debugEnabled && this.stepLogger) {
      const actions = Array.isArray(frame?.actions)
        ? frame.actions.map((action) => ({
            playerId: action?.playerId ?? null,
            action: action?.action ?? null,
          }))
        : [];
      this.stepLogger.logStep({
        turnIndex: this.config?.turnIndex ?? this.graph?.context?.possessionIndex ?? null,
        turnId: this.graph?.context?.turnId ?? null,
        possessionId: this.graph?.context?.possessionId ?? null,
        stepIndex: frameIndex,
        timestamp: frame?.timestamp ?? null,
        actions,
      });
    }

    const promises = [];
    const ownerId = findOwnerFromFrame(frame);
    if (ownerId && ownerId !== this.currentOwnerId) {
      const sprite = this.playerSprites?.[ownerId];
      if (sprite && this.ballSprite) {
        this.helpers.attachBallToPlayer?.(this.scene, this.ballSprite, sprite);
        this.currentOwnerId = ownerId;
      }
    }

    const players = frame?.players || {};
    for (const [playerId, payload] of Object.entries(players)) {
      const tweenPromise = this.createPlayerTween({
        playerId,
        payload,
        duration,
        frameIndex,
        timestamp: frame?.timestamp ?? null,
      });
      if (tweenPromise) {
        promises.push(tweenPromise.catch(() => {}));
      }
    }

    if (Array.isArray(frame?.passes)) {
      frame.passes.forEach((pass) => {
        const promise = this.handlePass(pass, frameIndex, frame?.timestamp ?? null);
        if (promise) promises.push(promise.catch(() => {}));
      });
    }

    if (Array.isArray(frame?.actions)) {
      frame.actions.forEach((action) => {
        const promise = this.handleAction(action, frame, frameIndex);
        if (promise) promises.push(promise.catch(() => {}));
      });
    }

    const summaryPromise = Promise.all(promises).then(() =>
      this.buildFrameSummary(frame, frameIndex, duration, rawDuration)
    );

    const wrappedPromise = summaryPromise.catch(() => {});
    this.pendingPromises.push(wrappedPromise);
    this.activePendingCount += 1;
    this.emitPendingSummary("frame-enqueued", { frameIndex });
    this.frameSummaries.set(frameIndex, summaryPromise);

    wrappedPromise.finally(() => {
      this.activePendingCount = Math.max(0, this.activePendingCount - 1);
      this.emitPendingSummary("frame-resolved", { frameIndex });
    });
  }

  onFrameComplete(frame, frameIndex) {
    const summaryPromise = this.frameSummaries.get(frameIndex);
    this.frameSummaries.delete(frameIndex);
    if (!summaryPromise) return;
    summaryPromise
      .then((summary) => {
        this.emitPendingSummary("frame-complete", { frameIndex });
        if (isAnimationDebugEnabled()) {
          this.scene?.events?.emit?.("possessionRunner:postStep", summary);
        }
      })
      .catch(() => {});
  }

  createPlayerTween({ playerId, payload, duration, frameIndex }) {
    const sprite = this.playerSprites?.[playerId];
    if (!sprite || !this.scene?.tweens?.add) return null;
    if (payload?.x == null || payload?.y == null) return null;
    const { x, y } = this.toPixels(payload.x, payload.y);

    return new Promise((resolve) => {
      const tween = this.scene.tweens.add({
        targets: sprite,
        x,
        y,
        duration,
        ease: "Linear",
        onStart: () => {
          if (payload?.hasBall && this.ballSprite) {
            if (this.currentOwnerId !== playerId) {
              this.helpers.attachBallToPlayer?.(
                this.scene,
                this.ballSprite,
                sprite
              );
              this.currentOwnerId = playerId;
            }
          }
        },
        onUpdate: () => {
          if (payload?.hasBall && this.ballSprite) {
            this.ballSprite.setPosition?.(
              sprite.x + BALL_ATTACH_OFFSET.x,
              sprite.y + BALL_ATTACH_OFFSET.y,
            );
          }
        },
        onComplete: () => {
          sprite.x = x;
          sprite.y = y;
          resolve();
        },
        onStop: () => {
          resolve();
        },
      });
      if (!tween) resolve();
    });
  }

  handlePass(pass, frameIndex, timestamp) {
    if (!this.helpers.runPass || !this.scene) return null;
    const rawDuration = toNumber(pass?.duration);
    const duration =
      rawDuration != null
        ? this.scalePassDuration(rawDuration)
        : animationConfig.pass.duration;
    const easing = pass?.easing ?? animationConfig.pass.easing;
    const promise = Promise.resolve(
      this.helpers.runPass(this.scene, {
        fromId: pass?.fromId ?? null,
        toId: pass?.toId ?? null,
        duration,
        easing,
        timestamp,
      })
    ).then(() => {
      if (pass?.toId) this.currentOwnerId = pass.toId;
    });
    return promise;
  }

  handleAction(action, frame, frameIndex) {
    const normalized = normalizeActionName(action?.action);
    if (isShotAction(normalized)) {
      return this.handleShot(action, frame, frameIndex);
    }
    if (isReboundAction(normalized)) {
      return this.handleRebound(action, frame, frameIndex);
    }
    return null;
  }

  handleShot(action, frame, frameIndex) {
    if (!this.helpers.shootBall || !this.ballSprite) return null;
    const shooterId = action?.playerId ?? null;
    if (!shooterId) return null;
    const playerState = frame?.players?.[shooterId];
    if (!playerState || playerState.x == null || playerState.y == null) return null;

    this.transitionTo(States.ShotAttempt, {
      event: "shot",
      shooterId,
      frameIndex,
      timestamp: frame?.timestamp ?? null,
    });

    const shotMeta = this.graph?.terminal?.shot ?? {};
    const result = shotMeta?.outcome ?? null;
    const promise = Promise.resolve(
      this.helpers.shootBall({
        scene: this.scene,
        ballSprite: this.ballSprite,
        fromCoords: { x: playerState.x, y: playerState.y },
        startTimestamp: frame?.timestamp ?? null,
        result,
        shooterPos: playerState?.position ?? null,
        shooterId,
        shooterTeamId: playerState?.teamId ?? shotMeta?.teamId ?? null,
        homeTeamId: this.config?.homeTeamId ?? this.graph?.context?.homeTeamId ?? null,
        stepIndex: frameIndex,
        turnIndex: this.config?.turnIndex ?? this.graph?.context?.turnIndex ?? null,
      })
    );

    return promise.then((outcome) => {
      this.lastShotOutcome = result ?? null;
      if (outcome?.grid) {
        this.lastMissLocation = outcome.grid;
      }
      return outcome;
    });
  }

  handleRebound(action, frame, frameIndex) {
    if (!this.helpers.animateRebound) return null;
    const reboundMeta = this.graph?.terminal?.rebound;
    if (!reboundMeta?.rebounderId) return null;
    const ballSpot = this.lastMissLocation ?? {
      x: frame?.players?.[reboundMeta.rebounderId]?.x ?? null,
      y: frame?.players?.[reboundMeta.rebounderId]?.y ?? null,
    };
    if (!ballSpot?.x && !ballSpot?.y) return null;

    const promise = Promise.resolve(
      this.helpers.animateRebound({
        scene: this.scene,
        ballSprite: this.ballSprite,
        playerSprites: this.playerSprites,
        animations: this.config?.animations ?? null,
        rebounderId: reboundMeta.rebounderId,
        ballSpot,
        shooterId: this.graph?.terminal?.shot?.shooterId ?? null,
        upcomingFastBreak: this.graph?.context?.fastBreak ?? false,
      })
    );

    return promise.then(() => {
      this.currentOwnerId = reboundMeta.rebounderId;
    });
  }

  buildFrameSummary(frame, frameIndex, duration, rawDuration) {
    return {
      frameIndex,
      timestamp: frame?.timestamp ?? null,
      duration: toNumber(duration) ?? null,
      rawDuration: toNumber(rawDuration ?? frame?.duration) ?? null,
      ownerId: this.currentOwnerId ?? null,
      actions: Array.isArray(frame?.actions)
        ? frame.actions.map((action) => ({
            playerId: action?.playerId ?? null,
            action: action?.action ?? null,
          }))
        : [],
      passes: Array.isArray(frame?.passes)
        ? frame.passes.map((pass) => ({
            fromId: pass?.fromId ?? null,
            toId: pass?.toId ?? null,
            duration: toNumber(pass?.duration) ?? null,
            scaledDuration:
              pass?.duration != null
                ? this.scalePassDuration(pass.duration)
                : null,
          }))
        : [],
    };
  }

  async handleTerminalState() {
    const stateMachine = this.scene?.stateMachine;
    if (!stateMachine) return;
    const terminal = this.graph?.terminal ?? {};

    if (terminal.turnover?.playerId) {
      const newOffenseId = this.graph?.context?.defenseTeamId ?? null;
      if (newOffenseId != null) {
        this.emitPossessionChange(newOffenseId, {
          event: "turnover",
          source: "runner",
        });
      }
      this.transitionTo(States.Turnover, {
        event: "turnover",
        playerId: terminal.turnover.playerId,
        cause: terminal.turnover.cause ?? null,
      });
      return;
    }

    if (terminal.shot?.outcome === "MAKE") {
      const newOffenseId = this.graph?.context?.defenseTeamId ?? null;
      if (newOffenseId != null) {
        this.emitPossessionChange(newOffenseId, {
          event: "shotMake",
          source: "runner",
          points: terminal.shot?.points ?? null,
        });
      }
      this.transitionTo(States.Inbound, {
        event: "shotMake",
        shooterId: terminal.shot?.shooterId ?? null,
        points: terminal.shot?.points ?? null,
      });
      return;
    }

    if (terminal.shot?.outcome === "MISS" && !terminal.rebound?.rebounderId) {
      this.transitionTo(States.Rebound, {
        event: "shotMiss",
        shooterId: terminal.shot?.shooterId ?? null,
      });
    }
  }

  transitionTo(nextState, ctx = {}) {
    const stateMachine = this.scene?.stateMachine;
    if (!stateMachine) return;
    const previous = stateMachine.state;
    if (previous === nextState) {
      return;
    }
    safeTransition(stateMachine, nextState, ctx);
    if (stateMachine.state !== previous && isAnimationDebugEnabled()) {
      this.scene?.events?.emit?.("possessionRunner:transition", {
        fromState: previous,
        toState: stateMachine.state,
        context: { ...ctx },
      });
    }
  }

  toPixels(x, y) {
    return gridToPixels(
      x,
      y,
      this.scene?.game?.config?.width,
      this.scene?.game?.config?.height
    );
  }

  async resolveTimeline() {
    if (typeof this.config?.createTimeline === "function") {
      return this.config.createTimeline(this.scene);
    }

    if (!this.timelineFactoryPromise) {
      const isNodeEnv =
        typeof process !== "undefined" &&
        process?.release?.name === "node";
      const basePath = "../animationTimeline";
      const modulePath = isNodeEnv ? `${basePath}.stub.js` : `${basePath}.js`;
      this.timelineFactoryPromise = import(modulePath);
    }

    const module = await this.timelineFactoryPromise;
    const factory = module?.createAnimationTimeline || module?.default || (() => null);
    return factory(this.scene);
  }

  async ensureHelpersLoaded() {
    if (this.helpersLoaded) return;
    if (!this.helperLoadPromise) {
      this.helperLoadPromise = (async () => {
        const isNodeEnv =
          typeof process !== "undefined" &&
          process?.release?.name === "node";
        const basePath = "../ballManager";
        const modulePath = isNodeEnv ? `${basePath}.stub.js` : `${basePath}.js`;
        const module = await import(modulePath);
        const source = module?.default || module || {};
        this.helpers = {
          attachBallToPlayer:
            this.helpers.attachBallToPlayer || source.attachBallToPlayer,
          runPass: this.helpers.runPass || source.runPass,
          animateRebound: this.helpers.animateRebound || source.animateRebound,
          shootBall: this.helpers.shootBall || source.shootBall,
        };
        this.helpersLoaded = Boolean(
          this.helpers.attachBallToPlayer &&
            this.helpers.runPass &&
            this.helpers.animateRebound &&
            this.helpers.shootBall
        );
      })();
    }

    await this.helperLoadPromise;
  }
}

export default PossessionRunner;
