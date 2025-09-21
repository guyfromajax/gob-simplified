export function createAnimationTimeline(scene) {
  const callbacks = new Map();
  const steps = [];
  return {
    add(config = {}) {
      steps.push(config);
      return this;
    },
    once(event, handler) {
      if (!callbacks.has(event)) callbacks.set(event, []);
      callbacks.get(event).push(handler);
      return this;
    },
    play() {
      for (const step of steps) {
        step.onStart?.();
        step.onComplete?.();
      }
      (callbacks.get('complete') || []).forEach((handler) => handler?.());
    },
  };
}

export default createAnimationTimeline;
