# Community Highlights System

Feed for the **Community Highlights** panel on **Mode Select** (`FrontEnd/static/mode-select.html`). Markup already exists: `section.community-highlights-section` → `.community-highlights-panel` → `.community-highlights-body` (currently “Coming Soon”; implementation replaces that placeholder).

---

## Product rules (agreed)

| Topic | Spec |
|--------|------|
| **Audience** | **Universal** — every signed-in user sees the same feed (everyone’s entries). |
| **Retention** | **20 rows maximum.** New rows insert at the top; when a 21st is added, **delete** the overflow from persistence so data does not grow beyond the visible list. |
| **When to create an entry** | **Only after franchise `POST /franchise/complete-week/phase-b` completes successfully** — not after phase A. |
| **Display name** | `user_name` from the user’s MongoDB `users` document. |
| **National rank** | User team’s **`natl_rank` from FTD** (`franchise_team_data`) **after** phase B persistence, with caveats below. |
| **Geek Points (display)** | **Net GP earned from that completed user game only** — not season total, not lifetime account total. |
| **V1 copy** | Single summary line per row (no box-score “highlights” stats in v1). |

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
- **Row layout (horizontal):**
  - **Left (main copy):** `{user_name}`, coaching `{user_team_name}` **beat** (win) / **lost to** (loss) `{opponent_team_name}`. `{user_team_name}` is now ranked **#{natl_rank}** in the nation. Reserve width so the GP column does not collide.
  - **Right:** `+/- {net GP for that game}` — **positive: bold gold**; **negative: bold red**. If the left block wraps to two lines, **vertically center** the GP block in the row.

---

## Row chrome / design (v1)

- **Goal:** Premium feel similar to the **Franchise** card on Mode Select (gradient, **semi-opaque overlay** so background does not overpower text, **inner content area** for type).
- **V1 fill:** Prefer **user team primary color** (and subtle secondary if needed) as the row background — **not** tiled `banner_primary` — for simpler layout and consistent branding. Optional later: light watermark or texture.

---

## New entry criteria (detail)

- **Trigger:** User finishes their **franchise** week for the human-played game: **phase B** has run and DB state (including rank/GP side effects for that flow) is committed.
- **Content:** Template line above; **no extra stat lines in v1**.

---

## References (implementation)

- Mode Select shell: `FrontEnd/static/mode-select.html` (`community-highlights-section`).
- Phase B / rank: `BackEnd/api/franchise_routes.py` — `_complete_week_finish_cpu_and_persist`, `_apply_regular_season_rank_prestige_updates`.
- FTD: `franchise_team_data_collection` — `natl_rank`.
- Geek Points for franchise games: existing win/loss (and related) helpers invoked during complete-week / phase B — **net delta for that game** must be computed or read for the highlight line (exact hook TBD in code).
