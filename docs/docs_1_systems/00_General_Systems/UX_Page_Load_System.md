# UX Page Load System

## Purpose

Define the user-experience rules for how FCC and related franchise-mode screens should load, cache, navigate, and preserve context so the product feels fast, stable, and location-consistent.

This document is focused on UX behavior and structural decisions, not just raw fetch mechanics.

## Core Principle

The FCC should behave like one persistent command center, even when some destinations are technically separate pages.

That means:

- the user should feel like they are staying inside one command-center location
- heavy pages should not bloat FCC initial load
- light summary views should feel instant
- deep data pages should preserve the same shell, header, background, and tab language

## Canonical Model

The FCC should use a hybrid model:

1. A persistent FCC shell
2. Lightweight in-shell tabs for summary content
3. Routed FCC pages for heavier or deeper content

This is the standard going forward.

## FCC Shell Rules

The FCC shell is the persistent command-center frame. It should remain visually stable across local tabs and routed FCC pages.

The shell includes:

- top nav / auth bar
- FCC background system
- FCC header
- FCC tab bar
- page-level spacing and panel grammar

When a user moves from one FCC destination to another, the shell should remain familiar so the page feels like a continuous location, not a full context switch.

## Tab Classification Rules

### Use local in-shell tabs when:

- the tab shows summary information
- the initial visible content is lightweight
- the user is expected to glance, not deeply work
- the tab can hydrate quickly from data FCC already needs
- the data slice is small and stable enough that it will not materially slow FCC first render

### Use routed FCC pages when:

- the destination contains large tables
- the destination needs sorting, filtering, or more complex interactions
- the destination is likely to grow over time
- the destination has its own meaningful fetch lifecycle
- the destination would noticeably slow FCC initial load if embedded as a true local tab

## Default FCC Pattern

The preferred UX pattern is:

1. Show a lightweight summary inside FCC when useful
2. Provide a deeper standalone page for the full experience
3. Preserve the FCC shell and tab appearance when that deeper page is visited

This gives the user:

- fast command-center scanning
- low-friction navigation
- deeper workflows without overloading FCC

## Recommended FCC Destination Types

### Good candidates for local tabs

- `Home`
- `Standings` summary
- `Tasks`
- other quick-reference summary modules

### Better candidates for routed FCC pages

- `Roster`
- `Player Stats`
- `Team Stats`
- `Schedule`
- `Rankings`
- `Awards`
- `Press`
- `Game Plan`
- `Playbooks`

These classifications can evolve, but the default bias should be:

- summary = tab
- deep data = routed page

## Page Load Rules

### FCC initial load

FCC initial load should hydrate only what is needed for:

- shell rendering
- top-level state
- currently visible default tab content
- any small summary blocks intentionally included on the landing state

FCC initial load should not fetch all tab data up front.

### Routed FCC pages

Routed FCC pages should fetch only their own required content after the shared shell context is available.

They should not depend on loading unrelated FCC destinations.

### Progressive disclosure

Always load the minimum needed for first meaningful paint.

Anything not visible or not immediately necessary should be deferred until:

- the user visits that destination
- the user expands the deeper workflow
- the user explicitly changes scope/filter/toggle

## Caching Rules

### Browser-session caching

Use browser-session caching for repeated navigation within the same franchise session.

Cache keys should include:

- page name
- `franchise_id`
- season
- week
- scope key if applicable

### Cache scope

Use:

- in-memory cache for the current page lifecycle
- `sessionStorage` for repeat visits within the same browser session

Do not rely on broad global caches by default.

### Invalidation

Cache should invalidate naturally when:

- season changes
- week changes
- franchise changes
- scope key changes

## Persistence Rules

Persist:

- user display/settings preferences
- return URLs when needed for shell continuity
- lightweight UI state only when it improves continuity

Do not persist:

- large view payloads in durable storage
- stale data that should naturally be invalidated by week/season transitions

## Navigation Rules

### Visual continuity

All FCC destinations should preserve:

- shared tab appearance
- shared shell structure
- shared background and panel language

### URL truth

Heavier destinations should still use real routes/URLs when appropriate.

This improves:

- maintainability
- ownership boundaries
- caching simplicity
- future scalability

### Return behavior

Deeper FCC pages should preserve return context so the user returns to the correct command-center state rather than a generic landing point.

## UX Goals

This system optimizes for:

- fast perceived load time
- low cognitive friction
- stable location memory
- clean information architecture
- scalable growth as FCC destinations become more complex

## Decision Standard

When deciding whether a new FCC destination should be a local tab or a routed page, ask:

1. Is this primarily a summary or a workflow?
2. Will loading this content slow FCC initial render?
3. Is the user likely to spend real time interacting with this destination?
4. Does this destination have enough complexity to justify owning its own fetch lifecycle?

If the answer leans toward workflow, complexity, or heavy data, it should be a routed FCC page inside the shared command-center shell.

## Initial FCC Implementation Standard

For the current FCC direction:

- preserve one universal tab appearance
- allow a mix of local tabs and routed FCC pages behind that appearance
- prefer summary content in FCC
- prefer deep data on dedicated routed pages
- preserve FCC shell continuity across both

## Rationale

This hybrid approach avoids two failures:

### Failure 1: Everything is a true tab

- FCC initial load becomes too heavy
- slow destinations penalize the whole page
- data ownership becomes tangled

### Failure 2: Everything is a separate page

- command-center continuity is weakened
- the product feels fragmented

The hybrid shell model keeps FCC feeling like one location while still allowing the architecture to scale.
