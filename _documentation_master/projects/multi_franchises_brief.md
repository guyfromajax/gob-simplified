# Multi-Franchise Slots Brief

> **Status:** Phase 1–3 done; **Phase 2 dual mode-select landed** (2026-07-26). Next: Phase 4 career/ATL polish as needed.  
> **Goal:** Let each account hold **two** concurrent franchise slots so a user can run two careers at once.  
> **Constraint:** Protect ownership isolation and session identity. Do not invent soft-archive in v1 unless product demands it.

**Related**
- Ownership: `BackEnd/utils/ownership.py` (`verify_franchise_owned_by_user`)
- Create gate: `BackEnd/api/franchise_routes.py` (`select-team` one-franchise check)
- Singular “current”: `GET /franchise/current`, `DELETE /franchise/delete-current` / `/franchise/current`
- FE session inventory: `_documentation_master/01_Data_Persistence/Cache_Usage_Documentation.md` §9
- **LS/URL hardening audit (Phase 3 detail):** [`multi_franchises_ls_url_audit.md`](./multi_franchises_ls_url_audit.md)
- Mode select: `FrontEnd/static/mode-select.js`
- Franchise overview: `_documentation_master/04_Franchise_Mode_Systems/Franchise_Mode_Overview.md`

---

## 1. Verdict (locked from audit)

| Question | Answer |
|---|---|
| Feasible? | **Yes** — data model is already `franchise_id`-scoped; product/API/FE assume one |
| DB bloat? | **~2× franchise-scoped storage** per dual-active user (FTD×128 + FPD/FRD + games dominate). Sustainable at modest scale; add retention before wide rollout |
| Cross-contam? | **Real** if singular APIs + global localStorage + `find_one({user_id})` stay as-is |
| Schema rewrite? | **No** — `franchises.user_id` index is already non-unique |

---

## 2. Current state (what blocks two slots today)

### Backend
- **Create:** `count_documents({"user_id"}) >= 1` → 400 (“delete first”).
- **Current:** `find_one({"user_id"})` — nondeterministic if two docs exist.
- **Delete-current:** same `find_one` — can wipe the wrong franchise.
- **Most gameplay routes:** already take `franchise_id` + ownership check (keep this pattern).

### Frontend
- Mode-select: single franchise card; “New Franchise” deletes current then creates.
- Global LS keys (not slot-scoped): `franchise_id` / `franchiseId`, `franchise_week`, `franchise_user_team*`, `franchise_complete_week_pending`, EOG snapshots, `last_game_*`.
- `API_CONFIG.currentFranchiseId()`: URL first, then LS fallback — silent wrong-franchise risk when URL omits id.

### User-scoped side effects
- Career merge into `users` (record, geek points, championships, archetypes) if both slots play.
- `around_the_league` hydration via `find_one({"user_id"})`.
- Press-conference sessions keyed by user + franchise; delete cascade incomplete.

---

## 3. Product decisions (resolve before / during build)

| # | Decision | Default recommendation |
|---|---|---|
| P1 | Cap | **2** hard cap per `user_id` |
| P2 | Slot UX | Mode-select shows **up to two cards**; empty slot = “Start Franchise” |
| P3 | New in a filled account | If one empty → create there. If two full → must **delete a specific slot** first (never auto-wipe “current”) |
| P4 | Career counters | **v1 = shared** across slots (document it). Per-slot career = later schema |
| P5 | Same school twice | **Allowed**; note `geek_points_by_team` / championships merge under one team key |
| P6 | FTE | Second slot **must not** re-enter tutorial (`fte_v2_complete` already user-scoped) |
| P7 | Soft-archive / park | **Out of scope for v1** — inactive slot = full second copy until hard delete |
| P8 | Featured / ATL | Explicit `franchise_id` (or “featured slot”) for board hydration — never `find_one(user_id)` |

---

## 4. Build plan (phased)

### Phase 0 — Contract (docs + invariants)

- [ ] Document invariant: **URL `franchise_id` is source of truth** for FCC / court / training / recruiting. LS is cache only, namespaced or cleared on switch.
- [ ] Document cap=2 and delete-by-id.
- [ ] List every `find_one({"user_id"` franchise lookup; convert or delete.

### Phase 1 — Backend API (no FE polish yet)

- [x] Raise create gate: `>= 1` → `>= 2` (constant `MAX_FRANCHISES_PER_USER = 2`).
- [x] Add `GET /franchise/list` → all franchises for JWT user (id, team, week, season, colors).
- [x] Keep `GET /franchise/current` as transitional (newest franchise) for old mode-select — Phase 2 switches to list.
- [x] Add **`DELETE /franchise/{franchise_id}`** (ownership-verified). `delete-current` remains for old UI but only when the user has ≤1 franchise (409 if two exist).
- [x] Cascade on delete: FTD, FPD, FRD, games + press_conference_sessions + R2 signed masters.
- [ ] Fix ATL / any other `find_one(user_id)` — deferred (needs featured-slot product call); still nondeterministic with two franchises.
- [x] **Thin Phase 3 warm-up:** `API_CONFIG.currentFranchiseId()` is URL-only (no LS fallback).

**Acceptance:** A test user can create two franchises via API; list returns both; delete A leaves B intact; ownership still rejects other users’ ids.

### Phase 2 — Mode-select UX (dual franchise container)

The mode-select **user / franchise home container** must hold **two franchise instances** side by side (or stacked on narrow viewports).

- [x] Replace single `#franchise-home-slot` card with a **two-slot layout** fed by `GET /franchise/list`.
- [x] **Empty state per slot** — each empty slot shows its own empty card / CTA (e.g. “Start Franchise” / “Find Your Program”), not one shared empty that disappears when either slot is filled. Occupied+empty = one active card + one empty card.
- [x] Occupied slot → Resume / Enter into that slot’s `franchise_id` (URL).
- [x] Delete confirms **which** franchise (team name + week) via `DELETE /franchise/{id}`; never “replace your franchise” / wipe-current.
- [x] If both full → create blocked until a specific slot is deleted.
- [x] Clear or rewrite global franchise LS when entering a slot — **done in Phase 3** (`FranchiseLS`); Phase 2 wires dual empty-state cards.

**Acceptance:** User with 0 / 1 / 2 franchises sees correct UI (two empties / one+empty / two occupied); creating second does not touch first; deleting one does not touch the other. ✅

### Phase 3 — FE session isolation (cross-contam kill)

> Full inventory + file map: [`multi_franchises_ls_url_audit.md`](./multi_franchises_ls_url_audit.md).  
> **Strategy (audit §6): Hybrid C** — URL-only identity; namespace week/team/pending; clear bare orphan keys on mode-select. **Landed 2026-07-26.**

- [x] Prefer **namespaced LS**: `franchise:{id}:week`, `franchise:{id}:user_team`, etc. — via `FrontEnd/static/js/shared/franchiseLocalStorage.js` (`window.FranchiseLS`).
- [x] Kill bare LS fallbacks: `currentFranchiseId()` URL-only; auth bar / tutorials / playbook-report / box-score read namespaced context only when URL has `franchise_id`.
- [x] Collapse `franchiseId` vs `franchise_id` dual-key smell (no longer write bare identity; clear both on exit).
- [x] `franchise_complete_week_pending` / EOG: namespaced as `complete_week_pending` / `eog_pgpc_snapshot`; box-score still id-checks; `clearOnFranchiseExit` wipes bare + all namespaces.
- [x] Court / FCC: refuse franchise flows without URL `franchise_id` (court already fails loud — keep).
- [x] Auth bar: no Slot A chrome on Slot B URL (and no franchise chrome without URL `franchise_id`).

**Acceptance:** Two tabs on two different franchise URLs do not overwrite each other’s week/team/pending complete-week; switching slots on mode-select leaves the other franchise’s server state untouched.  
**Gate:** Do not ship Phase 2 mode-select dual cards until Phase 3 hybrid (or equivalent) lands — see audit §7. ✅ Phase 3 hybrid landed.

### Phase 4 — Career / side systems (explicit)

- [ ] Document shared `users.record` / GP / championships / archetypes behavior for dual play.
- [ ] Confirm geek_points_by_team / championships_by_team behavior when both slots use the same school.
- [ ] FTE grandfather path: any franchise or `fte_v2_complete` — second create skips funnel.
- [ ] Recruit set consumption: remains per-franchise (two slots may consume two sets — expected).

### Phase 5 — Capacity / hygiene (before wide rollout)

- [ ] Measure disk: one mid-season franchise (FTD + games) → budget for 2× × active users.
- [ ] Optional: prune old `games` docs; warn when both slots are deep into seasons.
- [ ] Server load: two parallel complete-week / CPU sims — FE single-flight is per `franchise_id:week` (OK); watch worker pool.

---

## 5. Out of scope (v1)

- Soft-archive / “parked” franchise without full FTD footprint
- Per-slot career stats / separate GP ledgers
- More than 2 slots
- Cross-slot trading / shared recruiting pool between a user’s two franchises
- Changing sim engine or gameplay for multi-slot

---

## 6. Cross-contamination checklist (ship gate)

| Rank | Item | Done when |
|---|---|---|
| P0 | Create cap = 2; no auto-delete of sibling | ✓ |
| P0 | Delete by explicit `franchise_id` only | ✓ |
| P0 | Mode-select never calls delete-current blindly | ✓ |
| P1 | No `find_one({user_id})` for “the” franchise in live paths | ✓ |
| P1 | LS namespaced or cleared on slot switch | ✓ Phase 3 hybrid (`FranchiseLS`) |
| P1 | Pending complete-week / EOG refuse wrong franchise_id | ✓ |
| P2 | ATL / board hydration franchise-explicit | ✓ |
| P2 | `currentFranchiseId()` LS fallback removed or scoped | ✓ URL-only + namespaced context |
| P3 | Press sessions cascade on franchise delete | ✓ |

---

## 7. Suggested implementation order

1. Phase 1 API + tests (safe to land behind old UI if list unused)  
2. Phase 3 LS/URL hardening (can land partially before UX)  
3. Phase 2 mode-select slot UI  
4. Phase 4 docs + FTE/ATL polish  
5. Phase 5 capacity pass  

---

## 8. Key code touch list

| Area | Path |
|---|---|
| Create gate | `BackEnd/api/franchise_routes.py` (`select-team`) |
| Current / delete | same file — list + delete-by-id |
| Ownership | `BackEnd/utils/ownership.py` |
| Indexes | `BackEnd/db.py` (`ensure_franchises_user_id_index` — keep non-unique; optional `(user_id, slot)` later) |
| Mode select | `FrontEnd/static/mode-select.js` |
| Team select LS write | `FrontEnd/static/franchise-select-team.js` |
| FCC | `FrontEnd/static/franchise-command-center.js` |
| API config | `FrontEnd/static/js/config/api-config.js` (`currentFranchiseId`) |
| Auth chrome | `FrontEnd/static/js/shared/authBarInit.js` |
| Franchise LS helper | `FrontEnd/static/js/shared/franchiseLocalStorage.js` (`FranchiseLS`) |
| Complete-week pending | `FrontEnd/static/box-score.js`, finalize / EOG paths |
| ATL | `BackEnd/utils/around_the_league.py` |

---

## 9. Open questions for product (if not using §3 defaults)

1. Shared vs per-slot career record/GP — confirm shared for v1.  
2. Should “featured” franchise drive ATL / public board when both exist?  
3. Soft-delete retention later, or always hard-delete only?  
4. Allow same school in both slots (recommended yes)?
