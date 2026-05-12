import { tweenPlayerTo } from "./ballTween.js";
import { gridToPixels } from "../utils/gridToPixels.js";
import { getPlayerDuration } from "./turnAnimation.js";

const ENTRY_HOLD_DURATION = 300;

export async function runBenchEntrySequence(scene, { playerSprites, entryAnimation }) {
  const animations = Array.isArray(entryAnimation?.animations)
    ? entryAnimation.animations
    : [];
  if (!scene || animations.length === 0) return;

  const width = scene.game.config.width;
  const height = scene.game.config.height;

  animations.forEach((animation) => {
    const sprite = playerSprites?.[animation.playerId];
    const entrance = animation?.entrance;
    if (!sprite || !entrance) return;
    const entrancePx = gridToPixels(entrance.x, entrance.y, width, height);
    sprite.x = entrancePx.x;
    sprite.y = entrancePx.y;
  });

  if (scene.time) {
    await new Promise((resolve) => scene.time.delayedCall(ENTRY_HOLD_DURATION, resolve));
  }

  const tweens = [];
  animations.forEach((animation) => {
    const sprite = playerSprites?.[animation.playerId];
    const end = animation?.end;
    if (!sprite || !end) return;
    const endPx = gridToPixels(end.x, end.y, width, height);
    tweens.push(
      tweenPlayerTo(scene, sprite, endPx, {
        duration: getPlayerDuration(sprite, endPx.x, endPx.y),
        easing: "Linear",
      })
    );
  });

  await Promise.allSettled(tweens);
}
