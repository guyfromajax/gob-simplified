import * as Phaser from "https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.esm.js";
import { gridToPixels } from "../utils/gridToPixels.js";
import { attachBallToPlayer } from "./ballManager.js";
import { tweenBallTo, tweenPlayerTo, runPass } from "./ballTween.js";
import animationConfig, { FAST_BREAK_END_PAUSE_MS } from "./animation_config.js";
import { HOME_RIM_COORDS, AWAY_RIM_COORDS, HOME_TOP_KEY, AWAY_TOP_KEY } from "./courtConstants.js";
import {
  States,
  safeTransition,
  getDebugTransitions,
} from "../state/gameStateMachine.js";
import { getCurrentOwner } from "../ball/ballController.js";
import { createAnimationTimeline } from "./animationTimeline.js";
import { runInboundSetup } from "./turnAnimation.js";
import {
  DebugFlags,
  animationDebugLog,
  animationDebugWarn,
  isAnimationDebugEnabled,
} from "../utils/debugFlags.js";
import { getSceneStepLogger } from "./debugStepLogger.js";
import { appendToTextScroll } from "../utils/textScroll.js";

// Timeline-driven fast break sequence. Handles the initial sprint phase via a
// Phaser timeline so all player movements can be cancelled together if
// necessary. Subsequent passes and shots reuse existing tween helpers.

function fastBreakEndPause(scene) {
  const delay = DebugFlags?.FB_PAUSE ? FAST_BREAK_END_PAUSE_MS : 0;
  if (scene.skipToEnd || delay <= 0) return Promise.resolve();
  return new Promise((resolve) => scene.time.delayedCall(delay, resolve));
}

function mergePayload(base, extra) {
  const normalizedBase = base != null ? base : undefined;
  if (!extra) return normalizedBase;
  if (!normalizedBase) return { ...extra };
  return { ...normalizedBase, ...extra };
}

function computeFastBreakHopPath(start, target) {
  if (!target || start === target) return [];

  if (target === States.FastBreakOutlet) {
    switch (start) {
      case States.FastBreakOutlet:
        return [];
      case States.Rebound:
        return [States.FastBreakOutlet];
      case States.FastBreak:
      case States.ShotAttempt:
        return [States.Rebound, States.FastBreakOutlet];
      case States.HalfCourt:
        return [States.FastBreak, States.Rebound, States.FastBreakOutlet];
      case States.Inbound:
        return [
          States.HalfCourt,
          States.FastBreak,
          States.Rebound,
          States.FastBreakOutlet,
        ];
      case States.OutletSetup:
        return [
          States.HalfCourt,
          States.FastBreak,
          States.Rebound,
          States.FastBreakOutlet,
        ];
      case States.Turnover:
        return [States.FastBreak, States.Rebound, States.FastBreakOutlet];
      default:
        return [States.Rebound, States.FastBreakOutlet];
    }
  }

  if (target === States.FastBreak) {
    switch (start) {
      case States.FastBreak:
        return [];
      case States.FastBreakOutlet:
        return [States.FastBreak];
      case States.Rebound:
        return [States.FastBreak];
      case States.ShotAttempt:
        return [States.Rebound, States.FastBreak];
      case States.HalfCourt:
        return [States.FastBreak];
      case States.Inbound:
        return [States.HalfCourt, States.FastBreak];
      case States.OutletSetup:
        return [States.HalfCourt, States.FastBreak];
      case States.Turnover:
        return [States.FastBreak];
      default:
        return [States.FastBreak];
    }
  }

  return [target];
}

function runFastBreakTransition(scene, target, options = {}) {
  const machine = scene?.stateMachine;
  if (!machine || !target) return;

  const startState = machine.state;
  const path = computeFastBreakHopPath(startState, target);
  if (!path.length) return;

  const {
    debugStepIndex = null,
    context,
    applyContextToAllSteps = false,
  } = options;

  const debugTransitionsEnabled = getDebugTransitions();
  const debugPayload =
    debugTransitionsEnabled && debugStepIndex != null
      ? { stepIndex: debugStepIndex }
      : undefined;

  let blocked = false;

  for (let index = 0; index < path.length; index++) {
    const step = path[index];
    if (machine.state === step) continue;

    const prevState = machine.state;
    const includeContext = applyContextToAllSteps || index === path.length - 1;
    const payload = includeContext
      ? mergePayload(context, debugPayload)
      : debugPayload;

    safeTransition(machine, step, payload);

    if (machine.state === prevState) {
      blocked = true;
      animationDebugWarn("fastBreak: blocked transition", {
        start: startState,
        target,
        attempted: step,
        fromState: prevState,
        current: machine.state,
      });
      break;
    }
  }

  const expectedFinal = path[path.length - 1];
  if (!blocked && machine.state !== expectedFinal) {
    animationDebugWarn("fastBreak: final state mismatch", {
      start: startState,
      target,
      expected: expectedFinal,
      current: machine.state,
    });
  }
}

export async function runFastBreakSequence({
  scene,
  turnData,
  playerSprites,
  ballSprite,
  turnIndex = null,
}) {
  if (!scene || !turnData || scene.skipToEnd) return;
  if (!scene.ballSprite) scene.ballSprite = ballSprite;
  const animations = turnData.animations || [];
  const width = scene.game.config.width;
  const height = scene.game.config.height;
  const debugEnabled = isAnimationDebugEnabled();
  const stepLogger = debugEnabled ? getSceneStepLogger(scene) : null;
  const possessionId =
    turnData.possession_id ?? turnData.possessionId ?? turnData.possessionID ?? null;

  const fastBreakTurnKey =
    turnIndex ??
    turnData.id ??
    turnData.turn_id ??
    turnData.turnId ??
    null;

  if (fastBreakTurnKey != null) {
    if (scene.__fastBreakBannerTurnKey !== fastBreakTurnKey) {
      scene.__fastBreakBannerTurnKey = fastBreakTurnKey;
      scene.__fastBreakBannerLoggedThisTurn = false;
    }
  } else {
    scene.__fastBreakBannerTurnKey = null;
    scene.__fastBreakBannerLoggedThisTurn = false;
  }

  if (debugEnabled && stepLogger) {
    const maxSteps = Math.max(
      0,
      ...animations.map(anim => anim.movement?.length || 0)
    );
    for (let stepIndex = 0; stepIndex < maxSteps; stepIndex++) {
      const payload = {
        phase: "fastBreak",
        turnIndex,
        possessionId,
        turnId: turnData.id ?? turnData.turn_id ?? null,
        stepIndex,
        timestamp: null,
        actions: [],
      };
      for (const anim of animations) {
        const step = anim.movement?.[stepIndex];
        if (!step) continue;
        if (payload.timestamp == null && typeof step.timestamp === "number") {
          payload.timestamp = step.timestamp;
        }
        payload.actions.push({
          playerId: anim.playerId ?? anim.player_id ?? null,
          action: step.action || null,
        });
      }
      if (payload.actions.length) {
        stepLogger.logStep(payload);
      }
    }
  }

  // stop any existing timeline/tweens
  if (scene.__activeTimeline) {
    scene.__activeTimeline.stop();
    scene.__activeTimeline = null;
  }

  if (turnData.roles?.outlet_passer) {
    // Ensure we're in a valid state for fast break transition
    if (scene.stateMachine?.is(States.Inbound)) {
      if (debugEnabled)
        animationDebugLog('Fast break: correcting state from Inbound to Rebound before FastBreakOutlet transition');
    }
    runFastBreakTransition(scene, States.FastBreakOutlet, { debugStepIndex: 0 });

    if (!scene.__fastBreakBannerLoggedThisTurn) {
      if (typeof window !== "undefined" && window.TEXT_SCROLL_ENABLED) {
        appendToTextScroll("FAST BREAK!");
      }
      scene.__fastBreakBannerLoggedThisTurn = true;
    }

    const passerId = turnData.roles.outlet_passer;
    const receiverId = turnData.roles.outlet_receiver;
    const passerSprite   = playerSprites[passerId];
    const receiverSprite = playerSprites[receiverId];
    const receiverAnim   = animations.find(a => a.playerId === receiverId);
    const startGrid      = receiverAnim?.start || receiverAnim?.movement?.[0]?.coords;
    if (passerSprite && receiverSprite && startGrid) {
      attachBallToPlayer(scene, ballSprite, passerSprite);
      const rim  = passerSprite.team === "home" ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
      const dir  = rim.x > startGrid.x ? -1 : 1;
      const target = {
        x: Phaser.Math.Clamp(startGrid.x + dir * Phaser.Math.Between(15, 20), 4, 97),
        y: Phaser.Math.Clamp(startGrid.y + Phaser.Math.Between(-6, 6), 1, 50)
      };
      const targetPx = gridToPixels(target.x, target.y, width, height);
      await tweenPlayerTo(scene, receiverSprite, targetPx, {
        duration: animationConfig.fastBreak.outletMoveMs,
        easing:  animationConfig.pass.easing,
      });
      if (scene.skipToEnd) return;
      await runPass(scene, {
        fromId: passerId,
        toId:   receiverId,
        duration: animationConfig.fastBreak.passMs,
        easing:  animationConfig.pass.easing,
      });
      receiverAnim.start = target;
      if (receiverAnim.movement?.length) receiverAnim.movement[0].coords = target;
    }
    if (scene.skipToEnd) return;
    runFastBreakTransition(scene, States.FastBreak, { debugStepIndex: 1 });
    scene.events?.emit("fb:start");
  } else {
    runFastBreakTransition(scene, States.FastBreak, { debugStepIndex: 0 });
    scene.events?.emit("fb:start");
  }

  // Use backend timeline data instead of fixed duration
  const timeline = createAnimationTimeline(scene);
  if (!timeline && debugEnabled) {
    animationDebugWarn("fastBreak: timeline unavailable - skipping sprint animation", {
      hasTweenManager: !!scene?.tweens,
      hasCreateTimeline: typeof scene?.tweens?.createTimeline === "function",
      hasTimelineFactory: typeof scene?.tweens?.timeline === "function",
      hasAddTimeline: typeof scene?.tweens?.addTimeline === "function",
    });
  }

  const fallbackSprintDuration =
    animationConfig.fastBreak?.shotMs ?? animationConfig.fastBreak.shotMs ?? 0;
  let sprintDuration = fallbackSprintDuration;
  let earliestSprintTimestamp = null;
  let latestSprintTimestamp = null;

  const ownerAnim = animations.find(a => a.hasBallAtStep?.[0]);
  if (ownerAnim) {
    const ownerSprite = playerSprites[ownerAnim.playerId];
    if (ownerSprite) attachBallToPlayer(scene, ballSprite, ownerSprite);
  }

  // Process each animation using backend movement timeline
  for (const anim of animations) {
    const sprite = playerSprites[anim.playerId];
    if (!sprite || !anim.movement || anim.movement.length < 2) continue;

    const movement = anim.movement;
    const startStep = movement[0];
    const endStep = movement[movement.length - 1];
    
    if (!startStep || !endStep) continue;

    // Set initial position
    const startPx = gridToPixels(startStep.coords.x, startStep.coords.y, width, height);
    sprite.setPosition(startPx.x, startPx.y);

    // Use backend's duration and timing
    const duration = endStep.timestamp - startStep.timestamp;

    if (typeof startStep.timestamp === "number") {
      earliestSprintTimestamp =
        earliestSprintTimestamp == null
          ? startStep.timestamp
          : Math.min(earliestSprintTimestamp, startStep.timestamp);
    }
    if (typeof endStep.timestamp === "number") {
      latestSprintTimestamp =
        latestSprintTimestamp == null
          ? endStep.timestamp
          : Math.max(latestSprintTimestamp, endStep.timestamp);
    }

    // Apply team-specific constraints to move players further down court for separation
    let endX = endStep.coords.x;
    let endY = endStep.coords.y;
    
    // Apply constraints based on player team to create separation
    if (sprite.team === "home") {
      endX = Math.max(endX, 45); // Home team players move further down toward away basket (x ≥ 45)
    } else {
      endX = Math.min(endX, 55); // Away team players move further down toward home basket (x ≤ 55)
    }
    
    const endPx = gridToPixels(endX, endY, width, height);

    if (timeline) {
      // Add to timeline with backend timing
      timeline.add({
        targets: sprite,
        x: endPx.x,
        y: endPx.y,
        duration: duration,
        ease: "Sine.easeInOut"
      }, startStep.timestamp);
    } else {
      // Without a timeline, snap directly to the destination to avoid leaving players behind
      sprite.setPosition(endPx.x, endPx.y);
    }
  }

  if (
    typeof earliestSprintTimestamp === "number" &&
    typeof latestSprintTimestamp === "number" &&
    latestSprintTimestamp > earliestSprintTimestamp
  ) {
    sprintDuration = latestSprintTimestamp - earliestSprintTimestamp;
  }

  if (timeline) {
    scene.__activeTimeline = timeline;

    await new Promise(resolve => {
      timeline.once("complete", resolve);
      timeline.play();
    });

    scene.__activeTimeline = null;
    if (scene.skipToEnd) return;
  } else if (scene.skipToEnd) {
    return;
  }

  // Handle passes after sprint
  const passes = turnData.passes || [];
  if (passes.length > 0) {
    for (const p of passes) {
      if (scene.skipToEnd) break;
      await runPass(scene, {
        fromId: p.fromId || p.from_id,
        toId: p.toId || p.to_id,
        duration: p.duration || animationConfig.pass.duration,
        easing: animationConfig.pass.easing
      });
    }
  } else {
    const passEvents = [];
    for (const anim of animations) {
      const moves = anim.movement || [];
      for (const step of moves) {
        if (step.action === "pass") {
          const ts = step.timestamp;
          const receiverAnim = animations.find(a =>
            a.movement?.some(m => m.action === "receive" && m.timestamp === ts)
          );
          const receiveStep = receiverAnim?.movement.find(
            m => m.action === "receive" && m.timestamp === ts
          );
          const delta = receiveStep
            ? receiveStep.timestamp - ts
            : animationConfig.pass.duration;
          passEvents.push({
            timestamp: ts,
            fromId: anim.playerId,
            toId: receiverAnim?.playerId,
            duration: delta
          });
        }
      }
    }
    passEvents.sort((a, b) => a.timestamp - b.timestamp);
    for (const evt of passEvents) {
      if (scene.skipToEnd) break;
      await runPass(scene, {
        fromId: evt.fromId,
        toId: evt.toId,
        duration: evt.duration,
        easing: animationConfig.pass.easing
      });
    }
  }

  if (scene.skipToEnd) return;

  // Hold-up scenario mirrors previous implementation
  if (turnData.hold_up) {
    const bhId = getCurrentOwner(scene);
    const bhSprite = bhId != null ? playerSprites[bhId] : null;
    const stopperId = turnData.stopper_id;
    const stopperSprite = stopperId != null ? playerSprites[stopperId] : null;
    const promises = [];

    if (bhSprite) {
      attachBallToPlayer(scene, ballSprite, bhSprite);
      const topKey = bhSprite.team === "home" ? HOME_TOP_KEY : AWAY_TOP_KEY;
      const topKeyPx = gridToPixels(topKey.x, topKey.y, width, height);
      promises.push(
        tweenPlayerTo(scene, bhSprite, topKeyPx, {
          duration: sprintDuration / 2,
          easing: "Sine.easeInOut"
        })
      );

      const rim = bhSprite.team === "home" ? HOME_RIM_COORDS : AWAY_RIM_COORDS;

      if (stopperSprite) {
        const offsetX = bhSprite.team === "home" ? 6 : -6;
        const stopGrid = {
          x: topKey.x + offsetX,
          y: topKey.y + Phaser.Math.Between(-3, 3)
        };
        const stopPx = gridToPixels(stopGrid.x, stopGrid.y, width, height);
        promises.push(
          tweenPlayerTo(scene, stopperSprite, stopPx, {
            duration: sprintDuration / 2,
            easing: "Sine.easeInOut"
          })
        );
      }

      const inPlayDef = new Set((turnData.roles?.defense || []).map(id => String(id)));
      for (const [id, sprite] of Object.entries(playerSprites)) {
        if (sprite === bhSprite || sprite === stopperSprite) continue;
        if (sprite.team === bhSprite.team) {
          const spotGrid = {
            x: Phaser.Math.Between(50, 51),
            y: Phaser.Math.Between(10, 40)
          };
          const spotPx = gridToPixels(spotGrid.x, spotGrid.y, width, height);
          promises.push(
            tweenPlayerTo(scene, sprite, spotPx, {
              duration: sprintDuration / 2,
              easing: "Sine.easeInOut"
            })
          );
        } else {
          if (inPlayDef.has(String(id))) {
            const laneGrid = {
              x: Phaser.Math.Between(
                Math.min(topKey.x, rim.x) + 1,
                Math.max(topKey.x, rim.x) - 1
              ),
              y: Phaser.Math.Between(10, 40)
            };
            const lanePx = gridToPixels(laneGrid.x, laneGrid.y, width, height);
            promises.push(
              tweenPlayerTo(scene, sprite, lanePx, {
                duration: sprintDuration / 2,
                easing: "Sine.easeInOut"
              })
            );
          } else {
            const halfGrid = {
              x: Phaser.Math.Between(50, 51),
              y: Phaser.Math.Between(10, 40)
            };
            const halfPx = gridToPixels(halfGrid.x, halfGrid.y, width, height);
            promises.push(
              tweenPlayerTo(scene, sprite, halfPx, {
                duration: sprintDuration / 2,
                easing: "Sine.easeInOut"
              })
            );
          }
        }
      }
    }

    await Promise.all(promises);
    await fastBreakEndPause(scene);
    if (typeof scene.startNextHalfCourtOffense === "function") {
      scene.startNextHalfCourtOffense();
    }
    // Don't return here - continue to shot animation even in hold-up scenarios
  }

  // Shot animation - runs for both hold-up and non-hold-up scenarios
  const shooterId = turnData.shooterId || turnData.shooter_id || getCurrentOwner(scene);
  const shooterSprite = shooterId != null ? playerSprites[shooterId] : null;
  
  if (debugEnabled)
    animationDebugLog('Fast break shot animation check:', {
      shooterId,
      hasShooterSprite: !!shooterSprite,
      result_type: turnData.result_type,
      hold_up: turnData.hold_up,
      willAnimateShot:
        shooterSprite &&
        (turnData.result_type === "MAKE" || turnData.result_type === "MISS"),
    });
  
  // Only animate shot if there's a shot attempt (result_type indicates a shot was taken)
  if (shooterSprite && (turnData.result_type === "MAKE" || turnData.result_type === "MISS")) {
    attachBallToPlayer(scene, ballSprite, shooterSprite);
    const rimGrid = shooterSprite.team === "home" ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
    const rimPx = gridToPixels(rimGrid.x, rimGrid.y, width, height);
    await tweenPlayerTo(scene, shooterSprite, rimPx, {
      duration: sprintDuration / 2,
      easing: "Sine.easeInOut"
    });
    const arcHeight = animationConfig.fastBreak?.arcHeight ?? 50;
    await tweenBallTo(scene, ballSprite, rimPx, {
      duration: animationConfig.inbound.duration,
      easing: animationConfig.inbound.easing,
      arc: { height: arcHeight }
    });
    if (turnData.result_type === "MAKE") {
      if (debugEnabled)
        animationDebugLog('Fast break made shot detected - starting rim hold');
      const rimHoldMs = animationConfig.fastBreak?.rimHoldMs ?? 2000;
      await new Promise(resolve => scene.time.delayedCall(rimHoldMs, resolve));
      if (debugEnabled)
        animationDebugLog('Fast break rim hold completed - starting end pause');
      await fastBreakEndPause(scene);
      if (debugEnabled)
        animationDebugLog('Fast break end pause completed - proceeding to inbound setup');
      
      // Use backend possession_team_id to determine new offense team for inbound
      const resolveOffenseSide = (scene, teamId) =>
        teamId === scene.simData?.home_team_id ? "home" : "away";
      const newOffenseSide = resolveOffenseSide(scene, turnData.possession_team_id);
      
      if (debugEnabled)
        animationDebugLog('Fast break made shot - inbound setup:', {
          shooterTeam: shooterSprite.team,
          possession_team_id: turnData.possession_team_id,
          newOffenseSide,
          home_team_id: scene.simData?.home_team_id,
        });

      if (debugEnabled)
        animationDebugLog('About to call runInboundSetup for fast break made shot');
      await runInboundSetup({ scene, ballSprite, playerSprites, newOffenseSide });
      if (debugEnabled)
        animationDebugLog('runInboundSetup completed for fast break made shot');
    } else {
      // Handle missed fast break shot with ball bounce
      if (debugEnabled)
        animationDebugLog('Fast break missed shot - rebound progression:', {
          shooterId,
          rebounderId: turnData.rebounderId || turnData.rebounder_player_id,
          rebound_type: turnData.rebound_type,
          possession_team_id: turnData.possession_team_id,
        });
      
      const { bounceFromRim } = await import('./ballManager.js');
      const isHomeTeam = shooterSprite.team === "home";
      const miss = await bounceFromRim(
        scene,
        ballSprite,
        rimGrid,
        isHomeTeam,
        animationConfig.fastBreak.shotMs / 3
      );
      
      // Then handle the rebound
      const { animateRebound } = await import('./ballManager.js');
      await animateRebound({
        scene,
        ballSprite,
        playerSprites,
        animations: [],
        rebounderId: turnData.rebounderId || turnData.rebounder_player_id,
        ballSpot: miss.grid,
        shooterId: shooterId
      });
      
      // Handle defensive rebound setup after missed fast break shot
      // Since we force HCO after missed fast break shots, always use HCO
      const { runDefensiveReboundSetup } = await import('./turnAnimation.js');
      await runDefensiveReboundSetup({
        scene,
        ballSprite,
        playerSprites,
        rebounderId: turnData.rebounderId || turnData.rebounder_player_id,
        nextPlayType: "HCO" // Always HCO after missed fast break shot
      });
      
      await fastBreakEndPause(scene);
    }
  }
}

export default function runFastBreakSequenceWrapper(scene, { playerSprites, ballSprite, turnData }) {
  return runFastBreakSequence({ scene, playerSprites, ballSprite, turnData });
}

export { HOME_RIM_COORDS, AWAY_RIM_COORDS, HOME_TOP_KEY, AWAY_TOP_KEY } from "./courtConstants.js";
