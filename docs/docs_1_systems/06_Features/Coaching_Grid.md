# Coaching Grid ✅ **COMPLETE** (January 2025)

## Base Constants

**Purpose:** Desktop-only visualization page that displays a team's coaching status across four coaching archetypes in a 2D grid view.

**Core Components:**
- **2D Grid**: Crosshair design with vertical and horizontal axes intersecting at center
- **Four Archetype Dots**: Positioned based on effectiveness and momentum scores
- **Axis Labels**: "Embedded" (top), "Fragile" (bottom), "Stagnant" (left), "Compounding" (right)

**Data Mapping:**
- **Y-Axis (Effectiveness)**: Range 0-100, midpoint 50, conversion: `yPercent = 100 - effectiveness`
- **X-Axis (Momentum)**: Range 0-10, midpoint 5, conversion: `xPercent = (momentum / 10) * 100`

**Archetype Colors:**
- Authoritarian: `#ff4444` (red) - `var(--color-authoritarian)`
- Systems: `#d4a017` (yellow/burnt yellow) - `var(--color-systems-coach)`
- Player Maximizer: `#2d8f2d` (green) - `var(--color-player-maximizer)`
- Culture: `#9b59b6` (purple) - `var(--color-culture-builder)`

**Key Files:**
- `FrontEnd/static/coaching-grid.html` - Page structure and grid container
- `FrontEnd/static/coaching-grid.css` - Styling for grid, axes, dots, and labels
- `FrontEnd/static/coaching-grid.js` - Positioning logic and data mapping functions

## System Flow

1. **Page Load**: Coaching grid page loads with placeholder data
2. **Data Extraction**: JavaScript reads `data-effectiveness` and `data-momentum` attributes from archetype dots
3. **Position Calculation**: Converts effectiveness and momentum to X/Y percentages using conversion functions
4. **Dot Positioning**: Applies calculated positions using CSS `left` and `top` properties
5. **Visualization**: Dots displayed on grid with labels and colors

## Long Form Documentation

### Overview

The Coaching Grid is a desktop-only visualization page that displays a team's coaching status across four coaching archetypes. It provides a 2D grid view showing each archetype's position based on effectiveness and momentum scores.

**Location:** `FrontEnd/static/coaching-grid.html`  
**Status:** ✅ Fully implemented with placeholder data positioning  
**Scope:** User team only (computer teams not viewable)

### Layout Structure

**Page Title:**
- Centered "Coaching Grid" heading at top of page
- Font size: 2.5rem, font weight: 600

**Main Content:**
- Large 2D grid container centered on page
- Crosshair design with vertical and horizontal axes intersecting at center
- Square aspect ratio (1:1)
- Max width: 600px (responsive for desktop)
- White background with subtle border and shadow

**Axis Endpoint Labels:**
- **Top center:** "Embedded" (high effectiveness, 100)
- **Bottom center:** "Fragile" (low effectiveness, 0)
- **Left center:** "Stagnant" (low momentum, 0)
- **Right center:** "Compounding" (high momentum, 10)
- Font size: 1.2rem, font weight: 600

**Archetype Dots:**
- Four circular dots positioned on the grid
- Each dot has a text label placed near it
- Labels: "Authoritarian", "Systems", "Player Maximizer", "Culture"
- Dot size: 20-24px diameter
- Labels: Font size 0.9-1rem, neutral gray

### Data Mapping

**Y-Axis (Effectiveness):**
- Range: 0-100
- Midpoint: 50 (center of grid)
- **Top (Embedded):** 100 (maximum effectiveness)
- **Bottom (Fragile):** 0 (minimum effectiveness)
- Conversion: `yPercent = 100 - effectiveness` (inverted: higher effectiveness = higher on grid)

**X-Axis (Momentum):**
- Range: 0-10
- Midpoint: 5 (center of grid)
- **Right (Compounding):** 10 (maximum momentum)
- **Left (Stagnant):** 0 (minimum momentum)
- Conversion: `xPercent = (momentum / 10) * 100`

**Positioning Logic:**
- Dots positioned using `left` and `top` CSS properties with percentage values
- Transform used to center dots on their coordinates (`translate(-50%, -50%)`)
- Functions: `effectivenessToY(effectiveness)` and `momentumToX(momentum)` in `coaching-grid.js`

### Archetype Colors

Each dot uses the same color as the corresponding coaching archetype header colors on the Training page:

- **Authoritarian:** `#ff4444` (red) - `var(--color-authoritarian)`
- **Systems:** `#d4a017` (yellow/burnt yellow) - `var(--color-systems-coach)`
- **Player Maximizer:** `#2d8f2d` (green) - `var(--color-player-maximizer)`
- **Culture:** `#9b59b6` (purple) - `var(--color-culture-builder)`

Colors are defined as CSS variables in `coaching-grid.css`, matching `training.css` for consistency.

### Visual Styling

**Dots:**
- Medium-sized (20-24px diameter)
- Subtle border/outline (white border, shadow) for visibility on light background
- Hover effect: Slight scale increase and enhanced shadow
- Positioned using absolute positioning with percentage-based coordinates
- Background color matches archetype color

**Axis Lines:**
- Thin, neutral gray (`#999`)
- Vertical line: 1px width, full height, centered horizontally
- Horizontal line: 1px height, full width, centered vertically

**Labels:**
- **Axis labels:** Bold-ish, larger font (1.2rem), positioned at axis endpoints
- **Dot labels:** Smaller font (0.9-1rem), neutral gray, positioned to the right of each dot
- Consistent spacing and alignment

**Grid Container:**
- White background with subtle border and shadow
- Square aspect ratio (1:1)
- Responsive sizing for desktop (max-width: 600px)
- Border radius: 8px

### Data Source

**Coaching Object Structure:**
The grid reads data from the team's `coaching` object in the universal `teams` collection:

```json
{
  "coaching": {
    "authoritarian": {
      "score": 24,      // effectiveness value (0-100)
      "momentum": 0     // momentum value (0-10)
    },
    "systems coach": {
      "score": 92,
      "momentum": 5
    },
    "player maximizer": {
      "score": 35,
      "momentum": 9
    },
    "culture builder": {
      "score": 50,
      "momentum": 3
    }
  }
}
```

**Field Mapping:**
- `score` → Y-axis position (effectiveness)
- `momentum` → X-axis position (momentum)

**Current Implementation:**
- Uses placeholder data in HTML `data-*` attributes
- Data attributes: `data-archetype`, `data-effectiveness`, `data-momentum`
- JavaScript reads these attributes and calculates positions on page load

**Placeholder Data:**
- Authoritarian: effectiveness=24, momentum=0 (lower-left quadrant)
- Systems: effectiveness=92, momentum=5 (upper-center)
- Player Maximizer: effectiveness=35, momentum=9 (lower-right quadrant)
- Culture: effectiveness=50, momentum=3 (center-left)

### Implementation

**Positioning Functions:**

**`effectivenessToY(effectiveness)`:**
- Converts effectiveness (0-100) to Y coordinate percentage
- Formula: `return 100 - effectiveness` (inverted: higher effectiveness = higher on grid)
- Location: `coaching-grid.js` (line 9)

**`momentumToX(momentum)`:**
- Converts momentum (0-10) to X coordinate percentage
- Formula: `return (momentum / 10) * 100`
- Location: `coaching-grid.js` (line 19)

**`positionDots()`:**
- Positions all archetype dots on the grid
- Reads `data-effectiveness` and `data-momentum` attributes
- Calculates X/Y percentages using conversion functions
- Applies positions using CSS `left` and `top` properties
- Location: `coaching-grid.js` (line 27)

**Initialization:**
- Runs on page load via `DOMContentLoaded` event listener
- Calls `positionDots()` to position all dots
- Console logs positioning information for debugging

### Key Files

**Frontend:**
- `FrontEnd/static/coaching-grid.html` - Page structure and grid container
  - Grid container with crosshair axes
  - Four archetype dots with data attributes
  - Axis labels at endpoints
- `FrontEnd/static/coaching-grid.css` - Styling for grid, axes, dots, and labels
  - CSS variables for archetype colors (matching training.css)
  - Grid container styling (white background, border, shadow)
  - Axis line styling (neutral gray, 1px width/height)
  - Dot styling (colors, borders, hover effects)
  - Label positioning and typography
- `FrontEnd/static/coaching-grid.js` - Positioning logic and data mapping functions
  - `effectivenessToY()` - Effectiveness to Y coordinate conversion
  - `momentumToX()` - Momentum to X coordinate conversion
  - `positionDots()` - Main positioning function
  - Page load initialization

**Backend:**
- Currently uses placeholder data (no API integration yet)
- Future: Will connect to API endpoint to fetch user team's coaching data from appropriate mode document

### Future Enhancements

**Data Wiring:**
- Connect to API endpoint to fetch user team's coaching data
- Load coaching object from appropriate mode document (Single Game, Tournament, Franchise)
- Update dot positions dynamically based on real data
- Handle mode-specific data paths (`franchise_teams.{team_id}.coaching` vs `teams.{team_id}.coaching`)

**Interactive Features:**
- Tooltips showing exact effectiveness and momentum values on hover
- Click dots to view detailed archetype information
- Animation when positions change (smooth transitions)

**Visual Enhancements:**
- Grid lines or tick marks for better readability
- Quadrant labels or shading to show different coaching zones
- Legend explaining axis meanings
- Responsive design for mobile devices (currently desktop-only)

**Reference Documentation:**
- `docs/docs_1_systems/00_Data_Systems/Database_System.md` - Coaching attributes structure in universal teams collection
- `docs/docs_1_systems/06_GMO_Supporting_Systems/Training_System.md` - Training system that modifies coaching attributes

