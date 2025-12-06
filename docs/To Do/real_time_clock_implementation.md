# Real-Time Countdown Clock Implementation

## Overview
Implement a second-by-second countdown clock that runs in real-time during active gameplay, independent of turn completion. The clock will update continuously while the game is active and pause during dead ball situations.

## Current System
- Clock updates in chunks when `updateScoreboard()` is called after each turn
- Backend is authoritative (sends `time_remaining` and `clock` format)
- Direct DOM manipulation: `clockEl.textContent = liveClock`

## Implementation Structure

### 1. Core Timer Module
**File:** `FrontEnd/static/js/phaser/utils/gameClock.js`

**Responsibilities:**
- Manage the `setInterval` timer
- Track current time remaining (in seconds)
- Handle pause/resume logic
- Format time for display (MM:SS)
- Update DOM element directly

**Key Functions:**
```javascript
// Initialize clock with backend time
initClock(timeRemainingSeconds, clockElement)

// Start the countdown timer
startClock()

// Pause the countdown (timeouts, fouls, etc.)
pauseClock()

// Resume the countdown
resumeClock()

// Stop and reset the clock
stopClock()

// Sync with backend authoritative time (called after turn completion)
syncWithBackend(timeRemainingSeconds)

// Internal: Update DOM every second
updateClockDisplay()
```

**State Management:**
- `isRunning`: Boolean flag for active countdown
- `isPaused`: Boolean flag for paused state
- `timeRemaining`: Current time in seconds (authoritative)
- `intervalId`: Reference to setInterval for cleanup
- `clockElement`: DOM element reference

### 2. Integration Points

#### A. GameScene Initialization
**Location:** `FrontEnd/static/js/phaser/gameScene.js` - `create()` method

**Actions:**
- Import `gameClock.js`
- Initialize clock with `simData.time_remaining` and `clockEl`
- Store clock instance on scene: `this.gameClock = gameClock`

#### B. Turn Completion Sync
**Location:** `FrontEnd/static/js/phaser/gameScene.js` - `updateScoreboard()` function

**Actions:**
- After backend turn completes, sync clock: `this.gameClock.syncWithBackend(turn.time_remaining)`
- Clock continues from synced time (handles any drift)

#### C. Pause/Resume Triggers

**Pause Clock:**
- Timeout called (`AnimationEngine.handleTimeout()`)
- Foul-out popup shown (`showFoulOutPopup()`)
- Quarter break (locker room popup)
- Any dead ball situation where game is paused

**Resume Clock:**
- Turn animation starts (after timeout resume, foul-out resume, quarter start)
- Game resumes from pause

### 3. State Management

**Game States That Affect Clock:**
1. **Active Play**: Clock running, counting down
2. **Timeout**: Clock paused, waiting for resume
3. **Foul Out**: Clock paused, waiting for lineup selection
4. **Quarter Break**: Clock paused, waiting for next quarter
5. **Game Paused** (user pause button): Clock paused

**State Flags:**
- `scene.gameClock.isRunning`: Clock is actively counting
- `scene.gameClock.isPaused`: Clock is paused (but not stopped)
- `scene.isPaused`: User-initiated pause (separate from clock pause)

### 4. Backend Sync Strategy

**When Backend Sends Time:**
- After each turn completion (`turn.time_remaining`)
- After timeout resume (`simData.time_remaining`)
- After quarter start (`simData.time_remaining`)

**Sync Logic:**
1. Backend sends authoritative `time_remaining` (seconds)
2. Frontend clock syncs: `gameClock.syncWithBackend(timeRemaining)`
3. Clock continues counting down from synced value
4. Handles any drift between frontend timer and backend reality

**Edge Cases:**
- If frontend clock is ahead of backend: Reset to backend (backend is authoritative)
- If frontend clock is behind: Reset to backend (catch up)
- If sync happens during pause: Update time but don't resume

### 5. DOM Update Pattern

**Consistency with Current System:**
- Use same DOM element: `document.getElementById('game-clock')`
- Direct DOM manipulation: `clockEl.textContent = formattedTime`
- Same pattern as other scoreboard items (scores, fouls, timeouts)

**Format:**
- Display: `MM:SS` (e.g., "7:45")
- Internal: Seconds (e.g., 465)
- Conversion: `formatTime(seconds)` → `"MM:SS"`

### 6. Cleanup and Lifecycle

**Cleanup:**
- Clear interval when scene is destroyed
- Stop clock on game completion
- Reset clock on new game start

**Lifecycle:**
1. **Game Start**: Initialize with backend time, start clock
2. **During Game**: Clock runs continuously, syncs after each turn
3. **Pause Events**: Clock pauses, time preserved
4. **Resume Events**: Clock resumes from preserved time
5. **Game End**: Clock stops, cleanup interval

### 7. Error Handling

**Edge Cases:**
- Clock element not found: Log warning, gracefully degrade (fall back to turn-based updates)
- Backend time missing: Use last known time, continue countdown
- Timer drift: Sync with backend after each turn (handles drift)
- Multiple syncs: Last sync wins (backend is authoritative)

### 8. Testing Considerations

**Test Scenarios:**
- Clock counts down correctly during active play
- Clock pauses during timeout
- Clock resumes after timeout
- Clock syncs with backend after turn completion
- Clock handles rapid pause/resume cycles
- Clock formats time correctly (MM:SS)
- Clock stops on game completion
- Clock resets on new game

## Implementation Order

1. **Phase 1: Core Timer**
   - Create `gameClock.js` module
   - Implement basic countdown with setInterval
   - Direct DOM updates

2. **Phase 2: Integration**
   - Integrate into `gameScene.js`
   - Initialize on game start
   - Sync after turn completion

3. **Phase 3: Pause/Resume**
   - Add pause logic for timeouts
   - Add pause logic for foul-outs
   - Add pause logic for quarter breaks

4. **Phase 4: Polish**
   - Error handling
   - Edge case handling
   - Cleanup and lifecycle management

## Benefits of This Approach

1. **Consistent Pattern**: Uses same DOM manipulation as other scoreboard items
2. **Independent**: Doesn't interfere with turn-based updates
3. **Simple**: No event system overhead
4. **Maintainable**: Clear separation of concerns
5. **Performant**: Single DOM update per second is negligible

## Potential Future Enhancements

- Visual countdown animation (pulsing, color changes in final seconds)
- Audio cues for time remaining (optional)
- Shot clock integration (if implemented)
- Overtime handling (if different clock behavior needed)

## Notes

- Backend remains authoritative source of truth
- Frontend clock is for UX only (real-time feel)
- Sync after each turn ensures accuracy
- Pause/resume preserves game state correctly

