import {
  animationDebugLog,
  animationDebugWarn,
  isAnimationDebugEnabled,
} from "../utils/debugFlags.js";

function getTrackerKey({ possessionId, turnIndex }) {
  if (possessionId != null) return String(possessionId);
  if (turnIndex != null) return `turn:${turnIndex}`;
  return "turn:unknown";
}

function clonePayload(payload = {}) {
  try {
    return JSON.parse(JSON.stringify(payload));
  } catch (err) {
    return { ...payload };
  }
}

export class DebugStepLogger {
  constructor(label = "ANIM") {
    this.label = label;
    this.trackers = new Map();
  }

  reset(possessionId) {
    if (possessionId == null) return;
    this.trackers.delete(String(possessionId));
  }

  logStep(payload = {}) {
    if (!isAnimationDebugEnabled()) return;
    const trackerKey = getTrackerKey(payload);
    const tracker = this.trackers.get(trackerKey) || {
      lastTurnIndex: null,
      lastStepIndex: -Infinity,
    };

    if (tracker.lastTurnIndex !== payload.turnIndex) {
      tracker.lastTurnIndex = payload.turnIndex;
      tracker.lastStepIndex = -Infinity;
    }

    if (typeof payload.stepIndex === "number") {
      if (
        Number.isFinite(tracker.lastStepIndex) &&
        tracker.lastStepIndex !== -Infinity &&
        payload.stepIndex < tracker.lastStepIndex
      ) {
        animationDebugWarn(
          `${this.label}: stepIndex regression`,
          clonePayload({ ...payload, lastStepIndex: tracker.lastStepIndex })
        );
      }
      tracker.lastStepIndex = Math.max(tracker.lastStepIndex, payload.stepIndex);
    }

    this.trackers.set(trackerKey, tracker);
    animationDebugLog(`${this.label}: step`, clonePayload(payload));
  }
}

export function getSceneStepLogger(scene, label = "ANIM") {
  if (!scene) return null;
  if (!scene.__debugStepLogger) {
    scene.__debugStepLogger = new DebugStepLogger(label);
  }
  return scene.__debugStepLogger;
}

export default DebugStepLogger;
