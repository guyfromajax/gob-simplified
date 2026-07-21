"""Context and logging policy for non-interactive full-game simulations."""

from __future__ import annotations

import contextvars
import logging
from contextlib import contextmanager


_quiet_headless_sim = contextvars.ContextVar("quiet_headless_sim", default=False)


class _HeadlessSimulationFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not _quiet_headless_sim.get() or record.levelno >= logging.ERROR


_FILTER = _HeadlessSimulationFilter()


@contextmanager
def quiet_headless_simulation_logs():
    """Suppress per-turn diagnostics while retaining errors for the current context."""
    root = logging.getLogger()
    handlers = list(root.handlers)
    for handler in handlers:
        handler.addFilter(_FILTER)
    token = _quiet_headless_sim.set(True)
    try:
        yield
    finally:
        _quiet_headless_sim.reset(token)
        for handler in handlers:
            handler.removeFilter(_FILTER)


@contextmanager
def quiet_training_engine_logs():
    """Silence training_execution_v2's per-play/per-defense diagnostics for one
    execute_training call.

    Those lines are emitted at WARNING (so they survive a WARNING-only platform filter),
    which is fine for a single user-team run (~100 lines) but catastrophic for CPU
    auto-train: running the engine 127x/week emits ~12k WARNING lines in seconds, trips
    the platform log rate limit, and drops real signal (batch timing, actual errors).
    Raising just this logger to ERROR for the call keeps errors flowing and works both
    in-process and inside spawned pool workers (they import the same module). Level is
    saved/restored, and each worker processes one team at a time, so this is safe."""
    lg = logging.getLogger("BackEnd.models.training_execution_v2")
    prev = lg.level
    lg.setLevel(logging.ERROR)
    try:
        yield
    finally:
        lg.setLevel(prev)
