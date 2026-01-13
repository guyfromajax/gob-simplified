# Timeout vs Quarter Break: NG Values & Data Persistence Comparison

**Date:** January 2025  
**Purpose:** Side-by-side comparison of how player NG values and overall data persistence are handled for timeouts vs quarter breaks

---

## Overview

This document compares the data persistence flow for **timeouts** and **quarter breaks** across three phases:
1. **Going INTO** the break (recharge, save to DB)
2. **During Lineup Selection** experience (how data is loaded/displayed)
3. **Re-entering court.html** (how data is restored)

---

## Phase 1: Going INTO Timeout/Quarter Break

### Timeout Flow

**Location:** `BackEnd/models/game_manager.py::call_timeout()` (lines 175-272)  
**Save Location:** `BackEnd/api/api.py::call_timeout_endpoint()` (lines 2483-2550)

**Steps:**
1. **Recharge happens FIRST** (lines 225-258 in `game_manager.py`)
   - All players (lineup + bench) get random recharge: `[0.03, 0.04, 0.05, 0.06]`
   - Recharge happens in `call_timeout()` method
   - Debug logs track NG values before/after recharge

2. **Timeout turn is created** (line 196)
   - Stores `timeout_next_play_type` and `timeout_offense_team_id` in `game_state`

3. **Game state is saved to database** (lines 2514-2550 in `api.py`)
   - Called from `call_timeout_endpoint()` after `call_timeout()` returns
   - Uses `summarize_game_state(gm, exclude_animations=True)`
   - Saves to `games_collection` with `game_id`
   - Debug logs track NG values in memory vs. what's being saved

**Key Point:** Recharge happens BEFORE save, so recharged NG values should be visible on lineup screen.

---

### Quarter Break Flow

**Location:** `BackEnd/api/api.py::simulate_turn_endpoint()` (lines 2236-2333)

**Steps:**
1. **Quarter completes** (`quarter_complete = True` when `time_remaining <= 0`)

2. **Recharge happens** (lines 2241-2282)
   - All players (lineup + bench) get random recharge
   - Regular quarter break: `[0.7, 0.8, 0.9, 1.0, 1.1, 1.2]`
   - Halftime (Q2→Q3): `[1.5, 1.6, 1.7, 1.8, 1.9, 2.0]`
   - Recharge happens in `simulate_turn_endpoint()` when `quarter_complete=True`
   - Debug logs track NG values before/after recharge

3. **Quarter is incremented** (lines 2285-2288)
   - `gm.quarter += 1`
   - `gm.game_state["quarter"] = gm.quarter`

4. **Game state is saved to database** (lines 2301-2333)
   - Uses `summarize_game_state(gm, exclude_animations=True)`
   - Saves to `games_collection` with `game_id`
   - Debug logs track NG values in memory vs. what's being saved

**Key Point:** Recharge happens BEFORE save, so recharged NG values should be visible on lineup screen.

---

### Critical Issue: `summarize_game_state()` Only Saves Lineup Players

**Location:** `BackEnd/utils/shared.py::summarize_game_state()` (lines 736-759)

**Problem:**
- Line 738: `for pos, player in team_obj.lineup.items():` - Only iterates over **lineup players**
- Line 764: `has_fresh_turns = len(game.turns) > 0 and not exclude_animations`
- When `exclude_animations=True` (database saves), `has_fresh_turns = False`
- This means **bench players are NEVER saved to the database**

**Impact:**
- Recharge happens for all players (lineup + bench) ✅
- But only lineup players' NG values are saved to DB ❌
- Bench players' NG values are lost when game is saved

---

## Phase 2: During Lineup Selection Experience

### Timeout Flow

**Frontend:** Lineup screen loads with `resume_from_timeout=true` URL parameter  
**Backend:** `GET /api/game/{game_id}` (lines 609-680 in `api.py`)

**Data Loading:**
1. **Check if game is in memory** (line 621)
   - If `gm` exists in `ongoing_games` dictionary:
     - Reads from `gm.get_all_players()` (line 630)
     - Returns NG values from **in-memory** player objects
     - These should have recharged NG values ✅

2. **If game is NOT in memory** (lines 682-780)
   - Loads from database: `games_collection.find_one({"_id": game_id})`
   - Extracts players from `saved.get("players", [])`
   - Returns NG values from **saved document**
   - **Problem:** Only lineup players are in saved document (bench players missing)

**Key Point:** If game is in memory, NG values should be correct. If game is NOT in memory, only lineup players have NG values (bench players default to 1.0).

---

### Quarter Break Flow

**Frontend:** Lineup screen loads with `quarter={next_quarter}` URL parameter  
**Backend:** `GET /api/game/{game_id}` (same endpoint as timeout)

**Data Loading:**
1. **Check if game is in memory** (line 621)
   - If `gm` exists in `ongoing_games` dictionary:
     - Reads from `gm.get_all_players()` (line 630)
     - Returns NG values from **in-memory** player objects
     - These should have recharged NG values ✅

2. **If game is NOT in memory** (lines 682-780)
   - Loads from database: `games_collection.find_one({"_id": game_id})`
   - Extracts players from `saved.get("players", [])`
   - Returns NG values from **saved document**
   - **Problem:** Only lineup players are in saved document (bench players missing)

**Key Point:** Same issue as timeout - if game is NOT in memory, only lineup players have NG values.

---

## Phase 3: Re-entering court.html

### Timeout Flow

**Location:** `BackEnd/api/api.py::simulate_quarter_endpoint()` (lines 848-2048)  
**Resume Logic:** `BackEnd/main.py::simulate_quarter()` (lines 298-390)

**Steps:**
1. **Game is loaded from database** (lines 996-1110 in `api.py`)
   - Creates new `GameManager` instance
   - Loads team data, strategy settings, playbook settings
   - **Players are created fresh** via `Player.__init__()` which sets `NG = 1.0` by default

2. **Player stats and NG are restored** (lines 1196-1280 in `api.py`)
   - Iterates through `saved.get("players", [])`
   - For each saved player, finds matching player in roster
   - Restores `player.attributes["NG"]` from saved document
   - Calls `player._rescale_attributes()` to update scaled attributes
   - **Problem:** Only lineup players are in saved document, so bench players keep `NG = 1.0`

3. **Timeout resume logic** (lines 298-390 in `main.py`)
   - Checks `resume_from_timeout=True` flag
   - Skips all quarter initialization (opening tip, etc.)
   - Creates appropriate initial turn based on `timeout_next_play_type`
   - Clears timeout state from memory and database

**Key Point:** Bench players' NG values are NOT restored because they weren't saved in the first place.

---

### Quarter Break Flow

**Location:** `BackEnd/api/api.py::simulate_quarter_endpoint()` (lines 848-2048)  
**Quarter Init Logic:** `BackEnd/main.py::simulate_quarter()` (lines 215-620)

**Steps:**
1. **Game is loaded from database** (lines 996-1110 in `api.py`)
   - Creates new `GameManager` instance
   - Loads team data, strategy settings, playbook settings
   - **Players are created fresh** via `Player.__init__()` which sets `NG = 1.0` by default

2. **Player stats and NG are restored** (lines 1196-1280 in `api.py`)
   - Iterates through `saved.get("players", [])`
   - For each saved player, finds matching player in roster
   - Restores `player.attributes["NG"]` from saved document
   - Calls `player._rescale_attributes()` to update scaled attributes
   - **Problem:** Only lineup players are in saved document, so bench players keep `NG = 1.0`

3. **Quarter initialization** (lines 215-620 in `main.py`)
   - Resets clock and fouls for new quarter
   - Builds lineups (from DB or provided lineup IDs)
   - Creates initial turn (BIP for quarter start)
   - **Note:** Quarter break recharge was removed from here (line 411 comment)

**Key Point:** Same issue as timeout - bench players' NG values are NOT restored.

---

## Summary: Key Differences & Similarities

### Similarities

1. **Both recharge all players** (lineup + bench) before saving
2. **Both save to database** using `summarize_game_state(exclude_animations=True)`
3. **Both have the same bug:** Only lineup players are saved (bench players excluded)
4. **Both load from `/api/game/{game_id}`** for lineup screen
5. **Both restore stats/NG** from saved `players` array when returning to court

### Differences

| Aspect | Timeout | Quarter Break |
|--------|---------|---------------|
| **Recharge Amount** | `[0.03, 0.04, 0.05, 0.06]` (small) | `[0.7, 0.8, 0.9, 1.0, 1.1, 1.2]` (regular) or `[1.5, 1.6, 1.7, 1.8, 1.9, 2.0]` (halftime) |
| **Recharge Location** | `game_manager.py::call_timeout()` | `api.py::simulate_turn_endpoint()` |
| **Save Location** | `api.py::call_timeout_endpoint()` | `api.py::simulate_turn_endpoint()` |
| **Resume Logic** | `simulate_quarter()` with `resume_from_timeout=True` | `simulate_quarter()` with normal quarter init |
| **Initial Turn** | Based on `timeout_next_play_type` (SIP/FT/BIP) | Always BIP (quarter start) |
| **Quarter Increment** | No (same quarter) | Yes (`gm.quarter += 1`) |

---

## Root Cause of NG = 1.0 Bug

**The Problem:**
1. Recharge happens for all players (lineup + bench) ✅
2. But `summarize_game_state()` only saves lineup players ❌
3. When game is loaded from DB, bench players are created fresh with `NG = 1.0` ❌
4. Bench players' recharged NG values are lost ❌

**Why Lineup Players Also Show NG = 1.0:**
- If the game is NOT in memory when lineup screen loads, it reads from DB
- If the game IS in memory, it should show correct NG values
- If lineup players also show NG = 1.0, it suggests:
  - Game was not in memory when lineup screen loaded, OR
  - Recharge didn't happen (but logs should show it), OR
  - Something is resetting NG values after recharge but before save

**The Fix:**
- Modify `summarize_game_state()` to include ALL players (lineup + bench) when `exclude_animations=True`
- Change line 738 from `team_obj.lineup.items()` to `team_obj.get_all_players()`
- Ensure bench players' NG values are saved and restored correctly

---

## Files Involved

### Timeout Flow
- `BackEnd/models/game_manager.py::call_timeout()` - Recharge logic
- `BackEnd/api/api.py::call_timeout_endpoint()` - Save to DB
- `BackEnd/api/api.py::get_game_state()` - Load for lineup screen
- `BackEnd/main.py::simulate_quarter()` - Resume logic (lines 298-390)

### Quarter Break Flow
- `BackEnd/api/api.py::simulate_turn_endpoint()` - Recharge + save (lines 2236-2333)
- `BackEnd/api/api.py::get_game_state()` - Load for lineup screen
- `BackEnd/main.py::simulate_quarter()` - Quarter init (lines 215-620)

### Shared
- `BackEnd/utils/shared.py::summarize_game_state()` - **THE BUG IS HERE** (line 738)
- `BackEnd/api/api.py::simulate_quarter_endpoint()` - Game loading + restoration (lines 996-1280)

