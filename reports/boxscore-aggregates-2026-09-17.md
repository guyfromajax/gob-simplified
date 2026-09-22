# Box-score aggregates at the shipped defaults, n=40

Written for: Jamie, before any tuning decision. Measurement only — no code changed, nothing committed but this report.

**Short answer.** Seed 8000 was **not typical**: its free throws (p96), steals (p99), one team's fouls (p94) and turnovers (p94) all sit in the top decile of the 40-game field. Fouls are still high in the mean (25.3 per team per game), but the flags did not cause that — **fouls per possession are flat** (0.362 → 0.355, not resolved) while fouls per game fell only because the clock flag removed possessions. And the "possessions" number in this week's reports is **not a tempo number**: on the standard estimate the engine runs ~71 possessions per team at **1.05 points per possession**, which is normal.

## Footing (rule 6e)

- **Worker:** equiv-v3 `scratch_equiv3_fbdedupe.py`. Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`.
- **Tree:** `c2cf4d714`, both crash flags at their shipped ON defaults unless a row says "flags OFF".
- **Sim arm:** `ARM=sim`, `_is_full_simulation` **True** at Pattern A. **Played arm:** `ARM=played`, `_is_full_simulation` **False only inside the four gated Animator methods**.
- **Seeds 8000–8039 (n=40 games = 80 team-games per cell), CI = 1.96 × SEM.**
- **Probe integrity:** sim rows **80/80** identical to `equiv_v3_sim_reference_9910cd6fd.json`; played rows **80/80** identical to `d9a4f1517`.

## 1. Per team per game — production footing (`SEED_DEFENSES=1`)

| stat | sim mean ±CI | played mean ±CI |
|---|---|---|
| **PF** | **25.34 ±1.55** | 26.10 ±1.57 |
| **FTA** | **24.60 ±2.34** | 25.40 ±2.31 |
| FTM | 19.26 ±1.93 | 20.21 ±1.81 |
| FT% | 77.73 ±2.15 | 79.90 ±1.86 |
| FGA | 53.70 ±1.26 | 51.20 ±0.95 |
| FGM | 24.76 ±0.95 | 22.68 ±0.92 |
| FG% | 46.35 ±1.78 | 44.52 ±1.91 |
| 3PA | 18.24 ±0.88 | 17.20 ±0.94 |
| 3PM | 6.17 ±0.51 | 5.79 ±0.52 |
| 3P% | 33.99 ±2.49 | 33.82 ±2.83 |
| OREB | 8.26 ±0.79 | 8.41 ±0.72 |
| DREB | 23.65 ±0.97 | 23.34 ±1.15 |
| AST | 14.41 ±0.74 | 14.06 ±0.81 |
| **TO** | **15.19 ±0.92** | 15.85 ±1.01 |
| **STL** | **8.44 ±0.66** | 8.90 ±0.76 |
| BLK | 4.71 ±0.47 | 4.94 ±0.53 |
| PTS | 74.96 ±2.53 | 71.35 ±2.25 |

Combined per game (both teams): **50.7 fouls, 49.2 FTA, 30.4 turnovers, 16.9 steals** on sim.

### Distributions (p10 / p50 / p90), `SEED_DEFENSES=1`

| stat | sim | played |
|---|---|---|
| PF | 16 / 25 / 36 | 16 / 26 / 36 |
| FTA | 11 / 24 / 40 | 11 / 25 / 40 |
| FTM | 8 / 18 / 32 | 10 / 19 / 32 |
| FT% | 67 / 79 / 89 | 72 / 81 / 91 |
| FGA | 46 / 54 / 60 | 47 / 51 / 56 |
| FGM | 19 / 25 / 30 | 17 / 23 / 28 |
| FG% | 35 / 47 / 58 | 35 / 45 / 57 |
| 3PA | 13 / 18 / 23 | 12 / 17 / 23 |
| 3PM | 3 / 6 / 9 | 2 / 6 / 9 |
| 3P% | 18 / 33 / 50 | 20 / 33 / 53 |
| OREB | 5 / 8 / 13 | 5 / 8 / 12 |
| DREB | 18 / 24 / 30 | 17 / 23 / 31 |
| AST | 10 / 14 / 19 | 10 / 14 / 20 |
| TO | 11 / 15 / 21 | 10 / 16 / 22 |
| STL | 5 / 8 / 13 | 5 / 8 / 14 |
| BLK | 2 / 5 / 7 | 2 / 5 / 8 |
| PTS | 60 / 75 / 90 | 59 / 71 / 86 |

The spread is wide: fouls run 16 to 36 per team at the deciles, FTA 11 to 40.

### `SEED_DEFENSES=0` (control footing, empty defense catalogue)

| stat | sim | played |
|---|---|---|
| PF | 28.25 ±1.89 (18/27/41) | 29.41 ±1.80 (19/30/40) |
| FTA | 29.51 ±2.75 (17/28/49) | 31.20 ±2.85 (13/30/52) |
| FTM / FT% | 23.04 ±2.29 / 77.94 | 24.34 ±2.33 / 77.76 |
| FGA / FGM / FG% | 52.06 / 22.65 / 43.71 | 52.85 / 22.96 / 43.81 |
| 3PA / 3PM / 3P% | 14.18 / 4.45 / 31.48 | 15.07 / 4.71 / 30.77 |
| OREB / DREB | 8.82 / 24.32 | 8.68 / 25.26 |
| AST / TO / STL / BLK | 13.31 / 13.36 / 7.64 / 5.86 | 14.30 / 14.26 / 8.24 / 6.45 |
| PTS | 72.79 ±2.98 | 74.97 ±2.43 |

Fouls and free throws are **higher** on the control footing than in production (28.3 vs 25.3 PF, 29.5 vs 24.6 FTA).

### Where seed 8000 sits (sim, `SEED_DEFENSES=1`, percentile among 80 team-games)

| stat | Lancaster | Bentley-Truman |
|---|---|---|
| PF | 23 (p34) | **37 (p94)** |
| FTA | **43 (p96)** | 21 (p39) |
| FTM | **34 (p95)** | 16 (p34) |
| FGA | 58 (p72) | 55 (p52) |
| FGM | 25 (p44) | **32 (p94)** |
| 3PA / 3PM | 18 (p45) / 7 (p58) | 20 (p61) / 8 (p70) |
| OREB | 10 (p72) | 10 (p72) |
| DREB | 17 (p4) | 29 (p85) |
| AST | 15 (p52) | 15 (p52) |
| TO | 13 (p29) | **23 (p94)** |
| STL | **17 (p99)** | 6 (p15) |
| BLK | 6 (p61) | **10 (p98)** |
| PTS | **91 (p92)** | 88 (p82) |

**Was seed 8000 typical? No.** Eight of its 28 team-stat lines sit at or above the 90th percentile and it contains the single most extreme steals line in the 40-game field (17, p99). Its 60 combined fouls vs a 50.7 mean, and 64 combined FTA vs 49.2, are both roughly a 20% overshoot. The underlying concern is real but smaller than that game suggests: fouls and FTA are high in the mean too, just not that high.

## 2. Did the flags cause any of it? (sim arm, `SEED_DEFENSES=1`, paired n=40)

| stat | flags OFF | flags ON | Δ (paired) | resolved |
|---|---|---|---|---|
| PF | 28.40 | 25.34 | −3.06 ±2.04 | **yes** |
| FTA | 29.20 | 24.60 | −4.60 ±3.58 | **yes** |
| FTM | 23.11 | 19.26 | −3.85 ±3.05 | **yes** |
| FGA | 58.05 | 53.70 | −4.35 ±1.59 | **yes** |
| FGM | 26.75 | 24.76 | −1.99 ±1.16 | **yes** |
| 3PA | 18.84 | 18.24 | −0.60 ±1.08 | no |
| 3PM | 6.13 | 6.18 | +0.05 ±0.65 | no |
| OREB | 8.94 | 8.26 | −0.68 ±1.08 | no |
| DREB | 25.70 | 23.65 | −2.05 ±1.25 | **yes** |
| AST | 15.94 | 14.41 | −1.53 ±1.04 | **yes** |
| TO | 16.70 | 15.19 | −1.51 ±1.22 | **yes** |
| STL | 9.39 | 8.44 | −0.95 ±0.86 | **yes** |
| BLK | 5.91 | 4.71 | −1.20 ±0.70 | **yes** |
| PTS | 82.74 | 74.96 | −7.78 ±3.09 | **yes** |
| estimated possessions | 78.66 | 71.45 | −7.21 ±1.54 | **yes** |
| **fouls per estimated possession** | **0.3619** | **0.3545** | **−0.007 ±0.026** | **no** |
| **fouls per harness flip** | **0.6036** | **0.5887** | **−0.015 ±0.050** | **no** |

**Answer: purely the possessions.** Every counting stat fell by roughly the same proportion as possessions (−9.2% possessions, −10.8% fouls, −15.8% FTA), and both foul *rates* are flat and unresolved. Nothing in the foul logic changed — the flags only shortened the game in possession terms.

## 3. What is a "possession" in this harness?

**Definition.** The worker computes it at `scratch_equiv3_fbdedupe.py:364`:

```python
poss = sum(1 for t in turns if t.get("possession_flips"))
```

It counts **turns carrying the `possession_flips` flag**, which the engine sets when a turn hands the ball to the other team. Measured per game (sim, `SEED_DEFENSES=1`), the flag is set on:

| turn | per game |
|---|---|
| HCO MISS | 26.70 |
| HCO BLOCK | 7.33 |
| FREE_THROW | 5.25 |
| FAST_BREAK MISS | 1.90 |
| HCT MISS | 1.43 |
| FCP MISS | 1.12 |
| DREB FOUL | 0.03 |

**It is essentially "missed shots the defense rebounded, plus trips ending at the line".** Made baskets are not in the list — the possession change after a make is carried by the following BASELINE_INBOUND turn, which does not set the flag — and neither are live-ball turnovers routed through their own turn types.

**Standard estimate** (`FGA − OREB + TO + 0.44 × FTA`), per team per game:

| | estimated possessions | points per estimated possession |
|---|---|---|
| sim, `SEED_DEFENSES=1` | **71.45 ±0.95** | **1.048 ±0.031** |
| played, `SEED_DEFENSES=1` | 69.81 ±0.86 | 1.023 ±0.031 |
| sim, `SEED_DEFENSES=0` | 69.59 ±0.94 | 1.043 ±0.036 |
| played, `SEED_DEFENSES=0` | 72.17 ±0.77 | 1.039 ±0.031 |

**Plainly: the "possessions" figure in this week's reports is an internal unit, not tempo.** It counts about 43.75 flag-bearing turns per game against roughly 143 real possessions (71.45 per team × 2), so it captures under a third of them, and only a biased third — defensive rebounds and free throws. Any conclusion of the form "X points per possession" drawn from it is wrong by roughly 3×; the 1.71 figure in the earlier reports is such a number. What the counter is still valid for is **relative** comparison of the same quantity between arms or flag states (it moved −9.4% when the clock flag removed time, which the estimate corroborates at −9.2%).

On the standard estimate the engine's tempo (~71 possessions) and efficiency (~1.05) are both in normal basketball range.

## 4. Usage distribution

Per team-game, "starter" = the five on the floor at tipoff.

| cell | starter share of MIN | of FGA | of PTS | bench players with MIN > 0 | individual PTS p50 / p90 / max | game-high scorer is a bench player |
|---|---|---|---|---|---|---|
| sim `D=1` | 58.2% | 63.1% | 71.6% | 6.74 | 4 / 16 / 39 | **0%** |
| played `D=1` | 57.9% | 61.4% | 70.2% | 6.74 | 4 / 14 / 37 | 0% |
| sim `D=0` | 58.4% | 62.6% | 70.7% | 6.71 | 4 / 15 / 39 | 0% |
| played `D=0` | 57.9% | 63.0% | 73.3% | 6.74 | 4 / 16 / 44 | 0% |

**The 12-for-12, 32-point "bench" player was a starter.** `GameManager.get_box_score` labels rows by the lineup **at the final buzzer**, so anyone substituted out before the end appears as `BENCH_<id>` regardless of whether he started. In seed 8000, Trent Athens was in Bentley-Truman's tipoff five, played 1,152 of the game's 1,920 clock-seconds, and led all scorers. Across all 160 team-games measured here, the game's leading scorer was never an actual non-starter.

**Two things to be aware of when reading these box scores** (reported, not fixed):
- The `BENCH` / `BENCH_<id>` labels mean "off the floor at the buzzer", not "did not start".
- The `MIN` column is in **game-seconds**, not minutes: the five on the floor accumulate ~9,250 of a possible 9,600 (4 × 480 s × 5) per team-game.

## Not covered

- No engine logic, constant, threshold or default was changed; nothing was tuned; no commits.
- The played arm, `animator.py:1213`, the crash flags, the `randint(1,6)` and the rebound path were not touched.
- No tuning recommendations: the calls are Jamie's.
- The box score at `reports/box-score-sim-seed8000-2026-09-17.md` is left as it is, including its end-of-game position labels.
