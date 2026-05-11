/**
 * Opening Tip Animation
 * Handles the jump ball animation at the start of Q1 and OT periods
 */

import * as Phaser from "https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.esm.js";
import { tweenPlayerTo, getBallDuration } from "./ballTween.js";
import { appendToTextScroll } from "../utils/textScroll.js";
import { gridToPixels } from "../utils/gridToPixels.js";
import { getPlayerDuration } from "./turnAnimation.js";
import { attachBallToPlayer } from "./BallControllerAdapter.js";

const INITIAL_HOLD_DURATION = 2000; // Hold starting positions for 2 seconds (reduced from 4 seconds)
const ENTRANCE_HOLD_DURATION = 300;
const BALL_JUMP_HEIGHT = 5; // Ball jumps higher than players

/**
 * Animate the opening tip sequence
 * @param {Phaser.Scene} scene - The game scene
 * @param {Object} params - Parameters object
 * @param {Object} params.playerSprites - Dictionary of player sprites
 * @param {Object} params.ballSprite - The ball sprite
 * @param {Object} params.turnData - Turn data with animations and ball landing coords
 * @param {Function} params.onComplete - Callback when animation finishes
 */
export function runOpeningTipSequence(scene, { playerSprites, ballSprite, turnData, onComplete }) {
    
    // Removed pre-animation text append to avoid duplicate message
    // if (turnData.text) {
    //     appendToTextScroll(turnData.text);
    // }
    
    const animations = turnData.animations || [];
    const ballLandingCoords = turnData.ball_landing_coords || { x: 50, y: 25 };
    
    // Step 0: Position all players at their pre-tip entrance spots
    positionPlayersAtEntrance(scene, playerSprites, animations, ballSprite);

    // Step 1: Animate players into their opening-tip starting positions
    scene.time.delayedCall(ENTRANCE_HOLD_DURATION, () => {
        animatePlayersToTipStart(scene, playerSprites, animations, () => {
            // Step 2: Hold to show starting positions
            scene.time.delayedCall(INITIAL_HOLD_DURATION, () => {
                // Step 3: Jump ball animation
                animateJumpBall(scene, playerSprites, animations, ballSprite, () => {
                    // Step 4: Ball and players converge
                    animateConvergence(scene, playerSprites, animations, ballSprite, ballLandingCoords, () => {
                        // Opening tip sequence complete
                        if (onComplete) onComplete();
                    });
                });
            });
        });
    });
}

/**
 * Step 0: Position all players at their pre-tip entrance spots.
 */
function positionPlayersAtEntrance(scene, playerSprites, animations, ballSprite) {
    
    const canvasWidth = scene.game.config.width;
    const canvasHeight = scene.game.config.height;
    
    animations.forEach(anim => {
        const playerSprite = playerSprites[anim.playerId];
        if (!playerSprite) return;
        
        const startCoords = anim.entrance || anim.start;
        if (!startCoords) return;

        const pixelCoords = gridToPixels(startCoords.x, startCoords.y, canvasWidth, canvasHeight);
        playerSprite.x = pixelCoords.x;
        playerSprite.y = pixelCoords.y;
    });
    
    // Position ball at center court
    const ballStartCoords = { x: 50, y: 25 };
    const ballPixelCoords = gridToPixels(ballStartCoords.x, ballStartCoords.y, canvasWidth, canvasHeight);
    ballSprite.x = ballPixelCoords.x;
    ballSprite.y = ballPixelCoords.y;
    ballSprite.setVisible(true);
    
}

/**
 * Step 1: Animate all players from entrance spots into their jump-ball start spots.
 */
function animatePlayersToTipStart(scene, playerSprites, animations, onComplete) {
    const startTweens = [];
    const canvasWidth = scene.game.config.width;
    const canvasHeight = scene.game.config.height;

    animations.forEach(anim => {
        const playerSprite = playerSprites[anim.playerId];
        if (!playerSprite || !anim.start) return;

        const tipStartPixels = gridToPixels(anim.start.x, anim.start.y, canvasWidth, canvasHeight);
        const entranceDuration = getPlayerDuration(playerSprite, tipStartPixels.x, tipStartPixels.y);

        const tween = tweenPlayerTo(
            scene,
            playerSprite,
            tipStartPixels,
            {
                duration: entranceDuration,
                easing: 'Linear'
            }
        );

        startTweens.push(tween);
    });

    if (startTweens.length === 0 && onComplete) {
        onComplete();
        return startTweens;
    }

    Promise.allSettled(startTweens).then(() => {
        if (onComplete) onComplete();
    });

    return startTweens;
}

/**
 * Step 1: Animate both centers jumping and ball going up
 */
function animateJumpBall(scene, playerSprites, animations, ballSprite, onComplete) {
    const jumpTweens = [];
    const canvasWidth = scene.game.config.width;
    const canvasHeight = scene.game.config.height;
    
    // Find the two centers (they have action: "TIP_JUMP")
    const centerAnimations = animations.filter(anim => anim.action === "TIP_JUMP");
    
    centerAnimations.forEach(anim => {
        const playerSprite = playerSprites[anim.playerId];
        if (!playerSprite) return;
        
        const jumpCoords = anim.jumpCoords;
        const startCoords = anim.start;
        
        const jumpPixels = gridToPixels(jumpCoords.x, jumpCoords.y, canvasWidth, canvasHeight);
        const startPixels = gridToPixels(startCoords.x, startCoords.y, canvasWidth, canvasHeight);
        
        // ✅ Use distance-based duration for consistent speed (matches rest of game engine)
        const jumpDuration = getPlayerDuration(playerSprite, jumpPixels.x, jumpPixels.y);
        
        // Player jumps up and stays at peak (no coming down)
        const tween = scene.tweens.add({
            targets: playerSprite,
            x: jumpPixels.x,
            y: jumpPixels.y,
            duration: jumpDuration,
            ease: 'Quad.easeOut',
            onComplete: () => {
                // Stay at peak position
                // ✅ REMOVED: Opening tip logging (cluttering console)
            }
        });
        
        jumpTweens.push(tween);
    });
    
    // Ball jumps up and stays at peak (no coming down)
    const ballStartCoords = { x: 50, y: 25 }; // Center court
    const ballJumpCoords = { x: 50, y: 25 + BALL_JUMP_HEIGHT };
    
    const ballStartPixels = gridToPixels(ballStartCoords.x, ballStartCoords.y, canvasWidth, canvasHeight);
    const ballJumpPixels = gridToPixels(ballJumpCoords.x, ballJumpCoords.y, canvasWidth, canvasHeight);
    
    // ✅ FIX: Use getBallDuration() to respect game speed settings
    // This ensures ball animations respect Slow/Normal/Fast speed buttons
    const ballJumpDuration = getBallDuration(ballSprite, ballJumpPixels.x, ballJumpPixels.y);
    
    const ballTween = scene.tweens.add({
        targets: ballSprite,
        x: ballJumpPixels.x,
        y: ballJumpPixels.y,
        duration: ballJumpDuration,
        ease: 'Quad.easeOut',
        onComplete: () => {
            // Stay at peak position
            // ✅ REMOVED: Opening tip logging (cluttering console)
            scene.events?.emit('openingTipApex');
            
            // Wait a moment, then continue
            scene.time.delayedCall(100, () => {
                if (onComplete) onComplete();
            });
        }
    });
    
    jumpTweens.push(ballTween);
}

/**
 * Step 2: Ball goes to landing spot, players converge
 */
function animateConvergence(scene, playerSprites, animations, ballSprite, ballLandingCoords, onComplete) {
    const convergeTweens = [];
    const canvasWidth = scene.game.config.width;
    const canvasHeight = scene.game.config.height;
    
    // Find all non-center players (they have action: "CONVERGE_ON_BALL")
    const convergeAnimations = animations.filter(anim => anim.action === "CONVERGE_ON_BALL");
    
    convergeAnimations.forEach(anim => {
        const playerSprite = playerSprites[anim.playerId];
        if (!playerSprite) return;
        
        const endCoords = anim.end;
        
        // Convert grid coordinates to pixels
        const pixelCoords = gridToPixels(endCoords.x, endCoords.y, canvasWidth, canvasHeight);
        
        // ✅ Use distance-based duration for consistent speed (matches rest of game engine)
        const convergeDuration = getPlayerDuration(playerSprite, pixelCoords.x, pixelCoords.y);
        
        // Tween player to their convergence spot
        const tween = tweenPlayerTo(
            scene,
            playerSprite,
            pixelCoords,  // Pass as {x, y} object
            { duration: convergeDuration, easing: 'Linear' }
        );
        
        convergeTweens.push(tween);
    });
    
    // Ball tweens to landing spot
    const ballPixelCoords = gridToPixels(ballLandingCoords.x, ballLandingCoords.y, canvasWidth, canvasHeight);
    
    // ✅ REMOVED: Opening tip ball converging logging (cluttering console)
    
    // ✅ FIX: Use getBallDuration() to respect game speed settings
    // This ensures ball animations respect Slow/Normal/Fast speed buttons
    const ballConvergeDuration = getBallDuration(ballSprite, ballPixelCoords.x, ballPixelCoords.y);
    
    const ballTween = scene.tweens.add({
        targets: ballSprite,
        x: ballPixelCoords.x,
        y: ballPixelCoords.y,
        duration: ballConvergeDuration,
        ease: 'Quad.easeOut',
        onComplete: () => {
            // ✅ REMOVED: Opening tip ball landing logging (cluttering console)
            
            // ✅ FIX: Attach ball to the tip winner (player whose end coords match ballLandingCoords)
            // This matches the pattern used in inbound passes (IP → HCO transition)
            // The player who converges to the ball landing spot is the tip winner
            const tipWinnerSprite = findTipWinner(playerSprites, animations, ballLandingCoords, canvasWidth, canvasHeight);
            if (tipWinnerSprite) {
                // ✅ REMOVED: Opening tip ball attachment logging (cluttering console)
                attachBallToPlayer(scene, ballSprite, tipWinnerSprite);
                // Set flag so first HCO turn knows ball is already attached (like _previousTurnWasInbound)
                scene._previousTurnWasOpeningTip = true;
                
                // ✅ REFACTOR: Use centralized pass system for tip winner → PG pass
                // Find PG for the tip winner's team
                const tipWinnerTeam = tipWinnerSprite.team || tipWinnerSprite.team_id;
                let pgSprite = null;
                let pgId = null;
                
                for (const [id, sprite] of Object.entries(playerSprites)) {
                    const info = scene.playerInfo?.[id];
                    if (info?.pos === "PG" && (sprite.team === tipWinnerTeam || sprite.team_id === tipWinnerTeam)) {
                        pgSprite = sprite;
                        pgId = id;
                        break;
                    }
                }
                
                if (pgSprite && pgId) {
                    // Wait a moment for ball attachment to settle, then pass to PG
                    scene.time.delayedCall(300, async () => {
                        const { handlePassAnimation } = await import('./passDetection.js');
                        const syntheticPassInfo = {
                            passerId: tipWinnerSprite.playerId,
                            receiverId: pgId,
                            stepIndex: 0,
                            timestamp: Date.now()
                        };
                        await handlePassAnimation({
                            scene,
                            passInfo: syntheticPassInfo,
                            playerSprites
                        });
                        if (onComplete) onComplete();
                    });
                } else {
                    console.warn("⚠️ Could not find PG for tip winner's team, skipping pass");
                    // Wait a moment before continuing
                    scene.time.delayedCall(300, () => {
                        if (onComplete) onComplete();
                    });
                }
            } else {
                console.warn("⚠️ Could not find tip winner to attach ball to");
                // Wait a moment before continuing
                scene.time.delayedCall(300, () => {
                    if (onComplete) onComplete();
                });
            }
        }
    });
    
    convergeTweens.push(ballTween);
}

/**
 * Find the player who won the tip (player whose end coords match ballLandingCoords)
 * @param {Object} playerSprites - Dictionary of player sprites
 * @param {Array} animations - Opening tip animations
 * @param {Object} ballLandingCoords - Ball landing coordinates {x, y}
 * @param {number} canvasWidth - Canvas width
 * @param {number} canvasHeight - Canvas height
 * @returns {Object|null} Player sprite of tip winner, or null if not found
 */
function findTipWinner(playerSprites, animations, ballLandingCoords, canvasWidth, canvasHeight) {
    // Find the player whose end coords match the ball landing spot
    // The tip winner is the player who converges to the ball location
    for (const anim of animations) {
        if (anim.action === "CONVERGE_ON_BALL" && anim.end) {
            // Check if this player's end coords match the ball landing spot
            if (anim.end.x === ballLandingCoords.x && anim.end.y === ballLandingCoords.y) {
                const winnerSprite = playerSprites[anim.playerId];
                if (winnerSprite) {
                    return winnerSprite;
                }
            }
        }
    }
    return null;
}
