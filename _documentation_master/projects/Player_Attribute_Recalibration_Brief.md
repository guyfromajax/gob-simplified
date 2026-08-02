# Player Attribute Recalibration — Brief (entry point)

**Status: complete and validated (four-season live run).** This is the map; the detail lives in the evergreen system docs and the archived design doc.

## What it set out to do
Recalibrate players' starting attributes and their in-season / offseason progression to bring **steadiness** to the league. The original suspicion: universal-pool starting attributes were **too high** and young-player growth **too low**, from an anecdotal "steep team-talent dropoff from season 1 to season 2."

## What it actually found and shipped
The suspicion was mostly **wrong about the cause** — starting attributes weren't the problem. Measurement found and fixed a chain of real defects:

- **New position-rating formula** — five per-position weight vectors + **multiplicative** height fitness, which separates PF/C (the old additive-height formula collapsed interior positions). → `Position_Ratings_System.md`
- **Six-tier entry ladder + class-year rungs** (JH→SR ~doubles by construction); regenerated the universal pool via a rank-preserving migration. → `Player_Attribute_System.md`
- **Offseason development event** — absolute RT target × coaching factor; replaced the additive budget with a **shape attractor (α=0.55)** that targets both a level and a profile; fixed an **anchor/live desync** where in-season training silently wiped offseason growth; added **HT grow-into-frame**. This stopped the real defect — **shooting collapsing on turnover** (a big's scoring, a wing's shooting were being starved to ~half). → `Player_Development_System.md`
- **`entry_tier` persistence fix** — the season recruit write dropped `entry_tier`, so signed recruits were re-derived from undeveloped RT and **down-classified ~1.5 tiers**; the derive was also year-blind. → `Player_Development_System.md` / `Training_System.md`
- **Coaching quality** — saturating-coverage metric (points, not shares), a frozen reference, CPU trains it. **Dormant until pillar 3** wires per-player capture. → `Training_System.md`

**The s1→s2 dropoff is real but it's a *persistence* problem, not high starting attributes:** team strength rotates hard (≈3 of 13 top teams persist over four seasons), and recruiting outweighs development ~26:4 in season-over-season change. The lever is the prestige→recruiting link, not the starting scale. (See the backlog.)

## Where the detail now lives
| Topic | Doc |
|---|---|
| tiers, rungs, families, peaks, growth profile, ≥100 rate | `10_Players_Systems/Player_Attribute_System.md` |
| RT formula, weight vectors, height fitness, PF/C separation | `10_Players_Systems/Position_Ratings_System.md` |
| offseason event, shape attractor, anchor/live, grow-into-frame, invariants | `10_Players_Systems/Player_Development_System.md` |
| coaching quality, frozen reference, in-season model, CPU training | `09_Training_Systems/Training_System.md` |
| every tunable knob (levers vs calibration anchors, live vs dormant) | `11_Design_Systems/Tunable_Constants.md` |
| **the reasoning, rejected paths, and full project history** | `projects/Z-Completed/Player_Attribute_Recalibration_Design.md` |
| open items + Phase-4 tuning findings | `projects/Player_Attribute_Recalibration_Backlog.md` |
