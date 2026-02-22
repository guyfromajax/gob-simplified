function formatClock(seconds) {
  const safe = Math.max(0, Math.floor(Number(seconds) || 0));
  const minutes = Math.floor(safe / 60);
  const secs = safe % 60;
  return `${minutes}:${String(secs).padStart(2, '0')}`;
}

export function parseClockToSeconds(clock) {
  if (typeof clock === 'number' && Number.isFinite(clock)) {
    return Math.max(0, Math.floor(clock));
  }
  if (typeof clock !== 'string') return 0;
  const parts = clock.split(':');
  if (parts.length !== 2) return 0;
  const minutes = Number(parts[0]);
  const seconds = Number(parts[1]);
  if (!Number.isFinite(minutes) || !Number.isFinite(seconds)) return 0;
  return Math.max(0, Math.floor(minutes * 60 + seconds));
}

export function createGameClock({
  timeRemainingSeconds = 0,
  clockElement = null,
  tickMs = 450,
  onZero = null,
} = {}) {
  let timeRemaining = Math.max(0, Math.floor(Number(timeRemainingSeconds) || 0));
  let intervalId = null;
  let running = false;
  const pauseReasons = new Set();
  let tickIntervalMs = Math.max(50, Math.floor(Number(tickMs) || 450));

  const render = () => {
    if (clockElement) {
      clockElement.textContent = formatClock(timeRemaining);
    }
  };

  const clear = () => {
    if (intervalId) {
      clearInterval(intervalId);
      intervalId = null;
    }
  };

  const tick = () => {
    if (!running || pauseReasons.size > 0) return;
    if (timeRemaining <= 0) {
      clear();
      running = false;
      if (typeof onZero === 'function') onZero();
      return;
    }
    timeRemaining -= 1;
    render();
  };

  return {
    start() {
      if (running && intervalId) return;
      running = true;
      pauseReasons.clear();
      render();
      clear();
      intervalId = setInterval(tick, tickIntervalMs);
    },
    pause(reason = 'manual') {
      pauseReasons.add(String(reason || 'manual'));
    },
    resume(reason = null) {
      if (!running) return;
      if (typeof reason === 'string' && reason.length > 0) {
        pauseReasons.delete(reason);
      } else {
        pauseReasons.clear();
      }
    },
    stop() {
      running = false;
      pauseReasons.clear();
      clear();
    },
    syncWithBackend(timeRemainingSecondsValue) {
      const parsed = Math.max(0, Math.floor(Number(timeRemainingSecondsValue) || 0));
      timeRemaining = parsed;
      render();
    },
    setTickMs(nextTickMs) {
      const parsed = Math.max(50, Math.floor(Number(nextTickMs) || 450));
      tickIntervalMs = parsed;
      if (running) {
        clear();
        intervalId = setInterval(tick, tickIntervalMs);
      }
    },
    getState() {
      return {
        timeRemaining,
        running,
        paused: pauseReasons.size > 0,
        pauseReasons: Array.from(pauseReasons),
        tickMs: tickIntervalMs,
      };
    },
    render,
  };
}
