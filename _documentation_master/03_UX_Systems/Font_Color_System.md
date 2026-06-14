## Energy (NG) Color System (doc synced to code June 2026)

Visual feedback for player energy (NG) levels. **Thresholds are unified everywhere; color palettes differ by surface** (the set-lineup redesign moved to a brighter palette, the court page kept the original dark palette).

### Unified Thresholds (integer percent, `NG * 100`)

| Tier | Range | Class name |
|---|---|---|
| High | ≥ 90% | `high` |
| Medium | 80–89% | `medium` |
| Low | 70–79% | `low` |
| Critical | < 70% | `critical` |

### Surfaces

**1. Set-Lineup — Lineup Slot Rows**

- `set-lineup.js` slot rendering computes `energyClass` from `energyPercent` and emits `<span class="player-energy ${energyClass}">${energyPercent}%</span>`.
- `set-lineup.css` `.player-energy.{high|medium|low|critical}` applies **font color** (bright palette): high `#34EC27`, medium `#F5C518`, low `#ff9f43`, critical `#ff6d6d`. Bold weight.

**2. Set-Lineup — Roster Grid (Attributes pane, NG column)**

- `renderRosterAttributes()` in `set-lineup.js` uses local helper `getEnergyClass(ngValue)` and puts class `ng {tier}` on the NG cell.
- `set-lineup.css` `.roster-table td.ng.{tier}` applies the **same bright font colors** as the slot rows.
- *(Historical note: this surface previously used background colors on the NG and player-name cells; that was replaced by class-based font color in the redesign.)*

**3. Set-Lineup — Player View Cards**

- Player card headshot gets an **energy-colored border** plus an energy % readout in the matching color (`createPlayerCard` area of `set-lineup.js`).
- Uses the **dark palette** via inline thresholds: green `#00aa00` (> 0.89), yellow `#cccc00` (≥ 0.8), orange `#ff8800` (≥ 0.7), red `#cc0000` (< 0.7).

**4. Court Page — Live Box Score (Phaser sidebar)**

- `gameScene.js` defines `getEnergyColor(ng)` with the **dark palette** (same values as #3).
- Font color is applied to **all cells in the player's row** (name + every stat column), set initially from the starting NG and re-applied as `turn.player_energy[playerId].NG` updates during gameplay.

### Data Source

- NG lives on player attributes (`player.attributes.NG`, backend `BackEnd/models/player.py`).
- Live updates on the court page come from `player_energy` populated per turn (`BackEnd/models/turn_manager.py`).

### Key Files

- `FrontEnd/static/set-lineup.js` — slot rows (`energyClass`), roster grid (`getEnergyClass`), player cards (border colors)
- `FrontEnd/static/set-lineup.css` — `.player-energy.*` and `.roster-table td.ng.*` classes
- `FrontEnd/static/js/phaser/gameScene.js` — `getEnergyColor()` + row coloring in the live box score
- `BackEnd/models/turn_manager.py` — `player_energy` per-turn payload
