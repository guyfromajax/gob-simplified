/**
 * The ball's floor depth — ONE declaration, no imports.
 *
 * It had three separate values before: `initializeBallSprite` set 1000 (BallController.js:81),
 * the two tween paths set a local `BALL_DEPTH = 1000` (ballAnimationSimple.js:183,
 * ballTween.js:29), and `positionBallOnPlayer` set `playerSprite.depth + 1` = 2
 * (BallController.js:345). The last one was only ever safe because every player container sat
 * at depth 1.
 *
 * This module deliberately imports NOTHING: BallController -> ballTween ->
 * BallControllerAdapter -> BallController is a genuine import cycle, so a constant exported
 * from any of those three could be in the temporal dead zone for one of the others. A leaf
 * cannot participate in a cycle.
 */
export const BALL_DEPTH = 1000;
