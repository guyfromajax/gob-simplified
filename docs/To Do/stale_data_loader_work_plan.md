# Stale Data on Initial Page Load – Loader Overlay Work Plan

**Bug:** [#29] When users land on court.html (from quarter break, timeout, foul-out), open FCC/TCC (e.g. from team/mode select), or open the Lineup screen, they see stale or incorrect data (TOL 5, wrong scores, 100% NG, missing buttons) until data loads.

**Solution:** On each destination page, show an opaque (or near-opaque) dark overlay with centered loader gif until the page’s data is loaded and UI is correct. Then remove overlay and reveal content. User never sees wrong data.

---

## Universal vs entry-point-specific

**We use a universal rule:** every time the user **lands on** one of the four pages (any navigation to that URL), we show the overlay until the page is “ready.” We do **not** define or detect entry points (e.g. “only from mode select” vs “from Roster”).

- **Simpler:** No referrer checks, no state passed between pages, no list of entry points to maintain.
- **Same behavior everywhere:** Bookmark, refresh, back button, or any link → overlay until ready.
- **When data is already current** (e.g. user went Roster → FCC and data is fresh): the page still loads and fetches; “ready” may be fast, so the overlay can be very brief or negligible. If we want to optimize later (e.g. skip overlay when we have fresh cached data), we can add that without changing the rule.

**FCC/TCC tab switching:** The overlay is only for **initial page load**. When the user is already on FCC or TCC and switches between **tabs** (e.g. Roster, Stats, Schedule), that is in-page navigation—no new page load—so the overlay does **not** appear. We only show the overlay when the HTML document for that page first loads.

---

## Scope

| Page           | Show overlay until… |
|----------------|----------------------|
| **court.html** | `initializeGameStats()` (and any critical init) done; scoreboard, box scores, TOL correct. |
| **FCC**        | Franchise data fetched and full UI (including all buttons) rendered. |
| **TCC**        | Tournament data fetched and full UI (including all buttons) rendered. |
| **Lineup (set-lineup)** | Lineup/game data fetched and page UI (rosters, buttons) rendered. |

**Rule:** Every time we enter any of these four pages (by navigating to their URL), show overlay until “ready.” No entry-point list.

---

## Loader Overlay Spec

- **Overlay:** Full-viewport (or full content area). Opaque or very dark (e.g. `rgba(0,0,0,0.9)`) so user cannot see stale content behind it.
- **Loader:** `FrontEnd/static/images/loader1.gif` centered on screen.
- **Behavior:** Overlay + loader visible as soon as destination page runs (or as first paint). Removed only when “ready” for that page.

---

## Definition of “Ready”

- **Court:**  
  - `initializeGameStats()` has completed (game state fetched and applied).  
  - Scoreboard (scores, TOL) and box score sections (including NG if shown) updated from that state, or explicitly not shown until then.  
  - If `game_id` missing or init fails: either show error on overlay or reveal page with safe empty state; do not show stale defaults.

- **FCC:**  
  - Franchise (and any required) data fetched.  
  - Page UI built (including all buttons).  
  - Overlay removed only after render is complete.

- **TCC:**  
  - Tournament (and any required) data fetched.  
  - Page UI built (including all buttons).  
  - Overlay removed only after render is complete.

- **Lineup (set-lineup):**  
  - Game/lineup data fetched (e.g. roster, game context).  
  - Page UI built (lineup slots, buttons, header).  
  - Overlay removed only after render is complete.  
  - On failure: show error on overlay or safe fallback; do not show incomplete/stale lineup.

---

## Work Plan (Order of Work)

1. **Shared loader overlay utility (optional but recommended)**  
   - Add a small shared helper (e.g. show/hide full-page overlay + loader1.gif).  
   - Reuse on court, FCC, TCC, and set-lineup for consistent look and one place to change opacity/loader asset.

2. **Court (court.html)**  
   - On load: show overlay + loader immediately (in HTML or first JS).  
   - Keep overlay up until `initializeGameStats()` (and any other init that fills scoreboard/box scores) has finished and UI has been updated.  
   - Then hide overlay.  
   - Ensure TOL and NG are updated as part of this init (or by existing fixes); document any remaining gaps.  
   - Handle failure: if init fails or no `game_id`, keep overlay and show error message, or reveal with defined safe state—no silent stale defaults.

3. **FCC**  
   - On load: show overlay + loader before or as first paint.  
   - Keep overlay up until data fetch and full UI render (including buttons) are complete.  
   - Then hide overlay.  
   - Do **not** show overlay when user switches tabs (Roster, Stats, etc.)—only on initial page load.  
   - On fetch/render failure: show error on overlay or defined fallback; do not show incomplete “old” UI.

4. **TCC**  
   - Same pattern as FCC: overlay + loader until tournament data and full UI (including buttons) are ready.  
   - Do **not** show overlay on in-page tab switches—only on initial page load.  
   - On failure: error or safe fallback; no partial/stale UI.

5. **Lineup (set-lineup)**  
   - On load: show overlay + loader until game/lineup data is fetched and page UI is rendered.  
   - Then hide overlay.  
   - On failure: error on overlay or safe fallback; no stale/incomplete lineup.

6. **Verify**  
   - Test all four pages: navigate to each from various places (mode select, team select, from game, refresh, back).  
   - Confirm overlay appears on every **page load**, no flash of wrong data, overlay dark enough.  
   - On FCC/TCC, confirm overlay does **not** appear when switching tabs.

---

## When is the loader necessary?

With the **universal** rule, we always show the overlay on every load of these four pages until “ready.” We do not try to detect “cold” vs “warm” entry points.

- **When it’s clearly necessary:** First visit from mode select or team select, or after a long time away—data is loading, so overlay prevents stale UI.
- **When it might feel redundant:** User navigates back to FCC/TCC from e.g. Team Roster; data may already be current. With a full page load we still fetch; “ready” can be quick, so the overlay may be very short. We accept that for simplicity.
- **Optional later optimization:** If we add client-side caching and can render from fresh cache immediately, we could hide the overlay as soon as we have valid cached data (e.g. “ready” in 0ms). That would be a “skip overlay when not necessary” refinement without changing the universal rule. Not in scope for this phase.

---

## Out of Scope (This Phase)

- Loader on the *current* page when user presses the button (optional future UX polish).  
- Entry-point detection (only show loader when coming from X, Y, Z).  
- Cache-based “skip overlay when data already current” optimization.

---

## Success Criteria

- User never sees TOL 5, wrong scores, or 100% NG on court on any load.  
- User never sees incomplete FCC/TCC (e.g. missing buttons) or incomplete Lineup before data is loaded.  
- On FCC/TCC, switching between tabs does **not** show the overlay.  
- Overlay is dark enough that no stale content is visible behind it.  
- Clear behavior when init or fetch fails (no silent stale data).
