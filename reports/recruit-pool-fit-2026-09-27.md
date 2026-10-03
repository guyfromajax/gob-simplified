# Recruit pool fit at 1280 — 2026-09-27

Branch `ux/recruit-pool-fit`. The Lean column stays at the right edge, next to the watch star. Step (a) was enough. The name column was not capped, height and weight stayed separate, and Lean was not moved.

Content width at 1280 is 1180px (rail 64, page padding 18 each side). The pool scrollport is 1178px inside its border.

## Before (rendered, 1280)

Passive week, table 1288. Lean's right edge sat 109px past the content edge.

| Column | Width |
| --- | ---: |
| Watch | 44 |
| Recruit | 248 |
| POS | 44 |
| RT | 86 |
| YR | 40 |
| HT | 52 |
| WT | 44 |
| RGN | 44 |
| 12 attributes | 38 each (456) |
| Lean | 230 |
| **Total** | **1288** |

Invite week added the add/rank cell at 46. Table 1334.

The Lean column was 230 because of `min-width: 230px` and 14px of padding on each side. The ladder itself is 168px (three 52px slots and two 6px gaps).

## After (rendered, 1280)

Step (a) only: short columns sized to their content, cell padding tightened, the Lean column sized to the ladder plus the lock badge's overhang, and the add cell sized to its 26px button.

| Column | Before | After |
| --- | ---: | ---: |
| Watch | 44 | 36 |
| Recruit | 248 | 248 |
| POS | 44 | 32 |
| RT | 86 | 68 |
| YR | 40 | 24 |
| HT | 52 | 36 |
| WT | 44 | 30 |
| RGN | 44 | 32 |
| 12 attributes | 38 | 38 |
| Lean | 230 | 178 |
| **Passive total** | **1288** | **1140** |
| Add / rank | 46 | 30 |
| **Invite total** | **1334** | **1170** |

Passive spare against the 1180 content box is 40px. Invite spare is 10px (1170 vs the 1178 scrollport). Overflow is 0 in both. Lean's right edge is 39px inside the content edge. The add/rank cell stays after Lean and is on screen.

Nothing was dropped. Attribute tiles stay 30×26 at 1280 and 35.5×30.5 at 1920. Ladder slots stay 52px. Header labels did not need abbreviating. No backdrop-filter on the header.

## Header

Both layouts fit, so both are narrow tables. The sticky header pins under the page head (`top` equals `--gob-stick-top`; the column row stacks under the group row). The 16-row `gob-rep` repeat is removed when the table fits the scrollport. A table that still overflows keeps all 28 repeats. That path is covered by a 640px fixture; the live 1280 and 1920 pools do not take it.

## 1920

Columns stay capped. The only growth is the attribute gutter following the roster token (38 → 43.5). Passive table 1206 inside a 1664 content box. The spare space sits to the right of the table, not inside a column. Recruit stays 248.

## Checks

- `recruits-pool` 31 passed, including the 1280 Lean/overflow assertion and the narrow/wide header rule.
- `recruiting-tabs`, `invite-board`, `invite-board-layout`, `attr-tiles`, `subtabs`, `shell-1b` passed against this CSS (96 passed in that run; the three `recruits-pool` failures there were the harness bounds, fixed before the 31 passed re-run).
- Screenshots in `reports/recruit-pool-fit/`: real save week 3 and fixture week 22, at 1280×720 and 1920×1080. First row paints (Clifton Aguirre, RT A+→A++, 12 tiles). `elementFromPoint` on the filter count is unchanged in `recruiting-tabs`.
