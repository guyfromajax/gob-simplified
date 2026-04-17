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
- Green is reserved for high-priority actions.
- Orange and hero blue are accent colors and should not be used as broad structural fills.
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
- Hover states should use modest adjustments in brightness, border emphasis, and elevation.
- Press states should feel tactile through slight vertical compression or reduced lift.
- Primary action buttons must be visually distinct from navigation buttons.
- Disabled and dead states must remain legible while clearly unavailable.

### Usage Rules
- Action green is reserved for primary action buttons.
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

## Modal Rules
- Modals should use a clear header/body/footer structure when needed.
- Backdrops should separate the modal from the page without fully flattening page context.
- Modal copy should remain concise and scannable.
- Close behavior should be obvious and consistent.

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
- Hover states should slightly brighten the row background without becoming noisy.
- Row density should support quick scan speed and high information density.

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
