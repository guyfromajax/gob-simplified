# READY — crash Model A landed at t=0.7. Clean. Eye test next, then the reorder.

Report: `reports/crash-model-a-land-2026-09-19.md`. Four commits, flag ON by default.
New reference for both arms: `equiv_v3_reference_bf7ed1181_crashmodela.json`.

**The target was met.** Crasher-to-bounce x error no longer grows with shot distance:
before it ran 4.0 -> 8.0 across the bands, now 3.0 -> 4.0. y unchanged, as predicted.
§8.1 guard: **0 corrections** in every cell. All gates pass. Escape hatch reproduces
the previous reference 40/40. **Arm gap now +0.01** — sim and played score the same.

**Sim rebounder unchanged, exactly as predicted: OREB share +0.00.** Selection runs
before crash authoring, so it cannot move — and it didn't.

**Played OREB share moved +2.77** — but played's *before* was the outlier (23.3% vs
sim's 26.3%), and both now sit at ~26.1-26.4%. The flag brought played into line.
Mechanism located, not isolated: three proximity filters read `player.coords`, which
crash destinations write to — `NEAR_BOUNCE_REBOUND_ATTEMPTOR_DISTANCE`,
`FAST_BREAK_REBOUND_GEO_DISTANCE`, and the FT-rebound filter. So crash position
already partly reaches rebounding.

**One correction to my brief:** I said draws must be unchanged. Not achievable —
`randint` rejection-samples, so underlying draws depend on range width. Call count is
exactly 2 per crasher (the design property holds); raw draws shift a few hundred.
The agent fixed the docstring that claimed draw-neutrality.

Short bands came in at 6.3 vs a predicted 4.0 — because ~3% of bounces don't come from
the distance model at all (block spots, fast-break path). The model is fine; the
prediction was too clean.

**Next:** eye test (merge down — visible on every shot), then the reorder.
