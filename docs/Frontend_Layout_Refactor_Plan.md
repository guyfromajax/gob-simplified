 # Frontend Layout Architecture Refactor Plan

## Executive Summary

This document outlines a comprehensive refactor plan for the frontend responsive layout architecture of the game simulation application. The current architecture suffers from conflicting CSS layout systems and uncoordinated space allocation, leading to fragile layouts that break when fixes are applied. This plan proposes a transition to a **Pure CSS Grid with `grid-template-areas`** approach, establishing a single source of truth for space allocation and eliminating positioning conflicts.

---

## 1. Current Architecture Summary

### 1.1 Overall Structure

The application uses a **hybrid layout system** combining multiple CSS layout technologies:

```
┌─────────────────────────────────────────────────────────┐
│  #scoreboard (position: fixed, top: 0)                 │
├─────────────────────────────────────────────────────────┤
│  #main-container (display: flex, flex-direction: column)│
│  ├─────────────────────────────────────────────────────┤ │
│  │  .court-row (display: grid, 3 columns)              │ │
│  │  ├─ .player-stats-panel.away (280px)               │ │
│  │  ├─ #phaser-container (1fr)                        │ │
│  │  │   └─ canvas (width: 100%, height: auto)        │ │
│  │  └─ .player-stats-panel.home (280px)               │ │
│  ├─────────────────────────────────────────────────────┤ │
│  │  .playcall-row (display: grid, 3 columns)          │ │
│  │  ├─ <div></div> (empty left)                       │ │
│  │  ├─ #playcall-center (1fr)                         │ │
│  │  │   └─ [Playcall UI components]                   │ │
│  │  └─ <div></div> (empty right)                      │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Key CSS Variables

```css
:root {
  --scoreboard-height: 100px;
  --player-stats-width: 280px;
  --pbp-height: 120px;
  --court-bottom-trim: 80px;
  --side-padding: 10px;
}
```

### 1.3 Layout Technologies in Use

1. **Flexbox** (`#main-container`): Column-based flex container
2. **CSS Grid** (`.court-row`, `.playcall-row`): 3-column grid layouts
3. **Fixed Positioning** (`#scoreboard`, `#playcall-center`): Elements removed from document flow
4. **Absolute Positioning**: Various overlays and popups
5. **JavaScript Dynamic Positioning**: `updatePlaycallPosition()` function sets `top` property of `#playcall-center` based on canvas bottom

### 1.4 Space Allocation Strategy

**Current approach**: **Mixed and uncoordinated**

- **Scoreboard**: Fixed at top, consumes `--scoreboard-height` (100px)
- **Main Container**: `height: calc(100vh - var(--scoreboard-height))`, `margin-top: var(--scoreboard-height)`
- **Court Row**: `flex-shrink: 0` (doesn't compress)
- **Playcall Row**: `flex: 1` (fills remaining space), `min-height: 250px`
- **Phaser Container**: `height: fit-content`, canvas `max-height: calc(100vh - var(--scoreboard-height))`
- **Playcall Center**: `position: fixed`, dynamically positioned via JavaScript, `max-height: clamp(160px, 22vh, 260px)`

### 1.5 Critical Dependencies

- **JavaScript dependency**: `#playcall-center` positioning relies on `updatePlaycallPosition()` function that:
  - Queries canvas `getBoundingClientRect()`
  - Sets `top` property dynamically
  - Uses `ResizeObserver` and window resize listeners
  - Has timing dependencies (setTimeout delays for Phaser initialization)

---

## 2. Current Problems

### 2.1 Architectural Fragility

**Problem**: Fixing one layout issue creates new regressions in other viewport sizes.

**Root Cause**: Multiple layout systems (Flexbox, Grid, Fixed Positioning) compete for space allocation without a unified coordination mechanism. When one system's constraints change, others don't adapt predictably.

**Example**: 
- Attempted fix: Constrained `#playcall-center` height with `clamp()` and adjusted `align-items`
- Result: Court canvas completely covered Playcall Center on large iMac screens
- Why: Fixed positioning + JavaScript dynamic `top` + canvas `height: auto` + Grid `flex: 1` created conflicting space claims

### 2.2 Conflicting Space Allocation

**Problem**: Elements claim space in incompatible ways:

1. **Fixed Positioning Conflict**: `#playcall-center` uses `position: fixed` with `bottom: 0`, but JavaScript overrides `top` dynamically. This removes it from the Grid's space allocation while still occupying visual space.

2. **Flex vs Grid Conflict**: `#main-container` uses Flexbox column layout, but children (`.court-row`, `.playcall-row`) use CSS Grid. The Grid rows don't participate in Flexbox's space distribution predictably.

3. **Height Calculation Conflicts**:
   - Canvas: `height: auto` (content-based) + `max-height: calc(100vh - var(--scoreboard-height))`
   - Playcall Row: `flex: 1` (wants remaining space) + `min-height: 250px`
   - Playcall Center: `max-height: clamp(160px, 22vh, 260px)` (viewport-based)
   - These three systems don't coordinate, leading to overflow or underutilization

### 2.3 JavaScript Dependency for Core Layout

**Problem**: Core layout positioning relies on JavaScript execution timing and DOM queries.

**Issues**:
- `updatePlaycallPosition()` must wait for Phaser canvas creation (timing-dependent)
- Uses multiple `setTimeout` delays as workarounds
- `ResizeObserver` adds complexity and potential race conditions
- If JavaScript fails or is delayed, layout breaks

**Best Practice Violation**: CSS should handle layout; JavaScript should enhance, not define core structure.

### 2.4 Responsive Breakpoint Gaps

**Problem**: No systematic responsive breakpoint strategy.

**Current State**:
- Hardcoded widths (`280px` for player stats panels)
- Viewport-relative units (`22vh`, `100vh`) mixed with fixed units (`160px`, `260px`)
- No `@media` queries for different screen sizes
- Layout assumes desktop-first, breaks on tablets/mobile

### 2.5 Maintenance Burden

**Problem**: Layout changes require understanding multiple systems and their interactions.

**Symptoms**:
- Changes to one component affect unrelated components
- Debugging requires checking Flexbox, Grid, Fixed positioning, and JavaScript
- No single "source of truth" for where space comes from
- Comments like `/* CHANGE: reduced padding */` indicate ad-hoc fixes

---

## 3. Components and Containers Inventory

This section provides a comprehensive inventory of all major components and containers in `court.html` to understand the full scope of the refactor.

### 3.1 Top-Level Containers

| Container | ID/Class | Purpose | Current Positioning | Layout Role |
|-----------|----------|---------|---------------------|-------------|
| **Scoreboard** | `#scoreboard` | Displays game score, clock, team info | `position: fixed`, `top: 0` | Top bar (100px height) |
| **Main Container** | `#main-container` | Wraps court and playcall areas | `display: flex`, `flex-direction: column` | Primary layout container |
| **Court Row** | `.court-row` | Contains stats panels and court | `display: grid`, 3 columns | Horizontal layout for main content |
| **Playcall Row** | `.playcall-row` | Contains playcall center | `display: grid`, 3 columns | Horizontal layout for playcall |

### 3.2 Scoreboard Components (`#scoreboard`)

The scoreboard uses a complex CSS Grid layout with 27 columns. Key components:

| Component | ID/Class | Purpose | Grid Position |
|-----------|----------|---------|---------------|
| **Away Logo** | `#away-logo-container` | Away team logo | Column 2 |
| **Away Score** | `#away-score` | Away team score | Column 4 |
| **Away TOL/F** | `.tol-fouls.away` | Timeouts and fouls | Column 6 |
| **Away Active Player** | `.active-player-display.away-side` | Shows active player with ball | Column 8 |
| **Away Tempo Bar** | `#away-tempo-bar` | Tempo strategy indicator | Column 10 (commented out) |
| **Away Aggression Bar** | `#away-aggression-bar` | Aggression strategy indicator | Column 12 (commented out) |
| **Center Clock/Quarter** | `.center` | Game clock and quarter | Absolutely positioned center |
| **Home Aggression Bar** | `#home-aggression-bar` | Aggression strategy indicator | Column 16 (commented out) |
| **Home Tempo Bar** | `#home-tempo-bar` | Tempo strategy indicator | Column 18 (commented out) |
| **Home Active Player** | `.active-player-display.home-side` | Shows active player with ball | Column 20 |
| **Home TOL/F** | `.tol-fouls.home` | Timeouts and fouls | Column 22 |
| **Home Score** | `#home-score` | Home team score | Column 24 |
| **Home Logo** | `#home-logo-container` | Home team logo | Column 26 |

**Note**: Many strategy bars and playcall displays have been moved to the Playcall Center below the court.

### 3.3 Player Stats Panels

Two identical panels (left and right) displaying player and team statistics:

| Component | ID/Class | Purpose | Current Width | Content Sections |
|-----------|----------|---------|---------------|------------------|
| **Away Stats Panel** | `.player-stats-panel.away` | Left side player/team stats | `280px` | Player box score, Team box score |
| **Home Stats Panel** | `.player-stats-panel.home` | Right side player/team stats | `280px` | Player box score, Team box score |

#### 3.3.1 Player Box Score Section
- **Header**: Team name + stat toggle buttons (S1, S2, S3)
- **Table**: Player statistics (Name, PTS, REB, AST, F, etc.)
- **Tabs**: S1 (basic stats), S2 (advanced stats), S3 (defense stats)

#### 3.3.2 Team Box Score Section
- **Header**: Team name + team stat toggle buttons (S1, S2, S3)
- **S1 Tab**: Team totals (FG, 3PT, FT, Rebounds, Assists, etc.)
- **S2 Tab**: Offense/Defense breakdowns, Special Situations
- **S3 Tab**: Team attributes pills

### 3.4 Court Container (`#phaser-container`)

The center area containing the Phaser game canvas and game controls:

| Component | ID/Class | Purpose | Positioning |
|-----------|----------|---------|-------------|
| **Phaser Canvas** | `canvas` (inside `#phaser-container`) | Game animation canvas | `width: 100%`, `height: auto` |
| **Pre-Game Container** | `.pre-game-container` | Pre-game buttons overlay | `position: absolute` |
| **Sim Quarter Popup** | `#sim-quarter-popup` | Quarter simulation progress | `position: absolute` |
| **Game Controls** | `.game-controls` | Pause, speed, timeout buttons | `position: absolute`, bottom |
| **Speed Dropdown** | `#speed-dropdown` | Game speed selection menu | `position: absolute` |

### 3.5 Playcall Center (`#playcall-center`)

The unified tactical hub at the bottom of the screen:

| Component | ID/Class | Purpose | Current Positioning |
|-----------|----------|---------|---------------------|
| **Playcall Center** | `#playcall-center` | Main container for playcall UI | `position: fixed`, dynamically positioned via JS |
| **Status Row** | `#playcall-status-row` | Current offense/defense display | Flex row |
| **Main Row** | `#playcall-main-row` | Offense panel, lean meter, defense panel | Flex row, `align-items: center` |
| **Offense Panel** | `#offense-panel` | Offense play selection | Flex column, `flex: 1` |
| **Lean Meter** | `#lean-meter-container` | Momentum/lean indicator | Absolute center |
| **Defense Panel** | `#defense-panel` | Defense override controls | Flex column, `flex: 1` |

#### 3.5.1 Offense Panel Components
- **Panel Title**: "OFFENSE OVERRIDE"
- **Play Scroller**: Scrollable list of play options (`.play-scroller`)
- **Play Options**: Individual play cards (`.play-option`) with headshot and play info
- **Navigation Buttons**: Up/down arrows (`.play-nav-btn`)
- **Clear Button**: X button to clear override (`.clear-override-x-btn`)

#### 3.5.2 Lean Meter Components
- **Container**: `#lean-meter-container`
- **Meter**: `#lean-meter` (visual bar)
- **Positive Fill**: `#lean-fill-positive` (green/positive momentum)
- **Center Line**: `#lean-center-line` (neutral indicator)
- **Negative Fill**: `#lean-fill-negative` (red/negative momentum)

#### 3.5.3 Defense Panel Components
- **Panel Title**: "DEFENSE OVERRIDE"
- **Defense Type Buttons**: Man, Zone (`.defense-override-btn`)
- **Aggression Buttons**: Passive, Normal, Aggressive (`.defense-override-btn`)
- **Clear Buttons**: X buttons for individual overrides (`.defense-clear-x-btn`)
- **Clear Override Button**: Main clear button (`.clear-override-btn`)

### 3.6 Overlay Components

These components use absolute or fixed positioning and appear over the main layout:

| Component | ID/Class | Purpose | Positioning |
|-----------|----------|---------|-------------|
| **Player Tooltip** | `#player-tooltip` | Hover tooltip for player stats | `position: fixed` |
| **Play Tooltip** | `#play-tooltip` | Hover tooltip for play info | `position: fixed` |
| **Playcall HUD** | `#playcall-hud` | Playcall reveal overlay | `position: fixed` |
| **Locker Room Overlay** | `.locker-room-overlay` | Locker room screen | `position: fixed` |

### 3.7 Component Hierarchy Summary

```
body
├── #player-tooltip (overlay)
├── #play-tooltip (overlay)
├── #scoreboard (fixed top)
│   ├── #away-logo-container
│   ├── #away-score
│   ├── .tol-fouls.away
│   ├── .active-player-display.away-side
│   ├── .center (clock/quarter)
│   ├── .active-player-display.home-side
│   ├── .tol-fouls.home
│   ├── #home-score
│   └── #home-logo-container
├── #main-container (flex column)
│   ├── .court-row (grid, 3 columns)
│   │   ├── .player-stats-panel.away (280px)
│   │   │   ├── .player-box-score
│   │   │   └── .team-box-score
│   │   ├── #phaser-container (1fr)
│   │   │   ├── canvas (Phaser game)
│   │   │   ├── .pre-game-container
│   │   │   ├── #sim-quarter-popup
│   │   │   ├── .game-controls
│   │   │   └── #speed-dropdown
│   │   └── .player-stats-panel.home (280px)
│   │       ├── .player-box-score
│   │       └── .team-box-score
│   └── .playcall-row (grid, 3 columns)
│       ├── <div></div> (empty left)
│       ├── #playcall-center (1fr, fixed positioned)
│       │   ├── #playcall-status-row
│       │   └── #playcall-main-row
│       │       ├── #offense-panel
│       │       ├── #lean-meter-container
│       │       └── #defense-panel
│       └── <div></div> (empty right)
├── #playcall-hud (overlay)
└── .locker-room-overlay (overlay, when shown)
```

### 3.8 Key CSS Variables Used

| Variable | Value | Purpose |
|----------|-------|---------|
| `--scoreboard-height` | `100px` | Fixed height of scoreboard |
| `--player-stats-width` | `280px` | Width of left/right stats panels |
| `--pbp-height` | `120px` | Height for play-by-play (if used) |
| `--court-bottom-trim` | `80px` | Bottom trim space for court |
| `--side-padding` | `10px` | Horizontal padding |
| `--scoreboard-gap` | `20px` | Gap between scoreboard elements |
| `--home-vibrant-color` | `#ff6200` | Home team accent color |
| `--away-vibrant-color` | `#ff6200` | Away team accent color |

### 3.9 JavaScript Dependencies

| Function/Feature | Purpose | Dependency |
|-----------------|---------|------------|
| `updatePlaycallPosition()` | Dynamically positions `#playcall-center` below canvas | Phaser canvas creation, `getBoundingClientRect()` |
| `ResizeObserver` | Watches for canvas resize events | Browser API support |
| `initializeStatsToggle()` | Handles stat tab switching | DOM ready |
| Play navigation | Slot-based play selection | DOM ready, slot assignments |

---

## 4. Detailed Refactor Plan

### 4.1 Target Architecture: Pure CSS Grid with `grid-template-areas`

**Principle**: **Single Source of Truth for Space Allocation**

All layout space is allocated by a single CSS Grid container using named `grid-template-areas`. No fixed positioning for layout-critical elements. No JavaScript for core positioning.

### 4.2 Proposed Grid Structure

```css
#app-grid {
  display: grid;
  grid-template-rows: 
    var(--scoreboard-height)                              /* Fixed height: scoreboard (100px) */
    1fr                                                    /* Flexible: main content area (court + stats) */
    clamp(160px, 25vh, 300px);                            /* Constrained: playcall center (min 160px, max 300px) */
  grid-template-columns:
    var(--player-stats-width)    /* Fixed: left stats panel */
    1fr                          /* Flexible: court area */
    var(--player-stats-width);   /* Fixed: right stats panel */
  grid-template-areas:
    "scoreboard scoreboard scoreboard"
    "left-stats court right-stats"
    "playcall playcall playcall";
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}
```

**Note**: The playcall row uses `clamp()` directly as the grid row size to enforce constraints at the grid level, preventing unpredictable expansion. This addresses the architectural risk of `auto` rows causing fragility across different viewport sizes. Using `clamp()` directly (rather than nesting it inside `minmax()`) ensures cross-browser compatibility and reliable parsing.

### 4.3 Component Mapping

| Current Element | New Grid Area | Positioning Strategy |
|----------------|---------------|---------------------|
| `#scoreboard` | `scoreboard` | `grid-area: scoreboard` (no `position: fixed`) |
| `.player-stats-panel.away` | `left-stats` | `grid-area: left-stats` |
| `#phaser-container` | `court` | `grid-area: court` (with internal constraints) |
| `.player-stats-panel.home` | `right-stats` | `grid-area: right-stats` |
| `#playcall-center` | `playcall` | `grid-area: playcall` (no `position: fixed`) |

### 4.4 Space Allocation Rules

#### 4.4.1 Scoreboard Row
- **Height**: Fixed `var(--scoreboard-height)` (100px)
- **Behavior**: Always visible, never shrinks

#### 4.4.2 Main Content Row (Court + Stats Panels)
- **Height**: `1fr` (fills remaining vertical space)
- **Layout**: Elements are placed directly into root grid areas (`left-stats`, `court`, `right-stats`) defined in `#app-grid`. No nested grid is needed since the root grid already defines the 3-column structure.
- **Important**: If DOM structure requires an intermediate wrapper (e.g., for templating), ensure that wrapper has `min-height: 0` and `min-width: 0` to allow proper shrinking behavior.
- **Court Container Constraints**:
  ```css
  #phaser-container {
    grid-area: court;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    min-height: 0; /* Critical: allows shrinking */
    /* DOM defines strict box: container size is controlled by Grid 1fr allocation */
  }
  
  #phaser-container canvas {
    display: block;
    width: 100%;
    height: 100%;
    /* Canvas fills container; Phaser must be configured to match container dimensions */
    /* Do NOT use: max-width/max-height with width:auto/height:auto (causes weird shrinking) */
    /* Do NOT use: height: auto (breaks aspect ratio control) */
  }
  ```

#### 4.4.3 Canvas Sizing Contract

**Critical**: Establish a clear sizing authority to prevent "works on laptop, breaks on iMac" issues.

**Sizing Authority**: DOM wrapper (`#phaser-container`) controls dimensions; Phaser renders into the container.

**Implementation Pattern**:
- `#phaser-container` defines the available space (via Grid `1fr` row)
- Canvas CSS: `width: 100%; height: 100%` (fills container)
- Phaser Game config: Must be initialized to match container dimensions OR use Phaser's scale manager to adapt
- ResizeObserver: Observes `#phaser-container` and passes dimensions to Phaser's resize logic (if implemented)
- **Do not mix**: Either DOM controls size OR Phaser controls size, never both
- **Current approach**: Canvas fills container (`100%` × `100%`); Phaser must be configured to render at container size

**ResizeObserver Pattern** (see Phase 4 for implementation details):
- Observe `#phaser-container` (court wrapper), not `window`
- Pass container `getBoundingClientRect()` dimensions to Phaser's resize logic
- Avoid `window.innerHeight` and viewport math for layout decisions
- This keeps layout deterministic and screen-agnostic

**Why This Matters**: `<canvas>` elements don't behave like `<img>` with `object-fit`. Canvas rendering depends on both CSS size and internal resolution. Mixing DOM-controlled sizing with Phaser-controlled scaling leads to unpredictable behavior across different screen sizes.

#### 4.4.4 Playcall Row
- **Height**: `clamp(160px, 25vh, 300px)` (constrained at grid level)
- **Constraints**: Applied at grid row level, not just element level
  ```css
  #playcall-center {
    grid-area: playcall;
    overflow-y: auto; /* Allow scrolling if content exceeds max height */
  }
  ```
- **No JavaScript**: Grid automatically positions it below the main content row
- **Why Grid-Level Constraints**: Constraining the grid row itself (not just the element) prevents unexpected expansion due to `min-content` sizing, large padding, transforms, or `height: 100%` children. This removes an entire class of layout surprises. Using `clamp()` directly (not nested in `minmax()`) ensures reliable cross-browser parsing.

### 4.5 Responsive Breakpoints

#### 4.5.1 Desktop (Default)
- Full 3-column layout as described above
- Stats panels: `280px` each
- Court: `1fr` (flexible middle)

#### 4.5.2 Tablet (768px - 1024px)
```css
@media (max-width: 1024px) {
  :root {
    --player-stats-width: 200px;
  }
  
  #app-grid {
    grid-template-columns:
      var(--player-stats-width)
      1fr
      var(--player-stats-width);
  }
}
```

#### 4.5.3 Mobile (< 768px)
```css
@media (max-width: 768px) {
  #app-grid {
    grid-template-rows:
      var(--scoreboard-height)
      1fr
      auto  /* Stats panels as overlay or bottom sheet */
      auto; /* Playcall */
    grid-template-columns: 1fr;
    grid-template-areas:
      "scoreboard"
      "court"
      "stats"
      "playcall";
  }
  
  .player-stats-panel {
    /* Transform to overlay or bottom sheet */
    position: fixed;
    /* ... overlay styles ... */
  }
}
```

### 4.6 Migration Steps

#### Phase 1: Preparation
1. **Audit all `position: fixed` elements**
   - Identify which are truly "overlay" (modals, popups) vs "layout" (scoreboard, playcall)
   - Overlays can remain fixed; layout elements move to Grid

2. **Extract CSS Variables**
   - Consolidate all magic numbers into CSS variables
   - Document each variable's purpose

3. **Create backup branch**
   - Ensure rollback capability

#### Phase 2: Grid Container Creation
1. **Wrap entire layout in `#app-grid`**
   ```html
   <div id="app-grid">
     <!-- All existing content -->
   </div>
   ```

2. **Apply Grid CSS**
   - Define `grid-template-areas` as specified above
   - Set `display: grid` and grid properties
   - Use `clamp(160px, 25vh, 300px)` directly for playcall row (not nested in `minmax()`)

3. **Remove `position: fixed` from layout elements**
   - `#scoreboard`: Remove `position: fixed`, add `grid-area: scoreboard`
   - `#playcall-center`: Remove `position: fixed`, remove JavaScript positioning, add `grid-area: playcall`

**Exit Criteria**: Scoreboard and playcall are in grid; no `position: fixed` for layout elements; layout stable at 1920×1080, 2560×1440, and 3840×2160 viewports.

#### Phase 3: Component Migration
1. **Migrate Scoreboard**
   - Remove `position: fixed`, `top: 0`
   - Add `grid-area: scoreboard`
   - Verify visibility and positioning

2. **Migrate Stats Panels**
   - Place directly into root grid areas (`left-stats`, `right-stats`)
   - Add `grid-area: left-stats` / `grid-area: right-stats`
   - Ensure any intermediate wrappers have `min-height: 0` and `min-width: 0`
   - Test overflow behavior (scrollable content)

3. **Migrate Court Container**
   - Add `grid-area: court`
   - Set `#phaser-container` as strict box (DOM controls size)
   - Configure canvas CSS: `width: 100%; height: 100%` (fills container)
   - Ensure Phaser Game config matches container dimensions OR configure Phaser scale manager
   - Do NOT use `max-width/max-height` with `width:auto/height:auto`
   - Do NOT use `height: auto` on canvas
   - Remove JavaScript-dependent height calculations

**Exit Criteria**: All components correctly placed in grid areas; stats panels scroll properly; court container respects grid allocation; layout stable at 1920×1080, 2560×1440, and 3840×2160 viewports.

4. **Migrate Playcall Center**
   - Remove `position: fixed`, remove `updatePlaycallPosition()` JavaScript
   - Add `grid-area: playcall`
   - Set `min-height` and `max-height` constraints
   - Test that it appears below court automatically

#### Phase 4: JavaScript Cleanup
1. **Remove `updatePlaycallPosition()` function**
   - Delete the function and all event listeners
   - Remove `setTimeout` positioning calls
   - **Note**: ResizeObserver is still needed, but only for Phaser (see below)

2. **Implement Correct ResizeObserver Pattern for Phaser**
   - **Observe**: `#phaser-container` (court wrapper), NOT `window`
   - **Purpose**: Detect when Grid allocates new space to court container
   - **Action**: Pass container `getBoundingClientRect()` dimensions to Phaser's resize logic (if Phaser scale manager is configured)
   - **Alternative**: If Phaser uses fixed dimensions, ensure Phaser Game config matches container size on initialization
   - **Avoid**: `window.innerHeight`, viewport math, or any layout decisions based on window size
   - **Result**: Phaser renders into Grid-allocated space, keeping layout deterministic and screen-agnostic
   - **Canvas CSS**: Canvas uses `width: 100%; height: 100%` to fill container; Phaser handles internal resolution

3. **Update any JavaScript that queries layout**
   - Replace `getBoundingClientRect()` queries with Grid-aware alternatives if needed
   - Ensure Phaser canvas sizing works with new constraints
   - Verify no JavaScript sets `top`, `left`, `width`, or `height` for layout-critical elements

**Exit Criteria**: No JavaScript sets `top`/`left`/`width`/`height` for layout; only ResizeObserver → Phaser resize pattern remains; layout remains stable during window resize; verified at 1920×1080, 2560×1440, and 3840×2160 viewports.

#### Phase 5: Responsive Testing
1. **Test breakpoints**
   - Desktop (1920x1080, 2560x1440, 3840x2160)
   - Tablet (768x1024, 1024x768)
   - Mobile (375x667, 414x896)

2. **Test edge cases**
   - Very tall, narrow viewports
   - Very wide, short viewports
   - Window resizing during gameplay
   - Phaser canvas resize events

**Exit Criteria**: Resize during gameplay doesn't shift overlays or clip controls; layout stable across all tested viewport sizes; no visual regressions.

#### Phase 6: Documentation
1. **Update architecture docs**
   - Document Grid-based layout system
   - Explain space allocation rules
   - Document CSS variables

2. **Add code comments**
   - Explain Grid structure in CSS
   - Document responsive breakpoints
   - Note any remaining JavaScript dependencies (if any)

### 4.7 Benefits of New Architecture

1. **Predictable Space Allocation**: Grid explicitly defines where space comes from
2. **No JavaScript Dependency**: Layout works even if JavaScript fails
3. **Easier Debugging**: Single system to understand (Grid)
4. **Better Responsive Design**: Grid's `fr` units and `auto` rows handle viewport changes naturally
5. **Maintainability**: Changes to one area don't cascade unexpectedly
6. **Performance**: CSS Grid is highly optimized by browsers

### 4.8 Potential Challenges & Mitigations

#### Challenge 1: Phaser Canvas Sizing
**Risk**: Phaser may expect specific container dimensions. Mixing DOM-controlled sizing with Phaser-controlled scaling leads to unpredictable behavior.

**Mitigation**: 
- Establish clear sizing contract: DOM (`#phaser-container`) defines strict box; Phaser renders into it (see Section 4.4.3)
- Canvas CSS: Use `width: 100%; height: 100%` (fills container)
- Phaser config: Ensure Phaser Game dimensions match container size OR configure Phaser scale manager
- Avoid `max-width/max-height` with `width:auto/height:auto` (can cause weird shrinking)
- Avoid `height: auto` on canvas (breaks aspect ratio control)
- Use ResizeObserver on container (not window) to pass dimensions to Phaser resize logic (if implemented)
- Do not use `object-fit: contain` (doesn't work on `<canvas>`)
- Test thoroughly with different viewport sizes

#### Challenge 2: Stats Panel Overflow
**Risk**: Long player lists may overflow.

**Mitigation**:
- Ensure stats panels have `overflow-y: auto`
- Test with maximum expected content

#### Challenge 3: Playcall Center Height
**Risk**: Content may exceed `max-height` constraint.

**Mitigation**:
- `overflow-y: auto` allows scrolling
- Adjust `clamp()` values based on testing
- Consider collapsible sections if needed

#### Challenge 4: Migration Complexity
**Risk**: Large refactor may introduce bugs.

**Mitigation**:
- Phased approach (one component at a time)
- Comprehensive testing at each phase
- Keep backup branch for rollback

### 4.9 Success Criteria

1. ✅ **No JavaScript for core layout positioning**
2. ✅ **Layout works across all target viewport sizes**
3. ✅ **No regressions in existing functionality**
4. ✅ **Playcall Center always visible and properly positioned**
5. ✅ **Court canvas never covers Playcall Center**
6. ✅ **Stats panels remain accessible and scrollable**
7. ✅ **Scoreboard always visible at top**
8. ✅ **Responsive breakpoints work correctly**

### 4.10 Architectural Rules (Layout Invariants)

These rules are **non-negotiable** and must be enforced to maintain SS&S (Simple, Stable, & Scalable) architecture. Document these in code comments and enforce them in code reviews.

#### 4.10.1 Core Layout Rules

1. **Single Layout System**: Only CSS Grid defines major layout regions (scoreboard, court, stats panels, playcall). No mixing with Flexbox for primary layout structure.

2. **No Fixed Positioning for Layout**: `position: fixed` is only allowed for true overlays (modals, tooltips, popups). Layout-critical UI (scoreboard, playcall) must use Grid positioning.

3. **No JavaScript Layout Positioning**: JavaScript must never set `top`, `left`, `width`, or `height` properties for layout-critical elements. JavaScript can only:
   - Set dimensions for Phaser canvas (via ResizeObserver → Phaser resize)
   - Position overlays (modals, tooltips) relative to viewport
   - Handle animations and transitions (not layout)

4. **Grid/Flex Shrinking**: All grid and flex children that must shrink (e.g., court container, stats panels) must use `min-height: 0` or `min-width: 0` to allow proper shrinking behavior.

5. **Space Competition Prevention**: Court and HUD/overlays must never compete for vertical space. Grid allocates space; overlays position independently.

#### 4.10.2 Canvas Sizing Contract

6. **Single Sizing Authority**: Either DOM controls canvas container size OR Phaser controls canvas size, never both. Current contract: DOM (`#phaser-container`) defines strict box; Phaser renders into it.

7. **Canvas CSS**: Use `width: 100%; height: 100%` to fill container. Do NOT use `max-width/max-height` with `width:auto/height:auto`. Do NOT use `height: auto`. Phaser must be configured to render at container dimensions.

8. **ResizeObserver Scope**: ResizeObserver observes the Grid-allocated container (`#phaser-container`), not the window. Pass container dimensions to Phaser, not viewport dimensions.

#### 4.10.3 Grid Row Constraints

9. **Explicit Row Sizing**: Grid rows use explicit constraints (fixed heights, `clamp()`) rather than `auto` for layout-critical rows. Use `clamp()` directly (not nested in `minmax()`) for cross-browser reliability. Only overlay rows can use `auto`.

10. **No Double Grids**: Elements are placed directly into root grid areas. If nested grid is required for DOM structure, ensure all intermediate wrappers have `min-height: 0` and `min-width: 0`.

**Enforcement**: These rules should be documented in:
- Code comments at the top of `court.html` styles
- Architecture documentation
- Code review checklist
- Any future layout refactoring guides

---

## 5. Implementation Timeline Estimate

- **Phase 1 (Preparation)**: 2-4 hours
- **Phase 2 (Grid Container)**: 4-6 hours
- **Phase 3 (Component Migration)**: 8-12 hours
- **Phase 4 (JavaScript Cleanup)**: 2-4 hours
- **Phase 5 (Responsive Testing)**: 6-8 hours
- **Phase 6 (Documentation)**: 2-4 hours

**Total Estimate**: 24-38 hours

---

## 6. Alternative Approaches Considered

### 6.1 CSS Grid + Subgrid (Not Viable)
- **Why**: Subgrid support is still limited in browsers
- **Decision**: Use nested Grid instead

### 6.2 Flexbox-Only Approach
- **Why Not**: Flexbox doesn't provide explicit area names (`grid-template-areas` equivalent)
- **Decision**: Grid provides better semantic structure

### 6.3 Container Queries
- **Why Not**: Still experimental, limited browser support
- **Decision**: Use `@media` queries for now, consider migration later

---

## 7. Next Steps

1. **Review this plan** with frontend architecture expert
2. **Validate approach** against current codebase constraints
3. **Create feature branch** for refactor
4. **Begin Phase 1** (Preparation)
5. **Iterate** through phases with testing at each step

---

## Appendix A: Code Examples

### A.1 Current Problematic Code

```css
/* Current: Fixed positioning with JavaScript override */
#playcall-center {
  position: fixed !important;
  bottom: 0 !important;
  /* top set dynamically via JavaScript */
  left: calc(280px + var(--side-padding)) !important;
  right: calc(280px + var(--side-padding)) !important;
  max-height: clamp(160px, 22vh, 260px) !important;
}
```

```javascript
// Current: JavaScript-dependent positioning
function updatePlaycallPosition() {
  const canvas = document.querySelector('#phaser-container canvas');
  const playcall = document.getElementById('playcall-center');
  const canvasRect = canvas.getBoundingClientRect();
  playcall.style.top = `${canvasRect.bottom + 2}px`;
}
```

### A.2 Proposed Solution Code

```css
/* Proposed: Pure CSS Grid */
#app-grid {
  display: grid;
  grid-template-rows: 
    var(--scoreboard-height)                              /* Fixed height: scoreboard (100px) */
    1fr                                                    /* Flexible: main content area */
    clamp(160px, 25vh, 300px);                            /* Constrained: playcall center (grid-level constraint) */
  grid-template-columns: var(--player-stats-width) 1fr var(--player-stats-width);
  grid-template-areas:
    "scoreboard scoreboard scoreboard"
    "left-stats court right-stats"
    "playcall playcall playcall";
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

#playcall-center {
  grid-area: playcall;
  overflow-y: auto; /* Allow scrolling if content exceeds max height */
  /* No position: fixed, no JavaScript needed */
  /* Constraint is at grid row level, not element level */
}

#phaser-container {
  grid-area: court;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  min-height: 0; /* Critical: allows shrinking */
}

#phaser-container canvas {
  display: block;
  width: 100%;
  height: 100%;
  /* Canvas fills container; Phaser must be configured to match container dimensions */
}
```

---

**Document Version**: 1.0  
**Last Updated**: February 2, 2026  
**Author**: AI Assistant (Auto)  
**Status**: Draft - Awaiting Review
