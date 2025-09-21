const DEFAULT_EVENT_NAMES = {
  COMPLETE: "complete",
  STOP: "stop",
};

function toDuration(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value >= 0 ? value : 0;
  }
  const coerced = Number(value);
  if (!Number.isFinite(coerced) || coerced < 0) {
    return 0;
  }
  return coerced;
}

function createListenerRegistry() {
  const callbacks = new Map();
  return {
    once(event, handler) {
      if (typeof handler !== "function") return;
      if (!callbacks.has(event)) callbacks.set(event, []);
      callbacks.get(event).push(handler);
    },
    dispatch(event, ...args) {
      const handlers = callbacks.get(event);
      if (!handlers || handlers.length === 0) return;
      callbacks.delete(event);
      handlers.forEach((handler) => {
        try {
          handler(...args);
        } catch (error) {
          console.error(
            "timeline polyfill listener threw",
            error
          );
        }
      });
    },
    clear() {
      callbacks.clear();
    },
  };
}

function scheduleDelay(scene, duration, callback, pendingSet) {
  const safeDuration = toDuration(duration);
  let cancelled = false;
  let cancelFn;

  if (scene?.time?.delayedCall) {
    const timer = scene.time.delayedCall(safeDuration, () => {
      if (cancelled) return;
      pendingSet.delete(cancelFn);
      callback();
    });
    cancelFn = () => {
      if (cancelled) return;
      cancelled = true;
      pendingSet.delete(cancelFn);
      if (typeof timer?.remove === "function") {
        timer.remove(false);
      } else if (typeof timer?.destroy === "function") {
        timer.destroy();
      }
    };
  } else {
    const handle = setTimeout(() => {
      if (cancelled) return;
      pendingSet.delete(cancelFn);
      callback();
    }, safeDuration);
    cancelFn = () => {
      if (cancelled) return;
      cancelled = true;
      pendingSet.delete(cancelFn);
      clearTimeout(handle);
    };
  }

  pendingSet.add(cancelFn);
  return cancelFn;
}

function createTimelinePolyfill(scene) {
  const steps = [];
  const listeners = createListenerRegistry();
  const pendingDelays = new Set();
  let status = "idle"; // idle -> playing -> completed|stopped

  function clearPendingDelays() {
    for (const cancel of Array.from(pendingDelays)) {
      try {
        cancel();
      } catch (error) {
        console.error("failed to cancel timeline delay", error);
      }
    }
    pendingDelays.clear();
  }

  function runStep(index) {
    if (status !== "playing") return;
    if (index >= steps.length) {
      status = "completed";
      listeners.dispatch(DEFAULT_EVENT_NAMES.COMPLETE);
      return;
    }
    const step = steps[index] || {};
    try {
      step.onStart?.();
    } catch (error) {
      console.error("timeline polyfill onStart threw", error);
    }
    const duration = toDuration(step.duration);
    scheduleDelay(scene, duration, () => {
      if (status !== "playing") return;
      try {
        step.onComplete?.();
      } catch (error) {
        console.error("timeline polyfill onComplete threw", error);
      }
      runStep(index + 1);
    }, pendingDelays);
  }

  const timeline = {
    add(config = {}) {
      steps.push(config);
      return timeline;
    },
    once(event, handler) {
      listeners.once(event, handler);
      return timeline;
    },
    play() {
      if (status === "playing") return timeline;
      clearPendingDelays();
      if (steps.length === 0) {
        status = "completed";
        listeners.dispatch(DEFAULT_EVENT_NAMES.COMPLETE);
        return timeline;
      }
      status = "playing";
      runStep(0);
      return timeline;
    },
    stop() {
      if (status !== "playing") return timeline;
      status = "stopped";
      clearPendingDelays();
      listeners.dispatch(DEFAULT_EVENT_NAMES.STOP);
      return timeline;
    },
  };

  return timeline;
}

export { createTimelinePolyfill };
export default createTimelinePolyfill;
