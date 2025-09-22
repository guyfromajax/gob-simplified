import * as Phaser from "https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.esm.js";
import { createTimelinePolyfill } from "./timelinePolyfill.js";

// Simple wrapper around Phaser's timeline creation. Ensures any previously
// active timeline on the scene is stopped before creating a new one so that
// overlapping sequences do not conflict.
export function createAnimationTimeline(scene) {
  if (!scene) return null;
  if (scene.__activeTimeline) {
    scene.__activeTimeline.stop();
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
    } else if (Phaser?.Tweens?.Timeline) {
      try {
        timeline = new Phaser.Tweens.Timeline(tweens);
      } catch (error) {
        console.warn("Failed to construct Phaser timeline", error);
        timeline = null;
      }
    }
  }

  if (!timeline) {
    console.warn(
      "Phaser tween timeline unavailable; using timeline polyfill fallback"
    );
    timeline = createTimelinePolyfill(scene);
  }

  if (!timeline) return null;
  scene.__activeTimeline = timeline;

  timeline.once("complete", () => {
    if (scene.__activeTimeline === timeline) {
      scene.__activeTimeline = null;
    }
  });

  if (typeof timeline.once === "function") {
    timeline.once("stop", () => {
      if (scene.__activeTimeline === timeline) {
        scene.__activeTimeline = null;
      }
    });
  }
  return timeline;
}

export default createAnimationTimeline;
