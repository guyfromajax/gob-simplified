// Simple wrapper around Phaser's timeline creation. Ensures any previously
// active timeline on the scene is stopped before creating a new one so that
// overlapping sequences do not conflict.
export function createAnimationTimeline(scene) {
  if (!scene || !scene.tweens) return null;
  if (scene.__activeTimeline) {
    scene.__activeTimeline.stop();
    scene.__activeTimeline = null;
  }
  const { tweens } = scene;
  let timeline = null;

  if (typeof tweens.createTimeline === "function") {
    timeline = tweens.createTimeline();
  } else if (typeof tweens.timeline === "function") {
    timeline = tweens.timeline();
  } else if (typeof tweens.addTimeline === "function") {
    timeline = tweens.addTimeline();
  }

  if (!timeline) return null;
  scene.__activeTimeline = timeline;

  timeline.once("complete", () => {
    if (scene.__activeTimeline === timeline) {
      scene.__activeTimeline = null;
    }
  });
  return timeline;
}

export default createAnimationTimeline;
