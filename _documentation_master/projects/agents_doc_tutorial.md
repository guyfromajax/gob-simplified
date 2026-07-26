# Agent Instruction Files — Tutorial & Standing-Rule Playbook

How to give every agent (Claude Code, Codex, etc.) universal context that loads
automatically, so you stop re-explaining it per task. Written after discovering our
`docs/agents.md` was **not** at repo root and therefore likely never auto-loaded.

## The core rule: location = whether it loads

| Where the file lives | Auto-loaded? |
|---|---|
| Repo **root** (`AGENTS.md` / `CLAUDE.md`) | ✅ Yes — injected into every agent session |
| Up the directory tree from cwd (`CLAUDE.md`) | ✅ Yes (Claude Code) |
| `~/.claude/` (global) | ✅ Yes (Claude Code, all repos) |
| `docs/agents.md` or any subfolder | ❌ No — agents don't read it unless told |

**Our situation (2026-07):** repo had `docs/agents.md` but **no root `AGENTS.md`/`CLAUDE.md`**.
Confirmed not loaded — the Claude session's standing context was the memory index
(`MEMORY.md`), not `docs/agents.md`. That's why the file felt stale/ineffective.

## Which filename per tool

| Tool | Auto-loads |
|---|---|
| Claude Code | `CLAUDE.md` (root + dir tree + `~/.claude`) |
| Codex / Cursor / most others | `AGENTS.md` (repo root) |

**Multi-tool setup (we run Claude Code + Codex):** one source of truth, two names.
Make `AGENTS.md` the real file, symlink `CLAUDE.md → AGENTS.md` (or vice-versa). Both
tools read the same rules; you maintain one file.

```bash
# from repo root
git mv docs/agents.md AGENTS.md      # promote to root (or write fresh)
ln -s AGENTS.md CLAUDE.md            # Claude Code reads the same file
```

## How to write rules that actually stick

- **Short.** It loads every session — bloat is a real token cost and long files get skimmed.
- **Hard constraint, not vibes.** "Don't slow the sim" gets ignored; name the specific do-nots.
- **Attach a verification action.** A rule with "confirm the timer didn't regress" gets
  acted on; a bare principle doesn't.
- **Point to the source of truth**, don't duplicate it. Link the deep doc; keep the root
  file to the rule + the pointer.

## Reusable snippet — Sim performance invariant

Drop this into the root `AGENTS.md`/`CLAUDE.md`. Protects the pillars we built this cycle.

```markdown
**Sim performance is a protected invariant.** Before adding/altering a feature that
touches the sim, training, or week-advance paths:
- **Don't tax the hot engine path** (`motion_step_decision`, `phase_resolution`,
  `shot_manager`, `turn_manager`) with per-turn/per-shot logging or compute.
  Diagnostics stay behind `calibration_diagnostics_enabled` (off for full_sim/headless).
- **No N+1 DB access.** Never put a per-item query/write inside a loop — batch-load
  with `$in`, batch-write with `bulk_write(ordered=False)`.
- **RNG changes must be draw-safe** and per-subsystem; verify draw-count changes with a
  poison-test, not an exact diff.
- **Don't oversubscribe** the spawn pool vs. vCPUs (pymongo isn't fork-safe).
- **Measure, don't guess:** use `[FINALIZE-SUBTIMING]` / `[CPU-PERSIST-SUBTIMING]` /
  `[PS-TIMING]` / `[CPU-WEEK-TIMING]` and confirm no regression before shipping.
- Source of truth: `_documentation_master/projects/Sim_Perf_Capstone.md`.
```

## Honest expectations

- A root rule **dramatically reduces** per-task reminders — it does **not** eliminate them.
  Agents don't obey standing instructions perfectly, especially long ones.
- Compliance maximizers: **keep it short** + **name a concrete check**.
- **Belt-and-suspenders (optional):** a pre-commit/CI check that greps for new hot-path
  logging or N+1 patterns turns "requested" into "enforced." Consider if drift persists.

## Checklist to fix ours

- [ ] Promote/rewrite to root `AGENTS.md` (retire or move `docs/agents.md`).
- [ ] Symlink `CLAUDE.md → AGENTS.md`.
- [ ] Add the Sim performance invariant snippet.
- [ ] Trim the rest of the old content — delete anything dated/no-longer-true (it loads every session).

## Working practices that keep agent error rate low

Captured after a long, multi-session build (Sim Game Presentation) that shipped a
genuinely complex feature with very few errors. These are the **collaboration habits**
that did it — worth encoding as a working agreement so any agent (and the user)
defaults to them.

| Practice | What it means in action |
|---|---|
| **Trace, don't guess** | Before proposing a fix, trace the real code path / data shape and confirm the root cause with evidence (`file:line`), not inference. If a value's source is unknown, read it or ask — never assume. (This repeatedly changed the fix: e.g. "turns[] is cumulative", "RT comes from `_rt_at_position`, not the max".) |
| **Verify each piece before moving on** | Unit-test pure logic in isolation; **poison-test** guards to prove they actually fire (not just pass the happy path); app-boot check after touching any live-endpoint file; parse/compile-check before every commit. Don't stack unverified changes. |
| **Tight test-and-report loop** | Ship small increments to staging, user tests, reports **specific** findings (screenshot + console lines), iterate. Beats batching many changes and debugging them together. |
| **Scoped commits** | Commit only the files for *this* change (explicit pathspec), especially on a shared branch with concurrent agents — avoid sweeping in others' staged work. (We got bitten once by a bare `git commit` picking up a stray staged file.) |
| **Answer routing honestly** | When a task fits a different agent/approach better, say so with reasons instead of grabbing it. When a change touches a shared system, gate it so existing paths are untouched and confirm intent first. |
| **Report verified vs. inferred** | State plainly what was tested vs. what wasn't (e.g. "logic verified in node; browser render still needs your eyes"). Flag design bends/tradeoffs explicitly rather than silently adapting. |

### Reusable snippet — working agreement (drop into root `AGENTS.md`)

```markdown
**How to work here (keeps error rate low):**
- **Trace, don't guess.** Confirm root cause / data shape with file:line evidence
  before proposing a fix. If a value's source is unknown, read it or ask.
- **Verify each piece before moving on:** unit-test pure logic, poison-test guards
  to prove they fire, app-boot check after editing live-endpoint code, parse/compile
  before committing. No stacking unverified changes.
- **Small increments + report specifically.** Ship to staging, get a real test,
  report screenshot + console lines, iterate.
- **Scoped commits** (explicit paths) — the branch is shared with other agents; never
  sweep in files you didn't change.
- **Be honest:** verified vs. inferred, what wasn't tested, and any design bend —
  say it, don't paper over it.
- **Shared systems:** gate changes so existing paths are unaffected; confirm intent
  before altering a shared endpoint/behavior.
```
