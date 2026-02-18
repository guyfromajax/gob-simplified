# Canonical “your team” URL param – code review (franchise/tournament)

**Headline:** Set-lineup only uses `my_team` / `user_team_id` and ignores `team_id`. Franchise Play Next Game sometimes sent only `team_id` → “Can’t determine your team.” **Fix implemented (February 2026):** Franchise now uses the same approach as tournament: API-sourced team name first (`userTeamNameForLeaders` from `topData.team`), then id-derived fallback (`userTeamId` vs `home_id`/`away_id`), so the set-lineup URL always gets `my_team` when possible. No set-lineup change; fix at source in `franchise-command-center.js`. Scope: frontend URL params only (not backend APIs).

**Could this be caching?** Yes. `userTeamName` is read once from `localStorage.getItem('franchise_user_team')` and is **never** set from the API on this page; `userTeamId` is set from URL → localStorage → API (`topData.team_id`). So an “already logged in” session can have `userTeamId` but empty or stale `userTeamName` (e.g. different tab, pre-deploy cache, or `franchise_user_team` never written). Then `mySide` is `''` and the URL has `team_id` but no `my_team`. New login often repopulates or hits fresh state, so it can work. **Training:** Training uses `team_id` in the URL for API and when linking to game-plan/command center; it does **not** navigate to set-lineup or call `resolveTeam()`, so training working doesn’t exercise the bug path. **Deploy + cached tab:** Possible: old JS + new backend (or vice versa) or mixed localStorage can cause one-off wonkiness. **Bottom line:** Don’t over-engineer. Reproduce after hard refresh / incognito; if it still happens, a small fix is either (1) franchise derives `my_team` from `userTeamId` vs `home_id`/`away_id` when `userTeamName` doesn’t match, or (2) set-lineup fallback: if `team_id` present and matches home/away, use it. Either is low-risk; avoid big “canonical variable” refactors until you’re sure it’s reproducible.

---

## 1. Where set-lineup URLs are built (franchise & tournament)

| Entry point | File | team_id | my_team | user_team_id | Notes |
|-------------|------|--------|---------|--------------|--------|
| **Franchise – Play Next Game** | `franchise-command-center.js` ~1401 | ✅ if `userTeamId` | ✅ (API + id fallback) | ❌ | `mySide = userTeamName === home ? 'home' : (userTeamName === away ? 'away' : '')`. `userTeamName` is from `localStorage.getItem('franchise_user_team')` and is **never** set from API. So after session restore or when names don’t match, `mySide` is `''` → URL has `team_id` but **no** `my_team` → set-lineup fails. |
| **Tournament – Play Game** | `tournament.js` ~1676–1680 | ❌ | ✅ if `mySide` | ✅ if `userTeamId` | `mySide` from `userTeamName` (tournament doc / command center). Also: `home_id`/`away_id` are set to **team names** (`home`, `away`), not ObjectIds. |
| **Timeout → set-lineup** | `timeoutNavigationHelper.js` | ✅ passed through | ✅ passed through | ✅ in franchise/tournament | Helper copies `team_id`, `my_team`, `user_team_id` from source URL (or overrides). So if court URL had `team_id` but no `my_team`, the lineup URL would still lack `my_team`. |
| **Foul-out → set-lineup** | `foulOutPopup.js` | via helper overrides | ✅ | ✅ | Uses same helper; can pass `team_id` in overrides. If URL only had `team_id`, foul-out flow would still need `my_team` or set-lineup would need to derive it from `team_id`. |

**Conclusion:** Franchise Play Next Game was the only place that could build a set-lineup URL with `team_id` but without `my_team` (and without `user_team_id`) is **Franchise Play Next Game** when `userTeamName` is missing or doesn’t match `home`/`away`. Tournament always adds both when available; timeout/foul-out pass through whatever the court URL had.

---

## 2. set-lineup and “your team” resolution

- **File:** `FrontEnd/static/set-lineup.js`
- **URL reads (top-level):** `my_team`, `user_team_id`. **`team_id` is not read.**
- **`resolveTeam()` (~1039–1061):**
  - If `myTeamSide === 'home' | 'away'` → use it and set `teamName` from `homeTeam`/`awayTeam`.
  - Else if `userTeamIdParam` is set → compare to `homeId`/`awayId` and `homeTeam`/`awayTeam` to set `myTeamSide` and `teamName`.
  - Else → return false → alert “Can’t determine your team for this game.”

So any URL that has **only** `team_id` (and no `my_team` or `user_team_id`) fails today. Making **`team_id`** canonical for “your team” would mean teaching `resolveTeam()` to:
- Read `team_id` from the URL (in addition to or instead of `user_team_id`).
- When `team_id` is present and `home_id`/`away_id` are present, set `myTeamSide = (team_id === home_id || team_id === homeTeam) ? 'home' : 'away'` (and set `teamName` accordingly), with normalisation/compare logic as needed (e.g. ObjectId vs string, or name vs id).

That would fix the franchise Play Next Game bug without requiring franchise to also send `my_team`.

---

## 3. Bugs if we “lock in” `team_id` as the canonical variable

Interpretation: **“Lock in `team_id`”** = treat `team_id` as the single canonical way to pass “user’s team” in URLs and have set-lineup (and, where needed, other screens) derive `my_team` from `team_id` when `home_id`/`away_id` (or home/away names) are present.

- **Franchise Play Next Game:** **Fixed.** URL often has `team_id` only; set-lineup would resolve team from `team_id` and no longer show “Can’t determine your team.”
- **Tournament Play Game:** Today it sends `user_team_id` and `my_team`, not `team_id`. If we **only** accepted `team_id` and dropped `user_team_id`/`my_team`:
  - Tournament would need to **also** put `team_id` (ObjectId) in the set-lineup URL.
  - Tournament currently puts `home_id`/`away_id` as **names** (not ObjectIds). So set-lineup would need to support either:
    - Comparing `team_id` (ObjectId) to `home_id`/`away_id` when those are ObjectIds (so tournament would need to send ObjectIds in `home_id`/`away_id` for this path), or
    - Keeping a fallback that compares `user_team_id`/team name to `home`/`away`/`home_id`/`away_id` for backward compatibility.
- **Timeout / foul-out:** They already pass `team_id` through the helper. If the court URL had only `team_id` (e.g. after a franchise Play Next Game that didn’t add `my_team`), then after timeout/foul-out the lineup URL would still have only `team_id`. So **no new bug** if set-lineup learns to resolve from `team_id`; current “no my_team” bug would be fixed there too.
- **Single game mode:** Typically uses `my_team` (and sometimes `team_id` for team name). If we keep accepting `my_team` as valid and only add `team_id` as an additional way to resolve, single game is unchanged. If we ever required **only** `team_id` in single mode, we’d need to ensure all single-game entry points pass `team_id` (or derive it from `my_team` + `home_id`/`away_id`).

**Summary:** Locking in `team_id` and teaching set-lineup to resolve from it would fix the franchise bug and align with backend/APIs. The only risk is if we **removed** support for `my_team`/`user_team_id` without updating every caller (especially tournament) to send `team_id` and, where needed, ObjectIds in `home_id`/`away_id`.

---

## 4. Other consumers of `my_team` / `user_team_id` / `team_id`

These would be in scope if we want one canonical “user team” signal across the app:

| Consumer | Reads | Purpose |
|----------|--------|--------|
| **set-lineup.js** | `my_team`, `user_team_id` (not `team_id`) | Resolve “your team” and lineup slots. |
| **game-plan.js** | `my_team`, `user_team_id`, `team_id` | Uses `team_id` first in franchise/tournament; uses `myTeamSide` for lineup params (e.g. `home_pg`). If URL had only `team_id`, game-plan would need to derive `my_team` from `team_id` when `home_id`/`away_id` exist, or the upstream URL must include `my_team`. |
| **bootGame.js** | `my_team`, `team_id`, `user_team_id` | `teamId = team_id || (userTeamSide === 'home' ? home_id : away_id)`. Can derive side from `team_id` vs `home_id`/`away_id` if we want. |
| **court.html** | `my_team`, `team_id`, `user_team_id` | Same idea as bootGame. |
| **timeoutNavigationHelper.js** | Copies `team_id`, `my_team`, `user_team_id` | If source has only `team_id`, it already forwards `team_id`; set-lineup just needs to use it. |
| **timeoutButtonManager.js** | `my_team`, `team_id`, `user_team_id` | Builds params for set-lineup via helper; passes `team_id` and `user_team_id`. If court had only `team_id`, lineup URL would have only `team_id` unless we derive `my_team` in the helper. |
| **foulOutPopup.js** | `my_team`, `user_team_id` | Needs “user’s team” for lineup; could also accept `team_id` and derive side when possible. |
| **gameCompletionPopup.js** | `team_id` (from URL or home_id/away_id) | Builds links to tournament/franchise/box-score with `team_id`. No `my_team` dependency. |
| **playbooks.js** | `team_id`, `user_team_id`, `my_team` in places | Load/save by team; some links use `my_team`. |
| **box-score.js** | `my_team`, `user_team_id`, `team_id` | Highlights “your” team; could derive from `team_id` when present. |
| **training-report.js** | `team_id` | Uses `team_id` only; no `my_team`. |
| **Backend APIs** | `team_id` (and sometimes `user_team_id` in docs) | Already treat `team_id` as the canonical team identifier for FTD, roster, gameplan, etc. |

So the **scope of “canonical variable”** is not only “URL for franchise/tournament set-lineup” but also:

- **All frontend pages** that need “user’s team” or “user’s side” (set-lineup, game-plan, court, bootGame, timeout/foul-out flows, box-score, playbooks) and currently read `my_team` or `user_team_id` from the URL.
- **Single game mode** currently relies more on `my_team` (home/away); it can stay that way if we only add `team_id` as an alternative and don’t remove `my_team`.

So: **scope is URL params across franchise, tournament, and (optionally) single game** for any screen that needs “which team is the user’s.” It does **not** change backend API contracts (they already use `team_id`); it only affects how the frontend builds and reads URLs.

---

## 5. Recommendation (for implementation later)

- **Minimal fix (no “lock-in” yet):** In set-lineup `resolveTeam()`, **also** consider `urlParams.get('team_id')`. If `team_id` is present and matches `home_id`/`away_id` or `homeTeam`/`awayTeam`, set `myTeamSide` and `teamName`. That fixes the franchise Play Next Game bug without changing any URL builders.
- **Lock in `team_id` as canonical (franchise/tournament):**
  - Treat `team_id` as the primary “user team” URL param for franchise/tournament; have set-lineup (and, if desired, game-plan, timeout helper, foul-out) resolve “user’s side” from `team_id` when `home_id`/`away_id` (or names) are present.
  - Keep accepting `my_team` and `user_team_id` for backward compatibility and for single-game.
  - Ensure tournament either sends `team_id` in set-lineup URLs or keep supporting `user_team_id` + name comparison (tournament currently uses names in `home_id`/`away_id`).
- **Scope:** Canonical “user team” URL param applies to **all relevant frontend URL flows** (franchise, tournament, and optionally single game) that navigate to set-lineup, game-plan, court, box-score, etc. It does not expand to backend API contracts; those already use `team_id`.
