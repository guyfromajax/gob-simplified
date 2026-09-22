# Zone ring repair — Stage 1: repair and show

**Lead answer.** **All 14 self-intersecting rings are repairable by reorder alone** — same spots, same membership, different order, and every one comes out as a simple polygon with its area recovered from roughly half the intended region to 89–103% of it. But only **3 of the 14 are clean**: in the other 11 the spot list contains spots that lie *inside* the convex hull of its own set, so the repaired ring carries a notch or a thin spike around them. Those 11 are not blocked — they produce sane simple regions — but the notch is a basketball judgement and they are flagged for you in the pictures rather than asserted as correct. **2 zones need a design call and are not repaired here**: the two single-spot 1-3-1 corner-shift centres, for which three candidate spot sets are proposed and none chosen. **Repair opens no uncovered area** — the set of half-court spots covered by no defender is byte-for-byte identical before and after in all 11 tables. It does *increase* double-covered area, in one case from 40.0 to 88.0 square units, which is a real finding for the overlap rung and is set out in S1-d. Nothing is landed and no reference was re-cut.

## Footing (rule 6e)

- **Tree:** `feature/animation-reward` at **`52b0b2d6e`**. **No games were run in this pass** — every number here is static geometry over the tables in `BackEnd/utils/shared_defense.py:14-116`, so no arm or `_is_full_simulation` state applies. Stage 2 is where the footing clause bites.
- **Method:** areas are the ray-cast interior of `_point_in_polygon` sampled at 0.25 units; self-intersection is an all-pairs segment test over the ring excluding adjacent edges; the hull is a monotone-chain convex hull of the spot set.
- **Nothing landed.** `git diff HEAD` over tracked files is empty; the only new files are this report and its visual.
- Analysis scripts (session scratchpad, uncommitted): `zr/geo.py`, `zr/draw.py`.

## S1-a: Inventory — the count is 16, confirmed

All 55 definitions were measured. **16 are broken: 14 self-intersecting rings and 2 single-spot lists.** The report's count stands.

| defect | count | which |
|---|---|---|
| **single-spot list** (`< 3` guard → `_point_in_polygon` is False for every point) | **2** | `ZONE_131_LOWER_CORNER_SHIFT["C"]`, `ZONE_131_UPPER_CORNER_SHIFT["C"]` |
| **self-intersecting ring** | **14** | 2-3 NORMAL PG/SF/PF · 2-3 LOWER_SHIFT SG/SF/PF · 2-3 UPPER_SHIFT PG/SF/PF · 3-2 LOWER_SHIFT PF · 3-2 UPPER_SHIFT C · 1-3-1 NORMAL C · 1-3-1 LOWER_SHIFT C · 1-3-1 UPPER_SHIFT C |
| **duplicate vertices** (subset of the above) | 3 | `ZONE_32_LOWER_SHIFT["PF"]`, `ZONE_32_UPPER_SHIFT["C"]`, `ZONE_131_NORMAL["C"]` |
| sound | 39 | |

**One thing the inventory adds that the earlier report did not say:** the problem is not confined to the 16. **13 of the 39 "sound" rings also contain spots inside their own hull** — for example `ZONE_32_NORMAL["PF"]` and `["C"]` (2 each, testing 110.6 and 109.8 against a 146.0 hull), and `ZONE_131_NORMAL["PG"]` (3, testing 253.4 against 352.5). They happen to be written in an order that does not cross, so they are valid polygons, but they are still dented. **The underlying cause is that these lists were written as membership lists — "the spots this defender covers" — not as boundary walks.** The 16 are where that assumption broke visibly; the dents are where it broke quietly. Repairing the 16 does not change that, and a later pass may want to revisit whether interior spots belong in these lists at all. That is a redesign, out of scope here.

Full 55-row inventory is in the scratchpad output; the 14 repaired rows are tabulated in S1-b below.

## S1-b: The 14 self-intersecting rings, repaired by reorder

Every repair is **the same spot set in a different order**. No spot was added or removed — asserted programmatically for all 14 (`set(before) == set(after)`, column below). Where a ring had duplicate vertices they were **de-duplicated as part of that ring's repair**, which is the only place the brief allows it: `ZONE_32_LOWER_SHIFT["PF"]` (11 entries → 9), `ZONE_32_UPPER_SHIFT["C"]` (11 → 9), `ZONE_131_NORMAL["C"]` (13 → 11). All three duplicates were `basketSpot` / `midLane` repeats left behind by appending the shift spot to a copied list.

| table | pos | spots | area before | area after | hull | interior spots | set unchanged |
|---|---|---|---|---|---|---|---|
| `ZONE_23_NORMAL` | PG | 6 | 159.3 | **212.6** | 210.0 | **0** | yes |
| `ZONE_23_NORMAL` | SF | 7 | 55.2 | 92.3 | 98.0 | 1 | yes |
| `ZONE_23_NORMAL` | PF | 7 | 51.7 | 84.3 | 90.0 | 1 | yes |
| `ZONE_23_LOWER_SHIFT` | SG | 8 | 119.1 | 151.4 | 157.5 | 2 | yes |
| `ZONE_23_LOWER_SHIFT` | SF | 7 | 55.2 | 92.3 | 98.0 | 1 | yes |
| `ZONE_23_LOWER_SHIFT` | PF | 7 | 51.7 | 84.3 | 90.0 | 1 | yes |
| `ZONE_23_UPPER_SHIFT` | PG | 8 | 106.4 | 136.4 | 142.5 | 2 | yes |
| `ZONE_23_UPPER_SHIFT` | SF | 7 | 55.2 | 92.3 | 98.0 | 1 | yes |
| `ZONE_23_UPPER_SHIFT` | PF | 7 | 51.7 | 84.3 | 90.0 | 1 | yes |
| `ZONE_32_LOWER_SHIFT` | PF | 9 | 176.4 | 211.1 | 237.0 | 3 | yes |
| `ZONE_32_UPPER_SHIFT` | C | 9 | 175.7 | 211.1 | 236.5 | 3 | yes |
| `ZONE_131_NORMAL` | C | 11 | 123.7 | **224.6** | 247.0 | 4 | yes |
| `ZONE_131_LOWER_SHIFT` | C | 4 | 14.2 | **27.2** | 26.5 | **0** | yes |
| `ZONE_131_UPPER_SHIFT` | C | 4 | 13.9 | **27.2** | 26.5 | **0** | yes |

**Self-intersection: 14 before, 0 after.** Every repaired ring passes the segment-pair test.

(Where the after-area slightly exceeds the hull — 212.6 vs 210.0, 27.2 vs 26.5 — that is the rasteriser counting the boundary band plus the 0.01 on-edge tolerance in `_point_in_polygon`, not extra region. The two are the same polygon.)

**The three clean ones** — `ZONE_23_NORMAL["PG"]`, `ZONE_131_LOWER_SHIFT["C"]`, `ZONE_131_UPPER_SHIFT["C"]` — have every spot on the hull, so the repaired ring is the *only* simple ring through them. These need no judgement; they are simply right.

**The eleven with a notch.** These reach 89–96% of hull area. The shortfall is not error, it is the dent forced by putting an interior spot on the boundary. The two shapes worth looking at hardest in the visual:

- **`ZONE_32_LOWER_SHIFT["PF"]` and `ZONE_32_UPPER_SHIFT["C"]`** (89%) — these sets bolt the ball-side corner onto the *weak-side* big's zone, so the repaired ring is a broad upper region with a thin spike reaching across to the far corner. Geometrically simple, but the set itself is odd and the spike carries almost no area. If the intent was "the weak-side big also has the ball-side corner", the spike is what that looks like; if the intent was something else, this is the one to reject.
- **`ZONE_131_NORMAL["C"]`** (91%, 4 interior spots) — the baseline-wrapping centre. The repair nearly doubles it (123.7 → 224.6) but leaves a visible notch where the interior spots sit.

**No ring had to be abandoned.** The brief's escape hatch — "where a reorder alone cannot produce a sane region, say so and stop rather than adding spots" — was not needed: all 14 produced simple rings. But *sane* is your call, not the algorithm's, which is why the eleven are flagged rather than declared done.

**One related observation, not a repair:** even after repair, `ZONE_131_LOWER_SHIFT["C"]` and `ZONE_131_UPPER_SHIFT["C"]` are only **27.2** square units — a sliver from the rim out to the corner, against 122.6 for the PF beside them. They are now valid, but they are tiny. Whether a 1-3-1 centre should own a sliver that thin on a wing shift is a design question adjacent to S1-c, not a geometry defect. Flagging, not changing.

### Proposed lists (review before landing — nothing written to source)

```python
# ZONE_23_NORMAL
    "PG": ["key", "topLane", "midLane", "upper midCorner", "upper wing", "upper midWing"],
    "SF": ["lower apex", "lower midCorner", "lower corner", "lower midBaseline", "lower bird", "lower lowPost", "lower midPost"],
    "PF": ["upper midPost", "upper lowPost", "upper bird", "upper midBaseline", "upper corner", "upper midCorner", "upper apex"],

# ZONE_23_LOWER_SHIFT
    "SG": ["lower wing", "lower midCorner", "lower corner", "lower midBaseline", "lower apex", "lower bird", "lower midPost", "lower highPost"],
    "SF": ["lower apex", "lower midCorner", "lower corner", "lower midBaseline", "lower bird", "lower lowPost", "lower midPost"],
    "PF": ["upper midPost", "upper lowPost", "upper bird", "upper midBaseline", "upper corner", "upper midCorner", "upper apex"],

# ZONE_23_UPPER_SHIFT
    "PG": ["upper wing", "upper highPost", "upper midPost", "upper bird", "upper apex", "upper midBaseline", "upper corner", "upper midCorner"],
    "SF": ["lower apex", "lower midCorner", "lower corner", "lower midBaseline", "lower bird", "lower lowPost", "lower midPost"],
    "PF": ["upper midPost", "upper lowPost", "upper bird", "upper midBaseline", "upper corner", "upper midCorner", "upper apex"],

# ZONE_32_LOWER_SHIFT   (de-duplicated: basketSpot, midLane)
    "PF": ["midLane", "lower corner", "upper midBaseline", "basketSpot", "upper bird", "upper lowPost", "upper corner", "upper midCorner", "upper midPost"],

# ZONE_32_UPPER_SHIFT   (de-duplicated: basketSpot, midLane)
    "C": ["lower midPost", "lower midCorner", "lower corner", "lower lowPost", "lower bird", "basketSpot", "lower midBaseline", "upper corner", "midLane"],

# ZONE_131_NORMAL       (de-duplicated: basketSpot x2)
    "C": ["lower midPost", "lower midCorner", "lower corner", "lower midBaseline", "upper midBaseline", "lower lowPost", "lower bird", "upper lowPost", "basketSpot", "upper corner", "midLane"],

# ZONE_131_LOWER_SHIFT
    "C": ["lower lowPost", "lower corner", "lower midBaseline", "basketSpot"],

# ZONE_131_UPPER_SHIFT
    "C": ["upper lowPost", "basketSpot", "upper midBaseline", "upper corner"],
```

## S1-c: The two single-spot zones — proposals only

`ZONE_131_LOWER_CORNER_SHIFT["C"] = ["lower corner"]` and `ZONE_131_UPPER_CORNER_SHIFT["C"] = ["upper corner"]`. One point is not a polygon, so **these two defenders match nobody, ever** — rungs a/c/d are unreachable and they are pinned to a single coordinate by construction.

Context for the lower-corner shift, so the hole is legible: with the ball in the lower corner, **SF** has the ball-side perimeter (`lower midWing`, `lower wing`, `lower midCorner`), **PF** has the lane column, **SG** covers the entire weak side, **PG** covers the top. The centre is the only one left for the corner itself — and he cannot take it. Four real half-court spots end up covered by nobody: **`lower corner`, `lower midBaseline`, `lower bird`, `basketSpot`.**

Three candidates. Each is a simple ring; the upper-corner zone takes the mirror of whichever is chosen. **Pictures are in the visual, Part 2. Nothing is chosen.**

| | spots | area | fills of the 4 holes | who ends up sharing | what it says about the defence |
|---|---|---|---|---|---|
| **A — corner pocket** | `lower corner`, `lower midCorner`, `lower bird`, `lower midBaseline` | 49.3 | 3 of 4 (not `basketSpot`) | **SF** (`lower midCorner` double-covered) | C closes out the corner and the short baseline. The rim stays PF's. Largest area of the three, but it reaches back up into SF's perimeter, so the corner becomes a two-defender area resolved by the overlap rung. |
| **B — corner + baseline to the rim** | `lower corner`, `lower midBaseline`, `basketSpot`, `lower lowPost`, `lower bird` | 38.1 | **4 of 4** | **PF** (`lower lowPost` double-covered) | C becomes the baseline defender — corner, baseline drive lane and the rim. The only candidate that closes the `basketSpot` hole. Biggest change to who guards what; frees PF toward the high post. |
| **C — corner + short baseline** | `lower corner`, `lower midBaseline`, `lower lowPost`, `lower bird` | 26.8 | 3 of 4 (not `basketSpot`) | **PF** (`lower lowPost`) | The middle option: corner plus baseline up to the low post, rim still PF's. Smallest area, least disruption to the other four zones. |

The trade-off in one line: **A** keeps the rim with the PF and makes the corner a shared perimeter problem; **B** makes the centre a true baseline defender and is the only one that stops leaving the rim uncovered; **C** is the conservative middle. Your call.

## S1-d: Overlap and coverage, before and after

Coverage measured two ways: rasterised area over the union bounding box (0.5-unit sampling), and the 24 real half-court spots from `HCO_STRING_SPOTS` (backcourt, inbound, `hct_*` and `deep *` spots excluded — no zone should cover those).

| table | ≥1 zone area | | ≥2 zone area (the overlap rung's material) | | uncovered real spots |
|---|---|---|---|---|---|
| | before | after | before | after | before → after |
| `ZONE_23_NORMAL` | 511.8 | **623.2** | 15.2 | **23.5** | 1 → 1 (same) |
| `ZONE_23_LOWER_SHIFT` | 535.2 | **586.2** | 40.0 | **88.0** | 1 → 1 (same) |
| `ZONE_23_UPPER_SHIFT` | 534.2 | **586.0** | 35.2 | **80.0** | 1 → 1 (same) |
| `ZONE_32_NORMAL` | 654.2 | 654.2 | 9.8 | 9.8 | 0 → 0 (same) |
| `ZONE_32_LOWER_SHIFT` | 659.5 | 663.2 | 69.5 | **100.5** | 0 → 0 (same) |
| `ZONE_32_UPPER_SHIFT` | 660.2 | 663.8 | 68.8 | **100.5** | 0 → 0 (same) |
| `ZONE_131_NORMAL` | 578.2 | **649.8** | 33.5 | **64.0** | 0 → 0 (same) |
| `ZONE_131_LOWER_SHIFT` | 452.2 | 465.0 | 14.2 | 14.2 | 1 → 1 (same) |
| `ZONE_131_LOWER_CORNER_SHIFT` | 478.0 | 478.0 | 53.2 | 53.2 | 4 → 4 (same) |
| `ZONE_131_UPPER_SHIFT` | 466.2 | 479.5 | 14.8 | 14.8 | 1 → 1 (same) |
| `ZONE_131_UPPER_CORNER_SHIFT` | 495.0 | 495.0 | 59.8 | 59.8 | 4 → 4 (same) |

**No gap is opened.** The set of uncovered real spots is *identical* before and after in all eleven tables — not merely the same count, the same spots. Repair only ever adds covered area.

**The pre-existing gaps, which repair does not fix and which you should know about:**

| table | uncovered real spot(s) | note |
|---|---|---|
| all three **2-3** variants | **`basketSpot`** | **the rim itself is in no 2-3 defender's zone.** Pre-existing, unchanged by repair, and not something a reorder can fix — no 2-3 spot list contains `basketSpot`. Fixing it means adding a spot, which is a redesign. |
| `ZONE_131_LOWER_SHIFT` / `UPPER_SHIFT` | `lower bird` / `upper bird` | one weak-side baseline spot each |
| `ZONE_131_*_CORNER_SHIFT` | `basketSpot`, `bird`, `corner`, `midBaseline` | the S1-c hole — closed by whichever candidate you pick (fully by B, 3 of 4 by A or C) |

**The finding that is not neutral: repair materially increases double-covered area.** `ZONE_23_LOWER_SHIFT` goes from 40.0 to 88.0 square units (+120%), `ZONE_23_UPPER_SHIFT` 35.2 → 80.0, `ZONE_131_NORMAL` 33.5 → 64.0, the two 3-2 corner shifts 69 → 100.5. This is the expected consequence of each zone finally covering its intended region — neighbours that should abut now genuinely do — but it is not cosmetic. **The overlap rung already resolves 38.8% of all zone defender-steps** (the largest rung, per `reports/zone-empty-branch-2026-09-18.md`), and this will push it higher. Two defenders will be credited with the same offensive player more often, which means `_resolve_overlap_assignments` and `_apply_multi_defender_offsets` will both do more work, and the `random.choice` at `phase_resolution.py:8747` will fire more often. **Measuring that is Stage 2, and it should be measured explicitly per rung, not just as a net outcome.** If the overlap rung grows a lot, that is an argument for auditing `_resolve_overlap_assignments`, which has never been looked at.

## S1-e: The pictures

**`reports/zone-ring-repair-visual-2026-09-18.md`** — ASCII half-court, before and after side by side, for all 14 repaired rings plus the three S1-c candidates. Panels are zoomed to the zone region (x 62–92 at 1 unit per character, y 4–46 at 2 units per row, offense attacking the rim on the right) so the shapes are actually readable; `#` is the ray-cast interior, `*` a listed spot, `R` the rim, `.` a neighbouring zone in the design-call panels.

**This is the deliverable to approve or reject from.** The eleven notched rings are labelled as such in their own panel headers.

## S1-f: Stop

**Stage 1 ends here.** Nothing was landed, no repaired data was written to `shared_defense.py`, no game was simulated, and neither reference was touched — played stands at `d9a4f1517` and sim at `equiv_v3_sim_reference_9910cd6fd.json`, both unchanged and unqueried in this pass.

**What Stage 2 needs from you before it can start:**
1. Approve or reject the 14 repaired rings — in particular the eleven notched ones, and most particularly the two 3-2 corner-shift spikes.
2. Pick A, B or C for the 1-3-1 corner-shift centre (or reject all three).
3. Decide whether the pre-existing `basketSpot` gap in the 2-3 is in scope. It is a spot-set change, not a reorder, so it would be a separate commit from the repair.

## Not covered

- **Nothing was landed and no measurement was run.** No placement logic, constant, threshold or balance number was touched.
- `assign_zone_defender_coords` and its ladder — including the empty-zone branch — were not touched. This pass fixes the cause, not the fallback.
- `_point_in_zone` / `_point_in_polygon` were not touched. **The ray-cast is correct; the data was wrong.** No algorithm change is recommended.
- The crash flags, `animator.py:1213`, the `randint(1,6)`, the rebound path, R1 (Final Turn) and R2 (stopper) were not touched.
- **The 13 sound-but-dented rings were inventoried and left alone** — they are valid polygons and outside the brief's 16.
- The HCT zone tables further down `shared_defense.py` were not inventoried; the brief scoped this to the 55 definitions in the 2-3 / 3-2 / 1-3-1 tables.
