#!/bin/sh
# Railway/nixpacks start wrapper.
#
# numpy/scipy's C-extensions dlopen libstdc++.so.6 at runtime, but the nix-built
# Python's environment doesn't expose it on LD_LIBRARY_PATH. We must NOT use
# Debian's /usr/lib/x86_64-linux-gnu libstdc++ — loading Debian's libc into the
# nix Python crashes the interpreter ("__vdso_gettimeofday: invalid mode for
# dlopen()"). Instead, add the *nix* gcc lib dir (pulled in by nixLibs =
# ["stdenv.cc.cc.lib"] in nixpacks.toml), which matches the nix Python's ABI.
#
# Safe by construction: if the glob matches nothing it contributes an ignored
# path and the original LD_LIBRARY_PATH is preserved, so Python still starts.
# Reproducibility: Python randomises string hashing per process, and several sim
# code paths iterate sets or break ties in iteration order, so an unpinned process
# produces a different game from identical inputs. Pinning here does not help with
# games already played, but from now on a reported game can be replayed.
# See BackEnd/utils/repro and _documentation_master/projects/bugs.md.
export PYTHONHASHSEED=0

# Memory: glibc gives a threaded process up to 8 x CPU-count malloc arenas. On the
# 32-vCPU Railway service that ceiling let RSS ratchet from ~1 GB to 6.34 GB with
# only 2-3 users. Nothing leaked -- objects were freed, but glibc returns memory to
# the OS only from the top of an arena, so each arena kept its own high-water mark
# and RSS fell only on redeploy. Memory was 92% of the Railway bill ($19.57 of
# $21.17, Aug 2026); capping arenas at 2 took steady-state RSS from ~2.5 GB to
# ~110 MB. Diagnosis: RSS climbing while tracemalloc stays flat, plateauing rather
# than growing without bound, is allocator retention -- not a leak.
# Must be set before the process starts. Inherited by the cpu_week_pool spawn
# workers, so it caps their peaks too. Keep this on any long-running Python
# service; re-verify under real playtest load, where peak allocations are larger.
export MALLOC_ARENA_MAX=2

GCC_LIBS="$(echo /nix/store/*gcc*-lib/lib | tr ' ' ':')"
export LD_LIBRARY_PATH="${GCC_LIBS}:${LD_LIBRARY_PATH}"

exec /opt/venv/bin/uvicorn BackEnd.api.api:app --host 0.0.0.0 --port "${PORT:-8000}"
