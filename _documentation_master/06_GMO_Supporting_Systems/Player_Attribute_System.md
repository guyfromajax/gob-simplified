# Player Attribute System ✅ **COMPLETE** (January 2025)

## Base Constants

**Purpose:** Defines the standard display order and formatting rules for player attributes across all game interfaces.

**Core Attribute Order (15 attributes):**
1. SC - Shooting Close
2. SH - Shooting
3. ID - Inside Defense
4. OD - Outside Defense
5. PS - Passing
6. BH - Ball Handling
7. RB - Rebounding
8. ST - Strength
9. AG - Agility
10. ND - Endurance
11. IQ - Intelligence Quotient
12. FT - Free Throws
13. NG - Nerve/Game (Energy)
14. EM - Emotion
15. MO - Momentum

**Formatting Rules:**
- **SC through FT (12 attributes)**: Integer values, no decimals
- **NG**: Decimal with 2 places (0.00-1.00)
- **EM**: Emoji display (0-100 range)
- **MO**: Red/Green horizontal pill visualization (-10 to +10)

**Key Files:**
- `FrontEnd/static/training-report.js` - Attribute order constant and display logic
- `FrontEnd/static/training-report.css` - Momentum pill styling
- `FrontEnd/static/set-lineup.js` - Lineup screen attribute display

## System Flow

1. **Attribute Order Constant**: `ATTRIBUTE_ORDER` array defines standard order
2. **Display Rendering**: All attribute displays use this order for consistency
3. **Formatting Application**: Each attribute type uses appropriate formatting (integer, decimal, emoji, pill)
4. **Subset Displays**: When showing subset, maintain relative order

## Long Form Documentation

### Overview

The Player Attribute System ensures consistency in how player attributes are presented across all game interfaces. This includes the standard display order, formatting rules for different attribute types, and visual representations for special attributes (NG, EM, MO).

**Status:** ✅ Fully implemented - Standard attribute order enforced in Training Report and other displays

**Location:** Frontend display logic  
**Key Constant:** `ATTRIBUTE_ORDER` in `training-report.js` (lines 16-18)

### Standard Attribute Display Order

**CRITICAL:** When displaying all player attributes in a horizontal row, they must appear in this exact order:

1. **SC** - Shooting Close
2. **SH** - Shooting
3. **ID** - Inside Defense
4. **OD** - Outside Defense
5. **PS** - Passing
6. **BH** - Ball Handling
7. **RB** - Rebounding
8. **ST** - Strength
9. **AG** - Agility
10. **ND** - Endurance
11. **IQ** - Intelligence Quotient
12. **FT** - Free Throws
13. **NG** - Nerve/Game (Energy)
14. **EM** - Emotion
15. **MO** - Momentum

**Implementation:**
```javascript
// FrontEnd/static/training-report.js (lines 16-18)
const ATTRIBUTE_ORDER = [
  'SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT', 'NG', 'EM', 'MO'
];
```

**Applies To:**
- Training Report Player Report section
- Lineup screens
- Player detail pages
- Any other attribute grid or table displays
- Subset displays (maintain relative order)

### Attribute Display Formatting

#### Standard Integer Attributes (SC through FT)

The first 12 attributes (SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT) are displayed as **integer values**:
- No decimal places
- Direct numeric display (e.g., `85`, `72`, `50`)
- Range: 0-100 (typical)

#### NG (Nerve/Game / Energy)

- **Format:** Decimal value with 2 decimal places
- **Range:** 0.00 to 1.00 (typically displayed as 0.90, 0.99, 1.00, etc.)
- **Display Examples:** `1.00`, `0.99`, `0.98`, `0.90`, `0.75`
- **Purpose:** Represents player energy level (100% = 1.00)
- **Storage:** Stored as float in player attributes

#### EM (Emotion)

- **Format:** Emoji display based on value
- **Range:** 0-100
- **Emoji Mapping:**
  - **>= 80:** 😎 (Sunglasses) - Very positive
  - **>= 60:** 😊 (Big smile) - Positive
  - **>= 40:** 😐 (Straight face) - Neutral
  - **>= 20:** 😕 (Slight frown) - Negative
  - **< 20:** 😡 (Angry face) - Very negative
- **Purpose:** Visual representation of player emotional state
- **Implementation:** Value converted to emoji during display rendering

#### MO (Momentum)

- **Format:** Red/Green horizontal pill visualization
- **Range:** -10 to +10
- **Visual Design:**
  - **Container:** Horizontal pill with dark background
  - **Center Line:** Yellow vertical line at 50% (center point)
  - **Positive Momentum (0 to +10):** Green fill extending right from center
    - Fill width proportional to value (e.g., +5 = 25% fill, +10 = 50% fill)
  - **Negative Momentum (-10 to 0):** Red fill extending left from center
    - Fill width proportional to absolute value (e.g., -5 = 25% fill, -10 = 50% fill)
  - **No Integer Display:** The numeric value is NOT displayed on top of the pill
- **Purpose:** Visual representation of player momentum trend
- **CSS:** Styled in `training-report.css`

### Implementation Examples

**Training Report Player Report:**
- **Attributes view:** Displays all 15 attributes in standard order with appropriate formatting
- **Training Changes view:** Displays only changed attributes, maintaining standard order
- **Code:** `training-report.js` uses `ATTRIBUTE_ORDER` constant to filter and order attributes

**Lineup Screens:**
- Follows same order and formatting rules
- EM and MO use same visual representations
- Reference implementation in `set-lineup.js`

**Player Detail Pages:**
- Should follow same order and formatting rules
- When displaying a subset of attributes, maintain relative order (e.g., if showing SC, SH, MO, they appear in that order)

### Key Files

**Frontend:**
- `FrontEnd/static/training-report.js` - Training Report attribute display implementation
  - `ATTRIBUTE_ORDER` constant (lines 16-18)
  - Attribute filtering and ordering logic (lines 271-284)
- `FrontEnd/static/training-report.css` - Momentum pill styling
- `FrontEnd/static/set-lineup.js` - Lineup screen attribute display (reference for EM/MO formatting)

**Backend:**
- `BackEnd/models/player.py` - Player class with attribute storage
- `BackEnd/constants/__init__.py` - Attribute constant definitions (if any)

### Consistency Requirements

**All attribute displays must:**
1. Use the exact order defined in `ATTRIBUTE_ORDER`
2. Apply appropriate formatting based on attribute type
3. Maintain relative order when displaying subsets
4. Use consistent visual representations for NG, EM, and MO

**Benefits:**
- ✅ **User Experience:** Consistent attribute presentation across all interfaces
- ✅ **Maintainability:** Single source of truth for attribute order
- ✅ **Visual Clarity:** Special formatting for NG, EM, MO improves readability
- ✅ **Scalability:** Easy to add new attributes while maintaining order
