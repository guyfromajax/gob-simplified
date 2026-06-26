# Aggression System

Game-plan **Aggression** (passive / normal / aggressive) affects how often pressure turns produce events — steals, turnovers, and fouls — once a defender is already engaged with the ball handler. It does **not** decide who wins that encounter; it only turns the volume up or down on what happens next.

Implementation: `HCT_D8_*` constants and `_resolve_moment()` in `BackEnd/engine/dynamic_hct.py`. FCP and HCT share the full D8 path; HCO reuses the same math at half strength with extra gates (below).

---

## FCP / HCT vs HCO

Both paths use the same D8 bases and the same per-turn **`aggression_call`** multiplier (passive **0.7×**, normal **1.0×**, aggressive **1.3×**). HCO applies the same formula but at lower frequency and only on some possessions.

| | FCP / HCT | HCO |
|---|-----------|-----|
| **Shared D8 bases (decisive win, before agg)** | Defense wins → **30%** any event (`DEF_WIN_BASE 0.30`). Offense wins → **20%** reach-in (`DFOUL_BASE 0.20`). | Same constants |
| **Rate scaler** | Full strength (`event_scalar = 1.0`) | **Half strength** (`HCO_MOMENT_SCALAR = 0.5`) → effective peaks ~**15%** / ~**10%** at decisive margin |
| **When step checks run** | Every press/trap loop beat with a defender in range | Only after an **engagement roll** passes; then checked per motion skeleton step |
| **Engagement gate** | None — always contest when geometry says so | **Strategy slider 0–4** → **5%–75%** of possessions attempt any moment (`MOMENT_ENGAGEMENT_PCT_BY_AGGRESSION`) |
| **Team ratings in the contest** | `pt_efficiency` (def) / `pt_opp_modifier` (off) | `defensive_efficiency` / `offensive_efficiency` |
| **`aggression_call` inside the check** | Yes — scales event rate and reach-ins; steals get an extra agg bump | Yes — same multiplier when a moment actually fires |
| **Defense-wins cap** | **60%** max on any turnover event (`P_EVENT_MAX`) | Same cap (before the 0.5 scalar) |
| **Offense-wins cap** | None (valid probability 0–100% only) | Same |
| **Not covered by D8** | Pass interceptions (§14), FCP engagement geometry, steal→FB odds (0–4 slider) | Pass interceptions, hot-read lane width, motion step decisions |

**Plain read:** Tuning `DEF_WIN_BASE` / `DFOUL_BASE` moves **FCP and HCT directly**. HCO moves in the **same direction** but about **half as much**, and only on possessions that pass the separate engagement % roll first.

For designer tuning detail on the press/trap path, see **Aggression for designers (D8)** in [`FCP_System.md`](./FCP_System.md) and [`HCT_System.md`](./HCT_System.md).
