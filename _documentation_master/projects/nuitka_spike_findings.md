# Nuitka Compile Spike — Findings

**Date:** 17 September 2026
**What was tested:** Nuitka 4.2.1 standalone, macOS x86_64 (Intel), isolated venv
**Q1:** PASS — spawn-based process pool survives compilation; no worker-mode rewrite.
**Q2:** PASS with a font path issue — SciPy/NumPy/Pillow compile and paint; bundled Liberation font is in the dist but `_find_wm_font()` misses it.
**Platform:** macOS x86_64 only. Windows x64 is unverified.

---

# SPIKE: Nuitka compile viability — process pool + SciPy paint stack

**Status:** Q1 and Q2 compiled. Both stacks run. Q2 has a **bundled-font path bug** under Nuitka (not a SciPy failure).
**Date:** 17–18 September 2026
**Box:** Darwin 26.5.1, x86_64, 14 logical CPUs, Homebrew Python 3.13.5
**Compiler:** Nuitka 4.2.1 in an isolated `~/gob-nuitka-spike/.venv` (never activated `~/gob-simplified/venv`)
**Constraint honored:** no application-code edits, no branch, no commit. Source was read from `~/gob-simplified`; all writes stayed here.

---

## 0. Compile window

Source-mode on 17 Sep saw load 14.21 / 14 cores; compile was deferred.

Q1 compile ran 18 Sep 08:42 with load 3.39 2.57 2.43. Standalone Nuitka 4.2.1 finished in **51 s** (`logs/q1_compile.log`). Binary: `dist/q1/q1_main.dist/q1_pool` (Mach-O x86_64, 7.4 MB).

Q2 compile ran 18 Sep 08:50–09:36 (load 3.36 3.44 2.96). Standalone Nuitka 4.2.1 finished in **2748 s / 45.8 min**, 1459 C files (`logs/q2_compile.log`). Binary: `dist/q2/q2_main.dist/q2_paint` (Mach-O x86_64, 217 MB). Dist folder: **291 MB**.

---

## QUESTION 1 — Does the spawn-based process pool survive Nuitka?

### What was reproduced

Smallest program matching `BackEnd/utils/cpu_week_pool.py`:

- `mp.get_context("spawn")`
- `ProcessPoolExecutor`
- `_worker` lives in an imported module, not `__main__`
- deferred imports inside `_worker`: `from BackEnd.utils import sim_random` then `from BackEnd.api.franchise_routes import _run_franchise_cpu_full_simulation_core`
- picklable tuple tasks, results keyed by game index

No `multiprocessing.freeze_support()` on the honest entry point (`q1_main.py`). The real `BackEnd/main.py` does not call it either. `q1_main_freeze.py` exists only as a fallback if the compiled honest binary fails.

Trivial work per job: 0.35 s busy-wait, returns `(away, home, summary)` with the child PID.

### Run-from-source (PASS)

| Workers | Jobs | Unique worker PIDs | Wall | Status |
|---|---:|---:|---:|---|
| 4 | 8 | 4 | 0.898 s | OK |
| 1 | 8 | 1 | 2.944 s | OK |

- Did not hang, crash, or silently serialize to one process.
- 4-worker run used four distinct child PIDs and was ~3.3× faster than 1 worker (spawn overhead keeps this below 4× on 0.35 s jobs — expected).
- Seeded results were identical across worker counts (`idx=0 → 60/80`, `idx=1 → 61/81`, …).

### Run-compiled (PASS) — 18 Sep 08:42

Honest binary: no `freeze_support()`, no worker-mode argv guard. `sys.executable` was the compiled Mach-O. `compiled=True`. Both runs finished inside a 30 s timeout.

| Mode | Workers | Unique worker PIDs | Wall | Status |
|---|---:|---:|---:|---|
| source | 4 | 4 | 0.898 s | OK |
| **compiled** | **4** | **4** | **1.067 s** | **OK** |
| source | 1 | 1 | 2.944 s | OK |
| **compiled** | **1** | **1** | **2.871 s** | **OK** |

Answers:

- **Does the compiled binary spawn workers successfully?** Yes. Four distinct child PIDs at 4 workers (`84440, 84441, 84442, 84446`).
- **Hang, crash, infinite relaunch, or silent one-process fallback?** None of those. Pool did not break. All 8 jobs returned. 4-worker wall was ~2.7× faster than 1-worker (same as source: spawn overhead on 0.35 s jobs). Parent `sys.argv` was only the binary path — children did not re-enter `main()` as a second app launch.
- **Worker-mode entry point needed?** **No.** `q1_main_freeze.py` was not used. Nuitka 4.2.1's always-on multiprocessing plugin was enough for this pattern.
- **Source vs compiled?** Same. Seeded scores matched byte-for-byte (`idx=0 → 60/80` … `idx=7 → 67/72`) across source/compiled and 1/4 workers. No `BrokenProcessPool`.

Product implication: the spawn-pool pattern in `cpu_week_pool.py` **survives Nuitka standalone** on this box, without a worker-mode rewrite. The ~6.5× week-time cliff is **not** indicated by this spike. Residual risk: this repro is not the FastAPI/pymongo app — it is the spawn/import shape. A full-app compile could still trip on argv parsing or import-time side effects in the real entry point; the pool mechanism itself is not the blocker.

Logs: `logs/q1_compiled_4w.log`, `logs/q1_compiled_1w.log`.

---

## QUESTION 2 — Does the paint stack compile?

### What was reproduced

Copied verbatim from `~/gob-simplified`:

- `BackEnd/services/recruit_image.py`
- bundled `BackEnd/assets/fonts/LiberationSans-Bold.ttf` (the first `_find_wm_font()` candidate)

Kits/masks live in R2, not the repo. Generated a representative 900×1100 RGBA kit + L tank mask (`q2_paint/samples/`). Output canvas is still the real 3530×3412.

### Run-from-source (PASS)

```
FONT_RESOLVED=.../q2_paint/BackEnd/services/../assets/fonts/LiberationSans-Bold.ttf
FONT_EXISTS=True
FONT_IS_BUNDLED=True
FONT_IS_SYSTEM_LINUX=False
FONT_IS_SYSTEM_MAC=False
WHITE_SIZE=(3530, 3412) mode=RGBA
SIGNED_SIZE=(3530, 3412) mode=RGBA
STATUS=OK
```

The Mac system fallback (`/System/Library/Fonts/Supplemental/Arial Bold.ttf`) exists on this box and would have hidden a missed bundle. Source mode used the bundled Liberation font, not Arial, not `/usr/share/fonts/truetype/liberation/`.

Synthetic PNGs compress to ~260 KB (simple geometry). Real R2 kits at this canvas are ~10.5 MB. Size difference is input complexity, not a pipeline miss — dimensions and mode match production.

### Run-compiled — paint PASS, bundled font MISS — 18 Sep 09:36

SciPy / NumPy / Pillow **compiled and ran**. Both paint paths wrote the production canvas.

```
WHITE_SIZE=(3530, 3412) mode=RGBA
SIGNED_SIZE=(3530, 3412) mode=RGBA
WHITE sha1 a1fd3ebeb38740e86cd1b6fc8ad4e4c955479e24  (identical to source)
SIGNED sha1 66df9299526976ee264d65cecc2e2077fd21645f  (identical to source)
STATUS=FONT_FELL_BACK_TO_SYSTEM
```

Cold start of the 217 MB binary: **46 s**. Second run after the font-path diagnostic: **0.92 s**.

`--include-package=scipy` pulled the **entire** SciPy tree, including tests (`scipy.stats.tests.test_distributions` was one of the slow C files). That is why 1459 files / 46 min / 291 MB. Production should include `scipy.ndimage` (and its real deps), not `scipy.tests`.

### Bundled font — the actual Q2 defect

The TTF **was** copied into the dist:

`dist/q2/q2_main.dist/BackEnd/assets/fonts/LiberationSans-Bold.ttf` (414,568 bytes)

`_find_wm_font()` still resolved **Arial Bold**:

```
FONT_CANDIDATES[0]=.../q2_main.dist/BackEnd/services/../assets/fonts/LiberationSans-Bold.ttf
FONT_IS_BUNDLED=False
FONT_IS_SYSTEM_MAC=True
FONT_RESOLVED=/System/Library/Fonts/Supplemental/Arial Bold.ttf
```

Cause: Nuitka compiles `BackEnd.services.recruit_image` and does **not** create a real `BackEnd/services/` directory. `_find_wm_font()` builds `os.path.join(_HERE, "..", "assets", "fonts", ...)` and calls `os.path.exists` on that string **without** `normpath`. On Darwin, `exists(".../services/../assets/...")` is False when `services/` itself is missing — the kernel will not walk through a nonexistent component, even with `..`.

Confirmed without touching application code: `mkdir dist/q2/q2_main.dist/BackEnd/services` and re-run.

```
FONT_IS_BUNDLED=True
FONT_IS_SYSTEM_MAC=False
STATUS=OK
```

`os.path.normpath(candidate)` also makes `exists()` True against the file that is already in the dist.

This Mac hid the miss. A player machine will not have `/usr/share/fonts/truetype/liberation/` or `/System/Library/Fonts/Supplemental/Arial Bold.ttf`. `_find_wm_font()` then returns the first candidate anyway, and `ImageFont.truetype` raises. Wordmark stamping breaks offline.

Cheap fixes (WS-8, not done here):

1. `os.path.normpath` (and/or `os.path.realpath`) each candidate in `_find_wm_font()` before `exists()`.
2. Ship a dummy file under `BackEnd/services/` so Nuitka materializes that directory.
3. Resolve the font from a known bundle root, not `__file__` + `..`.

Liberation Sans is metrically compatible with Arial, which is why the signed SHA matched even on the fallback run — do not take that as proof the stamp is font-correct on a player box.

Logs: `logs/q2_compiled.log` (fallback), `logs/q2_compiled_fontfix.log` (after mkdir).

---

## Verdict

| Question | Result | Architecture change? |
|---|---|---|
| Q1 spawn pool survives Nuitka? | **Yes** | No. No worker-mode rewrite. |
| Q2 SciPy/NumPy/Pillow compile? | **Yes** | No. Do not drop `ndimage` or ship paint uncompiled. |
| Q2 bundled font resolves? | **Not with current `_find_wm_font()`** | Small path fix. Not a compile-stack failure. |

The December-risk items this spike was meant to catch are both green. The font bug is a packaging/path issue, cheap, and would have been a silent Mac-only pass.

---

## Isolation check

| Path | Role | Touched? |
|---|---|---|
| `~/gob-nuitka-spike/.venv` | this spike | created; Nuitka 4.2.1, Pillow 12.3.0, numpy 2.5.3, scipy 1.18.1 |
| `~/gob-simplified/venv` | other agent's measurement venv | **not activated, not pip-installed**. `site-packages` mtime still 6 Sep 2026; `pyvenv.cfg` still 18 Jul 2025 |

---

## Architecture notes (already true before compile)

1. The production pool's worker is a **module-level function**, not `__main__`. Spawn children re-import `BackEnd.utils.cpu_week_pool` and call `_worker`. That is the friendlier of the two frozen-binary patterns. The remaining risk is that `sys.executable` becomes the compiled app binary, so the child re-launches the app unless Nuitka's always-on multiprocessing plugin intercepts it.
2. Nuitka 4.2.1 enables the multiprocessing plugin by default (`isAlwaysEnabled = True`) and injects a freeze-support shim. That is why the honest (no `freeze_support`) binary is the first compiled test — if Nuitka's plugin does its job, the current application code does not need a worker-mode rewrite.
3. SciPy standalone **does** compile. The remaining Q2 work is (a) slim the include list so tests and unused subpackages are not compiled, and (b) make `_find_wm_font()` survive a missing `services/` directory in the dist tree.
