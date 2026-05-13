# SFX Manager Implementation

## Goal

Make in-game SFX for passes, receptions, shot attempts, missed shots, and made shots as reliable and precisely timed as possible.

Current behavior is close, but not fully reliable:

- SFX fires on most events, roughly 95% of observed instances.
- Timing is correct on many events, but a meaningful percentage feels delayed.

The target is not just "play the right file." The target is that gameplay SFX fires from a single reliable system and is synced to exact animation moments.

## Current Diagnosis

The current in-game SFX implementation can miss or feel delayed for several reasons:

- Some sounds are created at the moment of playback with `new Audio()`, which can introduce load/decode latency.
- Rapid repeated events can overlap or compete if each call creates a fresh audio object.
- Active sound references must be retained until playback ends; otherwise browser garbage collection or page state can make playback inconsistent.
- SFX calls are currently attached to helper calls and animation promise boundaries in several places. Those points are not always the exact visual moment the user expects.
- Some animation paths may still bypass the same SFX hooks used by the main HCO path.

## Desired Direction

In-game SFX should be driven by explicit animation markers, not broad gameplay events.

Examples:

- Pass release SFX: fire when the ball detaches from the passer.
- Reception SFX: fire when the ball attaches to the receiver.
- Shot attempt SFX: fire when the ball detaches from the shooter.
- Miss SFX: fire on rim/backboard impact.
- Made shot SFX: fire when the ball reaches the rim/net, or when the made-shot visual result begins, depending on which moment feels better.

The user should define timing in terms of visible basketball moments, not millisecond offsets. The code should map those moments to deterministic animation markers.

## Work Plan

### Phase 1: Inventory Current SFX Paths

- Trace every in-game SFX call site for:
  - HCO passes
  - HCO receptions
  - fast-break passes
  - shot attempts
  - made shots
  - missed shots
  - free throws, if currently covered or expected to be covered
- Identify which paths already use `gameSfx.js`.
- Identify any paths that still create one-off `Audio` objects for gameplay events.
- Identify any animation paths that can produce pass or shot visuals without firing the shared SFX helpers.

Deliverable: call-site inventory with current trigger moment and expected marker.

### Phase 2: Build Central In-Game SFX Manager

Create or expand a centralized gameplay SFX manager responsible for:

- Preloading all gameplay SFX before gameplay starts.
- Decoding/warming assets where browser APIs allow.
- Keeping active sound references until playback completes.
- Using small audio pools per file so rapid repeated events do not cancel each other.
- Normalizing volume and playback behavior in one place.
- Returning clear playback status for debug logging.

The SFX manager should become the only runtime path for pass, reception, shot attempt, made-shot, and missed-shot SFX.

### Phase 3: Add Debug Instrumentation

Add lightweight debug logging behind a flag.

Each SFX event should be able to report:

- event name
- selected file
- turn id or animation id when available
- animation path/module
- marker name
- playback accepted/rejected
- rejection reason if the browser provides one

This makes it possible to distinguish:

- missing SFX trigger
- bad file selection
- browser playback rejection
- audio overlap/pool issue
- timing issue

### Phase 4: Define Animation Markers

Introduce explicit marker names for the visual moments that need SFX:

- `pass_release`
- `pass_receive`
- `shot_release`
- `rim_contact`
- `made_net`

The exact marker list can be adjusted after tracing current animation systems.

Each marker should fire from the animation code at the exact visual moment, not after a broader helper promise resolves.

### Phase 5: Move SFX Calls Onto Markers

Replace direct SFX calls tied to broad helper boundaries with marker-driven calls.

Expected mappings:

- `pass_release` -> HCO/FB pass SFX
- `pass_receive` -> HCO/FB receive SFX
- `shot_release` -> inside/attack/outside shot attempt SFX
- `rim_contact` -> missed shot clank SFX
- `made_net` -> made shot swish / swish-with-rim SFX

If free throws are included, map them separately so they can share made/miss result SFX without accidentally using regular shot-attempt SFX.

### Phase 6: Validate With Targeted Scenarios

Test high-risk paths:

- HCO pass into shot
- HCO pass chain with multiple receptions
- HCO missed shot
- HCO made shot
- fast-break pass
- fast-break shot
- putback shot
- free throw make/miss, if included
- timeout/resume or quarter-start paths that may affect animation sequencing

For each scenario, verify:

- the expected event fires once
- the selected file is correct
- playback is not rejected
- timing matches the visual marker
- rapid repeated events do not cancel prior sounds unexpectedly

### Phase 7: Document Final Contract

Update sound and animation docs with:

- gameplay SFX manager ownership
- supported event names
- marker-to-SFX mapping
- file selection rules
- debug flag behavior
- any known browser audio limitations

## Success Criteria

- All pass, reception, shot attempt, made-shot, and missed-shot SFX route through one manager.
- Gameplay SFX assets are preloaded before normal turn animation playback.
- Every intended SFX event logs a traceable marker when debug mode is enabled.
- SFX timing is tied to exact animation markers instead of broad async function boundaries.
- No known gameplay animation path can produce a pass or shot visual without going through the shared SFX event system.

