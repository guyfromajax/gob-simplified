import { gridToPixels } from "../utils/gridToPixels.js";
import animationConfig, {
  FT_BETWEEN_SHOTS_DELAY_MS,
} from "./animation_config.js";
import { HOME_RIM_COORDS, AWAY_RIM_COORDS } from "./courtConstants.js";
import { bounceFromRim } from "./ballManager.js";
import { States, safeTransition, createTransitionGuard } from "../state/gameStateMachine.js";
import { getCurrentOwner, getPendingOwner } from "../ball/ballController.js";
import { DebugFlags, animationDebugLog } from "../utils/debugFlags.js";
import { getPlayerDuration } from "./turnAnimation.js";

function wait(scene, ms) {
  if (!ms) return Promise.resolve();
  return scene.time?.delayedCall
    ? new Promise((res) => scene.time.delayedCall(ms, res))
    : new Promise((res) => setTimeout(res, ms));
}

export async function runFreeThrowSequence(
  scene,
  {
    playerSprites,
    ballSprite,
    turnData,
    onUpdate,
    helpers = {},
    ftContext = {},
  }
) {
  const attach =
    helpers.attachBallToPlayer ||
    (await import("./ballTween.js")).attachBallToPlayer;
  const detach =
    helpers.detachBall || (await import("./ballTween.js")).detachBall;
  // ✅ STEP 3 MIGRATION: Import new ball animation functions
  const { animateShotToRim, animateBallToPosition } = await import("./ballAnimationSimple.js");
  const inboundSetup =
    helpers.runInboundSetup || (await import("./turnAnimation.js")).runInboundSetup;
  const rebound =
    helpers.animateRebound || (await import("./ballManager.js")).animateRebound;

  // Determine if this is the final free throw from turnData
  // If free_throws_remaining is provided, use it (turn-by-turn mode)
  // Otherwise fall back to ftContext (old batch mode)
  let isFinalTurn;
  let bonusType;
  if (turnData.free_throws_remaining !== undefined) {
    // Turn-by-turn mode: Check if no more FTs remain AFTER this shot
    // free_throws_remaining is AFTER the shot, so if it's 0, this was the final FT
    isFinalTurn = turnData.free_throws_remaining === 0;
    bonusType = turnData.one_and_one ? 'ONE_AND_ONE' : null;
  } else {
    // Batch mode: Use ftContext
    const { ftIndex = 1, ftTotal = 1 } = ftContext || {};
    isFinalTurn = ftIndex >= ftTotal;
    bonusType = ftContext?.bonusType;
  }

  const releaseGuard =
    !isFinalTurn && scene.stateMachine
      ? createTransitionGuard(scene.stateMachine, [States.Inbound, 'DeadBall'])
      : null;

  if (!scene || !playerSprites || !ballSprite || !turnData) {
    releaseGuard?.();
    return;
  }

  if (!scene.stateMachine?.is(States.FreeThrow)) {
    safeTransition(
      scene.stateMachine,
      States.FreeThrow,
      {
        stepIndex: 0,
        currentOwnerId: getCurrentOwner(scene),
        pendingOwnerId: getPendingOwner(scene),
      },
      ["stepIndex"]
    );
  }
  if (scene.tweens) {
    for (const sprite of Object.values(playerSprites)) {
      scene.tweens.killTweensOf(sprite);
    }
    scene.tweens.killTweensOf(ballSprite);
  }

  const animations = turnData.animations || [];
  const playerAnims = animations.filter((a) => a.playerId !== "ball");
  const ballAnim = animations.find((a) => a.playerId === "ball");
  const width = scene.game.config.width;
  const height = scene.game.config.height;

  if (!turnData.no_lane) {
    const promises = [];
    for (const anim of playerAnims) {
      const sprite = playerSprites[anim.playerId];
      const end = anim.movement?.[1]?.coords;
      if (!sprite || !end) continue;
      const px = gridToPixels(end.x, end.y, width, height);
      // Use distance-based duration for consistent speed
      const duration = getPlayerDuration(sprite, px.x, px.y);
      promises.push(
        new Promise((resolve) => {
          scene.tweens.add({
            targets: sprite,
            x: px.x,
            y: px.y,
            duration,
            ease: "Linear",
            onComplete: resolve,
            onStop: resolve,
          });
        })
      );
    }
    await Promise.all(promises);
  } else {
    const shooterAnim = playerAnims.find(
      (a) => a.playerId === turnData.shooter_id
    );
    const sprite = playerSprites[turnData.shooter_id];
    const end = shooterAnim?.movement?.[1]?.coords;
    if (sprite && end) {
      const px = gridToPixels(end.x, end.y, width, height);
      // Use distance-based duration for consistent speed
      const duration = getPlayerDuration(sprite, px.x, px.y);
      await new Promise((resolve) => {
        scene.tweens.add({
          targets: sprite,
          x: px.x,
          y: px.y,
          duration,
          ease: "Linear",
          onComplete: resolve,
          onStop: resolve,
        });
      });
    }
  }

  const shooterSprite = playerSprites[turnData.shooter_id];
  if (shooterSprite) attach(scene, ballSprite, shooterSprite);
  scene.events?.emit("ft:lineupComplete", {});

  const attempts = turnData.attempts || [];
  const moves = ballAnim?.movement || [];
  let moveIndex = 1;

  for (let i = 0; i < attempts.length; i++) {
    const result = attempts[i];
    scene.events?.emit("ft:attempt", { attempt: i + 1, total: attempts.length });
    await wait(scene, animationConfig.freeThrow.shooterPrepMs);
    detach(scene, ballSprite);

    const shotStep = moves[moveIndex];
    moveIndex++;
    const rimGrid =
      shotStep?.coords ||
      (turnData.offense_team_id === scene.simData?.home_team_id
        ? HOME_RIM_COORDS
        : AWAY_RIM_COORDS);
    const rimPx = gridToPixels(rimGrid.x, rimGrid.y, width, height);
    scene.events?.emit("ft:shotStart");
    const shotTweenOptions = {
      duration: animationConfig.freeThrow.shotMs,
      easing: "Sine.easeInOut",
    };

    // ✅ STEP 3 MIGRATION: Use new animateShotToRim() instead of tween()
    // animateShotToRim() handles ball detachment and shot animation
    const arcOption = animationConfig.freeThrow.useArc
      ? { height: animationConfig.freeThrow.arcHeight }
      : { height: animationConfig.freeThrow.arcHeight, enabled: false };

    await animateShotToRim(scene, rimPx, {
      duration: animationConfig.freeThrow.shotMs,
      easing: "Sine.easeInOut",
      arc: arcOption
    });

    scene.events?.emit(result === "MAKE" ? "ft:make" : "ft:miss");
    
    // Announce made free throw
    if (result === "MAKE") {
      const { showAnnouncement } = await import('../utils/announcements.js');
      const shooterId = turnData.shooter_id;
      const shooterSprite = playerSprites[shooterId];
      const shooterTeamId = turnData.offense_team_id;
      const isHomeTeam = shooterTeamId === scene.simData?.home_team_id;
      const teamStyle = isHomeTeam ? 'home' : 'away';
      
      // Handle both new nested structure (object) and old flat structure (string)
      const homeTeamField = scene.simData?.home_team;
      const awayTeamField = scene.simData?.away_team;
      const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
      const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
      const shooterTeamName = isHomeTeam ? homeTeamName : awayTeamName;
      
      const playerData = {
        playerId: shooterId,
        photo: shooterSprite?.photo || null,
        teamName: shooterTeamName
      };
      
      showAnnouncement("It's Good!", teamStyle, playerData);
    }
    
    await wait(scene, animationConfig.freeThrow.rimHoldMs);
    scene.events?.emit("ft:rimHoldEnd");

    const isLastAttempt = i === attempts.length - 1;
    const isFinalFT = isLastAttempt && isFinalTurn;
    const earlyExit = bonusType === 'ONE_AND_ONE' && result === 'MISS';
    let nextStateResolved = States.FreeThrow;
    if (result === "MAKE") {
      if (onUpdate) {
        try {
          onUpdate({ ...turnData, attempt: i, result });
        } catch (err) {
          console.error("Scoreboard update failed:", err);
        }
      }
      if (isFinalFT) {
        const possessionChanged =
          turnData.possession_flips ??
          (turnData.possession_team_id != null &&
            turnData.offense_team_id != null &&
            turnData.possession_team_id !== turnData.offense_team_id);
        if (possessionChanged) {
          safeTransition(
            scene.stateMachine,
            States.Inbound,
            {
              shotResult: result,
              currentOwnerId: getCurrentOwner(scene),
              pendingOwnerId: getPendingOwner(scene),
            },
            ["shotResult"]
          );
          const resolveOffenseSide =
            helpers.getOffenseSide ||
            ((scene, teamId) =>
              teamId === scene.simData?.home_team_id ? "home" : "away");
          
          // Try using possession_team_id directly (this should be the correct team after possession flip)
          const newOffenseSide = resolveOffenseSide(scene, turnData.possession_team_id);
          
          // Also calculate what we think it should be for comparison
          const expectedNewOffenseTeamId = possessionChanged 
            ? (turnData.offense_team_id === scene.simData?.home_team_id 
                ? scene.simData?.away_team_id 
                : scene.simData?.home_team_id)
            : turnData.offense_team_id;
          const expectedNewOffenseSide = resolveOffenseSide(scene, expectedNewOffenseTeamId);
          
          animationDebugLog('Final free throw made - inbound setup:', {
            possession_flips: possessionChanged,
            original_offense_team_id: turnData.offense_team_id,
            possession_team_id: turnData.possession_team_id,
            newOffenseSide,
            expectedNewOffenseTeamId,
            expectedNewOffenseSide,
            home_team_id: scene.simData?.home_team_id,
            away_team_id: scene.simData?.away_team_id,
            shooter_team_id: turnData.shooter_team_id,
            all_turnData_keys: Object.keys(turnData),
            next_defensive_setup: turnData.next_defensive_setup
          });
          
          // Let's also check what the current scene offense team is
          animationDebugLog('Scene offense team info:', {
            scene_offenseTeamId: scene.offenseTeamId,
            scene_simData: scene.simData
          });
          
          // Check if FCP/HCT is coming next - if so, skip retreat animation
          const skipRetreat = turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT";
          const pressureType = skipRetreat ? turnData.next_defensive_setup : null;
          if (skipRetreat) {
            console.log(`${turnData.next_defensive_setup} detected after FT - skipping defensive retreat to midcourt`);
          }
          
          await inboundSetup({
            scene,
            ballSprite,
            playerSprites,
            newOffenseSide,
            homeTeamId: scene.simData?.home_team_id,
            awayTeamId: scene.simData?.away_team_id,
            skipRetreat,
            pressureType,
          });
          scene.events?.emit?.("possessionChange", {
            offenseTeamId: turnData.possession_team_id,
          });
          nextStateResolved = States.Inbound;
        } else {
          safeTransition(
            scene.stateMachine,
            States.HalfCourt,
            {
              shotResult: result,
              currentOwnerId: getCurrentOwner(scene),
              pendingOwnerId: getPendingOwner(scene),
            },
            ["shotResult"]
          );
          nextStateResolved = States.HalfCourt;
        }
      } else {
        if (scene.tweens) {
          for (const sprite of Object.values(playerSprites))
            scene.tweens.killTweensOf(sprite);
          scene.tweens.killTweensOf(ballSprite);
        }
        await wait(scene, FT_BETWEEN_SHOTS_DELAY_MS);
        const resetStep = moves[moveIndex];
        moveIndex++;
        const resetGrid = resetStep?.coords || rimGrid;
        const spotPx = gridToPixels(
          resetGrid.x,
          resetGrid.y,
          width,
          height
        );
        // ✅ STEP 3 MIGRATION: Use new animateBallToPosition() instead of tween()
        // This is just moving ball back to shooter between free throws (not a shot)
        await animateBallToPosition(scene, spotPx, {
          duration: animationConfig.freeThrow.shotMs,
          easing: "Sine.easeInOut"
        });
        if (shooterSprite) attach(scene, ballSprite, shooterSprite);
      }
    } else {
      if (isFinalFT || earlyExit) {
        safeTransition(
          scene.stateMachine,
          States.Rebound,
          {
            shotResult: result,
            currentOwnerId: getCurrentOwner(scene),
            pendingOwnerId: getPendingOwner(scene),
          },
          ["shotResult"]
        );
        const miss = await bounceFromRim(
          scene,
          ballSprite,
          rimGrid,
          turnData.offense_team_id === scene.simData?.home_team_id,
          animationConfig.freeThrow.shotMs / 3
        );
        await rebound({
          scene,
          ballSprite,
          playerSprites,
          animations: [],
          rebounderId: turnData.rebounderId || turnData.rebounder_player_id,
          ballSpot: miss.grid,
          shooterId: turnData.shooter_id,
        });
        
        // Add defensive rebound setup for free throws (same as regular shots)
        const reboundData = {
          rebounderId: turnData.rebounderId || turnData.rebounder_player_id,
          rebound_type: turnData.rebound_type,
          next_play_type: turnData.next_play_type
        };
        
        animationDebugLog('Free throw missed - defensive rebound setup:', {
          rebounderId: reboundData.rebounderId,
          rebound_type: reboundData.rebound_type,
          next_play_type: reboundData.next_play_type,
          fast_break: turnData.fast_break
        });
        
        // Check if this is a defensive rebound and handle accordingly
        const isDreb = reboundData.rebound_type === "DREB";
        if (isDreb) {
          if (turnData.fast_break) {
            // Handle fast break after defensive rebound on free throw
            const { runFastBreakSequence } = await import('./fastBreak.js');
            await runFastBreakSequence({
              scene,
              playerSprites,
              ballSprite,
              turnData: {
                ...turnData,
                result_type: "FAST_BREAK",
                roles: turnData.roles || {}
              }
            });
          } else {
            // Handle HCO after defensive rebound on free throw
            const { runDefensiveReboundSetup } = await import('./turnAnimation.js');
            await runDefensiveReboundSetup({
              scene,
              ballSprite,
              playerSprites,
              rebounderId: reboundData.rebounderId,
              nextPlayType: reboundData.next_play_type || "HCO"
            });
          }
        }
        
        nextStateResolved = States.Rebound;
      } else {
        if (scene.tweens) {
          for (const sprite of Object.values(playerSprites))
            scene.tweens.killTweensOf(sprite);
          scene.tweens.killTweensOf(ballSprite);
        }
        await wait(scene, FT_BETWEEN_SHOTS_DELAY_MS);
        const resetStep = moves[moveIndex];
        moveIndex++;
        const resetGrid = resetStep?.coords || rimGrid;
        const spotPx = gridToPixels(
          resetGrid.x,
          resetGrid.y,
          width,
          height
        );
        // ✅ STEP 3 MIGRATION: Use new animateBallToPosition() instead of tween()
        // This is just moving ball back to shooter between free throws (not a shot)
        await animateBallToPosition(scene, spotPx, {
          duration: animationConfig.freeThrow.shotMs,
          easing: "Sine.easeInOut"
        });
        if (shooterSprite) attach(scene, ballSprite, shooterSprite);
      }
    }
    if (DebugFlags?.FSM) {
      animationDebugLog({
        state: States.FreeThrow,
        ftIndex,
        ftTotal,
        bonusType,
        shotResult: result,
        isFinalFT,
        nextStateResolved,
      }); // remove when stable
    }
    scene.events?.emit("ft:repeatOrExit");
  }

  releaseGuard?.();

  if (isFinalTurn && scene.stateMachine?.is(States.FreeThrow))
    safeTransition(scene.stateMachine, States.HalfCourt, {
      currentOwnerId: getCurrentOwner(scene),
      pendingOwnerId: getPendingOwner(scene),
    });
  scene.events?.emit("ft:end");
}

export default runFreeThrowSequence;

