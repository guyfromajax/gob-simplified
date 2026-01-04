## Play Builder System ✅ **COMPLETE** (January 2025)

**Base Constants**

1. **Play Types**: "motion" or "set_play"
2. **Set Play Variants**: `successful`, `mid_play_change`, `contested`, `broken` (4 variants)
3. **Motion Play Variants**: `base_loop` (1 variant)
4. **Version System**: Mid-Play Change, Contested, Broken support 6 versions each (v1-v6)
5. **Successful Variant**: Single skeleton only (no versions)
6. **Motion Plays**: No versions (Base Loop only)

**Play Builder System Flow (4 Steps)**

1. **Create/Load Play** - Enter name, select type (Motion/Set Play), select focus (Set Play only), create or load existing
2. **Build Variants** - Switch between variant tabs, build steps for each variant/version
3. **Mark Complete** - Mark variants as complete when ready (required for Successful/Base Loop before Save & Close)
4. **Save** - Save Draft (Ctrl+S) or Save & Close (validates Successful/Base Loop completion)

**Long Form Documentation**

### Overview

Play Builder V2 (`play-builder-v2.html`) is a web-based tool for creating and editing offensive plays. It supports two distinct play types: **Set Plays** and **Motion Plays**, each with different structures and requirements.

**Key Features:**
- Create new plays or load existing ones
- Variant tab system (4 variants for Set Plays, 1 for Motion Plays)
- Version system (6 versions for Mid-Play Change, Contested, Broken variants)
- Auto-copy from Successful/Base Loop
- Clone function for manual copying
- Completion tracking with status indicators
- Multiple save options (Draft, Save & Close, keyboard shortcuts)

### Play Types

#### Set Plays
- **Structure**: Four skeleton variants (`successful`, `mid_play_change`, `contested`, `broken`)
- **Focus**: Required - must select Inside, Attack, Outside, or Balanced
- **Variants**:
  - `successful`: Single skeleton with direct `steps` array (no versions)
  - `mid_play_change`, `contested`, `broken`: `versions` array (v1-v6), each with a `steps` array
- **Final Step Requirement**: Must have a `shoot` action in the final step
- **Shooter Validation**: Shots only allowed in final step

#### Motion Plays
- **Structure**: Single skeleton variant (`base_loop`)
- **Focus**: Not required (null in database)
- **Variants**: Only `base_loop` with direct `steps` array (no versions)
- **Loop Structure**: Circular motion with `is_final_step` flag marking loop end
- **Final Step**: Marked with checkbox when building - sets `is_final_step: true` and `loop_back_to: 0`
- **Shooter Validation**: Shots can occur at any step (no restrictions)

### Building Process

#### Step 1: Play Creation
1. **Enter Play Name**: Text input for play name
2. **Select Play Type**: Dropdown - "Motion" or "Set Play"
3. **Select Play Focus** (Set Play only): Dropdown - "Inside", "Attack", "Outside", or "Balanced"
   - Disabled for Motion plays
   - Required for Set Plays to enable "Create Play" button
4. **Create Play Button**: Enabled when name + type (+ focus for Set Plays) are provided
5. **Load Existing**: Select from dropdown and click "Load Play"

#### Step 2: Step Building
1. **Starting Formation Selection**: 
   - Preset formations: "3-2", "4-1", "5-0", "Screen Entry"
   - Custom: Manual positioning
   - **Note**: Formation must be manually saved as Step 0 by clicking "Add Step" after selection
2. **Step Building**:
   - Drag-and-drop players to court locations
   - Assign actions (handle_ball, pass, receive, shoot, drive, get_open)
   - Add position offsets for screens
   - **Motion Plays**: Checkbox to "Mark as Final Step (Loop End)" available when building new steps
3. **Add Step Button**: Saves current step and increments to next step
   - Timestamp calculation: `(currentStep - 1) * 300` (Step 0 = 0ms, Step 1 = 300ms, etc.)
4. **Variant Complete Button**: 
   - Auto-submits current step if incomplete
   - Auto-fills incomplete positions from previous step
   - Validates variant structure

#### Step 3: Variant Management
- **Variant Tabs**: Switch between variants using tabs
  - Set Plays: 4 tabs (Successful, Mid-Play Change, Contested, Broken)
  - Motion Plays: 1 tab (Base Loop)
- **Status Indicators**: 
  - 🟢 Green = Complete
  - 🟡 Yellow = In Progress (has steps, not marked complete)
  - ⚪ White/Gray = Not Started
- **Version Selector** (Set Plays only): Appears for Mid-Play Change, Contested, Broken variants
  - Switch between v1-v6 versions
  - Shows which versions exist and their shooter info
- **Auto-Copy**: When switching to empty variant/version, automatically copies from Successful (Set Plays) or Base Loop (Motion Plays)
- **Clone Function**: Manual "Clone from Successful/Base Loop" button (hidden when editing Successful/Base Loop)

#### Step 4: Save Options
1. **💾 Save Draft** (or Ctrl+S / Cmd+S)
   - Saves current state without closing
   - Great for incremental saves while building
   - No validation requirements

2. **✅ Save & Close**
   - Validates that "Successful" (Set Plays) or "Base Loop" (Motion Plays) is marked complete
   - Saves and returns to success screen
   - Use when all variants are ready

### Auto-Opposite Skeleton Creation

**Feature**: When a skeleton is marked as complete, an opposite version is automatically created (flipping "upper" and "lower" locations).

**Implementation:**
- Triggered when skeleton is marked complete (not step-by-step)
- Creates opposite skeleton as additional version within same variant
- Does not overwrite existing skeletons
- If no empty versions left, creates new version
- Applies to all variant types (including `base_loop` and `successful`)

**Location**: `FrontEnd/static/play-builder-v2.html` - `createOppositeVersionIfNeeded()`

### Database Structure

#### Set Play Structure
```json
{
  "name": "Play Name",
  "play_type": "set_play",
  "play_focus": "inside|attack|outside|balanced",
  "skeletons": {
    "successful": {
      "steps": [...],
      "complete": true
    },
    "mid_play_change": {
      "versions": [
        { "version": "v1", "steps": [...] },
        { "version": "v2", "steps": [...] }
      ]
    },
    "contested": {
      "versions": [...]
    },
    "broken": {
      "versions": [...]
    }
  }
}
```

#### Motion Play Structure
```json
{
  "name": "Play Name",
  "play_type": "motion",
  "play_focus": null,
  "skeletons": {
    "base_loop": {
      "steps": [
        {...},
        {"is_final_step": true, "loop_back_to": 0, ...}
      ],
      "complete": true
    }
  }
}
```

**Key Points:**
- **Set Plays**: `successful` has simple structure (steps array), other variants have `versions` array
- **Motion Plays**: Only `base_loop` variant, no versions, no other variants
- **Versions**: Only `mid_play_change`, `contested`, and `broken` have versions (v1-v6)
- **Storage**: Only versions with steps are saved (empty versions are omitted)

### Play Creation Data Structure

When a new play is created via Play Builder V2, the following fields are automatically populated:

#### Required Fields (Always Set)
- **`_id`**: MongoDB ObjectId (auto-generated)
- **`name`**: Play name (user-provided)
- **`play_type`**: "motion" or "set_play" (converted from user selection)
- **`play_focus`**: Set Plays: "inside", "attack", "outside", or "balanced"; Motion Plays: `null`
- **`skeletons`**: Complete skeleton structure with all variants and steps

#### Initialized Fields (Default Values)
- **`effectiveness`**: `0` (0-100 scale)
- **`cloaking`**: `0` (0-10 scale)
- **`momentum`**: `0` (0-10 scale)
- **`copy`**: `{}` (empty object, for play details page copy text)

#### Statistics Fields (Initialized to Zero)
- **`game_stats`**: `{times_run: 0, shot_attempts: 0, made_shots: 0, turnovers: 0, offensive_fouls: 0, defensive_fouls: 0}`
- **`season_stats`**: Same structure as `game_stats`, all initialized to 0

**Implementation:**
- **Frontend**: `savePlayToDatabase()` function builds play data object, explicitly sets all fields
- **Backend**: `BackEnd/api/play_routes.py` - `create_play()` endpoint validates and saves, uses `upsert=True` (matched by `name`)

### Validation Rules

1. **Successful Variant (Set Plays) / Base Loop (Motion Plays)**
   - Must be marked complete before "Save & Close"
   - Can save incomplete with "Save Draft"
   - Single version only (no version selector)

2. **Other Variants (Set Plays Only)**
   - No completion requirement for "Save & Close"
   - But recommended to mark complete when ready
   - Each version (v1-v6) is independent
   - OK to have some versions empty and others complete

3. **Empty Variants/Versions**
   - OK to have empty variants or versions (just 0 steps)
   - They'll use "successful" skeleton (Set Plays) or "base_loop" (Motion Plays) as fallback in game
   - Empty versions within a variant will fall back to the variant's other versions or successful

### Key Functions

**Frontend (`FrontEnd/static/play-builder-v2.html`):**
- `savePlayToDatabase()` - Saves play to MongoDB via `/api/plays` endpoint
- `updateAnimationVariantDropdown()` - Updates animation preview dropdown with available variants
- `validateCurrentStep()` - Validates step assignments (Set Plays: shoot only in final step; Motion Plays: no restrictions)
- `validateLoopStructure()` - Validates Motion play loop structure (checks `is_final_step` flag, at least 2 steps)
- `createOppositeVersionIfNeeded()` - Auto-creates opposite skeleton when marked complete
- `updateVariantTabsVisibility()` - Controls variant tab visibility based on play type

**Backend (`BackEnd/api/play_routes.py`):**
- `create_play()` - Validates and saves play data, uses `upsert=True` (matched by `name`)
- `PlayCreate` Pydantic model - Defines accepted fields

### Key Files

**Frontend:**
- `FrontEnd/static/play-builder-v2.html` - Play Builder V2 interface and logic

**Backend:**
- `BackEnd/api/play_routes.py` - Play creation/update endpoints
- `BackEnd/models/play_manager.py` - Play data management

**Database:**
- `plays_collection` - Universal plays library (MongoDB)

