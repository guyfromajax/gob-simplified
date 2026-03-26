/**
 * Pause/resume Phaser tweens on player sprites (freeze locomotion during announcements, etc.).
 * Does not pause the whole scene — only tweens whose targets are sprites in `playerSprites`.
 * Callers may import this from any animation path; not wired inside showAnnouncement by default
 * so each flow controls when freeze applies (avoid surprising global freezes).
 */

function forEachPlayerTween(scene, playerSprites, fn) {
  if (!scene?.tweens?.getTweensOf || !playerSprites || typeof fn !== "function") return;
  for (const sprite of Object.values(playerSprites)) {
    if (!sprite) continue;
    const list = scene.tweens.getTweensOf(sprite);
    if (!list?.length) continue;
    for (const t of list) {
      fn(t);
    }
  }
}

export function pauseTweensOfPlayerSprites(scene, playerSprites) {
  forEachPlayerTween(scene, playerSprites, (t) => {
    if (t && typeof t.pause === "function") t.pause();
  });
}

export function resumeTweensOfPlayerSprites(scene, playerSprites) {
  forEachPlayerTween(scene, playerSprites, (t) => {
    if (t && typeof t.resume === "function") t.resume();
  });
}
