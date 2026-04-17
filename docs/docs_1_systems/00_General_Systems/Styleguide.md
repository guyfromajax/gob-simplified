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
- `Inter` is used for body copy, metadata, labels, buttons, tables, helper text, and supporting UI language.
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
- Hover states should use modest adjustments in brightness, border emphasis, and elevation.
- Press states should feel tactile through slight vertical compression or reduced lift.
- Primary action buttons must be visually distinct from navigation buttons.
- Disabled and dead states must remain legible while clearly unavailable.

### Usage Rules
- Action green is reserved for primary action buttons.
- Navigation buttons should not compete visually with primary action buttons.
- Button treatments should support information-dense screens without becoming noisy.

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
- Pages whose primary information sits inside a tile or tile system should keep the horizontal line layer in the background shell.
- Pages whose primary information does not sit inside a tile system should remove the horizontal line layer and keep only the rest of the brand shell treatment.

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
