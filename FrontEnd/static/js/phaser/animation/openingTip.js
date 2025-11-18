/**
 * Opening Tip Animation
 * Handles the jump ball animation at the start of Q1 and OT periods
 */

import { tweenPlayerTo } from "./ballTween.js";
import { appendToTextScroll } from "../utils/textScroll.js";
import { gridToPixels } from "../utils/gridToPixels.js";
import { getPlayerDuration } from "./turnAnimation.js";

const INITIAL_HOLD_DURATION = 2000; // Hold starting positions for 2 seconds (reduced from 4 seconds)
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
    console.log("🏀 Running opening tip sequence:", turnData);
    
    // Removed pre-animation text append to avoid duplicate message
    // if (turnData.text) {
    //     appendToTextScroll(turnData.text);
    // }
    
    const animations = turnData.animations || [];
    const ballLandingCoords = turnData.ball_landing_coords || { x: 50, y: 25 };
    
    // Step 0: Position all players at their starting positions
    positionPlayersAtStart(scene, playerSprites, animations, ballSprite);
    
    // Step 1: Hold for 4 seconds to show starting positions
    scene.time.delayedCall(INITIAL_HOLD_DURATION, () => {
        // Step 2: Jump ball animation
        animateJumpBall(scene, playerSprites, animations, ballSprite, () => {
            // Step 3: Ball and players converge
            animateConvergence(scene, playerSprites, animations, ballSprite, ballLandingCoords, () => {
                console.log("✅ Opening tip sequence complete");
                if (onComplete) onComplete();
            });
        });
    });
}

/**
 * Step 0: Position all players at their starting positions
 */
function positionPlayersAtStart(scene, playerSprites, animations, ballSprite) {
    console.log("🏀 Positioning players at opening tip starting positions");
    
    const canvasWidth = scene.game.config.width;
    const canvasHeight = scene.game.config.height;
    
    // Position all players at their starting spots
    animations.forEach(anim => {
        const playerSprite = playerSprites[anim.playerId];
        if (!playerSprite || !anim.start) return;
        
        const startCoords = anim.start;
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
    
    console.log("✅ All players positioned for opening tip", {
        totalPlayers: animations.length,
        ballGridCoords: ballStartCoords,
        ballPixelCoords: ballPixelCoords,
        canvasSize: { width: canvasWidth, height: canvasHeight }
    });
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
                console.log(`🏀 Center ${anim.playerId} stays at peak`);
            }
        });
        
        jumpTweens.push(tween);
    });
    
    // Ball jumps up and stays at peak (no coming down)
    const ballStartCoords = { x: 50, y: 25 }; // Center court
    const ballJumpCoords = { x: 50, y: 25 + BALL_JUMP_HEIGHT };
    
    const ballStartPixels = gridToPixels(ballStartCoords.x, ballStartCoords.y, canvasWidth, canvasHeight);
    const ballJumpPixels = gridToPixels(ballJumpCoords.x, ballJumpCoords.y, canvasWidth, canvasHeight);
    
    // ✅ Use distance-based duration for ball (matches player speed system)
    // Calculate distance from current ball position to jump position
    const ballDistance = Phaser.Math.Distance.Between(
        ballSprite.x, ballSprite.y,
        ballJumpPixels.x, ballJumpPixels.y
    );
    // Use same speed as players (350 pixels/second default)
    const ballJumpDuration = (ballDistance / 350) * 1000; // Convert to milliseconds
    
    const ballTween = scene.tweens.add({
        targets: ballSprite,
        x: ballJumpPixels.x,
        y: ballJumpPixels.y,
        duration: ballJumpDuration,
        ease: 'Quad.easeOut',
        onComplete: () => {
            // Stay at peak position
            console.log("🏀 Ball stays at peak");
            
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
    
    console.log("🏀 Ball converging to:", {
        gridCoords: ballLandingCoords,
        pixelCoords: ballPixelCoords
    });
    
    // ✅ Use distance-based duration for ball (matches player speed system)
    // Calculate distance from current ball position to landing position
    const ballConvergeDistance = Phaser.Math.Distance.Between(
        ballSprite.x, ballSprite.y,
        ballPixelCoords.x, ballPixelCoords.y
    );
    // Use same speed as players (350 pixels/second default)
    const ballConvergeDuration = (ballConvergeDistance / 350) * 1000; // Convert to milliseconds
    
    const ballTween = scene.tweens.add({
        targets: ballSprite,
        x: ballPixelCoords.x,
        y: ballPixelCoords.y,
        duration: ballConvergeDuration,
        ease: 'Quad.easeOut',
        onComplete: () => {
            console.log("🏀 Ball landed at grid:", ballLandingCoords, "pixel:", { x: ballSprite.x, y: ballSprite.y });
            
            // Wait a moment before continuing
            scene.time.delayedCall(300, () => {
                if (onComplete) onComplete();
            });
        }
    });
    
    convergeTweens.push(ballTween);
}

