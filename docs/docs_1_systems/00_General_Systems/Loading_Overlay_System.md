# Loading Overlay System

## Purpose

The GOB Loading Overlay System is the shared blocking loading treatment used when the user is waiting on a meaningful state transition. It replaces stale or partially loaded UI with a deliberate full-screen loading state.

Use a Loading Overlay when:

- the user has initiated an action that transitions to a new page or new persistent state
- the current page should not remain interactive while work completes
- the load is long enough that a spinner or silent wait feels weak or unclear

Do not use a full-screen Loading Overlay for:

- tiny local waits inside a card, table, or module
- very fast actions where the overlay would flash
- places where an inline skeleton or lightweight shimmer is more appropriate

## Shared Component

The shared implementation lives in:

- [pageLoadOverlay.js](/Users/jamesdavies/gob-simplified/FrontEnd/static/js/shared/pageLoadOverlay.js)

The public API is:

```js
PageLoadOverlay.show(...)
PageLoadOverlay.hide()
```

## Variants

### Spinner Overlay

This is the legacy default variant.

Use when:

- the page only needs a neutral blocking loader
- no page-specific branded loading treatment has been defined yet

Example:

```js
PageLoadOverlay.show('Loading...');
```

### Pulse Page

This is the branded premium loading treatment for high-salience transitions.

Visual rules:

- full-screen dark shell: `#0d1124`
- large team visual at top
- bold headline in Bebas Neue
- supporting copy below
- green pulsing horizontal bar as the active indicator
- no spinner GIF

Use when:

- the user is entering a major flow
- the wait is long enough to justify branded presentation
- team context is available and improves the experience

Example:

```js
PageLoadOverlay.show({
  variant: 'pulse',
  title: '128 Teams Executing Training',
  subtitle: 'Morristown is executing training.',
  teamName: 'Morristown',
  assetKey: 'banner_primary'
});
```

Supported Pulse Page fields:

- `variant`: must be `'pulse'`
- `title`: primary headline
- `subtitle`: supporting status copy
- `teamName`: used with `getTeamAssetPath(...)` when a team visual should be shown
- `assetKey`: optional, defaults to `'banner_primary'`
- `imageSrc`: optional direct override if a specific image path is needed

## Current Implementations

### Franchise Select

The original branded loading experience exists in:

- [franchise-select-team.html](/Users/jamesdavies/gob-simplified/FrontEnd/static/franchise-select-team.html)
- [franchise-select-team.css](/Users/jamesdavies/gob-simplified/FrontEnd/static/franchise-select-team.css)
- [franchise-select-team.js](/Users/jamesdavies/gob-simplified/FrontEnd/static/franchise-select-team.js)

This page established the visual language that the shared Pulse Page variant now follows.

### Team Training

Training is the first shared `PageLoadOverlay` use upgraded to the Pulse Page.

Trigger point:

- [training.js](/Users/jamesdavies/gob-simplified/FrontEnd/static/training.js)

Current copy:

- title: `128 Teams Executing Training`
- subtitle: `{Team Name} is executing training.`

Behavior:

- shown immediately after the user presses `Submit Training`
- remains visible while user-team training and distant training complete
- hides automatically only on error; on success the page redirects to Training Report

## Phase Guidance

### Phase 1

Allowed:

- branded Pulse Page
- static custom copy
- real team visual

Not included:

- rotating player highlights
- fabricated flavor text
- fake progress percentages

### Phase 2

Future enhancement:

- real mid-process copy derived from actual backend progress or actual computed deltas

Important rule:

- never show fabricated player-result copy during loading
- if copy references a specific player or gain/loss, it must be backed by actual computed training data

## Implementation Rule

When upgrading an existing spinner to the Pulse Page:

1. keep the existing blocking behavior
2. preserve all success/error navigation
3. change only the presentation first
4. add dynamic progress copy only after a real backend progress path exists
