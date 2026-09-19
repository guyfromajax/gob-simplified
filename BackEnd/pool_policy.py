"""Desktop CPU-sim pool sizing. Railway default 8 is a 32-vCPU number."""

from __future__ import annotations

import os
import sys

# Live game + Phaser renderer keep these cores. Phase A yields to that workload.
LIVE_GAME_RESERVE_CORES = 2
WORKER_RSS_MB = 200
RESERVED_RAM_MB = 2048
# Conservative laptop cap until 4-core reference hardware measures the frame-rate floor.
CONSERVATIVE_DESKTOP_CAP = 4


def available_ram_mb() -> int | None:
    try:
        if sys.platform == "darwin":
            import subprocess

            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
            return int(out.strip()) // (1024 * 1024)
        pages = os.sysconf("SC_PHYS_PAGES")
        page = os.sysconf("SC_PAGE_SIZE")
        return int(pages * page) // (1024 * 1024)
    except (OSError, TypeError, ValueError):
        return None


def desktop_worker_count(
    *,
    cores: int | None = None,
    ram_mb: int | None = None,
    cap: int = CONSERVATIVE_DESKTOP_CAP,
) -> int:
    cpu = cores if cores is not None else (os.cpu_count() or 2)
    reserve = LIVE_GAME_RESERVE_CORES if cpu >= 4 else 1
    by_cpu = max(1, cpu - reserve)
    mem = ram_mb if ram_mb is not None else available_ram_mb()
    if mem is None:
        by_ram = by_cpu
    else:
        by_ram = max(1, (mem - RESERVED_RAM_MB) // WORKER_RSS_MB)
    return max(1, min(by_cpu, by_ram, cap))
