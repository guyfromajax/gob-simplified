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
