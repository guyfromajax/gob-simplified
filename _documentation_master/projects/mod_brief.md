# Custom Teams / League Modding Brief

> **Status:** Discovery only (2026-07-27) — no build yet.  
> **Goal:** Let franchise users “mod their league” by introducing custom teams from their own data — a best-in-class sports-sim feature.  
> **Constraint:** Do not invent soft-archive or rewrite the sim engine for v1. Prefer franchise-scoped overlays that preserve league topology.

**Related**
- Franchise overview: `_documentation_master/04_Franchise_Mode_Systems/Franchise_Mode_Overview.md`
- Persistence: `_documentation_master/01_Data_Persistence/Data_Persistence_System.md`
- Team assets: `_documentation_master/03_UX_Systems/Team_Images_System.md`
- Multi-franchise identity lessons: [`multi_franchises_brief.md`](./multi_franchises_brief.md)
- CPU playbooks: `_documentation_master/08_Playbooks_Systems/Computer_Team_Playbooks_System.md`
- Geek Points: `_documentation_master/02_User_Account_Systems/Geek_Points_System.md`

---

## 1. Verdict

| Question | Answer |
|---|---|
| Is this feasible? | **Yes** — as a **per-franchise overlay** that **replaces a league slot**, not as “add a 129th team.” |
| Smallest useful v1? | Replace **one** franchise slot (start with the user’s own program): name, mascot, colors, optional roster import. |
| What is *not* v1? | Custom conferences/regions, add/remove teams, alternate league sizes, shared Workshop mods, full asset studio. |
| Sim engine rewrite needed? | **No** — if the replaced core `teams._id` is retained as the schedule/bracket/game identity. |

**Locked recommendation (pending product confirm):** Custom teams are **per franchise slot**, not account-wide. Slot A’s custom Morristown clone does not appear in Slot B.

---

## 2. How GOB teams work today (why replace-not-add)

### League topology is rigid

Franchise init assumes:

- **128** teams total  
- **16** conferences × **8** teams  
- **8** regions (A–H) × **16** teams  

Key enforcers:

- `BackEnd/models/franchise_manager.py` — `ScheduleManager.generate_schedule`, `FranchiseManager.initialize_season`
- `BackEnd/tournament/franchise_tournament.py` — conference brackets expect 8 teams each
- FE conference labels in `franchise-command-center.js` (`A1`…`H2`)

Adding a free-floating 129th team breaks schedule + EOS. Editing conference membership without a full league editor is the same class of risk.

### Identity split (universal seed → franchise clone)

| Layer | Collection | Role |
|---|---|---|
| Universal seed | `teams` (+ `players`) | Canonical ObjectIds, conference/region, base prestige, colors, names |
| Franchise clone | `franchise_team_data` (FTD) | Per-franchise team state: attrs, playbook, recruiting, prestige, ranks |
| Franchise roster | `franchise_players_data` (FPD) | Per-franchise player attrs keyed `(franchise_id, player_id)` |

Init path: `FranchiseManager.initialize_season` loads all core teams, builds schedule, clones FPD for every player, creates one FTD row per team keyed `(franchise_id, team_id ObjectId)`.

User selection today: `POST /franchise/select-team` resolves `team_name` against `db.teams`, then stores both `user_team_id` (display name) and `user_team_object_id` (canonical ObjectId).

### Display / assets are often name-keyed

- `FrontEnd/static/common.js` → `getTeamAssetPath` derives banner/logo/court paths from display name/slug
- Missing custom slugs do **not** gracefully fall back unless we add an explicit policy
- Coach portraits / some FCC maps key off known school names

### Some live paths still read core `teams` for metadata

Examples that prefer core docs over FTD display:

- `franchise_routes._format_team_name_map`
- `franchise_tournament.get_team_conference_region`
- pieces of ATL / community highlight opponent resolution

Useful precedent already preferring FTD: `community_highlights._ftd_team_display` (name + colors).

---

## 3. Design principle for v1

> **Keep the league slot. Swap the program skin + roster.**

1. User picks an existing FTD/team ObjectId to **replace** (v1: own program only).  
2. That ObjectId stays the identity for schedule, games, standings, brackets, recruiting region, CPU playbook groups.  
3. Franchise-scoped overlay stores custom name / mascot / colors / roster.  
4. All UI and public boards resolve **FTD overlay → core fallback**.

This mirrors the multi-franchise lesson: **explicit franchise identity**, never “whatever `find_one({user_id})` returns.”

---

## 4. Proposed data shape (v1)

On the **FTD** for the replaced team (franchise-scoped):

```json
{
  "custom_team": {
    "enabled": true,
    "schema_version": 1,
    "name": "Ajax State",
    "mascot": "Geeks",
    "display_slug": "ajax_state",
    "primary_color": "#1F6FEB",
    "secondary_color": "#F4F7FB",
    "replaced_core_team_id": "<ObjectId string of original slot>",
    "asset_mode": "general",
    "imported_at": "<iso>",
    "source": "manual|csv|json"
  }
}
```

Notes:

- Prefer nesting under `custom_team` so we don’t collide with existing FTD fields that already use `team_name` / colors in some paths.
- `conference` / `region` stay those of the **replaced slot** — not user-editable in v1.
- Roster: replace FPD rows for that `team_id` (and update FTD `player_ids`) rather than inventing a parallel player collection.

Optional later: `custom_team.assets` pointing at uploaded R2 keys (banner, square, court, bg).

---

## 5. Import format (v1 opportunity)

Ship a **downloadable template** before a fancy editor.

**Team sheet (required):** name, mascot, primary_color, secondary_color, optional prestige seed, optional slug.  
**Roster sheet (optional in first cut):** jersey, first/last, year, height/weight, position ratings / attributes within existing clamps.

Validation gates:

- Unique normalized slug **within franchise**
- Hex colors, safe string lengths
- Roster size rules (active 12 / max 15 — match current franchise cut rules)
- Attribute clamps from existing training/player systems (`Tunable_Constants` / player clamps)
- Replaced slot must be a real FTD `team_id` for that franchise
- Reject conference/region overrides in v1

Formats: **JSON first** (easier schema/versioning); CSV as a friendlier second export of the same schema.

---

## 6. Extension points (where code should change)

| Area | Path / hook | v1 work |
|---|---|---|
| Create/update overlay | New franchise-owned API near `franchise_routes.py` | Ownership via `verify_franchise_owned_by_user`; never global `teams` writes |
| Display resolution | New shared helper modeled on `_ftd_team_display` | One function everywhere: FCC, schedule, standings, recruiting, brackets, ATL payloads |
| Roster load | `roster_loader.load_roster` | Accept ObjectId / FTD row; stop requiring core `name` lookup for custom overlays |
| Assets | `getTeamAssetPath` + Team Images doc | `asset_mode: general` until uploads exist |
| Select-team / branding | `franchise-select-team`, FCC paint, auth bar | Show custom name/colors from FTD |
| Geek Points | `franchise_geek_points.geek_points_team_key_for_franchise_user` | Explicit product choice (see §8) |
| Rank / prestige | `franchise_rank_prestige.py` | Mostly FTD-driven already — low risk if prestige seeded carefully |

**Do not touch for v1:** schedule generator topology, EOS bracket constructor, CPU auto-training payload shape, dual-slot cap logic.

---

## 7. Phased plan

### Phase 0 — Product locks (this brief)

- [ ] Confirm **replace-slot** model (not add-a-team).  
- [ ] Confirm v1 target: **user’s own program only** vs any CPU school.  
- [ ] Confirm GP/leaderboard behavior (see §8).  
- [ ] Confirm asset policy: general fallback vs require uploads.  
- [ ] Confirm import: manual form only vs JSON template in the same milestone.

### Phase 1 — Plumbing (no fancy UI)

- [ ] FTD `custom_team` schema + ownership-checked write API.  
- [ ] Shared display resolver; wire FCC + schedule/standings name/color reads.  
- [ ] Asset fallback to `general` for custom slugs.  
- [ ] Dev/admin path to apply overlay without a polished editor.

**Acceptance:** Franchise shows custom name/colors on FCC and in-game chrome; schedule/brackets still run; ObjectIds unchanged.

### Phase 2 — Roster import

- [ ] JSON (then CSV) template + validator.  
- [ ] Replace FPD roster for the slot; recompute position ratings / team totals as needed.  
- [ ] Prestige seed policy (inherit replaced school ± clamp, or import field).

**Acceptance:** User can import a legal 12–15 man roster and play a week without sim crashes.

### Phase 3 — Player-facing editor

- [ ] Mode-select / FCC entry: “Mod this program” (franchise-scoped).  
- [ ] Form for name/mascot/colors + file upload for roster template.  
- [ ] Clear warnings: mid-season remaps, irreversible roster wipe, competitive integrity.

### Phase 4 — Assets + polish

- [ ] Upload banner / square / court (R2), validation, defaults.  
- [ ] Coach portrait policy (generic Sammy vs upload).  
- [ ] ATL / community cards use custom branding consistently.

### Phase 5 — Later / out of scope until demanded

- Replace arbitrary CPU schools (full league paint)  
- Custom conferences / regions / 64-team leagues  
- Sharing / Workshop / cross-account mod packs  
- Editing playbooks as part of “mod” (already exists separately)

---

## 8. Open product decisions

1. **Who can be replaced in v1?** Own program only (recommended) vs any of the 128.  
2. **Geek Points / Titles by team:** keep scoring under the **replaced school’s canonical `team_id`** (simplest, slightly weird labeling), or introduce a franchise-scoped custom key (cleaner, more leaderboard work).  
3. **When can you mod?** Only at franchise create / week 1, or anytime with a hard roster reset warning?  
4. **Second franchise slot:** each slot mods independently (recommended — matches multi-franchise isolation).  
5. **Competitive / alpha stance:** custom teams allowed in community boards, or private-only until assets exist?

**Working defaults if you want to move without more debate:**

| Decision | Default |
|---|---|
| Scope | Replace own program only |
| Timing | Anytime, with explicit “wipe roster / reset branding” confirm |
| GP | Keep replaced school’s canonical GP bucket; show custom name in UI |
| Assets | `general` fallback |
| Isolation | Per franchise slot |

---

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Broken images for unknown slugs | Explicit `asset_mode: general` + FE fallback |
| Name maps still reading core `teams` | One resolver; grep-driven migration of name/color consumers |
| Roster import creates illegal attributes | Reuse existing clamps; reject on validate |
| Mid-season mod desyncs playbooks/scouting | Document wipe; optionally rebuild CPU/user playbook for that team |
| Users expect “add my alma mater as #129” | Product copy: “Replace a program in the 128” |
| Schema drift (region int vs A–H in seed scripts) | Do not accept region from import in v1 |

---

## 10. Suggested next step after this brief

1. Lock §8 defaults (or mark exceptions).  
2. Optional outside-agent pass: competitive UX research (OOTP / FHM / FM custom team import patterns) — **product only**, architecture stays here.  
3. Implement **Phase 1 plumbing** behind a feature flag / alpha gate.  
4. Parallel: draft the JSON schema + example template file in `_documentation_master/projects/` (e.g. `mod_team_template.example.json`).

---

## 11. Key code touch list (when build starts)

| Area | Path |
|---|---|
| Franchise init | `BackEnd/models/franchise_manager.py` |
| Select team | `BackEnd/api/franchise_routes.py` (`select-team`) |
| Roster load | `BackEnd/utils/roster_loader.py` |
| Team id resolve | `BackEnd/utils/team_id_resolver.py` |
| Display precedent | `BackEnd/utils/community_highlights.py` (`_ftd_team_display`) |
| Assets | `FrontEnd/static/common.js` (`getTeamAssetPath`) |
| FCC paint | `FrontEnd/static/franchise-command-center.js` |
| Indexes | `BackEnd/db.py` (`ensure_ftd_index`, `ensure_fpd_index`) |
| GP keys | `BackEnd/utils/franchise_geek_points.py` |

---

## 12. One-line summary

**v1 = franchise-scoped “reskin + optional roster replace” of an existing 128-slot ObjectId — not a new league structure.**
