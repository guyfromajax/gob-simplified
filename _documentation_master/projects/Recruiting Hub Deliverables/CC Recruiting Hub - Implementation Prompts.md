# Recruiting Hub Redesign — C+C Implementation Prompts

**Recommendation: a sequenced series, not one master prompt.** Reasons: (1) the work is large and stateful; (2) it includes a backend change (invite-loop decoupling) that shouldn't ride inside a UI prompt; (3) it's spine-first — the pool + lean object + phase strip must exist before the action layers hang off them. Implement and verify in order. **Prompt 0** establishes the shared foundation; **Prompts 1–5** map to D1–D5.

All prompts reference the approved HTML mockups in this project as the visual/behavioral source of truth. Match them; don't reinterpret. The hub **takes over `recruiting.html`'s role and URL**; `recruiting-invites.html`, `recruiting-orders.html`, and `recruiting-results.html` are deleted/redirected. The two FCC summary surfaces keep linking to `recruiting.html` (now the hub). **Prompt 0** establishes the shared foundation; **Prompts 1–6** map to D1–D5 plus the Training Report callout.

---

## Prompt 0 — Foundation (tokens, data, spine components)

**Goal:** Stand up the shared building blocks every later prompt uses. No full screens yet.

**Source:** `recruiting-spine.css`, `recruiting-spine-data.js`, `spine-lean.jsx`, `spine-phase.jsx`, `spine-pool.jsx`, and the GOB Style Guide (`Styleguide_updated.md`).

**Build:**
1. **Tokens** — base `#0b0d14`, navy `#27408E`, orange `#F79420` (non-gating actions), green `#34EC27` (gating + positive-semantic ONLY), gold `#FFD700`, light-blue `#4A90D9`. Fonts: Bebas Neue Pro (display) / Inter (data). **Recruit RT scale:** 0–29 red `#ff6d6d`, 30–39 gold `#FFD700`, 40–49 green `#34EC27`, 50+ light-blue `#4A90D9`.
2. **Recruit data model** — each recruit carries: name, pos, region (A–H), **year (new, sits after POS)**, archetype, HT, WT, 12 attributes (SC SH ID OD PS BH RB AG ST ND IQ FT), RT, and a **lean list**: ordered array of up to 3 slots, each `{team}` or `{open:true}`; derive `yourRank` (1/2/3 or none) and `leansToUser`; a `locked` flag for loyal/hard targets.
3. **Lean object = the Ranked Ladder** (`spine-lean.jsx`, variant B is the chosen one). Up to 3 ordered slots showing rank + team token. **Your team's slot glows green when #1, amber when on-list (#2–3); rival slots neutral; open slots dashed; a lock badge on a rival's #1 when the recruit is loyal.** This replaces the legacy comma-separated lean text cell everywhere it appears. Odds language for reference: #1 ≈ 8×, #2 ≈ 4×, #3 ≈ 2×, unlisted ≈ 1×.
4. **Phase strip** (`spine-phase.jsx`). Compact "Week NN · <Phase>" indicator that **expands to a season timeline**. Four phases: **Passive** (wks 1–19 & 27–34; the 27–34 stretch labeled **Tournament** on the timeline), **Invite Season** (20–26), **Signing Day** (35), **Results** (36). Includes the current-week "Now" marker and an orientation line ("Why can't I invite yet? It's Week 12 — invites begin Week 20"). **The phase is chosen by the calendar; the user never picks it.**
5. **Persistent "Recruit Pool" header anchor** — a header control present in **every** phase/state that returns the user to the pool (dismisses any overlay + scrolls to the pool). Build once here; every screen includes it.

**Acceptance:** lean ladder renders all states (you #1 / #2 / #3 / open slot / all-open / not-listed / loyal-locked / single / none); RT colors match the recruit scale; phase strip renders all four phases + expanded timeline; anchor is present and scrolls to the pool.

---

## Prompt 1 — D1: The Spine (pool + lean object + phase strip)

**Goal:** The persistent hub shell present in every phase.

**Source:** `Recruiting Hub Spine.html` (+ `spine-pool.jsx`).

**Build:** The **pool** — ~300 recruits grouped into **collapsible region sections (A–H)**, RT-descending default, **sortable headers**, search + region + "leaning to me" filters. Columns: Name (+archetype, new-lean/lost flags), POS, **Year**, HT, WT, the 12 attributes, RT (colored), and the **lean object**. Layout frame: **pool as the persistent left/main column, an action dock docked right** — empty in Passive. Provide the **condensed pool** variant (attributes collapse) for when a right dock is active, so the split holds down to a **1280px** laptop. Include the passive-phase **story strip** ("new leans this week / who dropped you") — read-only, no actions.

**Acceptance:** region collapse works; sort/filter work; condensed variant drops attributes and fits beside a 320px dock at 1280px; passive state shows no dock.

---

## Prompt 2 — D2: Invite Dock (Phase 2, wks 20–26)

**Goal:** Merge the two forked "Recruiting Orders" pages into one docked board.

**Source:** `Recruiting Hub Invite Dock.html` (+ `recruiting-dock.css`, `spine-dock.jsx`).

**Build:** Pool left (condensed), **invite board docked right**. The board is a **stack-ranked priority list of up to 20**; each week (20–26) the hub sends **one invite** to the top-ranked available recruit — **7 total**. Add a recruit via **+** in the pool (the + becomes a rank badge); **drag to reorder**; remove. Board header shows: count / 20, a **weekly tracker** (W20–26 pips: elapsed / current / upcoming), a **"leaning to you" badge**, and a **position breakdown**. Each slot shows the recruit's **your-standing chip** (#1/#2/#3) and a **lean-list fill indicator (0–3 circles)** = how many of his 3 lean slots teams already hold. No per-slot "sent/week" state (invites can repeat). **Save Board** = orange non-gating + success toast (per style guide).

**⚠ Backend item (call out to eng):** the hub **owns the invite loop end to end**. Today invites are saved on the recruiting page but executed from the Training page's "Submit Training." **Decouple this** so the hub ranks, saves, AND runs invites. This is the one backend-touching change in the redesign.

**Acceptance:** add/remove/drag-reorder all work; weekly tracker + badges + breakdown update live; Save shows toast; no cross-page coupling remains.

---

## Prompt 3 — D3: Signing Board (Signing Day, wk 35)

**Goal:** The payoff — one working surface, budget + binding promises.

**Source:** `Recruiting Hub Signing Board.html` (+ `recruiting-signing.css`, `spine-signing.jsx`).

**Build:** **Single surface** — the **Recruit Pool table is the working surface**: each row has an inline **points stepper**, a binary **Playing Time** promise toggle (checked = **Binding**), and a live **Sign Odds** read. A **slim right rail** ("Your Orders") holds the **50-point budget** (remaining + bar), a **promises** count (secondary to the budget number), and a **running list of every funded recruit** (points · odds, with remove + click-to-jump). **Auto-fill-then-adjust:** the pool pre-loads recruits leaning to you, top targets pre-funded. Pool keeps region filter + RT sort. **No recruit cap** — funding is bound only by the 50 points. **Submit Orders** = green **gating** (advances the season) + toast.
- **Sign-odds bands (placeholder heuristic — swap in real signing math):** Long shot → Slim → In the Mix → Strong. Reference scoring: base by standing (#1 ~48, #2 ~34, #3 ~26, open ~20, none ~16, elsewhere ~14, loyal ~8) + points×2.2 + 18 if Playing Time promised, clamped 4–99; bands ≥72 Strong, ≥48 In the Mix, ≥26 Slim, else Long shot.
- **Playing Time is the only promise type** (no tiers). Binding: honor the minutes or program standing suffers.

**Acceptance:** budget enforced (steppers stop at 0 remaining); promise toggles binding; odds recompute live; funded rail add/remove/jump work; Submit is green gating.

---

## Prompt 4 — D4: Results & Signed (states, not a page)

**Goal:** Results as **states of the hub**, reached without leaving.

**Source:** `Recruiting Hub Results.html` (+ `recruiting-results.css`, `spine-results.jsx`).

**Build:** Two states over the same hub:
1. **Weekly-visit results** (after each wk 20–26 processes) — a **dismissible panel that overlays the pool** (your visit + what changed + contested region activity). The pool remains the base layer beneath; "Back to hub" / the Recruit Pool anchor dismisses it.
2. **Week-36 final signings** — the pool's terminal state: same list, the lean column replaced by a **"Signed with"** column + Signed/Lost outcome, plus a summary (targets won / lost / leaned). This mirrors today's existing wk-36 results-mode switch on `recruiting.html`.

**Not a route.** No "Results page." The demo file's top toggle is a review affordance only — build these as calendar-driven hub states.

**Acceptance:** weekly panel overlays a live pool and dismisses to it; wk-36 renders the signed pool; no separate route is added.

---

## Prompt 5 — D5: Consistency sweep (tertiary surfaces)

**Goal:** Make every place recruit info appears read as one system.

**Sources:** `FCC Recruits Tab Update.html`, `FCC Recruiting Cards Update.html`, edited `Recruiting.html` (tutorial).

**Build:**
1. **FCC Recruits tab** — replace the comma-separated lean text cell with the **lean object (ranked ladder + your standing)**; **add the Year column after POS**; keep the 12 attributes and RT coloring.
2. **FCC Home card + Coach's Office card** — add a compact **standing marker** (green #1 dot / amber on-list dot + rank chip) per row; color **RT** on the recruit scale; make the **footnote phase-aware** (matches the phase strip: "Passive — leans come to you" / "Invite Season · Wk 22 · 3 of 7 sent" / "Signing Day · 50 points"). Keep the New-Leans "New" badge.
3. **Recruiting tutorial** (`tutorial-recruiting.html` in repo) — rename **"Recruiting Day" → "Signing Day"** throughout; fix stale mechanics: **50-point budget** (not 20) and **no 20-recruit cap** (bound by points); the ladder/RT explainers already match — keep them.

**Acceptance:** no comma-separated lean text cells remain on the FCC surfaces; Year present on full recruit displays; all footnotes/labels say Signing Day and reflect the current phase.

---

## Prompt 6 — Training Report recent-leans callout

**Goal:** Bring the Training Report's recruit callout into the same system. (This surface lives only in the repo — no mockup here; follow the ladder vocabulary from Prompt 0 / the hub pool exactly.)

**Source:** repo `training-report.html`; visual reference = the lean ladder in `spine-lean.jsx` / `Recruiting Hub Spine.html`.

**Build:** The small callout that surfaces recruits who **most recently added our team to their lean list**. Update it to: (1) render each recruit's lean as the **ranked ladder** — our team's slot highlighted (green when #1, amber when on-list #2–3), rival slots neutral, open slots dashed — instead of any text/among-list string; (2) color **RT** on the recruit scale (0–29 red, 30–39 gold, 40–49 green, 50+ light-blue); (3) if the callout shows any phase/verb, use the hub's language and the **Signing Day** name (never "Recruiting Day"). Keep it **read-only** and **link through to the hub**. Reuse the ladder markup/CSS from the hub pool so the two surfaces are byte-for-byte identical.

**Acceptance:** no text lean strings remain; the ladder is identical to the hub's; RT is colored on the recruit scale; the callout links into the hub and stays read-only.

---

## Global acceptance criteria (all prompts)
- The **persistent Recruit Pool anchor** is present and functional in every phase/state.
- **Green is used only** for gating actions and positive-semantic data (your-#1 / signed). Orange for non-gating saves.
- The lean object is **identical** across hub, FCC tab, FCC cards, and training report.
- The hub is **phase-aware by calendar** — the user never chooses the phase.
- Holds down to **1280px**; the pool↔dock split degrades gracefully.
