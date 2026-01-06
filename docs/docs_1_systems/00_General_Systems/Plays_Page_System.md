## Plays Page System ✅ **IMPLEMENTED** (January 2025)

**Base Constants**

1. **Page Location**: `FrontEnd/static/play-details.html`
2. **API Endpoint**: `GET /api/play/{play_name}` - Fetches play data including skeleton and copy
3. **Data Source**: `plays_collection` in MongoDB (universal collection)
4. **Play Types**: Motion Plays (continuous loop) and Set Plays (restart after completion)
5. **Animation**: Auto-starts on page load, uses same system as Play Builder v2

**Plays Page System Flow (6 Steps)**

1. **Page Load** - Extract `play_name` from URL parameters
2. **Data Fetch** - Fetch play data from `/api/play/{play_name}` endpoint
3. **Skeleton Loading** - Load appropriate skeleton based on play type (Motion: `base_loop`, Set Play: `successful` variant)
4. **Copy Display** - Display play copy text (`copy_1`, `copy_2`, `copy_3`) in info containers
5. **Animation Start** - Auto-start animation with continuous loop behavior
6. **Back Navigation** - Stop animation and navigate to page specified by `backTo` parameter

**Long Form Documentation**

### Overview

The Plays Page System provides detailed views for individual plays, displaying play animations and descriptive content. Each play has its own dedicated page that shows the play's animation and information.

**Location:** `FrontEnd/static/play-details.html`  
**Purpose:** Display play details, animations, and information  
**Status:** ✅ Fully implemented with auto-animating play visualization and dynamic back navigation

### Navigation

**Entry Point:**
- Play names in the Playbooks page are clickable links (except "To Be Added" placeholders)
- Clicking a play name navigates to `/play-details.html` with:
  - `play_name` parameter (URL encoded)
  - `backTo` parameter (explicitly set to `playbooks.html` or other source page)
  - All context parameters (mode, team_id, game_id/tournament_id/franchise_id, quarter, lineup, etc.)
  - `from` parameter (preserved for target page's back navigation)

**Back Navigation:**
- Back button (top-left) navigates to page specified by `backTo` parameter
- Defaults to `playbooks.html` if `backTo` parameter is missing (backward compatibility)
- Stops animation before navigation to prevent conflicts
- Preserves all game context parameters using `TimeoutNavigationHelper`

### Layout Structure

**Header:**
- **Play Name:** Centered, large gold font (2.5rem), with text shadow
- **Play Type:** Centered, smaller font (1.2rem), muted color (Motion or Set Play)

**2-Column Layout:**
- **Left Column (50% width):**
  - Three horizontal info containers
  - Each container has:
    - Title (gold color, 1.1rem): "Play Description", "Key Concepts", "Usage Tips"
    - Content area displaying play copy text (`copy_1`, `copy_2`, `copy_3`)
  - Containers are vertically centered as a unit, middle-aligned with animation container
  
- **Right Column (50% width):**
  - Court animation container
  - Same dimensions and styling as Play Builder v2 animation container
  - Centered horizontally and vertically within its column
  - Uses environment-aware court image path (supports localhost and Netlify)

### Animation System

**Auto-Start Behavior:**
- Animation begins automatically on page load
- No user interaction required
- Fetches play data from `/api/play/{play_name}` endpoint
- Loads appropriate skeleton based on play type:
  - **Motion Plays:** Uses `base_loop` skeleton (supports `versions` array format or direct `steps` array)
  - **Set Plays:** Uses `successful` variant, version v0 from `versions` array (or direct `steps` for backward compatibility)

**Animation Controls:**
- **Pause/Resume Button:** Located below the animation container, horizontally centered
- Button text changes: "⏸️ Pause" when playing, "▶️ Resume" when paused
- Button styling changes: Blue gradient when playing, green gradient when paused
- Clicking pauses/resumes the animation at the current step
- Animation state persists when paused (can resume from same step)

**Animation Logic:**
- Reuses animation system from Play Builder v2:
  - Same constants (court coordinates, positions, ball-handling actions)
  - Same rendering logic (`renderCourtVisualization()`)
  - Same step-by-step animation (`animateNextStep()`)
  - Player icons positioned using percentage-based coordinates
  - Ball sprite follows ball handler or pass/shoot actions
  - Smooth transitions between steps (1 second delay per step)

**Motion Play Animation:**
- Continuous loop behavior
- When reaching final step, loops back to step 0
- Runs indefinitely until page is closed or navigation occurs

**Set Play Animation:**
- Runs animation from start to finish
- Pauses for 2 seconds after completion
- Restarts from step 0
- Repeats continuously

**Player Rendering:**
- Player icons positioned at court locations based on skeleton step data
- Icons animate smoothly between positions using CSS transitions
- Ball sprite follows ball handler or shows pass/shoot animations
- Position offsets applied for screen actions (collision handling)

### Data Flow

**Page Load:**
1. Extract `play_name` from URL parameters
2. Fetch play data from `/api/play/{play_name}` endpoint
3. Display play name and type in header
4. Load skeleton data:
   - **Motion:** `base_loop` (checks for `versions` array format first, falls back to direct `steps` array)
   - **Set Play:** `successful` variant, version v0 from `versions` array (or direct `steps` for backward compatibility)
5. Load and display copy text (`copy_1`, `copy_2`, `copy_3`) in info containers
6. Initialize animation state
7. Auto-start animation

**Animation Loop:**
1. Process current step's `pos_actions` data
2. Update player positions and actions
3. Render court visualization with player icons and ball
4. Move to next step after 1 second delay
5. Handle looping logic (Motion: loop to 0, Set Play: pause then restart)

### Copy Display

**Data Structure:**
- Play copy stored in `copy` field of play document
- Format: `{ "copy_1": "...", "copy_2": "...", "copy_3": "..." }`
- Optional field (may be `null` or missing)

**Display Logic:**
- Checks for `playData.copy` object
- Handles both object format (`copy_1`, `copy_2`, `copy_3`) and array format
- Displays copy text in three info containers: "Play Description", "Key Concepts", "Usage Tips"
- Shows placeholder "Copy Goes Here" if copy data is missing

### Responsive Design

**Desktop:**
- 2-column grid layout
- All content fits above the fold
- Left column containers vertically centered
- Animation container centered in right column

**Mobile/Tablet:**
- Stacks vertically (right column first, then left column)
- Animation container remains full width
- Info containers stack below animation
- Maintains readability and usability

### Key Files

**Frontend:**
- `FrontEnd/static/play-details.html` - Main page structure and animation logic
- `FrontEnd/static/playbooks.js` - Navigation integration (clickable play names, sets `backTo` parameter)
- `FrontEnd/static/js/shared/timeoutNavigationHelper.js` - Parameter building for navigation

**Backend:**
- `BackEnd/api/play_routes.py` - `GET /api/play/{play_name}` endpoint

**API Endpoints:**
- `GET /api/play/{play_name}` - Fetch play data for details page (returns play document with skeletons and copy)

### Back Button Nav ✅ **IMPLEMENTED** (January 2025)

**Purpose:**
Dynamic back navigation system that allows the play details page to navigate back to any source page, making it future-proof for new entry points.

**Implementation:**

1. **Navigation TO Play Details:**
   - Source page (e.g., `playbooks.js`) sets `backTo` parameter when navigating to play-details
   - Example: `params.set('backTo', 'playbooks.html')`
   - This explicitly tells play-details where to navigate back to

2. **Back Button Click:**
   - `goBack()` function in `play-details.html` checks for `backTo` parameter
   - If `backTo` exists: Navigates to that page
   - If `backTo` missing: Defaults to `playbooks.html` (backward compatibility)
   - Stops animation before navigation to prevent conflicts/freezes
   - Preserves all game context parameters using `TimeoutNavigationHelper`

3. **Animation Handling:**
   - `stopAnimation()` called at start of `goBack()` function
   - Prevents animation loop from blocking navigation
   - Clears animation intervals and resets animation state

4. **Parameter Preservation:**
   - Uses `TimeoutNavigationHelper.buildGameNavigationParams()` to preserve all game context
   - Preserves `from` parameter for target page's own back navigation
   - Maintains game state across navigation (quarter, game_id, lineup, etc.)

**Benefits:**
- **Explicit:** Source page explicitly sets where to go back to
- **Dynamic:** Works from any entry point (playbooks, game-plan, command center, etc.)
- **Future-Proof:** New entry points just need to set `backTo` parameter
- **Backward Compatible:** Defaults to `playbooks.html` if `backTo` is missing

**Example Usage:**
```javascript
// From playbooks.js (current)
params.set('backTo', 'playbooks.html');

// Future: from game-plan.html
params.set('backTo', 'game-plan.html');

// Future: from command center
params.set('backTo', 'franchise-command-center.html');
```

**Key Files:**
- `FrontEnd/static/play-details.html` - `goBack()` function (lines 402-459)
- `FrontEnd/static/playbooks.js` - `navigateToPlayDetails()` function (sets `backTo` parameter)

