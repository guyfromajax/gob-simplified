# Multi-Franchise — LS / URL Hardening Audit

> **Date:** 2026-07-25  
> **Scope:** Inventory-only. No code changes. Reinforces Phase 3 of [`multi_franchises_brief.md`](./multi_franchises_brief.md).  
> **Companion:** `_documentation_master/01_Data_Persistence/Cache_Usage_Documentation.md` §9 (broader cache inventory; this doc is multi-slot–focused).

---

## 0. Verdict

| Question | Answer |
|---|---|
| Does this change feasibility? | **No** — still feasible |
| Does Phase 3 remain necessary? | **Yes** — global franchise LS is real cross-contam risk |
| Is URL mostly already correct? | **Yes** — most franchise pages read `?franchise_id=` and pass it to APIs |
| Hardest hardening work? | Bare global LS writers + `currentFranchiseId()` LS fallback + auth-bar team chrome + incomplete `clearFranchiseLocalStorage` |

**Good news already in tree:** `box-score.js` refuses to apply `franchise_complete_week_pending` unless `pending.franchise_id === urlFranchiseId`. Pattern to copy.

---

## 1. Classification legend

| Tag | Meaning |
|---|---|
| **URL-canonical** | Page/API identity must come from URL (or explicit arg). Safe for multi-slot when consistently used. |
| **Cache OK (scoped)** | Key already includes `franchiseId` (or gameId). Low multi-slot risk. |
| **Dangerous global** | One key for “the” franchise. Last writer wins across slots/tabs. |
| **Dangerous fallback** | Prefers URL but falls back to global LS / singleton — silent wrong franchise. |
| **Must clear / namespace on slot switch** | Required Phase 3 action. |

---

## 2. `localStorage` — franchise-related keys

### 2.1 Dangerous globals (must namespace or clear on slot entry)

| Key | Writers | Readers | Notes |
|---|---|---|---|
| `franchiseId` | `franchise-select-team.js` (on create) | `gobTutorialAlerts.js`; cleared by `clearFranchiseLocalStorage` | CamelCase. **Not** what `currentFranchiseId()` reads. |
| `franchise_id` | **No setItem found** in FE | `api-config.js` `currentFranchiseId()`; `gobTutorialAlerts.js`; clear list | Underscore key is cleared but apparently never written — fallback often dead. Still dangerous if anything starts writing it. |
| `franchise_week` | `bootGame.js`, `finalizeGame.js`, `franchise-command-center.js` | `finalizeGame.js` (fallback when URL week missing) | Slot A week overwrites Slot B. |
| `franchise_user_team` | `franchise-select-team.js`, `franchise-command-center.js` | FCC, `authBarInit.js`, `playbook-report.js`, `gobTutorialAlerts.js`, mode-select | Auth bar / chrome shows wrong school. |
| `franchise_user_team_id` | FCC | FCC, mode-select, tutorials, auth bar | Same. |
| `franchise_user_team_primary_color` | FCC | `authBarInit.js` | Same. |
| `franchise_complete_week_pending` | `finalizeGame.js` (JSON incl. `franchise_id`) | `box-score.js` (**id-checked**); cleared FCC / completion / PGPC | Global key but payload has id — box-score already gates. Still only one pending at a time (Slot B can clobber Slot A’s pending JSON). |
| `franchise_eog_pgpc_snapshot` | `finalizeGame.js` | Cleared with pending | Same clobber pattern — confirm readers also id-check. |
| `last_game_id` | `gameScene.js` | Resume / box-score paths | Not franchise-scoped; dual-slot + dual-mode collision. |
| `last_game_user_team_side` | `gameScene.js` | `box-score.js` | Same. |
| `last_box_score_gameId` / `last_box_score_url` | (debug / resume helpers) | Cleared on franchise exit | Low severity. |
| `game_home` / `game_away` | game setup | Cleared on franchise exit | Shared with single; clear on slot switch. |

**Canonical cleanup today:** `mode-select.js` → `clearFranchiseLocalStorage()` removes the franchise context keys + last_game_* + game_home/away + `playbooks_position_filters_franchise_*`.  
**Gap:** Does **not** remove `franchise_complete_week_pending` or `franchise_eog_pgpc_snapshot` (those are cleared elsewhere on successful complete-week / FCC entry). Slot switch without that path can leave stale pending.

### 2.2 Cache OK (already scoped)

| Key / pattern | Scope | Risk |
|---|---|---|
| `playbooks_position_filters_franchise_*` | Per-franchise prefix | Low — cleared on franchise exit |
| `gob_training_form_draft_*` (**sessionStorage**) | `{franchiseId}\|…` | Low |
| `playbooksDraft:*` / `playbooksDraftRestoreOnce:*` (**sessionStorage**) | Includes `franchiseId` | Low |
| `fcc-shell:{franchiseId}:{teamId}` (**sessionStorage**) | Per franchise | Low — two tabs OK; same tab switch may show warm paint of other until fetch (overlay covers) |
| `resource:{page}:{franchiseId}:{season}:{week}:…` (**sessionStorage**) | Per franchise | Low |
| `defenseMatchupsDontShow_{gameId}` etc. | Per game | Low |

### 2.3 Dual-key smell

Create writes **`franchiseId`**; `currentFranchiseId()` reads **`franchise_id`**. Multi-slot hardening should **collapse to one namespaced scheme** and stop relying on either bare key.

---

## 3. URL contract (already mostly healthy)

### Canonical query params (franchise surfaces)

| Param | Role |
|---|---|
| `franchise_id` | **Required** identity for FCC, recruiting, training, stats, schedule, rankings, brackets, news, cut-players, practice squad, awards, etc. |
| `team_id` | User (or viewed) team; backend still prefers franchise `user_team_object_id` for authoritative ops |
| `week` | Often present; some paths fall back to LS `franchise_week` |
| `mode=franchise` | Mode detection alongside id |
| `game_id` | Court / box-score |
| `return_url` | Navigation crumb |

### Pages that correctly require / propagate `franchise_id` (sample — pattern is widespread)

FCC, schedule, stats, rankings, leaders, news, brackets, recruiting hub/orders/invites/results, training + reports, playbooks, cut-players, team-roster-view, practice-squad standings/bracket, awards, court (bootGame prefers URL; avoids writing franchise_id to LS for identity).

### Gaps / fallbacks to kill or tighten

| Location | Behavior | Phase 3 action |
|---|---|---|
| `api-config.js` `currentFranchiseId()` | URL → else LS `franchise_id` | **Remove LS fallback** or require explicit arg for paint; never invent id from bare LS |
| `finalizeGame.js` | Week from LS if missing | Prefer URL / API state only |
| `bootGame.js` | Writes `franchise_week` from URL | Stop writing global, or write namespaced |
| `authBarInit.js` | Team chrome from LS | Resolve from URL franchise fetch or pass-through; don’t show Slot A colors on Slot B |
| `gobTutorialAlerts.js` | Reads `franchise_id` \|\| `franchiseId` from LS | URL only |
| `playbook-report.js` | `franchise_user_team` from LS for display | Prefer API / URL context |
| Mode-select `currentFranchise` singleton | From `GET /franchise/current` | Replace with list + explicit card id |

---

## 4. Collision scenarios (multi-slot)

| # | Scenario | What happens today | Severity |
|---|---|---|---|
| S1 | Two tabs: FCC Slot A + FCC Slot B | sessionStorage caches are id-scoped → **OK** for ResourceCache/fcc-shell. Global LS team/week last writer wins → **auth bar / week helpers wrong** | P1 |
| S2 | Slot A finishes game → pending complete-week; user opens Slot B box-score | box-score **id-checks** → won’t run A’s pending on B. But A’s pending JSON may be **overwritten** if B also writes pending | P1 |
| S3 | Mode-select “Resume” while LS still holds other slot’s team/week | Navigates with `currentFranchise.franchise_id` in URL (OK if API list fixed). LS stale until FCC overwrites | P2 |
| S4 | Image paint without `franchise_id` in URL | `currentFranchiseId()` LS fallback → wrong franchise paint / ensure | P1 |
| S5 | New Franchise wipe (today) | `clearFranchiseLocalStorage` + delete-current | P0 product — must become delete-by-id |
| S6 | Court mid-game Slot A; mode-select opens Slot B in another tab | `last_game_*` global; resume helpers confuse | P2 |
| S7 | Complete-week Phase B in-flight keyed `franchise_id:week` | Client single-flight is **scoped** → OK; server load doubles if both advance | Capacity, not LS |

---

## 5. Phase 3 hardening checklist (file-mapped)

### Must-do before dual-slot UX ships

- [ ] **Namespace or dual-write scheme** for: week, user_team, user_team_id, primary_color — e.g. `franchise:{id}:week` — **or** clear all bare keys on every slot entry from mode-select.
- [ ] **Stop writing** bare `franchiseId` / never depend on bare `franchise_id` in LS for identity.
- [ ] **`currentFranchiseId()`:** URL only (or explicit argument). No LS fallback.
- [ ] **Extend `clearFranchiseLocalStorage`** (or replace with `clearFranchiseLocalStorage(franchiseId?)`) to include `franchise_complete_week_pending`, `franchise_eog_pgpc_snapshot`.
- [ ] **Pending / EOG:** keep id-check (box-score); add same check on every reader of `franchise_eog_pgpc_snapshot`; consider namespaced pending keys so two slots can both hold pending.
- [ ] **Auth bar:** don’t paint franchise team from global LS when URL franchise ≠ LS; prefer no franchise chrome until context known.
- [ ] **Writers to update:** `franchise-select-team.js`, `franchise-command-center.js`, `bootGame.js`, `finalizeGame.js`, `gameScene.js` (last_game_*), `authBarInit.js`, `gobTutorialAlerts.js`, `api-config.js`, `playbook-report.js`, `mode-select.js`.

### Already OK — don’t break

- [ ] Keep URL `franchise_id` propagation on FCC child pages.
- [ ] Keep ResourceCache / fcc-shell / training draft / playbooksDraft franchise scoping.
- [ ] Keep box-score pending `franchise_id` equality check; extend pattern elsewhere.
- [ ] Keep CPU clients keyed `franchise_id:week`.

### Tests / manual ship gate

- [ ] Two franchises; Tab A week 5 FCC + Tab B week 12 FCC → reload A → still week 5 server truth; chrome matches A.
- [ ] Finish game on A (pending set); open B box-score → no Phase B for A; return to A box-score → pending still valid (or namespaced).
- [ ] Paint/ensure player image on page **without** franchise in URL must no-op or require explicit id — never Slot B’s LS.
- [ ] Delete Slot A → LS cleared; Slot B resume still works.

---

## 6. Recommended Phase 3 strategy (pick one)

| Option | Approach | Pros | Cons |
|---|---|---|---|
| **A — Clear on switch** | On mode-select slot entry, wipe all bare franchise LS; rely on URL + first FCC fetch to repopulate | Smaller change | Two tabs still fight over globals |
| **B — Namespace** | `franchise:{id}:*` for all franchise context; drop bare keys | Two tabs safe | More touch sites |
| **C — Hybrid (recommended)** | Namespace week/team/pending; **remove** identity LS entirely; URL-only id; clear bare orphans on login/mode-select | Matches “URL is law” | Medium effort |

**Recommendation:** **C**. Identity never in LS; context cache namespaced; pending namespaced or single-pending with hard id checks everywhere.

---

## 7. Feasibility reinforcement

| Concern | After this audit |
|---|---|
| “Is FE too tangled?” | **No** — risk is concentrated in ~10 global keys + ~8 writer files + one fallback helper |
| “Will URL pages need rewrites?” | **Mostly no** — they already take `franchise_id` |
| “Block Phase 1 API?” | **No** — land list/cap/delete-by-id first |
| “Block Phase 2 mode-select?” | **Yes until Phase 3 hybrid lands** (or land mode-select behind feature flag after C) |

---

## 8. Open confirmations (product / eng)

1. Allow **two simultaneous pending complete-weeks** (one per slot)? → pushes namespaced pending. If no, document “one pending globally” and id-check forever.
2. Auth bar on non-franchise pages: show **last** franchise team, **featured** slot, or nothing?
3. Collapse `franchiseId` vs `franchise_id` LS keys as part of Phase 3 (recommended yes).
