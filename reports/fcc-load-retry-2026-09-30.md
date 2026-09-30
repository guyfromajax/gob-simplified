# FCC season-load failure state — 2026-09-30

Branch `fix/fcc-load-retry` off `origin/develop` (includes `fix/flow-integrity` and
`fix/fcc-stale-return` — read first; neither was undone).

## 1. The old path (as mapped)

- **`fetchJSONWithStatus(url)`** (`franchise-command-center.js:27`): one fetch → `{data, status}`.
  - 401/403 → `{null, status}` + `AccessDenied.checkAccessDenied(res)` (**redirects**).
  - any non-ok (5xx, 429, …) → logs + `{null, status}`.
  - thrown error (offline / down desktop engine) → catch → `{null, status: 0}`.
- **`fetchCommandCenterData()`** (`:55`): initial read + retries at `[1000, 2000, 4000]ms` = **4 attempts, ~7s total**. Breaks early on `data` (success) or status in `[401, 403, 404]`. It calls `fetchJSONWithStatus` directly — **not** `fetchWithRateLimitRetry` (that's only the week POST routes), so a **429 is treated as a transient failure and retried** on the 1/2/4s schedule; if it 429s all four times, `data` is null. There is no explicit request timeout; a hung socket awaits the browser default.
- **The consumer** (`init()`, `:1454`): `topDataResult.data` null →
  - status 404 → `showFranchiseGoneNotice()` (full-screen "This Franchise No Longer Exists"). *(handled)*
  - **anything else (status 0 network, 5xx, exhausted 429, and the non-redirecting 401/403 edge) → `publishFccUserTeam(''); return;`** — the `finally` hides `#page-load-overlay` and the player is left with: top bar "--"/"NR", the Office stuck on its loading skeleton, and **`#play-now` still `disabled` from `:2074`** (only re-enabled at `:1524` on success). A dead, unexplained button. **This is the bug.**

**Other silent-failure spots found (noted, out of this task's scope):**
- `gobAdvance.js` `load()` — the shared Advance on **browse** pages fetches command-center data and, on failure, `resolve(null)` then paints nothing, leaving Advance unpainted. Same silent shape, different surface.
- `init()` `:1555` — if `recoverCpuSimsBeforeFccRender()` returns null (a CPU-sim resume that could not be recovered), `init` also returns silently. Different cause; left as-is.

## 2–5. The new states

On the real load failure (status **not** 404 and **not** 401/403), `init` now calls **`showSeasonLoadError(status)`** instead of returning silently:

- **Error card in the Office main area** (`#office-root`), built from the shared design-system classes **`.gob-view-error` / `.gob-view-retry`** (`css/gob-views.css`) — no new styling, **nothing added to the frozen `franchise-command-center.css`**:
  - headline **"Couldn't load your season"**
  - one cause line when known: **"Connection lost."** (status 0), **"Server error."** (5xx), **"The server is busy."** (429)
  - a **neutral Retry** button (`data-sfx="SFX_SELECT"`, not Advance).
- **Retry** (`:100`-area handler) re-runs the **full load** (`init()`, same retry policy). While retrying: the button is disabled and reads **"Retrying…"** (a `fccSeasonRetrying` guard blocks double-submits). On success the Office renders normally (`renderHomeTab` → `GOBOffice.render` replaces the card) and Advance re-enables; on repeat failure a fresh card replaces the old one.
- **Advance while failed** (`markAdvanceSeasonLoadFailed`): stays `disabled`, **looks** disabled (inline `opacity: 0.4; cursor: not-allowed` — `.hero-btn` has no `:disabled` rule and its sheet is frozen), plays **no sound** (a disabled button dispatches no click, so its `data-sfx` hook cannot fire), and its `aria-label`/`title` read **"Season didn't load: retry above"**. Cleared on a successful load (`:1618`).
- **Desktop/offline**: a down local engine throws → `{null, status: 0}` → the same "Connection lost." card. No profile-specific code; verified in both profiles. (The desktop engine-crash screen in `desktop/` is separate and untouched.)

Backend, week-route retry counts, and `fetchWithRateLimitRetry` were **not** changed.

## Tests

`tests/e2e/fcc-load-retry.spec.js` (route-mocks `/franchise/command-center/data`):
1. every attempt fails (500) → card visible ("Couldn't load your season" + "Server error." + Retry); `#play-now` disabled with the reason `aria-label`; clicking it leaves `__gobSfxCalls` empty (no sound).
2. fail (network) until Retry, then succeed → click Retry → error card gone, `#office-root` not `data-office-state="error"`, Advance enabled, reason label cleared.
3. 429-then-200 → Office loads, **no** error card.
4. desktop profile (`GOB_BUILD_PROFILE='desktop'`) + engine unreachable → same card, Advance disabled.

**4 passed** (targeted run).

## Gates (real numbers)

- **pytest** `--ignore=tests/e2e -q`: **4260 passed, 14 skipped, 109 xfailed, 1 xpassed, 0 failed** (240s).
- **check_ui_tokens.py** `--strict --no-write`: **exit 0** (franchise-command-center.js is legacy JS; no colour literals added anyway).
- **check_migration_gates.py**: **passed** (Gate A 0/0; Gate B 136 lines/44 files — unchanged; no franchise-identity `URLSearchParams` added).
- **Full Playwright** (workers=1, port 8000, CI unset, no other run): **780 passed, 6 skipped, 1 failed** — the one failure is `player-stats.spec.js:166` "player cell matches the roster row", a 2px row-height measurement flake (`46 <= 44`) in a spec my change does not touch; it **passes 6/6 on isolated re-run**. My `fcc-load-retry.spec.js` (4) and every FCC/office spec pass.

## Screenshots (`reports/fcc-load-retry/`, 1280, scroll 0)

| State | File |
|---|---|
| Failure card (500 → "Server error.") + disabled Advance | `failure-card-1280.png` |
| Retrying (busy "Retrying…" button) | `retrying-1280.png` |
| Recovered Office after Retry (Advance re-enabled) | `recovered-office-1280.png` |

STATUS: COMPLETE
