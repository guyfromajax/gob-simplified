# Player Attribute System (**verified 2026-06-13**)

> Frontend display-order/formatting doc. Verified vs `training-report.js`: emoji map (`getEmotionEmoji` L1103-1109: ≥80 😎 / ≥60 😊 / ≥40 😐 / ≥20 😕 / else 😡) and momentum-pill math (`createMomentumPill` L1112+: green=success / red=error / `(mo/10)*50%` fill, +10→50%) **match exactly**; NG `toFixed(2)`, integer floor for SC–FT (`createAttributeCell` L1046+). **Correction applied:** `ATTRIBUTE_ORDER` is **14 attributes (MO excluded)** at L53-55 — *not* 15 at L16-18. MO is rendered on the **lineup screen** (`set-lineup.js` L1528/L1568), not in the Training Report grid; `createAttributeCell` retains an MO branch but the Report's order array never feeds it MO.

## Base Constants

**Purpose:** Defines the standard display order and formatting rules for player attributes across all game interfaces.

**Core Attribute Order (Training Report = 14 attributes; MO is a 15th attribute shown only on the lineup screen):**
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
15. MO - Momentum *(excluded from `ATTRIBUTE_ORDER` / Training Report; rendered on the lineup screen)*

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
**Key Constant:** `ATTRIBUTE_ORDER` in `training-report.js` (~L53-55) — **14 entries, MO excluded** (see code comment L52: "MO (Momentum) is excluded from Training Report display")

### Standard Attribute Display Order

**CRITICAL:** When displaying player attributes in a horizontal row, they must appear in this exact order. *(The Training Report renders #1-14 only; MO (#15) is shown on the lineup screen, not the Report grid.)*

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
// FrontEnd/static/training-report.js (~L53-55) — MO intentionally excluded
const ATTRIBUTE_ORDER = [
  'SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT', 'NG', 'EM'
];
```

> MO is **not** in this array, so the Training Report grid does not render it. MO's pill is shown on the lineup screen instead (`set-lineup.js`). The `createAttributeCell` MO branch (`training-report.js` ~L1074) only fires if a caller passes `MO`, which `ATTRIBUTE_ORDER` no longer does.

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
- **Attributes view:** Displays the 14 `ATTRIBUTE_ORDER` attributes (SC–EM) in standard order with appropriate formatting (MO excluded)
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
  - `ATTRIBUTE_ORDER` constant (~L53-55, 14 entries, MO excluded)
  - Attribute filtering and ordering logic (~L937-951)
  - `createAttributeCell` NG/EM/MO formatting (~L1046), `getEmotionEmoji` (~L1103), `createMomentumPill` (~L1112)
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
