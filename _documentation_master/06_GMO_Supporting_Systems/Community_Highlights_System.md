# Community Highlights System

Feed for the **Community Highlights** panel on **Mode Select** (`FrontEnd/static/mode-select.html`). Markup already exists: `section.community-highlights-section` → `.community-highlights-panel` → `.community-highlights-body` (currently “Coming Soon”; implementation replaces that placeholder).

---

## Product rules (agreed)

| Topic | Spec |
|--------|------|
| **Audience** | **Universal** — every signed-in user sees the same feed (everyone’s entries). |
| **Retention** | **20 rows maximum.** New rows insert at the top; when a 21st is added, **delete** the overflow from persistence so data does not grow beyond the visible list. |
| **When to create an entry** | **Only after franchise `POST /franchise/complete-week/phase-b` completes successfully** — not after phase A. |
| **Display name** | `username` from the user’s MongoDB `users` document (email local-part when unset), same idea as the alpha leaderboard. **Render the username in bold** everywhere it appears in highlight copy. |
| **National rank** | User team’s **`natl_rank` from FTD** (`franchise_team_data`) **after** phase B persistence, with caveats below. |
| **Geek Points (display)** | **Net GP earned from that completed user game only** — not season total, not lifetime account total. |
| **Standard game copy** | One summary line: beat / lost, **scores**, **regular-season W–L** (weeks 1–26 results only), and national rank (`#--` when rank is missing or skipped). |

---

## `natl_rank` after Phase B (source of truth)

Phase B runs **`_apply_regular_season_rank_prestige_updates`** inside **`_complete_week_finish_cpu_and_persist`** (`BackEnd/api/franchise_routes.py`). When that helper runs, it recomputes ranks and **`$set`s `natl_rank` on FTD for teams in that franchise** for the ranking pass.

**Caveats (do not assume rank always updates every phase B):**

- **Regular season weeks only:** the helper **returns without updating** if the completed week is **outside weeks 1–26** (EOS / playoff weeks use a different path).
- **Franchise rank/prestige v2:** if **`use_franchise_rank_prestige_v2`** is false for that franchise doc, the helper **exits early** and does not refresh `natl_rank`.
- **Idempotency:** if rank/prestige was **already applied** for that week, the helper **skips**.

**Implementation fallback when `natl_rank` is missing or skipped:** e.g. show `#--`, omit the rank clause, or last-known rank — **decide in build** and keep copy consistent.

---

## Display rules

- **Order:** Every new entry is a **new row at the top**; existing rows shift down.
- **Standard row (horizontal):**
  - **Left (main copy):** **`{user_name}` (bold)**, coaching `{user_team_name}`, **beat** (win) / **lost to** (loss) `{opponent_team_name}` **`{user_score}`-`{opponent_score}`**. `{user_team_name}` is now **`{user_team_record}`** (regular-season wins-losses, e.g. `5-3`) **& ranked** **`{rank_label}`** (e.g. `#7` or `#--`) in the nation. Same sentence when scores are omitted (older payloads): beat/lost line without the numeric score pair, then record and rank. Reserve width so the GP column does not collide.
  - **Right:** `+/- {net GP for that game}` — **positive: bold gold**; **negative: bold red**. If the left block wraps to two lines, **vertically center** the GP block in the row.
  - **Persistence:** Each stored standard entry includes **`user_team_record`** (string `W-L`) computed at flush from franchise `results` weeks 1–26 via the same standings helper used for the conference RS highlight `Record:` line.

---

## Special display rules

- These **instances** occupy **two text rows** that read as **one card**: shared border and background (no “split” border between announcement and details).
- **Row 1:** Announcement (`announcement_line`).
- **Row 2:** Details (`details_line`).
- **Row chrome:** Conference **regular-season title**, **conference tournament win**, and **regional tournament win** use the **same team-gradient treatment** as normal highlights (`variant: standard_row`). **National tournament win** uses **`variant: national_gold`** (premium gold styling on Mode Select).

- If the user finishes the regular season as **#1 seed in their conference** (conference regular-season champion):
  - **Announcement:** "`{user_name}`, coaching {user team name}, wins the Conference `{n}` regular season title."
  - **Details:** "Record: {user record} -- Top Scorer: {name}: {PPG} -- Top Rebounder: {name}: {RPG} -- Top Defender: {name}: {DEF%} or — if no qualifier."
  - **Top Defender:** qualifies only with **≥ 156 DEFA** for the season (26 games × 6 DEFA per game).

- If the user wins a **conference**, **regional**, or **national** tournament final:
  - **Announcement:** e.g. wins the Conference `{n}` Tournament; wins the `{region}` Regional Tournament; wins the National Tournament (see `BackEnd/utils/community_highlights.py`).
  - **Details:** "Championship Game: {user team}: {score} - {opponent}: {score} -- POTG: …" when box score is available.

---

## Row chrome / design

- **Goal:** Premium feel similar to the **Franchise** card on Mode Select (gradient, **semi-opaque overlay** so background does not overpower text, **inner content area** for type).
- **Fill:** **User team primary / secondary** as the row background — **not** tiled `banner_primary` — for simpler layout and consistent branding. **National champion** row adds the gold variant above. Optional later: light watermark or texture.

---

## New entry criteria (detail)

- **Trigger:** User finishes their **franchise** week for the human-played game: **phase B** has run and DB state (including rank/GP side effects for that flow) is committed.
- **Content:** Templates above; standard rows include **scores**; special rows add **announcement + details** and optional POTG on championship details.

---

## References (implementation)

- Mode Select shell: `FrontEnd/static/mode-select.html` (`community-highlights-section`); rendering: `FrontEnd/static/mode-select.js` (`renderCommunityHighlights`), styles: `FrontEnd/static/mode-select.css`.
- Pending + flush: `BackEnd/utils/community_highlights.py` (`build_community_highlight_pending`, `flush_community_highlight_pending_after_week`, `_build_standard_entry` / `_user_regular_season_record` for **`user_team_record`** on standard rows).
- Phase A wiring: `BackEnd/api/franchise_routes.py` — `_complete_week_process_user_game_block` (passes `game_id`, `eos_game_meta` into pending), `complete_week_phase_a`, monolithic `complete_week`.
- Phase B / rank: `BackEnd/api/franchise_routes.py` — `_complete_week_finish_cpu_and_persist`, `_apply_regular_season_rank_prestige_updates`.
- FTD: `franchise_team_data_collection` — `natl_rank`.
- Geek Points for franchise games: win/loss helpers during complete-week; **net delta for that game** is stored on the pending payload and on each feed entry.
