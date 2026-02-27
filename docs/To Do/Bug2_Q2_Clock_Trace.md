# Bug 2: Q2 frontend clock starts at ~1:37 — code trace

## Symptom
Front-end game clock for the second quarter started at ~1:37; backend appeared correct (game kept simming past when frontend showed 0:00).

## Trace (actual code paths)

### 1. Where the frontend gets initial clock (gameScene.js)

- **Lines 511–522:** Initial `liveClock` and then `initialClockSeconds` drive the game clock display.
- **Branch:** `resumeFromTimeout && simData.turns?.length > 0` → use first turn’s clock; **else** → `liveClock = urlParams.get('clock') || simData.clock || '8:00'`.
- **Lines 539–541:** `initialClockSeconds = (typeof simData.time_remaining === 'number' ? simData.time_remaining : null) ?? parseClockToSeconds(liveClock)`.

So for **Q2 start after quarter break**: `resumeFromTimeout` is false → we use **`urlClock || simData.clock || '8:00'`**. If the URL has `clock=1:37`, that wins over `simData.clock`.

### 2. Where URL can get a clock param

- **timeoutNavigationHelper.js 114–117:** `clockTime = clock || sourceParams.get('clock')`; if present, `params.set('clock', clockTime)`.
- **set-lineup.js 1587:** When building params for court, `clock: currentUrlParams.get('clock')` is passed to `buildGameNavigationParams`. So if set-lineup’s URL has `clock`, it is forwarded to the court URL.
- **gameScene.js 2778–2795:** Quarter break navigation to set-lineup uses `sourceParams = new URLSearchParams(window.location.search)` and does **not** pass an explicit `clock`. So `clockTime = sourceParams.get('clock')` — i.e. court’s current URL. If the court URL ever has `clock` (e.g. from a prior timeout flow or any future URL update), that value is carried to set-lineup and then back to court for Q2.

### 3. Backend for Q2 start

- **main.py 336–341:** For `not resume_from_timeout`, `time_remaining = 480`, `clock = "8:00"`. So the backend state (and thus `summarize_game_state` → response) is correct for a new quarter.
- **api.py 3619:** `frontend_summary = summarize_game_state(gm, ...)` after `simulate_quarter` → response includes `clock` and `time_remaining` from that state.

So the wrong value is not coming from the simulate-quarter response when it’s a normal Q2 start; it’s used only if the frontend **prefers URL over that response**.

### 4. Root cause (in code)

- For **quarter break** (Q2+ start, `resumeFromTimeout === false`), the scene uses **`urlClock || simData.clock || '8:00'`**. So any `clock` in the URL (e.g. left over from Q1 or from a timeout flow) overrides the correct `simData.clock` / `simData.time_remaining` for the new quarter.
- No code path was found that *reliably* clears or omits `clock` when navigating to court for a **new** quarter from set-lineup; the helper forwards `sourceParams.get('clock')` when present.

### 5. Surgical fix

For **new quarter start** (quarter > 1 and not resuming from timeout), treat the **simulate-quarter response as the only source of truth** for the initial game clock. Do not use the URL `clock` param for that case.

- **File:** `FrontEnd/static/js/phaser/gameScene.js`
- **Location:** In the `else` branch that sets `liveClock` (around 518–522), when `this.quarter > 1 && !resumeFromTimeout`, set `liveClock` from `simData.clock` only (e.g. `simData.clock || '8:00'`), and do not use `urlParams.get('clock')`.

This preserves timeout-resume and Q1 behavior (URL and simData unchanged) and fixes Q2+ start when a stale `clock` is present in the URL.
