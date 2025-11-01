import * as Phaser from "https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.esm.js";
import { gridToPixels } from "../utils/gridToPixels.js";
import { attachBallToPlayer } from "./BallControllerAdapter.js";
import { tweenBallTo, tweenPlayerTo, runPass } from "./ballTween.js";
import animationConfig from "./animation_config.js";
import { HOME_RIM_COORDS, AWAY_RIM_COORDS, HOME_TOP_KEY, AWAY_TOP_KEY } from "./courtConstants.js";
import { States, safeTransition } from "../state/gameStateMachine.js";
import { getCurrentOwner } from "../ball/ballController.js";
import { runInboundSetup } from "./turnAnimation.js";
import { animationDebugLog, isAnimationDebugEnabled } from "../utils/debugFlags.js";
import { appendToTextScroll } from "../utils/textScroll.js";

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
  if (!scene || !turnData || scene.skipToEnd) return;
  if (!scene.ballSprite) scene.ballSprite = ballSprite;
  
  const width = scene.game.config.width;
  const height = scene.game.config.height;
  const debugEnabled = isAnimationDebugEnabled();
  
  // Stop any existing timeline/tweens
  if (scene.__activeTimeline) {
    scene.__activeTimeline.stop();
    scene.__activeTimeline = null;
  }
  
  // Transition to FastBreakOutlet or FastBreak state
  if (turnData.roles?.outlet_passer) {
    safeTransition(scene.stateMachine, States.FastBreakOutlet);
  } else {
    safeTransition(scene.stateMachine, States.FastBreak);
  }
  scene.events?.emit("fb:start");
  
  // ============================================================================
  // PHASE 1: OUTLET PASS (if applicable)
  // ============================================================================
  if (turnData.roles?.outlet_passer && turnData.roles?.outlet_receiver) {
    await animateOutletPhase(scene, turnData, playerSprites, ballSprite, width, height);
    
    // Transition to FastBreak state after outlet
    safeTransition(scene.stateMachine, States.FastBreak);
  }
  
  if (scene.skipToEnd) return;
  
  // ============================================================================
  // PHASE 2: FAST BREAK RESOLUTION
  // ============================================================================
  const result = turnData.result_type;
  const holdUp = turnData.hold_up;
  
  if (result === "MAKE" || result === "MISS") {
    // Shot attempt scenario
    await animateFastBreakShot(scene, turnData, playerSprites, ballSprite, width, height);
  } else {
    // Defensive stop, foul, turnover, or steal - all use same defensive stop positioning
    await animateDefensiveStop(scene, turnData, playerSprites, ballSprite, width, height);
  }
  
  if (scene.skipToEnd) return;
  
  // ============================================================================
  // PHASE 3: CLEANUP & STATE TRANSITIONS
  // ============================================================================
  scene.events?.emit("fb:end");
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
  
  // Move outlet receiver to outlet spot (keep existing logic)
  const receiverCurrentGrid = {
    x: (receiverSprite.x / width) * 100,
    y: 50 - (receiverSprite.y / height) * 50
  };
  const direction = targetBasket.x > receiverCurrentGrid.x ? 1 : -1;
  const outletTarget = {
    x: Phaser.Math.Clamp(
      receiverCurrentGrid.x + direction * Phaser.Math.Between(15, 20),
      4,
      97
    ),
    y: Phaser.Math.Clamp(
      receiverCurrentGrid.y + Phaser.Math.Between(-6, 6),
      1,
      49
    )
  };
  const outletPx = gridToPixels(outletTarget.x, outletTarget.y, width, height);
  
  const promises = [];
  
  // Move outlet receiver
  promises.push(
    tweenPlayerTo(scene, receiverSprite, outletPx, {
      duration: 500,
      easing: "Sine.easeInOut"
    })
  );
  
  // SIMULTANEOUSLY animate defenders chasing
  const defendersList = turnData.roles?.defense || [];
  console.log("🏀 FB Outlet - Defenders list:", defendersList);
  const defendersSet = new Set(defendersList.map(d => d.player_id || d));
  console.log("🏀 FB Outlet - Defenders Set:", Array.from(defendersSet));
  
  let defenderCount = 0;
  for (const [id, sprite] of Object.entries(playerSprites)) {
    if (defendersSet.has(id)) {
      defenderCount++;
      // Defenders chase: random Y (15-35), X toward basket (50 to basket-15)
      const defenderTarget = {
        x: isHomeOffense 
          ? Phaser.Math.Between(50, 65)  // Home offense: X 50-65
          : Phaser.Math.Between(35, 50), // Away offense: X 35-50
        y: Phaser.Math.Between(15, 35)
      };
      const defenderPx = gridToPixels(defenderTarget.x, defenderTarget.y, width, height);
      promises.push(
        tweenPlayerTo(scene, sprite, defenderPx, {
          duration: 500,
          easing: "Sine.easeInOut"
        })
      );
    }
    // All other players hold position (no animation)
  }
  
  console.log(`🏀 FB Outlet - Animating ${defenderCount} defenders with receiver. Total promises: ${promises.length}`);
  
  // Wait for ALL movements (receiver + defenders) to complete simultaneously
  await Promise.all(promises);
  
  // THEN outlet pass
  await runPass(scene, {
    fromId: passerId,
    toId: receiverId,
    duration: 500,
    easing: "Sine.easeInOut"
  });
}

/**
 * Phase 2a: Fast Break Shot Attempt
 * - Ball handler moves near rim
 * - Defender follows
 * - All others move to standard positions
 */
async function animateFastBreakShot(scene, turnData, playerSprites, ballSprite, width, height) {
  const shooterId = turnData.roles?.shooter?.player_id || turnData.shooter_id || getCurrentOwner(scene);
  const shooterSprite = playerSprites[shooterId];
  
  if (!shooterSprite) return;
  
  const isHomeOffense = shooterSprite.team === "home";
  const basket = isHomeOffense ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
  
  // Ball handler moves to shot spot near rim
  const shotSpot = {
    x: isHomeOffense
      ? basket.x - Phaser.Math.Between(2, 6)  // Home: basket - 2-6
      : basket.x + Phaser.Math.Between(2, 6), // Away: basket + 2-6
    y: basket.y + Phaser.Math.Between(-6, 6)  // ±6 from basket Y
  };
  
  // Clamp to bounds
  shotSpot.x = Phaser.Math.Clamp(shotSpot.x, 4, 97);
  shotSpot.y = Phaser.Math.Clamp(shotSpot.y, 1, 49);
  
  const shotPx = gridToPixels(shotSpot.x, shotSpot.y, width, height);
  
  const promises = [];
  
  // Move shooter
  attachBallToPlayer(scene, ballSprite, shooterSprite);
  promises.push(
    tweenPlayerTo(scene, shooterSprite, shotPx, {
      duration: 600,
      easing: "Sine.easeInOut"
    })
  );
  
  // Move primary defender
  // Check top-level defender field first (from shot_manager), then roles.defense array
  // Use defenderId directly if available, otherwise try to extract from defender object/string
  let defenderId = turnData.defenderId;
  
  if (!defenderId) {
    let defenderData = turnData.defender || (turnData.roles?.defense && turnData.roles.defense[0]);
    if (defenderData) {
      if (typeof defenderData === 'string') {
        defenderId = defenderData;
      } else if (defenderData.player_id) {
        defenderId = defenderData.player_id;
      } else if (defenderData.playerId) {
        defenderId = defenderData.playerId;
      }
    }
  }
  
  const defenderSprite = defenderId ? playerSprites[defenderId] : null;
  
  console.log("🏀 FB Shot - Defender lookup:", {
    defenderId,
    hasSprite: !!defenderSprite,
    turnDataDefenderId: turnData.defenderId,
    turnDataDefender: turnData.defender
  });
  
  if (defenderSprite) {
    // Defender position: 3 spots closer to basket, ±2 Y from shooter
    const defenderSpot = {
      x: isHomeOffense
        ? shotSpot.x + 3  // Home attacking right (X=91): defender is +3 (toward basket)
        : shotSpot.x - 3, // Away attacking left (X=9): defender is -3 (toward basket)
      y: shotSpot.y + Phaser.Math.Between(-2, 2)  // ±2 Y range from shooter
    };
    defenderSpot.x = Phaser.Math.Clamp(defenderSpot.x, 4, 97);
    defenderSpot.y = Phaser.Math.Clamp(defenderSpot.y, 1, 49);
    
    console.log("🏀 FB Shot - Defender position:", {
      defenderId,
      shotSpot,
      defenderSpot,
      isHomeOffense
    });
    
    const defenderPx = gridToPixels(defenderSpot.x, defenderSpot.y, width, height);
    promises.push(
      tweenPlayerTo(scene, defenderSprite, defenderPx, {
        duration: 600,
        easing: "Sine.easeInOut"
      })
    );
  } else {
    console.warn("🏀 FB Shot - No defender sprite found!", {
      defenderId,
      turnDataDefenderId: turnData.defenderId,
      turnDataDefender: turnData.defender,
      availableSprites: Object.keys(playerSprites)
    });
  }
  
  // Move all other players to standard positions (same as defensive stop)
  await moveOtherPlayersToStandardPositions(
    scene,
    playerSprites,
    shooterId,
    defenderId,
    turnData,
    width,
    height,
    promises
  );
  
  await Promise.all(promises);
  
  // Shoot the ball
  safeTransition(scene.stateMachine, States.ShotAttempt);
  
  // Adjust rim position for made shots (1 grid unit closer to shooter)
  const adjustedBasket = { ...basket };
  if (turnData.result_type === "MAKE") {
    adjustedBasket.x = isHomeOffense ? basket.x - 1 : basket.x + 1;
  }
  
  const rimPx = gridToPixels(adjustedBasket.x, adjustedBasket.y, width, height);
  await tweenBallTo(scene, ballSprite, rimPx, {
    duration: 400,
    easing: "Sine.easeInOut",
    arc: { height: 50 }
  });
  
  // Handle outcome
  if (turnData.result_type === "MAKE") {
    appendToTextScroll("Good!");
    await new Promise(resolve => scene.time.delayedCall(1000, resolve));
    
    // Inbound setup
    const newOffenseSide = isHomeOffense ? "away" : "home";
    const skipRetreat = turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT";
    const pressureType = skipRetreat ? turnData.next_defensive_setup : null;
    if (skipRetreat) {
      console.log(`${turnData.next_defensive_setup} detected after fast break - skipping defensive retreat`);
    }
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
  } else {
    // Miss - handle rebound
    appendToTextScroll("Missed!");
    safeTransition(scene.stateMachine, States.Rebound);
    
    const { bounceFromRim, animateRebound } = await import('./ballManager.js');
    const miss = await bounceFromRim(scene, ballSprite, basket, isHomeOffense, 300);
    
    await animateRebound({
      scene,
      ballSprite,
      playerSprites,
      animations: [],
      rebounderId: turnData.rebounderId || turnData.rebounder_player_id,
      ballSpot: miss.grid,
      shooterId
    });
    
    // Defensive rebound setup if needed
    if (turnData.rebound_type === "DREB") {
      const { runDefensiveReboundSetup } = await import('./turnAnimation.js');
      await runDefensiveReboundSetup({
        scene,
        ballSprite,
        playerSprites,
        rebounderId: turnData.rebounderId || turnData.rebounder_player_id,
        nextPlayType: "HCO"
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
  const ballHandlerData = turnData.roles?.ball_handler;
  const ballHandlerId = ballHandlerData?.player_id || ballHandlerData || getCurrentOwner(scene);
  const ballHandlerSprite = playerSprites[ballHandlerId];
  
  if (!ballHandlerSprite) return;
  
  const isHomeOffense = ballHandlerSprite.team === "home";
  const topKey = isHomeOffense ? HOME_TOP_KEY : AWAY_TOP_KEY;
  const basket = isHomeOffense ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
  
  const promises = [];
  
  // Move ball handler to top of key
  attachBallToPlayer(scene, ballSprite, ballHandlerSprite);
  const topKeyPx = gridToPixels(topKey.x, topKey.y, width, height);
  promises.push(
    tweenPlayerTo(scene, ballHandlerSprite, topKeyPx, {
      duration: 600,
      easing: "Sine.easeInOut"
    })
  );
  
  // Move stopper (if exists) - same Y as ball handler, 3 X closer to basket
  const stopperId = turnData.stopper_id;
  const stopperSprite = stopperId ? playerSprites[stopperId] : null;
  
  if (stopperSprite) {
    const stopperSpot = {
      x: isHomeOffense
        ? topKey.x - 3  // 3 closer to basket
        : topKey.x + 3,
      y: topKey.y  // Same Y as ball handler
    };
    stopperSpot.x = Phaser.Math.Clamp(stopperSpot.x, 4, 97);
    
    const stopperPx = gridToPixels(stopperSpot.x, stopperSpot.y, width, height);
    promises.push(
      tweenPlayerTo(scene, stopperSprite, stopperPx, {
        duration: 600,
        easing: "Sine.easeInOut"
      })
    );
  }
  
  // Move other defenders in list - same Y, 15 X closer to basket from their current position
  const defendersList = turnData.roles?.defense || [];
  const defendersSet = new Set(defendersList.map(d => d.player_id || d));
  
  for (const [id, sprite] of Object.entries(playerSprites)) {
    if (id === ballHandlerId || id === stopperId) continue;
    
    if (defendersSet.has(id)) {
      // Other defenders: same Y, 15 X closer to basket
      const currentGrid = {
        x: (sprite.x / width) * 100,
        y: 50 - (sprite.y / height) * 50
      };
      
      const defenderTarget = {
        x: isHomeOffense
          ? currentGrid.x - 15  // 15 closer to home basket
          : currentGrid.x + 15, // 15 closer to away basket
        y: currentGrid.y  // Same Y
      };
      defenderTarget.x = Phaser.Math.Clamp(defenderTarget.x, 4, 97);
      
      const defenderPx = gridToPixels(defenderTarget.x, defenderTarget.y, width, height);
      promises.push(
        tweenPlayerTo(scene, sprite, defenderPx, {
          duration: 600,
          easing: "Sine.easeInOut"
        })
      );
    }
  }
  
  // Move all other players (not involved) to half court
  await moveOtherPlayersToStandardPositions(
    scene,
    playerSprites,
    ballHandlerId,
    stopperId,
    turnData,
    width,
    height,
    promises
  );
  
  await Promise.all(promises);
  
  // Display outcome text
  if (turnData.hold_up) {
    appendToTextScroll("Defensive stop!");
  }
  
  // Transition to HalfCourt for next possession
  safeTransition(scene.stateMachine, States.HalfCourt);
}

/**
 * Helper: Move all non-involved players to their positions
 * - Defenders in list: chase toward basket (X: 50 to basket-15, Y: 15-35)
 * - Other players: move to half court (X: 45-55, Y: 15-35)
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
  const defendersList = turnData.roles?.defense || [];
  const defendersSet = new Set(defendersList.map(d => d.player_id || d));
  
  // Determine which basket is being attacked
  const shooterSprite = playerSprites[ballHandlerId];
  const isHomeOffense = shooterSprite?.team === "home";
  const basket = isHomeOffense ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
  
  for (const [id, sprite] of Object.entries(playerSprites)) {
    // Skip shooter and primary defender (already animated)
    if (id === ballHandlerId || id === primaryDefenderId) {
      continue;
    }
    
    let targetSpot;
    
    // Animate defenders in the list to chase positions
    if (defendersSet.has(id)) {
      // Defenders chase: X between 50 and 15 spots closer to basket
      const minX = isHomeOffense ? 50 : basket.x + 2;
      const maxX = isHomeOffense ? basket.x - 2 : 50;
      
      targetSpot = {
        x: Phaser.Math.Between(Math.min(minX, maxX), Math.max(minX, maxX)),
        y: Phaser.Math.Between(15, 35)
      };
    } else {
      // All other players: move to half court
      targetSpot = {
        x: Phaser.Math.Between(45, 55),
        y: Phaser.Math.Between(15, 35)
      };
    }
    
    const targetPx = gridToPixels(targetSpot.x, targetSpot.y, width, height);
    promises.push(
      tweenPlayerTo(scene, sprite, targetPx, {
        duration: 600,
        easing: "Sine.easeInOut"
      })
    );
  }
}

// Export for backwards compatibility
export default function runFastBreakSequenceWrapper(scene, { playerSprites, ballSprite, turnData }) {
  return runFastBreakSequence({ scene, playerSprites, ballSprite, turnData });
}

export { HOME_RIM_COORDS, AWAY_RIM_COORDS, HOME_TOP_KEY, AWAY_TOP_KEY } from "./courtConstants.js";
