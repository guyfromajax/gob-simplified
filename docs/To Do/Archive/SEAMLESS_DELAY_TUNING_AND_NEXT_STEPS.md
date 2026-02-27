# Seamless Transitions: Delay Tuning Plan & Next-Step Options

This doc supports reducing the pause between turns in two parts: (1) a step-by-step plan to **tune or reduce existing fixed delays** (align first, then implement), and (2) a **framing of tradeoffs** for later approaches (preload vs batch vs same-response).

---

## Part 1: Step-by-Step Plan — Reduction / Tuning of Fixed Delays

**Goal:** Shorten the perceived pause at turn boundaries by reducing or making configurable the fixed delays that run after shots, rebounds, and fast breaks. No backend or request-flow changes.

**Impact (from analysis):** These delays add ~1.5–3+ seconds per shot/rebound turn. Tuning can remove ~1–1.5 s per such turn—often more than the API round-trip—with low risk.

---

### Step 1: Centralize and document current delay values

- **Action:** List every fixed delay that contributes to "pause" at turn boundaries, with current value and file/line (or config key).
- **Output:** A single reference table (in this doc or a short "Delay inventory" section) so we can track what we change and why.
#### Delay inventory (Step 1 output)

| Purpose | Current value | Location | Config key (if any) |
|--------|----------------|----------|---------------------|
| **Shot (HCO) rim hold** — ball at rim after make/miss before outcome | 1000 ms | `ShotAnimationSystem.js` ~991, ~998–1002 | — (hardcoded) |
| **Shot (fast break) rim hold** | 2000 ms | `ShotAnimationSystem.js` ~991 | — (hardcoded; `isFastBreak ? 2000 : 1000`) |
| **Shot make — announcement hold** (after "It's Good!" before inbound) | 1000 ms | `ShotAnimationSystem.js` ~1108 | — (hardcoded) |
| **Made shot rim hold** (ballManager path; allows announcement) | 1000 ms | `ballManager.js` ~615–618 | — (hardcoded) |
| **Rebound — delay before possession secured** (after rebounder reaches spot) | 1000 ms | `ballManager.js` ~1030–1033 | `animationConfig.rebound.attachDelayMs` (default 1000) |
| **Offensive rebound — pause before kickout/putback** | 1000 ms | `turnAnimation.js` ~2663–2667 | `animationConfig.offensiveRebound.pauseMs` (default 1000) |
| **Free throw rim hold** (legacy path) | 300 ms | `freeThrow.js` ~242 | `animationConfig.freeThrow.rimHoldMs` |
| **Free throw make — rim hold** (non-final FT, ball at rim) | 1000 ms | `FreeThrowAnimationSystem.js` ~287–290 | — (hardcoded) |
| **Fast break make — hold after "It's Good!"** | 1000 ms | `fastBreak.js` ~966 | — (hardcoded) |
| **Fast break defensive stop — hold after "Great Stop!"** | 1000 ms | `fastBreak.js` ~1581 | — (hardcoded) |
| **SIP — hold after ball placed with inbound passer** | 200 ms ×2 | `turnAnimation.js` ~495, ~506 (onComplete/onStop) | — (hardcoded) |
| **Inbound (BIP/setup) — hold after ball placed with passer** | 200 ms ×2 | `turnAnimation.js` ~1816, ~1819 | — (hardcoded) |
| **Config: fast break rim hold** (default; not yet used in ShotAnimationSystem) | 2000 ms | `animation_config.js` ~62 | `defaults.fastBreak.rimHoldMs` |

**Small / non-boundary delays (for reference only):**  
50–100 ms: `fastBreak.js` (pass complete, rebounder polling), `ballManager.js` (watcher cleanup 200+50).  
**Quarter start only:** `openingTip.js` — `INITIAL_HOLD_DURATION` 2000 ms (tip-off hold).

**Step 1 status:** ✅ Complete — use the table above when centralizing (Step 3) and when choosing targets (Step 2).

---

### Step 2: Define target values and constraints

- **Action:** For each delay from Step 1, decide:
  - **Target value** (e.g. 1000 → 500 ms) or "make configurable" (e.g. by game speed).
  - **Constraint:** Minimum time needed for announcements, score pop, or "possession secured" feel (so we don't remove entirely without testing).
- **Suggested starting targets (to align):**
  - **Rim hold (shot):** 1000 ms → 500–600 ms (normal); 2000 ms → 1000–1200 ms (fast break) — keep enough time for "swish"/announcement.
  - **Rebound attach delay:** 1000 ms → 400–500 ms (ball "secured" by rebounder).
  - **Offensive rebound pause (before kickout/putback):** 1000 ms → 300–500 ms.
  - **Free throw rim hold:** Keep or slightly reduce (e.g. 300 ms already in config for one path; 1000 ms in FreeThrowAnimationSystem — align with design).
  - **Fast break rim hold:** Align with rim hold (shot) targets above.
#### Step 2 — Proposed targets (align / adjust before Step 3)

| Delay (from inventory) | Current | Proposed target | Constraint / note |
|------------------------|---------|-----------------|-------------------|
| Shot (HCO) rim hold | 1000 ms | **500 ms** | Ball at rim only; min ~400 ms so outcome visible. |
| Shot (fast break) rim hold | 2000 ms | **1000 ms** | Ball at rim for FB; announcement hold is separate. |
| Shot make — announcement hold | 1000 ms | **1000 ms** (keep) | Keep for announcement display ("It's Good!" / AND-1). |
| Made shot rim hold (ballManager) | 1000 ms | **1000 ms** (keep) | Keep for announcement display. |
| Rebound attach delay | 1000 ms | **500 ms** | Ball "secured"; min ~400 ms so attach doesn't feel instant. |
| Offensive rebound pause | 1000 ms | **400 ms** | Before kickout/putback; can go 300 ms if needed. |
| Free throw rim hold (legacy) | 300 ms | **300 ms** (keep) | Already short. |
| Free throw make — rim hold (FT system) | 1000 ms | **1000 ms** (keep) | Keep for announcement display. |
| Fast break make — hold after "It's Good!" | 1000 ms | **1000 ms** (keep) | Keep for announcement display. |
| Fast break defensive stop — "Great Stop!" | 1000 ms | **1000 ms** (keep) | Keep for announcement display. |
| SIP — hold after ball placed | 200 ms ×2 | **150 ms ×2** (or keep 200) | Optional reduction. |
| Inbound (BIP) — hold after ball placed | 200 ms ×2 | **150 ms ×2** (or keep 200) | Same as SIP. |
| Config: fast break rim hold (default) | 2000 ms | **1000 ms** | Match once driven from config in Step 3. |

**Summary:** **Announcement holds stay 1000 ms** (shot make, made shot ballManager, FT make rim hold, FB "It's Good!", FB "Great Stop!"). Reduce: Shot (HCO) rim hold 500 ms; rebound attach 500 ms; OREB pause 400 ms; Shot (FB) rim hold 2000→1000 ms; inbound 150 ms optional; 300 ms FT keep. **Optional (later):** overrides in `animation_config` for production tuning.

**Step 2 status:** Proposed targets above — confirm or adjust, then proceed to Step 3.

---

### Step 3: Implement changes in config first

- **Action:** Change only `animation_config.js` (and any defaults that feed it) so that all delay values flow from one place. Replace hardcoded 1000/2000 ms in ShotAnimationSystem, ballManager, fastBreak, FreeThrowAnimationSystem, turnAnimation with `animationConfig.*` (or equivalent) where they are not already.
- **Outcome:** One source of truth for delay tuning; future changes are in one file (or one override object).

**Step 3 status:** ✅ Complete. Added to `animation_config.js`: `shot` (rimHoldMs, makeAnnouncementHoldMs, madeRimHoldMs), `freeThrow.makeRimHoldMs`, `fastBreak.makeAnnouncementHoldMs` & `defensiveStopHoldMs`, `inbound.holdAfterPlaceMs`. Replaced hardcoded delays in ShotAnimationSystem, ballManager, FreeThrowAnimationSystem, fastBreak, turnAnimation. Values unchanged (Step 4 will apply targets).

---

### Step 4: Apply the chosen target values

- **Action:** Update the centralized values (or overrides) to the targets agreed in Step 2.
- **Files likely touched:** `animation_config.js`; optionally `ShotAnimationSystem.js`, `ballManager.js`, `fastBreak.js`, `FreeThrowAnimationSystem.js`, `turnAnimation.js` if any literals remain.
- **Check:** No new magic numbers; all boundary delays documented or config-driven.

**Step 4 status:** ✅ Complete. Applied: **shot rim hold** 1000 ms (kept; used for both makes and misses in ShotAnimationSystem). **Fast break rim hold** 2000 → 1000 ms (makes only; FB misses use rebound flow). **Inbound hold** 200 ms (unchanged). **Rebound attach** 1000 → 500 ms. All transition hold times are documented in **`docs/docs_1_systems/05_Animation_System/Transition_Systems.md`** for future tweaks.

---

### Step 5: Test and validate

- **Action:** Manually (and optionally with a short checklist) verify:
  - **Shot → miss → DREB → next HCO:** Pause feels shorter; score/announcement still readable; ball attach doesn't look glitchy.
  - **Shot → make:** Brief rim hold then transition; no regression.
  - **Fast break make/miss:** Same.
  - **Offensive rebound (kickout/putback):** Pause before next action feels acceptable.
  - **Free throw:** No regressions.
- **Rollback:** If anything feels wrong, revert to previous values (or lower only the problematic delay).

---

### Step 6: (Optional) Tie to game speed

- **Action:** If we have a game-speed factor (e.g. "fast" vs "normal"), consider scaling these delays by that factor so faster play has shorter pauses. Implement only after base tuning is validated.

---

**Summary — order of work:**  
1) Audit and list delays → 2) Agree targets and constraints → 3) Centralize in config → 4) Apply values → 5) Test → 6) (Optional) Game-speed scaling.

---

## Part 2: Tradeoffs — Preload vs Batch vs Same-Response (Next Turn)

After delay tuning, the remaining "pause" is largely the **API round-trip** for the next turn. The three ways to get the next turn earlier (or without an extra wait) are summarized below.

| Criterion | **Preload** (fetch next while current animates) | **Batch** (backend returns N turns per request) | **Same-response** (current + next turn in one response) |
|-----------|--------------------------------------------------|--------------------------------------------------|---------------------------------------------------------|
| **Long-term SS&S** | Good: frontend stays "one turn at a time"; backend API unchanged. | **Strongest:** one source of truth (backend decides how many turns); frontend just consumes a list. | Good: one request per "step"; contract is "current + optional next." |
| **Risk to existing code** | **Lowest:** add a parallel fetch and a small buffer; `simulateTurnByTurn` and handlers mostly unchanged. | **Medium:** backend must support returning multiple turns; frontend loop changes (consume batch, then request next batch). | **Medium–low:** backend adds optional `next_turn`; frontend uses it when present. |
| **Backend change** | **None** (still one turn per request). | **Yes:** new or extended endpoint (or flag) that runs N turns and returns a list. | **Yes:** include next turn (or preview) in current response when possible. |
| **When next turn is available** | When current turn *starts* (or shortly after), if next request is fired then. | When the batch is returned (next turn is already in the array). | When current turn is returned (next is in the same payload). |
| **Best for** | Minimizing change; keeping "one request per turn" semantics. | Clean, scalable "chunks of turns"; future features (replay, rewind). | Minimal frontend loop change; bridge can run as soon as current handler finishes. |

**One-line takeaway:**

- **Most long-term SS&S:** **Batch** (backend owns "how many turns"; frontend is a simple consumer).
- **Least likely to break existing code:** **Preload** (no backend change; small frontend addition).
- **Easiest to plug into current "one response per turn" flow:** **Same-response** (backend adds optional field; frontend uses it for bridging when present).

**Other considerations:**

- **Preload:** Need a clear rule for *when* to fire the next request (e.g. at turn start vs after first step). Too early can waste work on timeout/foul-out; too late and the next turn might not be ready when the current one ends.
- **Batch:** Need a policy for batch size (e.g. "until next dead ball / timeout / quarter" or "fixed N"). Timeouts and quarter end require the frontend to stop consuming the batch and possibly request a new state.
- **Same-response:** Backend must compute the next turn (or a minimal preview) when returning the current one. Slightly more work per response, but the next turn is available immediately for a BallSpot-style bridge.

**Part 2 (Preload) implementation:** ✅ Done in `gameScene.js` `simulateTurnByTurn()`. `fetchTurnData(offenseOverride, defenseOverride)` runs the simulate-turn request. The loop uses a preloaded turn when one is available and there are no overrides; otherwise it fetches (with overrides). Preload is started at the start of each iteration (after receiving the current turn, before animating) when the turn is not TIMEOUT and not the final turn of the quarter. On preload failure, the loop falls back to a fresh fetch. No backend changes.
