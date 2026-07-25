# Multi-Franchise Slots Brief

> **Status:** Proposed — feasibility audited 2026-07-25; **LS/URL hardening audited 2026-07-25**  
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

- [ ] Raise create gate: `>= 1` → `>= 2` (constant `MAX_FRANCHISES_PER_USER = 2`).
- [ ] Add `GET /franchise/list` → all franchises for JWT user (id, team, week, season, colors, updated_at).
- [ ] Deprecate / stop relying on `GET /franchise/current` for multi-slot (keep temporarily as “first list item” only if needed for grandfather clients — prefer remove from mode-select).
- [ ] Replace delete-current with **`DELETE /franchise/{franchise_id}`** (ownership-verified). Remove “delete whatever find_one returns.”
- [ ] Cascade on delete: FTD, FPD, FRD, games (existing) **+** `press_conference_sessions` for that franchise; clear ATL presence for that franchise if any.
- [ ] Fix ATL / any other `find_one(user_id)` to require `franchise_id` or featured-slot field on user/franchise.

**Acceptance:** A test user can create two franchises via API; list returns both; delete A leaves B intact; ownership still rejects other users’ ids.

### Phase 2 — Mode-select UX

- [ ] Two slot cards from `/franchise/list`.
- [ ] Empty slot → team select (create).
- [ ] Occupied → Resume / Play into that `franchise_id` (URL).
- [ ] Delete confirms **which** franchise (team name + week); never “replace your franchise” without picking.
- [ ] Clear or rewrite global franchise LS when entering a slot (see Phase 3).

**Acceptance:** User with 0 / 1 / 2 franchises sees correct UI; creating second does not touch first; deleting one does not touch the other.

### Phase 3 — FE session isolation (cross-contam kill)

> Full inventory + file map: [`multi_franchises_ls_url_audit.md`](./multi_franchises_ls_url_audit.md).  
> **Recommended strategy (audit §6): Hybrid C** — URL-only identity; namespace week/team/pending; clear bare orphan keys on mode-select.

- [ ] Prefer **namespaced LS**: `franchise:{id}:week`, `franchise:{id}:user_team`, etc. — drop bare identity keys.
- [ ] Kill bare LS fallbacks: `currentFranchiseId()` URL-only; auth bar / tutorials / paint helpers.
- [ ] Collapse `franchiseId` vs `franchise_id` dual-key smell (create writes camelCase; reader expects underscore).
- [ ] `franchise_complete_week_pending` / EOG: keep box-score id-check; namespace so two slots don’t clobber; extend `clearFranchiseLocalStorage` to include these keys.
- [ ] Court / FCC: refuse franchise flows without URL `franchise_id` (court already fails loud — keep).
- [ ] Auth bar: no Slot A chrome on Slot B URL.

**Acceptance:** Two tabs on two different franchise URLs do not overwrite each other’s week/team/pending complete-week; switching slots on mode-select leaves the other franchise’s server state untouched.  
**Gate:** Do not ship Phase 2 mode-select dual cards until Phase 3 hybrid (or equivalent) lands — see audit §7.

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
| P1 | LS namespaced or cleared on slot switch | ✓ |
| P1 | Pending complete-week / EOG refuse wrong franchise_id | ✓ |
| P2 | ATL / board hydration franchise-explicit | ✓ |
| P2 | `currentFranchiseId()` LS fallback removed or scoped | ✓ |
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
| Complete-week pending | `FrontEnd/static/box-score.js`, finalize / EOG paths |
| ATL | `BackEnd/utils/around_the_league.py` |

---

## 9. Open questions for product (if not using §3 defaults)

1. Shared vs per-slot career record/GP — confirm shared for v1.  
2. Should “featured” franchise drive ATL / public board when both exist?  
3. Soft-delete retention later, or always hard-delete only?  
4. Allow same school in both slots (recommended yes)?
