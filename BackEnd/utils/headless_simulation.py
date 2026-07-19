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
