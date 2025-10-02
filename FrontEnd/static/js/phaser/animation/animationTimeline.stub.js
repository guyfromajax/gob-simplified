import { createTimelinePolyfill } from "./timelinePolyfill.js";

export function createAnimationTimeline(scene) {
  if (!scene) return null;

  if (scene.__activeTimeline) {
    scene.__activeTimeline.stop?.();
    scene.__activeTimeline = null;
  }

  const tweens = scene.tweens || scene.sys?.tweens || null;
  let timeline = null;

  if (tweens) {
    if (typeof tweens.createTimeline === "function") {
      timeline = tweens.createTimeline();
    } else if (typeof tweens.timeline === "function") {
      timeline = tweens.timeline();
    } else if (typeof tweens.addTimeline === "function") {
      timeline = tweens.addTimeline();
    }
  }

  if (!timeline) {
    timeline = createTimelinePolyfill(scene);
  }

  if (!timeline) return null;

  scene.__activeTimeline = timeline;

  timeline.once?.("complete", () => {
    if (scene.__activeTimeline === timeline) {
      scene.__activeTimeline = null;
    }
  });

  timeline.once?.("stop", () => {
    if (scene.__activeTimeline === timeline) {
      scene.__activeTimeline = null;
    }
  });

  return timeline;
}

export { createTimelinePolyfill };

export default createAnimationTimeline;
