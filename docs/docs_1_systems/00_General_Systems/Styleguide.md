# Style Guide

## Purpose
This document defines the core visual and interaction standards for Geeked-Out Basketball. It is intended to establish one shared design language across command centers and, over time, the full product.

## Color System

### Core Brand Color
- Default primary color: `#27408E`

### Universal Secondary Colors
- Dark neutral: `#747474`
- Mid neutral: `#999999`
- White: `#FFFFFF`
- Black at 50% opacity: `rgba(0, 0, 0, 0.50)`
- Black at 35% opacity: `rgba(0, 0, 0, 0.35)`
- Black at 15% opacity: `rgba(0, 0, 0, 0.15)`

### Action Color
- Primary action green: `#34EC27`

### Hero Accent Colors
- Orange: `#F79420`
- Blue: `#4065AF`

### Color Usage Rules
- `#27408E` is the default shell anchor color for the product.
- Neutral graphite and steel tones should carry most UI structure, especially tabs, panels, and content surfaces.
- Green (`#34EC27`) is reserved exclusively for gating actions that advance game state — `Play Next Game`, `Run Training Camp`, `Sim Next Round`, and equivalent actions.
- Orange and hero blue are accent colors and should not be used as broad structural fills.
- All other primary action buttons use orange (`#F79420`).
- Team-color theming should primarily affect atmosphere and background expression, not core readability surfaces.

## Typography

### Display Typeface
- `Bebas Neue`

### Supporting Typeface
- `Inter`

### Typography Usage Rules
- `Bebas Neue` is used for display text, tab labels, major section headers, and command-center headlines.
- `Inter` is used for body copy, metadata, labels, tables, helper text, and supporting UI language.
- `Bebas Neue` is the universal font for all buttons across the product.
- Universal button typography uses a larger `Bebas Neue` treatment with positive tracking so the copy feels intentional and premium.
- Display typography should feel bold, condensed, and game-native.
- Supporting typography should remain clean, readable, and dense enough for management-sim interfaces.

## Buttons

### Universal Button Shape
- Standard button footprint: minimum `138px` width and fixed `42px` height
- Standard internal horizontal padding: `18px`
- Standard corner radius: `10px`
- Standard border: `1px solid rgba(255, 255, 255, 0.28)`
- Standard top highlight: `inset 0 1px 0 rgba(255, 255, 255, 0.18)`
- Standard motion: slight upward lift on hover and slight compression on press
- This is the shared base shape for FCC navigation-adjacent buttons, action buttons, and standalone page return buttons
- Color may change by button role, but the structural shape should remain consistent unless there is a clear reason to break the system

### Behavior
- Buttons should feel responsive, deliberate, and restrained.
- All button copy uses `Bebas Neue`.
- Button font size should satisfy both rules at once:
- Horizontal: button text should fill approximately `60–70%` of the button's total width with comfortable equal padding on each side.
- Vertical: cap height should sit at approximately `45–55%` of the button's total height with breathing room above and below.
- If those two sizing rules are in tension, prioritize the vertical rule.
- All button copy uses positive tracking between `1px` and `2px`.
- Hover states should use modest adjustments in brightness, border emphasis, and elevation.
- Press states should feel tactile through slight vertical compression or reduced lift.
- Primary action buttons must be visually distinct from navigation buttons.
- Disabled and dead states must remain legible while clearly unavailable.

### Usage Rules
- Primary action buttons that advance game state use action green (`#34EC27`).
- Primary action buttons that save settings, configure preferences, or perform non-gating actions use orange (`#F79420`).
- These two button types must remain visually distinct and semantically consistent across the entire product.
- Any page with a primary action or save button must keep that button visible on screen at all times.
- If page content is long enough to require vertical scrolling, the button's containing header or action bar must remain present on screen while the user scrolls.
- Navigation buttons should not compete visually with primary action buttons.
- Button treatments should support information-dense screens without becoming noisy.

### Back / Return Link Treatment
- The standard `Back` / `Back to Locker Room` treatment should be a low-weight ghost or text link, not a filled button.
- It should use a small left arrow followed by the label.
- It should be left justified above the primary content container.
- Copy should use subdued white or light grey in resting state and brighten modestly on hover.
- It should remain clearly functional without competing with the page title or primary CTA.

## Tabs

### Behavior
- Tabs should use one universal visual language across FCC and future command-center screens.
- Tab copy must remain centered horizontally and vertically.
- Tabs should use system-driven sizing when presented in structured rows.
- Only one tab container should render at a time.

### Visual Rules
- Resting tabs should use neutral steel / graphite fills.
- Selected tabs should use a higher-contrast neutral active state rather than a locked blue fill.
- Tab styling should remain stable even when the page background shifts to team-color mode.

### Architectural Direction
- Tabs may visually present as tabs while functioning as route-driven page links where appropriate.

## Surfaces

### Containers And Panels
- Primary content containers should use neutral dark surfaces.
- Panel styling should emphasize clarity, structure, and hierarchy over decoration.
- Team-color influence inside containers should remain subtle.
- Borders, shadows, and highlights should support depth without reducing readability.

### Surface Rules
- Background atmosphere may shift with team-color mode.
- Core data surfaces should remain neutral and readable across many possible team colors.
- For FCC data-heavy containers, if the data surface naturally occupies more than 50% of the available horizontal space, it should fill to the right edge of the container rather than leaving unused dead space.

## Page Background System

### Core Brand Background
- The FCC background is the core brand page design for Geeked-Out Basketball.
- It should be used as the default shell treatment for command-center pages and major destination pages that should feel part of the same product space.

### Composition
- Base page atmosphere should use a vertical blue gradient anchored to `#27408E`, with a slightly lighter top and a deeper blue lower range.
- The primary page shell should sit inside a large rounded container rather than relying on a flat full-bleed page.
- That shell should use layered diagonal banding to create directional motion across the page.
- The shell should also use a faint repeating ellipse / circular texture layer to reinforce the brand’s technical sports-sim feel.
- Texture and banding should remain subtle enough that text and data surfaces stay easy to read.

### Structural Rules
- The shell should use a soft white border, large corner radius, and restrained shadow to separate it from the page background.
- Foreground content must sit above the background layers at all times.
- Background design should feel architectural and systemic, not decorative.
- Core content surfaces inside the shell should remain neutral dark panels rather than inheriting the full blue atmospheric treatment.
- Pages whose primary information sits inside dark tiles or cards should keep the horizontal line layer in the background shell.
- Pages whose primary information sits directly on the page shell, without dark tiles or cards holding that data, should remove the horizontal line layer and keep only the rest of the brand shell treatment.

## Theme Behavior

### Default Mode
- The interface uses the default GOB shell color anchored to `#27408E`.

### Team Colors Mode
- The page atmosphere may inherit the active team’s primary color.
- Structural UI elements such as tabs and panels should remain largely neutral.
- If no active franchise team context exists, the system must fall back to Default mode.

## Interaction States
- Every reusable interactive component should define: default, hover, active, selected, disabled, and dead states.
- State changes should be readable immediately but should not feel exaggerated or toy-like.

## Modal System

### Two Modal Types

GOB uses two distinct modal types. Every modal must be classified as one before implementation.

#### Functional Modals
Used for confirmations, warnings, settings changes, and destructive actions. Goal is clarity and speed — get the user to a decision and out.

**Canonical examples:**
- Auto-Train confirmation (training.html) — first canonical implementation
- In-game timeout confirmation
- End of quarter confirmation
- Delete Franchise confirmation
- Unsaved changes warning

**Shared CSS classes:** `.gob-modal-overlay`, `.gob-modal-backdrop`, `.gob-modal-box`, `.gob-modal-accent`, `.gob-modal-body`, `.gob-modal-title`, `.gob-modal-subtitle`, `.gob-modal-actions`, `.gob-modal-btn-primary`, `.gob-modal-btn-secondary`, `.gob-modal-btn-dismiss`

**Design rules:**
- Surface: `rgba(22, 26, 36, 0.98)`
- Backdrop: `rgba(0, 0, 0, 0.72)`
- Accent bar: 3px top bar in `#F79420` (orange default), `#34EC27` (green for gating confirms), `#ff6d6d` (red for destructive)
- Max width: `420px`
- Border: `1px solid rgba(255,255,255,0.12)`
- Border radius: `14px`
- Title: Bebas Neue 28px white
- Subtitle/copy: Inter 14px `rgba(255,255,255,0.55)`
- Single dismiss action: full-width ghost button
- Two actions: primary `flex: 2` + secondary/cancel `flex: 1`
- Two-action rows use `flex-direction: row` with primary `flex: 2`, secondary `flex: 1`
- Single dismiss action uses `width: 100%` (full width is appropriate when there is only one button)
- Buttons are full-width stacked only in Action-Only Modals where all choices are equal weight
- No background imagery
- No decorative elements

##### Action-Only Modal (Functional Modal sub-pattern)
A stripped-down Functional Modal with no title and no copy — the entire content is a button group. Used when the decision is self-evident from context and copy would be redundant.

**Canonical example:**
- Pre-game quarter modal (`court.html`) — Play Quarter vs Sim Full Game choice at quarter start

**Design rules:**
- Same surface, backdrop, border, border-radius as Functional Modal
- Orange accent bar at top (`3px`, `#F79420`) — provides brand moment in absence of a title
- No title element, no subtitle element
- Button group: `display: flex; flex-direction: column; gap: 10px; padding: 24px 28px 28px`
- Each button: full width (`width: 100%`), `height: 46px`, Bebas Neue 18px
- Primary action: orange `#F79420`, `color: #15181f`
- Secondary action(s): ghost treatment — `rgba(255,255,255,0.06)` background, `rgba(255,255,255,0.14)` border
- No dismiss/cancel button — backdrop click or ESC does not dismiss (player must make a choice)
- Max width: `420px`

#### Moment Modals
Used for emotionally significant events — game results, training report reveals, season milestones, recruiting outcomes. Goal is payoff — the user should feel the weight of the moment.

**Canonical examples:**
- End of Game result
- Training Camp complete
- Season complete
- Major recruiting commit

**Design rules:**
- Surface: `rgba(13, 17, 36, 0.97)`
- Backdrop: `rgba(0, 0, 0, 0.72)`
- Team banner or contextually relevant image as full-bleed background with darkening gradient overlay
- Outcome is the visual hero — largest most prominent element
- W/L or success/failure badge top-right using semantic color (green for positive, red for negative)
- Subject of the moment gets portrait spotlight section
- Max width: `560px`
- Border: `1px solid rgba(255,255,255,0.12)`
- Border radius: `16px`
- Button row: `display: flex; flex-direction: row; gap: 12px` — primary action `flex: 2`, secondary action `flex: 1`
- Buttons are never stacked full-width in Moment Modals — side-by-side with flex ratio communicates action hierarchy
- Primary button height: `44px`. Secondary button height: `44px`.
- Entrance: subtle scale from `0.96` to `1.0` over `200ms ease`

#### Strategic Modals
Used during active gameplay at decision points — quarter breaks, timeouts, foul-outs, any moment where the coach must make a tactical adjustment before play resumes. Goal is fast, confident decision-making under mild pressure. Data-dense but not celebratory.

**Canonical example:**
- Defense Matchups popup (`defenseMatchupsPopup.js`) — shown at Q1 start, quarter breaks, timeouts, and foul-outs

**Design rules:**
- Surface: `rgba(18, 22, 32, 0.98)` — slightly lighter than Functional to support data density
- Backdrop: `rgba(0, 0, 0, 0.75)`
- No accent bar — replaced by subtle team-color tinted panel headers using `rgba(teamColor, 0.2)` fill and `rgba(teamColor, 0.6)` border
- Title: Bebas Neue 24px `rgba(255,255,255,0.5)` — deliberately muted, the data is the hero not the title
- Wider layout permitted — max width `1160px` to support side-by-side team comparison panels
- Border: `1px solid rgba(255,255,255,0.12)`
- Border radius: `16px`
- Position badges use the GOB system-wide position color map:
  - PG: `#4065AF` · SG: `#7B5EA7` · SF: `#3A8C4A` · PF: `#C0392B` · C: `#D4A017`
- Submit/confirm action is full-width green (gating — advances gameplay)
- Dismiss/skip option is a low-prominence checkbox or ghost link, never a competing button
- Drag-and-drop interactions for reordering use standard GOB drag visual feedback
- No background imagery — data surfaces must remain fully readable
- Backdrop click does NOT dismiss — user must explicitly submit or the game cannot proceed

### Shared Rules (All Three Types)
- Backdrop click dismisses Functional Modals only
- Moment Modals and Strategic Modals require explicit button action to dismiss
- ESC dismisses Functional Modals only
- Only one modal visible at a time
- All button copy uses Bebas Neue
- Toggle visibility via `.is-visible` class, not inline `display` style

## Toast Notifications

### Purpose
- Toasts are the standard approval/confirmation pattern for successful save actions and similar lightweight confirmations.
- Toasts should replace success modals when the user does not need to make a follow-up decision.
- Toasts should confirm success without interrupting flow.

### Placement
- Toasts should be fixed to the bottom right of the viewport.
- Standard offset: `22px` from the right edge and `22px` from the bottom edge.
- Toasts must appear above all page content.

### Container Treatment
- Background: `rgba(28, 33, 43, 0.97)`
- Border: `1px solid rgba(255, 255, 255, 0.14)`
- Left accent border: `3px solid` status color
- Corner radius: `12px`
- Padding: `14px 18px`
- Minimum width: `260px`
- Maximum width: `320px`
- Shadow: `0 10px 24px rgba(0, 0, 0, 0.3)`

### Content Structure
- Left: small status icon container
- Center: text block
- Right: dismiss control
- The icon container should be:
  - `20px` square
  - circular
  - lightly tinted with the accent color
  - bordered with the accent color
- Success icon should use a white checkmark.

### Typography
- Title:
  - `Bebas Neue`
  - `16px`
  - full white
  - letter spacing `0.04em`
- Subline:
  - `Inter Regular`
  - `12px`
  - `rgba(255, 255, 255, 0.54)`

### Dismiss Control
- Use a simple `×` character on the far right.
- Resting color: `rgba(255, 255, 255, 0.3)`
- Hover color: full white
- Dismiss should reverse the entrance animation before removal.

### Motion
- Toasts should slide in from the right.
- Entrance transition:
  - from `transform: translateX(120%)`
  - to `transform: translateX(0)`
  - opacity `0` to `1`
  - duration `220ms`
  - easing `ease`
- Exit should reverse the same motion.

### Behavior
- Toasts should auto-dismiss after `3 seconds`.
- Only one toast should be visible at a time per page context.
- If a new toast is triggered before the current one dismisses, reuse the existing toast and reset the timer rather than stacking.
- Toasts should be used for save approvals such as:
  - `Game Plan Saved`
  - `Playbooks Saved`

### Status Color Rules
- Success toast accent color: action green `#34EC27`
- Other statuses may use a different accent color when appropriate, but the structure and typography should remain the same.

## Data Surfaces
- Tables, scroll regions, placeholders, and empty states should follow the same neutral-surface system as panels.
- Placeholder and in-development states should be centered, legible, and visually quiet.
- Data-heavy views should favor clarity and scan speed over ornament.
- Unless the data volume makes it impossible, pages and tabs should open with their primary content visible above the fold.
- Above-the-fold fit should be achieved by reducing dead space and tightening panel composition before introducing scroll.

## Table / Data Grid System

### Canonical References
- The live FCC `Roster` grid is a canonical reference.
- The live FCC `Player Stats` grid is a canonical reference.
- The standalone `Rankings` page, after its contained-panel conversion, is a canonical reference.

### Container Rules
- Data grids should sit inside a dark contained panel rather than directly on the page shell.
- The panel should use the standard neutral dark surface treatment:
  - rounded corners
  - soft border
  - restrained inset highlight
  - restrained outer shadow
- Data grids should not appear as flat spreadsheets dropped onto the page.

### Scroll And Width Rules
- Data-heavy grids should use a horizontal scroll container when needed.
- Scrollbars should be styled in the same subdued neutral treatment used on FCC data grids.
- If a data grid naturally occupies more than 50% of the available horizontal width, it should expand to fill the available width before relying on scroll.
- Minimum table width may still be used to preserve column legibility.

### Header Row Rules
- Header rows should be sticky when appropriate.
- Header background should use a faint metallic / glass-like neutral treatment, not a flat fill.
- Header text should use:
  - `Inter`
  - small size
  - bold weight
  - uppercase
  - modest letter spacing
- Header text color should be a muted white, lower contrast than the body rows.

### Body Row Rules
- Body rows should use subtle horizontal separators only.
- Avoid full boxed cell borders or spreadsheet-style gridlines.
- Alternate rows should use a very subtle neutral shade shift.
- Dark data grids must never use white or near-white zebra striping.
- Hover states should slightly brighten the row background without becoming noisy.
- Row density should support quick scan speed and high information density.

### Implementation Rule
- Redesigned resource pages and management surfaces should use the shared canonical GOB data-grid system rather than inheriting legacy table styling from older page-specific stylesheets.

### Alignment Rules
- Text-heavy first columns should usually be left aligned.
- Numeric/stat columns should usually be centered unless there is a specific readability reason to right align them.
- Important text cells such as the first/name column should carry stronger weight than supporting cells.

### Link Rules
- Linked names inside grids should remain clearly readable on dark surfaces.
- Links should not default to underlined in resting state.
- Underline on hover is preferred over louder treatments.

### Rankings-Specific Rules
- Rankings pages should use the same contained panel and row system as FCC `Roster` and `Player Stats`.
- Rankings-specific semantic text treatments should be preserved:
  - previous win text in green
  - previous loss text in red
  - other result-specific emphasis only where meaningful

### Design Intent
- The system should read as a structured management-sim data surface.
- It should feel contained, deliberate, and premium.
- It should never drift into default browser table styling or Excel-sheet aesthetics.

## Audio Rules
- UI click sounds should be consistent across equivalent interactions.
- Navigation, action, and confirmation sounds should each follow a distinct pattern.
- Sound should reinforce interaction hierarchy, not overwhelm it.

## Remaining Sections To Formalize
- Spacing system
- Typography scale
- Iconography
- Table system
- Form controls
- Modal sizing rules
- Page-level theming rules
- Audio mapping by interaction type

## Open Confirmation
- Confirm that `Bebas Neue` and `Inter` should be locked as the official system typefaces.
