import * as Phaser from "https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.esm.js";
import { gridToPixels } from "../utils/gridToPixels.js";
import { attachBallToPlayer } from "./BallControllerAdapter.js";
import { tweenBallTo, tweenPlayerTo, runPass } from "./ballTween.js";
import animationConfig from "./animation_config.js";
import { HOME_RIM_COORDS, AWAY_RIM_COORDS, HOME_TOP_KEY, AWAY_TOP_KEY } from "./courtConstants.js";
import { States, safeTransition } from "../state/gameStateMachine.js";
import { getCurrentOwner } from "../ball/ballController.js";
import { runInboundSetup, getPlayerDuration } from "./turnAnimation.js";
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
  
  const currentState = scene.stateMachine?.state;
  
  // ✅ Check current state before transitioning - avoid invalid transitions
  // For defensive stops after HCO, we're already in HalfCourt, so transition to FastBreak directly
  // For Fast Break from DREB, we should be in Rebound/OutletSetup, so can transition to FastBreakOutlet
  if (turnData.roles?.outlet_passer && currentState !== States.FastBreak && currentState !== States.FastBreakOutlet) {
    // Only transition to FastBreakOutlet if we have outlet pass and we're not already in Fast Break state
    // Check if we can transition (must be coming from Rebound or OutletSetup)
    if (currentState === States.Rebound || currentState === States.OutletSetup) {
      safeTransition(scene.stateMachine, States.FastBreakOutlet);
    } else {
      // Coming from HalfCourt (defensive stop scenario) - go directly to FastBreak
      safeTransition(scene.stateMachine, States.FastBreak);
    }
  } else if (currentState !== States.FastBreak && currentState !== States.FastBreakOutlet) {
    // No outlet pass or already in Fast Break state - just ensure we're in FastBreak
    safeTransition(scene.stateMachine, States.FastBreak);
  }
  
  scene.events?.emit("fb:start");
  
  // ============================================================================
  // PHASE 1: OUTLET PASS (if applicable)
  // ============================================================================
  if (turnData.roles?.outlet_passer && turnData.roles?.outlet_receiver) {
    await animateOutletPhase(scene, turnData, playerSprites, ballSprite, width, height);
    
    // Transition to FastBreak state after outlet (only if not already there)
    if (scene.stateMachine?.state !== States.FastBreak) {
      safeTransition(scene.stateMachine, States.FastBreak);
    }
  }
  
  if (scene.skipToEnd) return;
  
  // ============================================================================
  // PHASE 2: FAST BREAK RESOLUTION
  // ============================================================================
  const result = turnData.result_type;
  
  console.log("🏀 Fast Break - Phase 2:", {
    result_type: result,
    current_state: scene.stateMachine?.state,
    next_play_type: turnData.next_play_type,
    has_animations: !!turnData.animations?.length
  });
  
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
  const newOffenseTeam = isHomeOffense ? "home" : "away";
  
  // Find the original MISS turn to get offense_getback list
  let missTurn = null;
  const currentIndex = scene.currentTurn || 0;
  const previousTurn = scene.simData?.turns?.[currentIndex - 1];
  const currentTurn = scene.simData?.turns?.[currentIndex];
  
  if (previousTurn?.result_type === "MISS") {
    missTurn = previousTurn;
  } else if (currentTurn?.result_type === "MISS") {
    missTurn = currentTurn;
  }
  
  const getBackList = missTurn?.offense_getback || [];
  
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
  const defendersSet = new Set(defendersList.map(d => d.player_id || d));
  
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
  }
  
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
  
  // Wait for ALL movements (receiver + defenders + advancing players) to complete simultaneously
  await Promise.all(promises);
  
  // THEN outlet pass (happens after all players are in position, but visually flows with the movement)
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
  // Use distance-based duration for consistent speed
  const shooterDuration = getPlayerDuration(shooterSprite, shotPx.x, shotPx.y);
  promises.push(
    tweenPlayerTo(scene, shooterSprite, shotPx, {
      duration: shooterDuration,
      easing: "Linear" // Match HCO step movements
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
  
  // console.log("🏀 FB Shot - Defender lookup:", {
  //   defenderId,
  //   hasSprite: !!defenderSprite,
  //   turnDataDefenderId: turnData.defenderId,
  //   turnDataDefender: turnData.defender
  // });
  
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
    
    // console.log("🏀 FB Shot - Defender position:", {
    //   defenderId,
    //   shotSpot,
    //   defenderSpot,
    //   isHomeOffense
    // });
    
    const defenderPx = gridToPixels(defenderSpot.x, defenderSpot.y, width, height);
    // Use distance-based duration for consistent speed
    const defenderDuration = getPlayerDuration(defenderSprite, defenderPx.x, defenderPx.y);
    promises.push(
      tweenPlayerTo(scene, defenderSprite, defenderPx, {
        duration: defenderDuration,
        easing: "Linear" // Match HCO step movements
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
    // Show announcement with shooter headshot
    const { showAnnouncement } = await import('../utils/announcements.js');
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
      teamName: shooterTeamName
    } : null;
    
    const teamStyle = isHomeOffense ? 'home' : 'away';
    showAnnouncement("It's Good!", teamStyle, shooterPlayerData);
    
    await new Promise(resolve => scene.time.delayedCall(1000, resolve));
    
    // Inbound setup
    const newOffenseSide = isHomeOffense ? "away" : "home";
    const skipRetreat = turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT";
    const pressureType = skipRetreat ? turnData.next_defensive_setup : null;
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
    
    // Find the original MISS turn that led to this Fast Break
    // The current turnData is the FAST_BREAK turn, but we need the original MISS turn
    // to get the offense_getback list
    let missTurn = null;
    const currentIndex = scene.currentTurn || 0;
    const previousTurn = scene.simData?.turns?.[currentIndex - 1];
    const currentTurn = scene.simData?.turns?.[currentIndex];
    
    // Check previous turn first (the MISS that led to this Fast Break)
    if (previousTurn?.result_type === "MISS") {
      missTurn = previousTurn;
    } else if (currentTurn?.result_type === "MISS") {
      missTurn = currentTurn;
    }
    
    
    await animateRebound({
      scene,
      ballSprite,
      playerSprites,
      animations: [],
      rebounderId: turnData.rebounderId || turnData.rebounder_player_id,
      ballSpot: miss.grid,
      shooterId,
      turnData: missTurn // Pass the original MISS turn so get-back players can be excluded
    });
    
    // Defensive rebound setup if needed
    if (turnData.rebound_type === "DREB") {
      const { runDefensiveReboundSetup } = await import('./turnAnimation.js');
      await runDefensiveReboundSetup({
        scene,
        ballSprite,
        playerSprites,
        rebounderId: turnData.rebounderId || turnData.rebounder_player_id,
        nextPlayType: turnData.next_play_type || "HCO", // Use turnData.next_play_type instead of hardcoded "HCO"
        turnData: missTurn // Pass the original MISS turn so we can get offense_getback list
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
  console.log("🛑 Fast Break Defensive Stop:", {
    current_state: scene.stateMachine?.state,
    next_play_type: turnData.next_play_type,
    has_animations: !!turnData.animations?.length,
    animation_count: turnData.animations?.length || 0,
    stopper_id: turnData.stopper_id
  });
  
  // ✅ Use backend animation end coords for positioning (matches other transitions like DREB -> HCO)
  // This ensures frontend sprite positions match backend player.coords for accurate distance calculations
  const animations = turnData.animations || [];
  const promises = [];
  
  if (animations.length > 0) {
    // Use backend animation end coords for positioning (consistent with other animations)
    for (const anim of animations) {
      const sprite = playerSprites[anim.playerId];
      if (!sprite || !anim.movement || anim.movement.length < 2) continue;
      
      const endStep = anim.movement[anim.movement.length - 1];
      if (!endStep || !endStep.coords) continue;
      
      const endPixels = gridToPixels(endStep.coords.x, endStep.coords.y, width, height);
      
      // Use distance-based duration for consistent speed (matches HCO step movements)
      const duration = getPlayerDuration(sprite, endPixels.x, endPixels.y);
      
      // Track if this player has the ball
      const hasBall = anim.hasBallAtStep?.[anim.movement.length - 1] || false;
      if (hasBall) {
        attachBallToPlayer(scene, ballSprite, sprite);
      }
      
      promises.push(
        tweenPlayerTo(scene, sprite, endPixels, {
          duration,
          easing: "Linear" // Match HCO step movements
        })
      );
    }
  } else {
    // Fallback to manual positioning if animations are missing (backwards compatibility)
    console.warn("⚠️ animateDefensiveStop - No animations found, using manual positioning");
    
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
      stopperSpot.x = Phaser.Math.Clamp(stopperSpot.x, 4, 97);
      
      const stopperPx = gridToPixels(stopperSpot.x, stopperSpot.y, width, height);
      const stopperDuration = getPlayerDuration(stopperSprite, stopperPx.x, stopperPx.y);
      promises.push(
        tweenPlayerTo(scene, stopperSprite, stopperPx, {
          duration: stopperDuration,
          easing: "Linear"
        })
      );
    }
    
    // Move other defenders and non-involved players
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
  }
  
  await Promise.all(promises);
  
  // ✅ Show "Great Stop!" announcement with stopper headshot (for Fast Break defensive stops)
  if (turnData.fast_break === true && turnData.stopper_id) {
    const stopperId = turnData.stopper_id;
    const stopperSprite = playerSprites[stopperId];
    
    if (stopperSprite) {
      const { showAnnouncement } = await import('../utils/announcements.js');
      const stopperInfo = scene.playerInfo?.[stopperId];
      const stopperTeamId = stopperSprite?.team_id;
      
      // Handle both new nested structure (object) and old flat structure (string)
      const homeTeamField = scene.simData?.home_team;
      const awayTeamField = scene.simData?.away_team;
      const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
      const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
      const stopperTeamName = stopperTeamId === scene.homeTeamId ? homeTeamName : awayTeamName;
      
      // Determine offense side for defense team calculation
      const ballHandlerData = turnData.roles?.ball_handler;
      const ballHandlerId = ballHandlerData?.player_id || ballHandlerData || getCurrentOwner(scene);
      const ballHandlerSprite = playerSprites[ballHandlerId];
      const isHomeOffense = ballHandlerSprite?.team === "home";
      
      const stopperPlayerData = stopperInfo ? {
        playerId: stopperId,
        photo: stopperSprite?.photo || null,
        teamName: stopperTeamName
      } : null;
      
      // Defensive stop: show in defense team color (they benefited)
      const defenseTeam = isHomeOffense ? 'away' : 'home';
      showAnnouncement("Great Stop!", defenseTeam, stopperPlayerData);
      
      await new Promise(resolve => scene.time.delayedCall(1000, resolve));
    }
  } else {
    // Display outcome text for non-Fast Break stops
    if (turnData.hold_up) {
      appendToTextScroll("Defensive stop!");
    }
  }
  
  // Transition to HalfCourt for next possession (only if not already there)
  const currentState = scene.stateMachine?.state;
  if (currentState !== States.HalfCourt) {
    safeTransition(scene.stateMachine, States.HalfCourt);
  }
  
  // ✅ Ensure HCO setup is triggered after defensive stop transitions to HCO
  // This ensures players are properly positioned for the next HCO turn
  if (turnData.next_play_type === "HCO") {
    console.log("🛑 Fast Break Defensive Stop -> HCO transition:", {
      next_play_type: turnData.next_play_type,
      has_startNextHalfCourtOffense: typeof scene.startNextHalfCourtOffense === "function",
      current_state: scene.stateMachine?.state
    });
    
    if (typeof scene.startNextHalfCourtOffense === "function") {
      scene.startNextHalfCourtOffense();
    }
  }
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
    // Use distance-based duration for consistent speed
    const playerDuration = getPlayerDuration(sprite, targetPx.x, targetPx.y);
    promises.push(
      tweenPlayerTo(scene, sprite, targetPx, {
        duration: playerDuration,
        easing: "Linear" // Match HCO step movements
      })
    );
  }
}

// Export for backwards compatibility
export default function runFastBreakSequenceWrapper(scene, { playerSprites, ballSprite, turnData }) {
  return runFastBreakSequence({ scene, playerSprites, ballSprite, turnData });
}

export { HOME_RIM_COORDS, AWAY_RIM_COORDS, HOME_TOP_KEY, AWAY_TOP_KEY } from "./courtConstants.js";
