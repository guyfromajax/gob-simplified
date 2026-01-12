# Game Document Size Analysis

**Date Created:** January 11, 2026  
**Status:** 🔍 ANALYSIS  
**Priority:** 🔴 CRITICAL  
**Related:** Task 2 (Database Optimization) from Go Live Plan

## Key Finding: Turns Are NOT Saved to Database

**Critical Discovery:**
Looking at `BackEnd/utils/shared.py` line 971-972:
```python
if exclude_animations:
    turns = []  # Empty array - don't save turns to database (prevents document size issues)
```

**When saving to database:**
- `exclude_animations=True` (always True for database saves)
- `turns = []` (empty array)
- **Turns and animation data are NOT saved to the database!**

**When sending to frontend (real-time):**
- `exclude_animations=False` (for real-time frontend display)
- `turns = deepcopy(game.turns)` (full turns with animations)
- **Turns and animation data ARE included in API responses**

---

## So What's Making the Document Heavy?

If turns aren't being saved, what's causing the 10-25x size growth after Q1?

### 1. **Players Array** 🔴 LIKELY BIGGEST CONTRIBUTOR

**What's in each player object:**
```python
{
    "playerId": player.player_id,
    "name": player.name,
    "team": team_key,
    "team_id": team_obj.team_id,
    "pos": pos,
    "jersey": player.jersey,
    "photo": getattr(player, "photo", None),
    "primary_color": team_obj.primary_color,
    "secondary_color": team_obj.secondary_color,
    "x": coords.get("x", 0),
    "y": coords.get("y", 0),
    "stats": player.stats.get("game", {}),  # ⚠️ Grows with each quarter!
    "attributes": {
        "EM": player.attributes.get("EM", 0),
        "CH": player.attributes.get("CH", 0),
        "MO": player.attributes.get("MO", 0),
        "NG": player.attributes.get("NG", 1.0)
    }
}
```

**Size Growth:**
- **New game:** ~10 players × ~500 bytes = ~5 KB
- **After Q1:** ~10 players × ~2,000 bytes = ~20 KB (stats accumulated)
- **After Q4:** ~10 players × ~8,000 bytes = ~80 KB (all stats)

**Stats object grows with:**
- Points, rebounds, assists, steals, blocks, fouls
- Field goals made/attempted, 3-pointers made/attempted
- Free throws made/attempted
- Turnovers, minutes played
- Plus any other game-specific stats

**Estimated Contribution:** 30-50% of document size

---

### 2. **Teams Object** 🟡 MEDIUM CONTRIBUTOR

**What's in teams object:**
```python
{
    "name": team.name,
    "team_id": team.team_id,
    "mascot": team.mascot,
    "colors": {...},
    "score": score,
    "points_by_quarter": [...],
    "team_fouls": number,
    "timeouts": number,
    "attributes": team_attributes,
    "box_score": {...},  # ⚠️ Grows with each quarter!
    "totals": {...},     # ⚠️ Grows with each quarter!
    "strategy_settings": {...},
    "strategy_calls": {...},
    "plays": {...},      # ⚠️ Could be large (all plays with stats)
    "scouting": {...},   # ⚠️ Could be large (scouting data for all players)
    "playbook_settings": {...}
}
```

**Size Growth:**
- **New game:** ~5-10 KB per team = ~10-20 KB total
- **After Q1:** ~10-15 KB per team = ~20-30 KB total (box_score, totals grow)
- **After Q4:** ~15-25 KB per team = ~30-50 KB total

**Largest contributors:**
- `plays` object (all plays with game_stats) - could be 5-10 KB per team
- `scouting` object (scouting data) - could be 2-5 KB per team
- `box_score` (grows with each quarter) - could be 3-5 KB per team
- `totals` (grows with each quarter) - could be 1-2 KB per team

**Estimated Contribution:** 20-40% of document size

---

### 3. **Text Log** 🟡 MEDIUM CONTRIBUTOR

**What's in text_log:**
- Array of text strings describing each turn
- "Player X made a 2-point shot"
- "Player Y committed a foul"
- etc.

**Size Growth:**
- **New game:** Empty or ~1 KB
- **After Q1:** ~50 turns × ~50 bytes = ~2.5 KB
- **After Q4:** ~200 turns × ~50 bytes = ~10 KB

**Estimated Contribution:** 5-15% of document size

---

### 4. **Game State Metadata** 🟢 SMALL CONTRIBUTOR

**What's in game state:**
- `quarter`, `is_final`, `week`
- `home_team_id`, `away_team_id`
- `user_team_side`
- Various game state flags

**Size:** ~1-2 KB (constant, doesn't grow)

**Estimated Contribution:** <5% of document size

---

## Summary: What's Actually Making It Heavy

### Turns/Animations: **NOT SAVED** ✅
- Turns are set to `[]` when saving to database
- Animation data is NOT in the saved document
- **This is already optimized!**

### Players Array: **BIGGEST CONTRIBUTOR** 🔴
- Each player's `stats` object grows with each quarter
- 10 players × growing stats = significant size increase
- **Estimated:** 30-50% of document size

### Teams Object: **SECOND BIGGEST** 🟡
- `plays` object (all plays with game_stats)
- `scouting` object (scouting data)
- `box_score` and `totals` (grow with each quarter)
- **Estimated:** 20-40% of document size

### Text Log: **SMALLER BUT GROWS** 🟡
- Grows linearly with number of turns
- **Estimated:** 5-15% of document size

---

## Answer to Your Questions

### Q: What are the largest contributors?
**A:** 
1. **Players array** (30-50%) - especially player stats that accumulate
2. **Teams object** (20-40%) - especially plays, scouting, box_score
3. **Text log** (5-15%) - grows with each turn

### Q: Turn data and animation data?
**A:** 
- **Turns are NOT saved** (set to `[]` when `exclude_animations=True`)
- **Animation data is a subset of turn data** (stored within each turn object)
- **But neither is in the database!** They're only in real-time API responses

### Q: Is animation data a subset of turn data?
**A:** 
- **Yes!** Animation data is stored within each turn object
- Each turn contains:
  - `animations` array (player movements, coordinates, actions)
  - `text` (narration)
  - `time_elapsed`
  - `offensive_state`
  - `foul_type`
  - etc.

---

## Your Ideas?

You mentioned you have a few ideas. Based on this analysis, potential optimizations:

1. **Don't store full player stats in game document** - Only store deltas or summary
2. **Don't store plays/scouting in game document** - Load from team document when needed
3. **Archive old text_log entries** - Only keep recent turns
4. **Use projections when loading** - Only load what's needed for each screen
5. **Separate game state from game history** - Store turns separately if needed

What are your ideas?

