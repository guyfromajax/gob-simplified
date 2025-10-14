/**
 * Opening Tip Animation
 * Handles the jump ball animation at the start of Q1 and OT periods
 */

import { tweenPlayerTo } from "./ballTween.js";
import { appendToTextScroll } from "../utils/textScroll.js";

const INITIAL_HOLD_DURATION = 4000; // Hold starting positions for 4 seconds
const JUMP_DURATION = 1500; // Jump animation duration (up and down)
const CONVERGE_DURATION = 1500; // Convergence duration
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
    
    // Display the text
    if (turnData.text) {
        appendToTextScroll(turnData.text);
    }
    
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
    
    // Position all players at their starting spots
    animations.forEach(anim => {
        const playerSprite = playerSprites[anim.playerId];
        if (!playerSprite || !anim.start) return;
        
        const startCoords = anim.start;
        playerSprite.x = startCoords.x * 4;
        playerSprite.y = (50 - startCoords.y) * 4;
    });
    
    // Position ball at center court
    const ballStartCoords = { x: 50, y: 25 };
    ballSprite.x = ballStartCoords.x * 4;
    ballSprite.y = (50 - ballStartCoords.y) * 4;
    ballSprite.setVisible(true);
    
    console.log("✅ All players positioned for opening tip");
}

/**
 * Step 1: Animate both centers jumping and ball going up
 */
function animateJumpBall(scene, playerSprites, animations, ballSprite, onComplete) {
    const jumpTweens = [];
    
    // Find the two centers (they have action: "TIP_JUMP")
    const centerAnimations = animations.filter(anim => anim.action === "TIP_JUMP");
    
    centerAnimations.forEach(anim => {
        const playerSprite = playerSprites[anim.playerId];
        if (!playerSprite) return;
        
        const jumpCoords = anim.jumpCoords;
        const startCoords = anim.start;
        
        // Player jumps up then returns
        const tween = scene.tweens.add({
            targets: playerSprite,
            x: jumpCoords.x * 4,
            y: (50 - jumpCoords.y) * 4,
            duration: JUMP_DURATION / 2,
            ease: 'Quad.easeOut',
            yoyo: true,
            onComplete: () => {
                // Return to start position
                playerSprite.x = startCoords.x * 4;
                playerSprite.y = (50 - startCoords.y) * 4;
            }
        });
        
        jumpTweens.push(tween);
    });
    
    // Ball jumps even higher
    const ballStartCoords = { x: 50, y: 25 }; // Center court
    const ballJumpCoords = { x: 50, y: 25 + BALL_JUMP_HEIGHT };
    
    const ballTween = scene.tweens.add({
        targets: ballSprite,
        x: ballJumpCoords.x * 4,
        y: (50 - ballJumpCoords.y) * 4,
        duration: JUMP_DURATION / 2,
        ease: 'Quad.easeOut',
        yoyo: true,
        onComplete: () => {
            ballSprite.x = ballStartCoords.x * 4;
            ballSprite.y = (50 - ballStartCoords.y) * 4;
            
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
    
    // Find all non-center players (they have action: "CONVERGE_ON_BALL")
    const convergeAnimations = animations.filter(anim => anim.action === "CONVERGE_ON_BALL");
    
    convergeAnimations.forEach(anim => {
        const playerSprite = playerSprites[anim.playerId];
        if (!playerSprite) return;
        
        const endCoords = anim.end;
        
        // Tween player to their convergence spot
        const tween = tweenPlayerTo(
            scene,
            playerSprite,
            endCoords.x,
            endCoords.y,
            CONVERGE_DURATION,
            'Linear'
        );
        
        convergeTweens.push(tween);
    });
    
    // Ball tweens to landing spot
    const ballTween = scene.tweens.add({
        targets: ballSprite,
        x: ballLandingCoords.x * 4,
        y: (50 - ballLandingCoords.y) * 4,
        duration: CONVERGE_DURATION,
        ease: 'Quad.easeOut',
        onComplete: () => {
            console.log("🏀 Ball landed at", ballLandingCoords);
            
            // Wait a moment before continuing
            scene.time.delayedCall(300, () => {
                if (onComplete) onComplete();
            });
        }
    });
    
    convergeTweens.push(ballTween);
}

