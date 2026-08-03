# GOB — Asset Storage & Delivery Architecture

**Product:** Geeked-Out Basketball
**Status:** Recommendation for alignment
**Date:** 2 August 2026
**Scope:** All game art — league assets, generated assets, and user uploads — across web play, online play, and downloadable builds.

---

## 0. Why this document exists

Team Builder made every player a potential asset author. That raised a question the codebase had never had to answer: **where does art live, who pays for it, and what happens when someone deletes their franchise?**

The immediate worry was repo bloat from user-created courts. That specific risk does not exist — user-generated content never touches version control — but the question underneath it is real, and worth answering once rather than per-feature.

---

## 1. The rule

> **Store bytes only for what a computer cannot recreate.**

This is not a new principle. `Recruit_Image_System.md` already locks it for uniforms:

> *"A uniform is a recipe, not an image."*

Everything below is that decision, generalized. It is also the same shape as the architectural rule from Phase 0 (§3.1a, *resolve at the edge, on the way out*): keep the durable thing minimal and canonical, and produce the presentation form at the last possible moment.

---

## 2. Three asset classes

| Class | Examples | What is stored | Where |
|---|---|---|---|
| **Derivable** | Team courts, generated banners, uniforms | **The recipe** — colours, name, mascot, abbreviation | Mongo, inside the franchise document |
| **Non-derivable** | User-uploaded logos and player images | **The bytes** | R2, keyed by franchise |
| **Static league** | 129 courts, 128 banners, 129 card banners, 8 squares | **The bytes**, authored once, identical for every player | Git (source of truth) → R2 (delivery) |

The three classes have genuinely different lifecycles, and conflating them is what makes asset architecture feel complicated.

---

## 3. Derivable assets — the recipe travels, the image never does

A custom court is fully determined by five colour values. A generated banner is determined by two colours plus three strings. Both render deterministically, in a few milliseconds, on a canvas.

**Store the parameters. Never store the render.**

| Property | Parameters | Stored render |
|---|---|---|
| Size | ~100 bytes | 1–2 MB |
| Works offline | Yes | Only if pre-fetched |
| Online opponent sees it | Yes — params ride in the game payload | Requires a fetch |
| New device | Yes | Requires a fetch |
| Survives a generator improvement | **Yes** | **No — silently stale** |
| Cleanup on franchise delete | Nothing to clean | Lifecycle required |

The staleness row is the one that decides it. If the court generator ever changes — a hardwood texture, a line weight, a fix — every stored render is silently wrong and needs a re-render migration. **A recipe cannot go stale, because the current generator always produces current output.**

### 3.1 This resolves the online-play question

An online opponent needs to see your custom court. They do **not** need your image; they need your five parameters, which ride in the game payload at roughly 100 bytes and render locally on their machine.

One mechanism covers every case:

- **Offline** — regenerate from parameters in the local save
- **Online** — regenerate from parameters in the game payload
- **New device** — regenerate from parameters in the franchise API

No bandwidth, no storage, no sync, no cleanup. **Parameters travel; images don't.**

### 3.2 The unverified assumption — render cost

**This model assumes regeneration is cheap. That has not been measured.**

A court is 3,333 × 2,083 — roughly 7 million pixels — with a hardwood texture, arcs, and a dozen markings. If that renders in ~50ms, regenerate-on-demand is straightforwardly correct. If it takes several hundred milliseconds on a mid-range laptop, or seconds on a phone, every game start pays for it.

**Measure before relying on it:** render time for a full court on a desktop and on one low-end device.

**If it is slow, the architecture does not change — a cache is added.** Hold the rendered blob for the session, or in IndexedDB, as a **derived, disposable cache**:

- Parameters remain the only canonical storage
- The cache can be discarded at any moment and rebuilt from parameters
- A generator change invalidates the cache automatically; it can never go stale in the way a *stored render* can, because nothing depends on it surviving

> The distinction that matters: **a cache is disposable, storage is authoritative.** Caching a render is compatible with §1; persisting one as the source of truth is not.

### 3.3 The business property

A user who creates a custom program with a generated court and banner adds **about 100 bytes** to storage. Not two megabytes.

Storage therefore scales with **uploads**, not with **franchises**. A player who never uploads a file costs nothing incremental, no matter how many teams they build. This is what makes the model sustainable without ongoing attention.

---

## 4. Non-derivable assets — user uploads

Per §6.4 of the v2 plan, users may upload a horizontal logo and player images. Nothing can reconstruct these, so they must be stored.

**Store in R2, keyed by franchise.** Requirements:

- **Normalize before storing** (§6.4) — read, draw to canvas at target dimensions, re-encode, store the normalized result. Never store the raw upload.
- **Cascade delete.** `_cascade_delete_franchise` is the existing hook; it already cleans FPD, FTD, FRD and games.
- **An orphan sweeper.** Cascade delete handles the happy path. A partial failure leaves objects nothing points at, and nothing will ever notice. A periodic job listing stored objects and dropping any whose franchise no longer exists is cheap now and unpleasant to retrofit.
- **Per-franchise quota**, enforced at upload, so one user cannot become an unbounded cost.

### 4.1 Offline limitation, stated deliberately

A downloadable build with no network cannot fetch an uploaded logo. Either it is cached locally on first online session, or the offline experience falls back to the generated banner. **This is the one place where offline is genuinely degraded, and it should be a stated decision rather than a discovery.**

---

## 5. Static league assets — a delivery question, not a storage one

The 129 courts, 128 banner primaries, 129 card banners and 8 squares are immutable and identical for every player. Roughly 300 MB total.

**Recommendation: keep git as the source of truth; publish to R2 on deploy; serve web from R2.**

| | Benefit |
|---|---|
| Off the Netlify deploy | Faster builds, no size pressure |
| Served from CDN edge | Faster first paint, globally |
| Git remains canonical | One source of truth, fully reversible |
| Zero egress cost | R2 charges nothing for bandwidth |

**Do not rewrite git history to remove them.** That is a large, irreversible operation solving a problem (~300 MB in history) that is annoying rather than harmful. If clone times become a genuine obstacle later, Git LFS is the incremental step.

### 5.1 Use R2, not Cloudflare Images

Cloudflare Images performs automatic optimization and resizing. **Court images must be exactly 3,333 × 2,083** — `Team_Images_System.md` forbids resizing or re-encoding because the animation system depends on those dimensions.

A CDN silently serving a helpfully-optimized 2,048px court would break play in a way that presents as a rendering bug and would be extremely hard to trace. If Images is ever used for anything, **courts must be excluded explicitly.**

### 5.2 Downloadable builds bundle locally

A download with no server also has no CDN. Static league assets are **packaged into the download at build time** and read from disk. R2 is the delivery path for web only.

This is why git stays the source of truth: the build step needs a local copy to package.

---

## 6. Play modes — one resolver, two backends

Local and online play need different storage. They do **not** need different systems.

> **One asset resolver. Two storage backends. The play mode selects the backend. Everything above the resolver is mode-agnostic.**

### 6.1 What actually differs by mode

| Class | Local download | Web | Online | Real difference? |
|---|---|---|---|---|
| **Derivable** (courts, banners, uniforms) | Render from params in the save | Render from params in the API | Render from params in the game payload | **None.** Identical code. |
| **Static league** | Bundled on disk | R2 | Either | **A base URL.** Not a system. |
| **Uploads** | Player's own disk | R2 | R2 | **Yes** — genuinely different storage |

Only one row is a real divergence. Derivable assets are mode-agnostic by construction, which is the compounding return on §3: because the recipe travels instead of the image, the hardest asset class becomes the one that needs no accommodation at all.

### 6.2 Where uploads live, and why

| Mode | Uploads live | Why |
|---|---|---|
| **Download, local only** | The player's disk | No one else needs the asset; no other device needs it |
| **Web** | R2 | No durable local disk — browser storage is cleared, and a player expects their team on any machine |
| **Online, either build** | R2 | The opponent must be able to fetch it |

**The test:** *does anyone other than the creator, or any device other than the one that created it, need to reach this asset?* If neither, it stays local.

This keeps the cheap case cheap. A player who downloads the game and never goes online costs **nothing** — no storage, no egress, no lifecycle. Infrastructure cost begins only when a player uses something that genuinely requires infrastructure.

It also means the R2 upload path is **not** a prerequisite for a downloadable build. It is a prerequisite for web and for online.

### 6.3 Mode transitions are one-time migrations, never sync

A local-only player subscribes and goes online: their uploaded logo must now exist on R2. An online player downloads the game: assets must exist locally.

> **Handle each as a single explicit migration event — push on first online session, pull on first download. Never a continuous two-way sync.**

Two-way sync between a local disk and object storage is where this class of architecture fails: conflict resolution, staleness, partial states, and "which copy is newer" are all unbounded problems. A one-time, explicitly-triggered copy is simple, debuggable, and sufficient.

### 6.4 What must be true today

**None of this needs building now. It needs not to be foreclosed.**

The single requirement is that **assets resolve through one function with a seam where a backend can be swapped in.** That is already true — `getTeamAssetPath` is the chokepoint Phase 0 consolidated 37 call sites into, and it is the correct place for the backend to be selected.

Write down the rule, keep the seam, and implement a backend when a mode exists that needs it.

> **Assumption to confirm:** the state of online play — planned, in progress, or further out — is not established in this document. If online play does not exist yet, §6.2's R2 requirements are design-ahead and should not be built.

---

## 7. Cost model

| Item | Volume | Monthly cost |
|---|---|---|
| Static league assets | ~300 MB | **~$0.005** |
| Egress, all traffic | any | **$0** — R2 charges no egress |
| Read operations | 1M | **$0.36** |
| Derivable user assets | 100 bytes / franchise | **~$0** |
| User uploads | ~1.4 MB / uploading franchise | ~$0.02 per 1,000 franchises |

**Cost is not a constraint at any plausible scale**, provided derivable assets stay derivable. The single decision that keeps it that way is not storing renders.

---

## 8. Open items

| # | Item | Owner |
|---|---|---|
| 1 | Server-side rendering — deferred. Social previews, OG images, emailed recaps would need a headless render path. **Nothing is foreclosed:** the recipe is preserved, so a server renderer can be added later without changing what is stored. | Jamie — later |
| 2 | Upload limits — max file size, per-franchise quota, behaviour when a subscription lapses | Jamie |
| 3 | Cache strategy for R2 — versioned paths vs purge-on-deploy. **Versioned paths recommended**; purges are a class of bug that only appears in production. | — |
| 4 | Migration — existing franchises have no stored court parameters. Lazy fallback to primary/secondary defaults is simpler than a backfill and behaves identically. | — |
| 5 | Offline behaviour for uploaded assets (§4.1) — cache on first online session, or fall back to generated | Jamie |
| 6 | **State of online play** — planned, in progress, or further out. Determines whether §6.2's R2 requirements are current work or design-ahead. | Jamie |
| 7 | **Measure court render time** (§3.2) — desktop and one low-end device. The only unverified assumption underpinning §1. Cheap to obtain; either confirms the design or adds a disposable cache to it. | Grok, next time in that code |

---

## 9. Sequencing

None of this blocks Team Builder. Suggested order:

1. **Make court parameters round-trip** (v2 plan §6.3b) — already a live defect, already scoped
2. **Static assets to R2** — self-contained, no feature dependency
3. **Upload storage + cascade delete + sweeper** — with v2 plan §6.4 (3c), which needs it, and only once web or online play requires it
4. **Downloadable build packaging** — when a download build actually exists

Steps 1 and 2 are independent and can run in either order. **Nothing in §6 is on this list** — it is a rule to hold, not work to schedule, until a mode exists that needs a second backend.

---

## 10. Decision log

| # | Decision | Rationale |
|---|---|---|
| 1 | Store bytes only for what a computer cannot recreate | Generalizes the existing *"a uniform is a recipe, not an image"* decision to courts and banners |
| 2 | Derivable assets store parameters, never renders | ~100 bytes vs 1–2 MB; works offline; and a recipe cannot go stale when the generator improves |
| 3 | Parameters travel in the online game payload | One mechanism serves offline, online and new-device; no image transfer at all |
| 4 | User uploads live in R2, keyed by franchise, with cascade delete and an orphan sweeper | Non-derivable by definition; cascade delete alone leaves orphans nothing points at |
| 5 | Git stays the source of truth for static league assets; R2 is a delivery path | Reversible, keeps one canonical copy, and the download build needs a local copy to package |
| 6 | R2, not Cloudflare Images | Automatic resizing would violate the exact court dimensions the animation system depends on |
| 7 | No git history rewrite | Large and irreversible, solving an annoyance rather than a harm |
| 8 | Server-side rendering deferred, not designed out | Preserving the recipe means a headless renderer can be added later with no change to what is stored |
| 9 | **One asset resolver, two backends — not two systems** (§6) | Only uploads genuinely differ by mode. Derivable assets are mode-agnostic by construction; static assets differ by a base URL. |
| 10 | **Local-only play needs no infrastructure at all** | Nobody else and no other device needs the asset. Cost begins only when a player uses something that requires infrastructure. |
| 11 | **Mode transitions are one-time migrations, never continuous sync** | Two-way sync between local disk and object storage brings unbounded conflict, staleness and partial-state problems. Push on first online, pull on first download. |
| 12 | **Build nothing for modes that do not exist yet** | The only requirement today is that assets resolve through one function with a swappable backend — already true of `getTeamAssetPath` |
| 13 | **A rendered court may be cached, never stored** (§3.2) | A cache is disposable and rebuildable from parameters, so it cannot go stale. Storage is authoritative, and an authoritative render silently diverges the moment the generator changes. |
