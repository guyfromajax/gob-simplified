# Player Image Generator — Work Plan

**Purpose:** Produce ~1,440 new player portrait masters for conferences 2–16 (15 conferences × 8 teams × 12 players) that match the visual universe of the existing Conference 1 set — without the original illustrator.

**Status:** Phase A pilot — **Chapel Hill** (Conference 2). Tooling choice still open; team brief + roster locked below.

**Owner / QC:** Jamie (reject batches that fail thumbnail + side-by-side checks against Conf1).

**Related docs:**
- [`00_Operations/Player_Image_System.md`](../00_Operations/Player_Image_System.md) — R2 delivery, resolver, upload runbook
- [`projects/image_migration.md`](image_migration.md) — storage architecture; future layered uniform pipeline (not built)
- [`scripts/upload_player_images_to_r2.py`](../../scripts/upload_player_images_to_r2.py) — idempotent upload to R2

---

## Scope

| Item | Count | Notes |
|------|------:|-------|
| Conferences to cover | 15 | Conf1 (8 teams) already has masters in R2 |
| Teams | 120 | 15 × 8 |
| Players per team | 12 | Franchise roster size |
| **New portrait masters** | **1,440** | One finished PNG per player `_id` |
| Uniform designs | 120 | One locked jersey template per team (colors, trim, wordmark, logo placement) |

**Existing assets to leverage:** team `primary_color` / `secondary_color`, mascots, logos, court images (all teams). Conf1 portraits on R2 as **style reference only**.

---

## Target master spec (must match Conf1 + pipeline)

Derived from live Conf1 masters on `assets.geekedoutgames.com` and [`Player_Image_System.md`](../00_Operations/Player_Image_System.md).

| Property | Value |
|----------|--------|
| Format | PNG, **RGBA** (transparent background) |
| Dimensions | **3530 × 3412** (nearly square; match Conf1 framing) |
| File size | ~3–7 MB typical (full-res master; CDN serves 128/256/512 transforms) |
| Filename | `<player_uuid>.png` (player document `_id`) |
| R2 key | `players/master/<player_uuid>.png` |
| Framing | Front-facing bust, shoulders up, soft frontal lighting |
| Style | Illustrated sports portrait (semi-realistic, “same game as Conf1”) — **not** photo, not flat cartoon |

**Upload path:** stage → `assets_staging/players/` → `./venv/bin/python3 scripts/upload_player_images_to_r2.py`

---

## Conf1 reference set (style bible inputs)

Conf1 was created by a human artist in Photoshop. AI must approximate that **franchise art bible**, not generic “sports headshot.”

**Curate 30–50 Conf1 masters for training / `--sref`:**
- Diverse faces (skin tone, age, hair, facial hair, build)
- Same camera angle and crop on every pick
- Mix of teams (all 8 Conf1 teams represented)
- Exclude outliers (weird crops, artifacts, off-style experiments)

**Style elements to lock (document during Phase A):**
- Head/shoulder crop and centering
- Expression range (Conf1 tends friendly/neutral — confirm from refs)
- Skin rendering (smooth gradients, not photographic pore detail)
- Jersey integration (wordmark at bottom of frame; trim/piping pattern)
- Edge treatment on alpha cutout (no white halos)

Public sample URL pattern:
`https://assets.geekedoutgames.com/players/master/<uuid>.png`

Manifest of uploaded Conf1 UUIDs: [`scripts/r2_upload_manifest.csv`](../../scripts/r2_upload_manifest.csv)

---

## Constraints

- **Original artist unavailable** (cost-prohibitive).
- **Jamie = sole QC** — workflow must favor volume of “almost right” + fast reject, not perfect first generation.
- **AI weakness:** team wordmarks, logos, and exact typography — plan to **composite outside the generator** (Photoshop/Figma templates per team).
- **Do not** rely on raw text-to-image alone (ChatGPT/DALL·E without heavy style reference) — too much drift from Conf1.

---

## Uniform workflow — white base + identical team composite (**locked for production**)

**Decision:** Generate **face/bust only** on a **plain white tank** (no team colors, no text, no logos). Apply **one identical uniform composite per team** in Photoshop/Figma to all 12 players. Do **not** prompt team jersey colors into the AI generator for final masters.

### Why

| Problem with team colors in AI prompt | White base + composite fix |
|---------------------------------------|----------------------------|
| 12 slightly different jerseys per roster | One PSD layer — pixel-identical wordmark, trim, logo placement |
| AI garbles **SKY**, logos, typography | Wordmark/logo built once in Photoshop |
| Color drift between players (`#87b5e6` vs washed-out blue) | Exact hex from team DB in template |

Conf1 masters were **hand-painted with jersey in the image** — they were not built this way. Conf2+ composite may read *slightly* different from Conf1 at full-res but should match at **256px roster thumbnail** if bust style is locked. Acceptable for v1; optional Conf1 retrofit later.

### Per-team workflow (repeat × 120 teams)

```
1. Build uniform template (Phase B)     →  one PSD at 3530×3412
2. Generate 12 white-tank busts (AI)    →  variable face/age/build only
3. Composite same uniform on each bust  →  identical layer position/scale × 12
4. Post-process + export                →  alpha cleanup, <uuid>.png
5. QC at 256px                          →  regen bust if neck/collar misaligns
```

**Rule:** If the composite looks “pasted,” **regenerate the bust** (same prompt skeleton). Do not hand-tweak uniform position per player except for rare outlier crops.

### Layer stack (Photoshop)

Bottom → top:

1. **AI bust** — white tank, transparent background (RGBA from generator + alpha cleanup)
2. **Uniform overlay** — sky blue body, navy trim, optional chest logo (from banner crop)
3. **Wordmark** — **SKY** (or team mascot text) at bottom of frame, Conf1-style block letters
4. **Edge pass** — mask neck/shoulders so jersey sits naturally; no white halos

**Alternative layer order:** bust on bottom, full uniform PNG (including neck trim) on top with face cutout masked through — whichever matches Conf1 neck integration faster in pilot. Lock one approach on Stanley Keith, then reuse.

### Uniform development (three phases)

Per team, develop the jersey **before** batching faces:

| Phase | What | Output |
|-------|------|--------|
| **1 — Design** | Build uniform on blank 3530×3412 canvas **or** over a Conf1 portrait for proportions (no final player face required) | PSD with `UNIFORM_OVERLAY` layers: body color, trim, wordmark, optional logo |
| **2 — Fit (Stanley)** | Generate Stanley’s **white-tank** bust → drop overlay → iterate neck/collar/wordmark placement | Approved composite; **locked** overlay position + scale |
| **3 — Batch** | Generate 11 more white-tank busts → apply **identical** overlay → export all 12 | `<uuid>.png` per roster row |

**Gate:** Do not generate players 2–12 until Phase 2 passes QC at **256px** next to Conf1.

### Bust framing & overlay alignment

**Torsos do not need to be pixel-identical.** Shoulder width, neck thickness, and build will vary by player (guard vs center). One locked overlay still works when **framing** stays consistent — not when every bust is the same size.

| Must stay consistent (via fixed prompt + Xenon style ref) | Can vary |
|-------------------------------------------------------------|----------|
| Crop: bust, shoulders up, centered | Shoulder width, muscular vs lean build |
| Head scale relative to frame (neck/collar lands in same zone) | Neck thickness |
| Pose: front-facing, neutral | Height/weight read in face and shoulders |
| Aspect ratio: 1:1 → upscale to 3530×3412 | — |

The **plain white tank** in the prompt gives a consistent neckline anchor — misaligned busts are easier to spot before compositing.

**When the overlay breaks:** bust is zoomed differently, tilted, or cropped higher/lower than Stanley → **regenerate that bust** (same prompt skeleton). Do **not** resize or reposition `UNIFORM_OVERLAY` per player except rare outliers (prefer regen).

**Photoshop guide layer (recommended after Stanley is approved):**

1. Keep Stanley’s approved bust on a layer at **~30% opacity**, labeled `GUIDE — do not export`.
2. Place each new white-tank bust under the locked `UNIFORM_OVERLAY` and align to the guide — head size and neck position should match within a small tolerance.
3. If a bust doesn’t land on the guide, treat it as a bad generation, not a uniform adjustment.

### What AI generates vs what Photoshop owns

| Step | Tool | Notes |
|------|------|-------|
| Face, skin, hair, expression, build | **Midjourney** (pilot) / Astria or Flux (scale) | Xenon Fletcher style ref; `--sw 100`, 1:1 |
| Plain white tank, no graphics | Same AI tool | In **fixed prompt block** — see below |
| Team colors, trim, wordmark, logo | **Photoshop / Figma** | Not Midjourney, not Astria, not Flux |
| Alpha cleanup, export 3530×3412 | Photoshop or `rembg` + manual | Match Conf1 edge treatment |

**No AI tool produces identical uniforms across 12 faces.** Tool choice affects **portrait style consistency**, not uniform fidelity. Best combo: **MJ or Astria for faces** + **one PSD per team** for jerseys.

### White-tank prompt block (fixed — prepend to every generation)

Use this **instead of** team color hints in the AI prompt:

```
wearing plain white basketball tank top, no logos, no text, no team colors,
simple white jersey with neutral collar
```

Full fixed block (style + jersey):

```
Front-facing basketball player portrait, bust shoulders up, centered composition,
soft frontal lighting, illustrated semi-realistic sports game art style,
smooth skin gradients, friendly neutral expression, transparent background,
wearing plain white basketball tank top, no logos, no text, no team colors,
simple white jersey with neutral collar,
no watermark, college basketball player age appearance
```

**Remove** lines like `wearing sky blue #87b5e6 basketball tank jersey` from production prompts once the uniform template is approved.

### Pilot exception

Stanley Keith test generations may have used team colors in-prompt for style exploration. **Chapel Hill players 2–12:** white base only → composite Chapel Hill template.

---

## Recommended tooling (to be confirmed in pilot)

### Primary production path (scale)

1. **Train a “GOB portrait style” model** on curated Conf1 masters (one-time setup):
   - **Astria** or **Krea** (low ML overhead), or
   - **Flux LoRA** via fal.ai / Replicate (more control, more setup)
2. **Generate** with trained model or **Flux Kontext** (reference-guided) per player.
3. **Composite** team uniform template (120 PSDs/Figma files) — logo + wordmark applied outside AI.
4. **Post-process** — crop to spec, alpha cleanup, export PNG.
5. **Upload** via existing R2 script.

### Pilot path (one team, this week)

**Midjourney `--sref`** using 2–3 Conf1 portrait URLs as style reference. Fast way to compare “same universe?” before committing to LoRA training.

Example skeleton (prompt details TBD):
```
[player description], basketball player portrait bust shoulders up,
soft frontal lighting, illustrated sports game style, transparent background
--sref [conf1-url] --sw 100 --ar 1:1
```

### Explicitly deprioritized

| Tool | Why |
|------|-----|
| Plain ChatGPT / DALL·E text-only | Style drift; poor logo/wordmark fidelity |
| Full hand-paint at 1,440 | Cost/time (original artist path) |

**Tooling choice is an open decision** — resolved after Phase A pilot compares Midjourney `--sref` vs trained Flux/Astria on one team.

---

## Production phases

### Phase A — Style lock (1 team, ~12 portraits)

**Goal:** Pick production generator; reject if Conf1 + new portraits don’t read as one product at **256px** (roster / set-lineup thumbnail size).

| Step | Output |
|------|--------|
| Curate Conf1 reference set | 30–50 URLs / local copies for training or `--sref` |
| Run 3-way pilot (optional) | Same 12-player brief → Midjourney `--sref` vs Astria/LoRA vs Flux Kontext |
| Side-by-side QC | Conf1 vs pilot in roster UI mock or browser at 256px |
| **Gate** | Lock tool + prompt skeleton before Phase B |

### Phase B — Uniform template (per team)

**Goal:** One locked jersey design per team before generating 12 faces.

| Step | Output |
|------|--------|
| Pull team colors, mascot, logo from DB / static assets | Brief per team (hex, logo file path) |
| Build template | PSD or Figma: jersey shape, trim, color blocks, wordmark slot, logo slot |
| Optional outsource | Freelancer builds 120 templates only (cheaper than full illustration) |
| **Gate** | Template approved before any player batch for that team |

### Phase C — Team batch (12 players)

**Goal:** 12 approved masters per team.

| Step | Output |
|------|--------|
| Fixed prompt skeleton | Same framing/lighting/style + **white tank** every time |
| Variable per player | Face, skin tone, hair, age vibe, build (from roster if available) |
| Variable per team | **Uniform template only** (composite in Photoshop — not in AI prompt) |
| Generate 12 busts → composite **same** uniform layer → post | 12 PNGs |
| **Gate** | Jamie approves 12/12 before next team |

**Batch order:** one conference at a time (8 teams × 12 = **96 portraits per conference**) to reduce uniform context-switching.

### Phase D — Post-process + upload

| Step | Action |
|------|--------|
| Crop / frame | 3530×3412, bust centered like Conf1 |
| Alpha | Remove halos (`rembg` or Photoshop) |
| Rename | `<player_uuid>.png` |
| Stage | `assets_staging/players/` |
| Upload | `upload_player_images_to_r2.py` (dry-run first) |
| Spot check | 3 random players per team in live roster on staging |

---

## QC checklist (reject if any fail)

Review at **256px width** (primary) and full-res (edge/alpha).

- [ ] Same illustration family as Conf1 (not photo-real, not anime, not stock “AI portrait”)
- [ ] Correct bust framing (front-facing, shoulders visible, similar crop to Conf1)
- [ ] Team jersey colors match `primary_color` / `secondary_color`
- [ ] Wordmark / logo placement matches team template (legible, not AI-garbled text)
- [ ] Clean transparent background (no white fringe, no leftover studio backdrop)
- [ ] No visible AI artifacts (extra fingers, melted ears, asymmetric eyes, neck seams)
- [ ] Sits believably in roster grid next to Conf1 players without looking “imported”

**Reject policy:** Regenerate individual failures; don’t advance team batch until 12/12 pass.

---

---

## Phase A pilot — Chapel Hill (Conference 2)

**Why this team:** Conference 2, high prestige (659), distinct palette (sky blue + navy), abstract mascot (Sky). No existing player portraits — clean slate for tooling comparison.

### Team identity

| Field | Value |
|-------|--------|
| Name | Chapel Hill |
| Mascot | Sky |
| `team_id` | `CHAPEL_HILL` |
| Conference | 2 (Region A) |
| Primary color | `#87b5e6` (sky blue) |
| Secondary color | `#1e2f5b` (navy) |
| Prestige | 659 |
| Source | [`teams/128_teams.txt`](../../teams/128_teams.txt) row 12 |

### Static assets (repo)

| Asset | Path | Status |
|-------|------|--------|
| Banner (wordmark + mascot mark) | `FrontEnd/static/images/teams/chapel_hill/chapel_hill_banner_primary.jpg` | Present |
| Court | `FrontEnd/static/images/teams/chapel_hill/chapel_hill_court.jpg` | Present |
| Square logo | `FrontEnd/static/images/teams/chapel_hill/chapel_hill_logo_square.png` | **Missing** — crop mark from banner or run logo pipeline (`tmp/team-logo-pipeline/team-logo-manifest.json` has prompts) |
| Background | `FrontEnd/static/images/teams/chapel_hill/chapel_hill_background.png` | **Missing** |

Logo/mascot creative reference: [`tmp/team-logo-pipeline/team-logo-manifest.json`](../../tmp/team-logo-pipeline/team-logo-manifest.json) → `team_id: CHAPEL_HILL` (sky-inspired symbolic mark, not a creature mascot).

### Uniform template brief (Phase B — lock before batch QC)

Match Conf1 **visual result**: team jersey + wordmark visible at bottom of frame (see Four Corners “HARVEST” on Conf1 masters). **Build method for Conf2+:** composite onto white-tank AI busts — see [Uniform workflow](#uniform-workflow--white-base--identical-team-composite-locked-for-production).

| Element | Chapel Hill spec |
|---------|------------------|
| Jersey body | `#87b5e6` (sky blue tank) |
| Trim / piping | `#1e2f5b` (navy) at neck and armholes |
| Bottom wordmark | **SKY** — bold collegiate block letters, navy fill + subtle outline (Photoshop only; never AI text) |
| Logo placement | Small sky mark optional on chest — crop from banner, not AI-generated |
| Style | Same tank cut and proportions as Conf1 portraits |

**Deliverable:** one PSD/Figma file at **3530×3412**, filename e.g. `chapel_hill_uniform_composite.psd`:

- Uniform + wordmark + optional logo on dedicated layers (grouped as `UNIFORM_OVERLAY`)
- Test composite on **Stanley Keith** white-tank bust before generating players 2–12
- Same `UNIFORM_OVERLAY` position/scale for all 12 exports — no per-player uniform edits

**Gate:** Jamie approves template on one test bust → then run 12-player batch.

### Roster — 12 players (UUID = export filename)

Pulled from `gob` / `gob-staging` (`team: "Chapel Hill"`), 2026-07-05.

| Jersey | Name | `_id` (filename) | Year | Ht | Wt |
|-------:|------|------------------|------|---:|---:|
| 4 | Stanley Keith | `86b911a5-c022-4041-aefd-175a0e1f2acf` | sophomore | 73 | 206 |
| 10 | Landon Turley | `ac26dbe2-e590-49aa-9bde-745584e548f9` | junior | 70 | 167 |
| 11 | Brice Monroe Jr | `f8b7f7b5-bd62-420a-a31e-08ae8c95fb93` | freshman | 73 | 192 |
| 17 | Otis Nixon | `da3e79a7-5fec-46d4-b847-bdf2870e1fe8` | junior | 68 | 159 |
| 25 | Nathan Randolph | `5a27f1b1-ba4a-417e-bd83-45abd8ef5829` | junior | 72 | 200 |
| 27 | Colt Robles | `99f962c5-3624-4082-a420-916f7999241f` | sophomore | 70 | 167 |
| 30 | Dale Butler | `e297fdab-a3da-45d0-af00-1742e371915d` | sophomore | 68 | 175 |
| 31 | Shorty Holmstrom | `d5e6f137-86ff-4c0b-9e5b-5afd094826d5` | senior | 74 | 205 |
| 32 | Thanh Small | `d8b1e862-fbee-44f7-b8b9-160531c0b8df` | freshman | 77 | 235 |
| 34 | Dayton Weber | `c642adfa-692a-4f3f-8e3a-6401543c7a45` | sophomore | 70 | 169 |
| 46 | Eugene Johnston | `eb149eb8-bb89-4d90-8779-e02f1bd6d6d5` | freshman | 79 | 238 |
| 55 | Darren Parrish | `05f93933-514a-4a4e-805e-c76ba8c12dfa` | senior | 73 | 200 |

**Staging folder after export:** `assets_staging/players/<uuid>.png` (12 files).

### Conf1 style references (for `--sref` / LoRA training)

**Primary style anchor (locked):** **Xenon Fletcher** — Bentley-Truman, senior (#0). Chosen as the canonical Conf1 look for all pilot generations.

| Label | Player | URL |
|-------|--------|-----|
| **Primary — Xenon Fletcher** | Bentley-Truman | `https://assets.geekedoutgames.com/players/master/8487cb3b-887b-472a-90d9-f46caa572d46.png` |
| Alt B | Conf1 (manifest) | `https://assets.geekedoutgames.com/players/master/131abe35-8f84-41ce-ba4c-154556289954.png` |
| Alt C | Conf1 (manifest) | `https://assets.geekedoutgames.com/players/master/1ac0782e-e1b3-4cb6-9462-b1ff032ed9ed.png` |

Use **Xenon Fletcher** for every style reference unless a specific generation drifts — then try an alt. Filename / UUID: `8487cb3b-887b-472a-90d9-f46caa572d46.png`.

Full Conf1 UUID list: [`scripts/r2_upload_manifest.csv`](../../scripts/r2_upload_manifest.csv) (98 rows).

### Prompt template (draft — refine during pilot)

**Fixed block** (append to every generation after the variable player block):
```
Front-facing basketball player portrait, bust shoulders up, centered composition,
soft frontal lighting, illustrated semi-realistic sports game art style,
smooth skin gradients, friendly neutral expression, transparent background,
wearing plain white basketball tank top, no logos, no text, no team colors,
simple white jersey with neutral collar,
no watermark, college basketball player age appearance
```

Team colors and **SKY** wordmark are **not** in the AI prompt — added in the [uniform composite](#uniform-workflow--white-base--identical-team-composite-locked-for-production) step.

**Age appearance** (map from roster `year` — canonical labels in [`BackEnd/utils/player_year.py`](../../BackEnd/utils/player_year.py)):

| Class year | Apparent age | Prompt direction |
|------------|--------------|------------------|
| **Default** (Sophomore–Senior, Graduate) | **18–22**, clearly college | “college-aged”, “young adult college basketball player” — no mid-20s+ or grizzled veteran look |
| **Freshman** | **17–19**, college with optional younger skew | Same college band, but allow slightly softer/younger face (less defined jaw, boyish) — a **few** can read closer to late high school |
| **JH** | **16–17**, high-school skew | Noticeably younger than upperclassmen — lean face, less mature features; still athletic portrait, not child |

**Rules:**
- Never prompt “30s”, “mature man”, “bearded veteran”, etc. — Conf1 reads as college roster, not pro.
- Height/weight from roster inform **build**, not age (a 6'7" freshman is still young-faced).
- Chapel Hill pilot has no JH players; 4 freshmen use the Freshman row above.

### Appearance / ethnicity assignment

**Always specify** face/ethnicity in every player prompt. Omitting it does **not** produce a race-neutral image — the model falls back to its own bias (inconsistent and usually wrong for roster diversity).

We do **not** force the same ethnic mix on every team. Use **D1-inspired base rates** as independent per-player odds so teams naturally vary (one roster might skew heavily Black, another more mixed).

**Base distribution** (each non–name-gated draw):

| Category | Weight | Prompt labels (examples) |
|----------|-------:|--------------------------|
| Black | **55%** | “Black man”, dark brown skin, … |
| White | **35%** | “white man”, light skin, … |
| **Other** | **10%** | Split when Other is rolled: **Hispanic/Latino**, **East Asian**, or **non-descript** (ambiguous/mixed features, no strong ethnic read) — **equal thirds** (~3.3% each globally) unless a name override applies |

**Per team:** roll (or assign) **each of the 12 players independently**. Do not rebalance to hit exact percentages on a 12-man roster — variance is intentional.

**Name-overt check** (before rolling base distribution):

1. If first/last name **strongly suggests** an ethnicity (examples: `Robles` → Hispanic; `Thanh` → East Asian; `Holmstrom` → white/Nordic; `Weber` → white/German; `Monroe` / `Nixon` → Black-leaning), flip **50/50**:
   - **Match (50%):** use that ethnicity in the prompt.
   - **No match (50%):** ignore the name hint; assign via **base distribution** (single draw for that player).
2. If no strong name read → **base distribution** only.

Record `Assignment` source per player (`distribution`, `name-match`, `name-no-match→distribution`) in the team table for audit/QC.

**Chapel Hill pilot assignments** (one sample outcome of the rules above — 7 Black / 4 white / 1 Hispanic / 1 Asian):

| Player | Year | Category | Source | Draft visual prompt fragment |
|--------|------|----------|--------|------------------------------|
| Stanley Keith (#4) | SO | Black | distribution | college-aged Black man ~19–20, short hair, athletic build 6'1" |
| Landon Turley (#10) | JR | White | distribution | college-aged white man ~20–21, average build 5'10" |
| Brice Monroe Jr (#11) | FR | Black | name-match | college-aged Black man ~18–19, slightly youthful face, muscular 6'1" |
| Otis Nixon (#17) | JR | Black | name-match | college-aged Black man ~20–21, shorter guard build 5'8", lean |
| Nathan Randolph (#25) | JR | White | name-no-match→distribution | college-aged white man ~20–21, 6'0", average build |
| Colt Robles (#27) | SO | Hispanic | name-match | college-aged Latino man ~19–20, 5'10" |
| Dale Butler (#30) | SO | Black | distribution | college-aged Black man ~19–20, compact build 5'8" |
| Shorty Holmstrom (#31) | SR | White | name-match | college-aged white man of Scandinavian features ~21–22, 6'2", stocky build |
| Thanh Small (#32) | FR | East Asian | name-match | college-aged East Asian man ~18–19, youthful face, tall center 6'5", heavy build |
| Dayton Weber (#34) | SO | Black | name-no-match→distribution | college-aged Black man ~19–20, 5'10", average build |
| Eugene Johnston (#46) | FR | White | distribution | college-aged white man ~18–19, youthful face, tallest on roster 6'7", 238 lb |
| Darren Parrish (#55) | SR | Black | distribution | college-aged Black man ~21–22, 6'1", solid build |

Re-roll assignments for other teams using the same rules; do not copy Chapel Hill’s mix.

### Midjourney — web Create (locked pilot recipe)

| Setting | Value |
|---------|--------|
| Style Reference | Xenon Fletcher PNG only — `8487cb3b-887b-472a-90d9-f46caa572d46.png` |
| Omni Reference | **Empty** |
| Aspect ratio | **1:1** |
| Mode | **Standard** (SD) |

**Do not** put team colors or wordmarks in the prompt. White tank only.

**Example — Stanley Keith (#4):**
```
college-aged Black man about 19-20, short hair, athletic build 6 foot 1,
Front-facing basketball player portrait, bust shoulders up, centered composition,
soft frontal lighting, illustrated semi-realistic sports game art style,
smooth skin gradients, friendly neutral expression, transparent background,
wearing plain white basketball tank top, no logos, no text, no team colors,
simple white jersey with neutral collar,
no watermark, college basketball player age appearance
```

Discord slash syntax (equivalent):
```
/imagine college-aged Black man about 19-20, short hair, athletic build 6 foot 1, [FIXED BLOCK]
--sref https://assets.geekedoutgames.com/players/master/8487cb3b-887b-472a-90d9-f46caa572d46.png
--sw 100 --ar 1:1
```

**Operational rules:**
- Max **2 generation attempts** per player before escalating (tweak variable block only — keep fixed block identical).
- Pick best of 4 upscaled results; avoid endless Vary loops unless a batch is clearly off-style.
- Swap only the **variable** line per player (from roster table above); copy-paste fixed block verbatim.

### Pilot execution checklist

1. [ ] Build Chapel Hill uniform PSD (`chapel_hill_uniform_composite.psd`) — sky blue, navy trim, **SKY** wordmark
2. [ ] Generate **white-tank** bust for Stanley Keith (Midjourney + Xenon style ref)
3. [ ] Composite uniform layer on Stanley; QC neck/collar alignment → **lock layer position**
4. [ ] Side-by-side vs Conf1 at **256px** in roster / set-lineup
5. [ ] Generate white-tank busts for remaining **11** players (same fixed block, swap variable only)
6. [ ] Apply **identical** uniform overlay to all 12; alpha cleanup; export 3530×3412 RGBA PNG per UUID
7. [ ] Upload 12 to staging R2; verify in app (`window.PLAYER_IMAGE_REMOTE = true` on localhost optional)
8. [ ] Lock tool + prompt → remaining 7 Conference 2 teams

---

## Prompt structure (production — after pilot)

**Fixed (every generation):**
- Front-facing bust, shoulders up
- Soft frontal lighting
- Illustrated sports game portrait style matching GOB Conf1 reference set
- **Plain white basketball tank** — no logos, no text, no team colors
- **College-aged appearance (18–22)** unless year is Freshman (younger skew) or JH (high-school skew) — see **Age appearance** table in Phase A pilot section
- Transparent background
- No text generated in-image (wordmark added in composite step)

**Variable per player:** roster `year` → age band; height/weight → build; **ethnicity/appearance always explicit** via [Appearance / ethnicity assignment](#appearance--ethnicity-assignment) (D1 base rates + name-overt 50% rule; independent per player, no forced team rainbow).

**Variable per team:** uniform template composite only (colors, trim, wordmark, logo) — **not** in AI prompt. See [Uniform workflow](#uniform-workflow--white-base--identical-team-composite-locked-for-production).

---

## Scale & effort estimate

| Metric | Estimate |
|--------|----------|
| Team batches | 120 |
| Portraits | 1,440 |
| ~15 min / team (generate + composite + QC + export) | **~30 hours** focused solo work |
| Uniform templates (if DIY) | +20–40 hours, or outsource ~120 templates |

Upload and resolver integration are **already built** — no code change required per portrait if filenames match player `_id`.

---

## Future optimization (out of scope for v1)

[`image_migration.md`](image_migration.md) describes **runtime layering**: store `players/base/{uuid}.png` + `uniforms/{team_id}/overlay.png` and composite at CDN serve time. **v1 production workflow** already composites uniform onto bust in Photoshop and uploads a **finished** `players/master/{uuid}.png` (same delivery path as Conf1). Runtime layering is a future optimization if uniforms change without regenerating faces.

---

## Next steps

1. ~~Pick pilot team~~ → **Chapel Hill** (locked).
2. ~~Uniform workflow~~ → **white base + identical team composite** (locked — see dedicated section).
3. **Build Chapel Hill uniform PSD** — test on Stanley white-tank bust; resolve missing `chapel_hill_logo_square.png` (banner crop or logo pipeline).
4. **Generate 12 white-tank busts** — Midjourney + Xenon style ref; max 2 attempts/player.
5. **Composite + upload** — 12/12 QC at 256px → staging R2.
6. **Scale** — remaining 7 Conference 2 teams after Chapel Hill pass.

---

## Open decisions

| # | Question | Status |
|---|----------|--------|
| 1 | Production tool: Midjourney `--sref` vs Astria/Krea vs Flux LoRA + Kontext | Open — Phase A |
| 2 | Uniform workflow: white base + identical PSD composite per team | **Locked** |
| 2b | Uniform templates: DIY vs freelance designer (templates only) | Open |
| 3 | Pilot team | **Chapel Hill** (`CHAPEL_HILL`, Conf 2) |
| 4 | Player appearance assignment | **Locked:** D1 base 55/35/10; independent per player; name-overt 50% rule; always prompt explicitly |
| 5 | Whether to train LoRA on all 98 Conf1 or curated subset | Open |
| 6 | Chapel Hill square logo: crop from banner vs generate from logo pipeline | Open |
