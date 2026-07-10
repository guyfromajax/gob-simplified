# Player Image Generator — Decision Log

Append-only record of **what we locked and why** while building the portrait
pipeline. This is the rationale trail; the step-by-step *runbook* (how to actually
run the pipeline) will be written separately once every stage is built.

**Goal:** generate ~1,440 illustrated player portrait "masters" (Conferences
2–16: 15 conf × 8 teams × 12 players) matching the hand-painted Conf1 art style,
without the original artist. Output spec: PNG RGBA, 3530×3412, named
`<player_uuid>.png`, uploaded to Cloudflare R2 at `players/master/<uuid>.png`.
Conf1 (96 players) already has bespoke art and is **never touched** — it's used
only as a style/body/expression reference.

Priorities (in order): **1. Quality/style-match · 2. Ease of use · 3. Cost.**

---

## Tooling

- **Image model: Nano Banana 2 Lite** (Gemini `gemini-3.1-flash-lite-image`),
  via Google AI Studio GUI and the `google-genai` Python SDK. Chosen after a
  bake-off; it matches the semi-realistic Conf1 style and does reference-guided
  edits well.
- **Segmentation/finishing:** `onnxruntime` + `u2net_human_seg` (not `rembg`,
  which fails to build on Python 3.13 via numba/llvmlite).
- **Data source:** Mongo `gob-staging.players` (1,536 docs). Export script pulls
  height, weight, jersey, year, and attributes ST/AG/RT.

---

## Age & style

- **Age: 16–17 aspirational** (reads high-school / young). This is a high-school
  sim — reverses the brief's "college-aged." Confirmed by user preference.
- **Art style:** semi-realistic illustrated, matching Conf1. Front-facing
  head-and-shoulders bust, plain light/cream background, white tank for the base
  body (uniforms applied later).

---

## Body archetypes — the TWO-AXIS model

Body = **FRAME** (skeleton/silhouette) × **DEFINITION** (muscle vs. fat). The two
are independent: a broad frame can be cut, toned, or soft. Only the frame needs
a generated reference body; definition is a per-player prompt modifier.

### FRAME — 5 locked templates
Files: `tmp/portrait-pilot/reference_bodies/final/{slight,lean,normal,broad,doughy}.png`

| Template | How it's built | Reads as |
|---|---|---|
| **slight** | base −10% shoulder width | small, youthful, narrow |
| **lean**   | base (0%)                | slim average |
| **normal** | base +8%                 | average athletic |
| **broad**  | base +15%                | big-framed forward |
| **doughy** | separate NB body         | soft/heavier, still an athlete |

**Why a "warp ladder" instead of 5 separate NB generations:** NB would **not**
reliably vary shoulder width off a neutral anchor — every "build" came out
looking like Normal (verified: shoulder-width spread was ~1% across 5 separate
generations). Fighting it with adjectives failed across ~6 rounds; anchoring
Broad to a real broad player (Cedric Buckles) got the width but dragged in his
adult face, dreads, and photo-real style (broke family consistency). **Solution:**
generate ONE clean young base body, then derive the width tiers by a
**horizontal shoulder warp** (head size held constant). This guarantees a
consistent family (same face/style/background/framing) that differs *only* in
frame width — which is exactly the archetype axis. The warp is also kept as a
reusable tool for nudging any body's frame later.

**Design decisions along the way:**
- Started at 9 archetypes (3 heights × 3 builds) → collapsed. **Height barely
  reads in a bust crop** (you only see head + shoulders + neck), so height is NOT
  a full axis. What reads: shoulder width, neck thickness, face fullness.
- "Slight" captures genuinely small players (the Mose Hawkins / Lucky Forte read)
  via narrow frame + youthful proportion, not a height number.
- Dropped "Rangy" (tall + lean) — indistinguishable from Lean in a bust.
- **Doughy is a terminal type, pinned to Soft** — you can't be round-with-fat AND
  cut-with-no-fat, so Doughy never combines with Cut/Toned. It gets its own base
  body because fat changes the whole silhouette.
- Validated against 22 real Conf1 players — all fit the frames; the two "misfits"
  were cases where the *original bespoke art ignored the stats* (e.g. a 5'9"/163
  ST-5 guard drawn with big shoulders). Our system ties body to stats, so it's
  actually *more* consistent than the original art.
- **Known caveat (open):** `normal` (+8%) and `broad` (+15%) currently clip at
  the frame edge, so both read ~+3% visible — the top pair doesn't separate yet.
  Fix is a ~12% base zoom-out (deferred; user chose to move on).

### DEFINITION — 3-level modifier (prompt-only, no extra bodies)

| Modifier | Means (composition, NOT width) |
|---|---|
| **Cut**   | defined muscle, low body fat |
| **Toned** | average tone (default) |
| **Soft**  | undefined, carrying fat |

**Why rename the middle to "Toned":** an earlier "Solid = thick with mass"
conflated definition with *frame width* (that's Broad's job). Definition describes
only muscle-vs-fat; width belongs to the frame axis. A "big powerful thick" guy is
**Broad + Soft/Toned**, not a definition value.

### Routing (classifier: `scripts/classify_player_archetypes.py`)
- DEFINITION: `Cut` if RT≥75 or (ST≥65 & AG≥45); `Soft` if RT≤45 & AG≤30; else `Toned`.
- FRAME base from BMI tertiles (Lean<25.5 / Broad≥26.5 / Normal between), then:
  - **Doughy** if Soft & BMI≥26.5 & ST<55 (heavy + soft + weak = fat, not powerful).
  - **Slight** if height≤69" & lean/normal build (short broad guys stay Broad).
  - **Mass override:** weight≥235 & ST≥65 → Broad, because BMI under-rates very
    tall players (a 7'0"/260 ST-105 monster reads Normal by BMI otherwise).
- *Note:* classifier frame names predate the final 5-template rename and the
  Broad/BroadMax split; to be reconciled when we wire generation.

---

## Facial expressions — 10, weighted, UUID-seeded

Distilled from a 29-face Conf1 reference study into 10 distinct expressions
(warmest → darkest), weighted so the roster skews neutral/friendly with rare
extremes. Seeded off each player's UUID (stable across runs, natural mix).
Lives in `EXPRESSIONS` in `classify_player_archetypes.py`.

`calm neutral (4) · warm friendly smile (3) · pleasant closed smile (3) ·
cheerful open smile (2) · confident smirk (2) · composed/stoic (2) ·
big beaming grin (1) · stern/hard (1) · intense game-face (1) · menacing (1)`

- **menacing** added as the deliberate inverse of the big beaming grin.
- Expression rides on the **face**, generated per player — independent of the
  neutral body templates.

Per-player variety = **5 frames × 3 definitions × 10 expressions = 150** base
combinations, before unique faces/skin/hair/character-details.

---

## Uniforms — recolor-in-place (NOT drop-on templates)

Tested two ways to put a team's uniform on many bodies:
- **Drop a rigid uniform PNG** at fixed coordinates → aligned reasonably (NB holds
  the body tight, ~7px collar variance) but the underlying white tank **peeked**
  at the shoulders and it read pasted.
- **Recolor-in-place** — recolor each player's *own* white tank to the team
  colors + stamp the wordmark. Follows each body's exact tank shape, keeps its own
  fabric folds, no peek. **Winner.**

This also future-proofs the long-term vision: generate recruits in white tanks;
when recruited, recolor their existing tank to the new team's uniform. No rigid
template needed; works on any body/archetype.

- Team colors come from `teams/128_teams.txt` (primary/secondary hex).
- Wordmark: **Bebas Neue Pro** (`FrontEnd/static/fonts/BebasNeuePro-Bold.otf`),
  script-applied (deterministic, consistent) — NOT painted by NB (NB wordmarks
  were inconsistent across a team).
- All 12 players on a team share the **exact same** jersey hex (color-locked).

---

## Character details (sparingly)

Afro, dreads, goggles, headband, earrings, etc. — sprinkled at low rates,
UUID-seeded. At scale: ~40% wordmark-only jerseys, ~50% wordmark+number, ~10%
unique layouts. (Accessories are a separate axis from expression.)

---

## Pipeline hygiene

- **Skip-if-exists** guard in the generation driver: skip any player who already
  has an image (auto-excludes Conf1's 96 and anything already generated). Makes
  the run idempotent/resumable.
- The 5 files in `reference_bodies/final/` are the canonical template catalog;
  everything else in `reference_bodies/` is iteration history.

---

## Open items / deferred

- [ ] `normal`/`broad` frame separation (base zoom-out fix).
- [ ] Reconcile classifier frame names with the final 5 templates.
- [ ] Face axis: skin tone / ethnicity / hair distribution (UUID-seeded vs.
      specified proportions) — next decision.
- [ ] Build per-player generation driver (body-lock + face + definition + expression).
- [ ] Finishing: face-anchored framing (preserve natural head-size variation —
      do NOT equalize head size, or "big head reads big" is lost), white-halo
      alpha cleanup, cutout, crop to 3530×3412.
- [ ] Uniform recolor-in-place + script wordmark at scale.
- [ ] Contact-sheet QC tool; R2 upload (`scripts/upload_player_images_to_r2.py`).
- [ ] Validate full Chapel Hill (12) end-to-end before scaling to 1,440.
