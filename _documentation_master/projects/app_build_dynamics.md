# App & Build Dynamics — GOB

**Purpose:** Reference for how GOB's builds behave across the Playtest, Next Fest Demo, and paid launch — and how access/revocation differ between Steam distribution and direct-from-site distribution.

**Last updated:** July 2026

---

## 0. The core mental model

The single most important idea, because it clears up most of the confusion:

> **The game files always download to the user's computer.** What you control is not whether files exist on their disk — it's whether they're *authorized to run*. "Revoking access" never means reaching onto their machine to delete anything. It means turning off a lock that the build checks before (or during) running.

A build is only as revocable as the locks you deliberately build into it. Two possible locks:

1. **Steam's access check** — exists only for builds distributed through Steam. Steam's client verifies entitlement before authorizing launch. You toggle this from the Steamworks backend.
2. **Your backend auth** — exists only if *you build the build to phone home*. The build authenticates against your servers on launch; you reject the token to kill it.

Neither lock is automatic. You choose, per build, which locks to include. **This is the whole game.**

---

## 1. The three builds are different artifacts

They are not one game in three states. They are (potentially) three different builds with different locks compiled in, serving different jobs.

| Build | Steam lock | Backend lock | Standalone? | Job |
|---|---|---|---|---|
| **Playtest** | Yes (if via Steam) | **Yes** | No — depends on backend | Validate PMF; must be revocable |
| **Next Fest Demo** | Yes (via Steam) | Optional | Can be either | Public, permanent, free; wishlist driver |
| **Paid launch (single-player)** | **No** | **No** | **Yes** — runs forever | Owned product; runs offline like OOTP |

The paid single-player build having **zero** locks is a deliberate choice, not an oversight — see §4.

---

## 2. Playtest dynamics

**Scope:** Full-loop game — everything needed to experience the core franchise-management fantasy end to end. **Not** feature-crippled. A build artificially capped (e.g. "no progression past season one") can't measure the PMF signal you're collecting (e.g. retention into a second season). Cut features by *readiness* (leave out things that aren't built/stable), never by artificial gating.

**Caveat:** "Full loop" ≠ "ship the bug list." Feature-complete-enough to validate the fantasy, stable-enough not to poison first impressions (playtest users talk and screenshot). This is why the rollout is gated → controlled-open → stress-test: start with diehards who forgive rough edges while the build hardens.

**Access model:** Backend-dependent by design. The build authenticates to your servers on launch. This is what makes it revocable and what protects against cannibalization — an orphaned playtest build is worthless because the half of the game that lives on your servers stops answering.

**Teardown (the anti-cannibalization mechanism):** Wind the playtest down before the March launch. You do **not** need expiring codes or a self-destructing build. You revoke centrally:
- Flip the Playtest off in Steamworks → "Request Access" button disappears, Steam stops authorizing launch.
- Stop honoring playtest-tier tokens on your backend → the build can't function regardless of what's on disk.

The **strategic** cannibalization risk (not technical) is a too-complete, too-long free playtest satisfying the itch so testers don't convert. Mitigate by keeping it gated/cohort-based (waves, not always-on), and converting the audience into wishlisted founder-buyers *while engaged* rather than letting them play free indefinitely until they drift.

---

## 3. Next Fest Demo dynamics

**Different tool from the Playtest — different revocability, therefore different scoping.**

- **Playtest = revocable → can be generous.** You can turn it off, so you can afford to hand testers the full loop.
- **Demo = permanent → must be limited.** It's public, free, and lives in the player's library forever; you *cannot* revoke it. So this is the build you deliberately scope-limit (a season cap, a time limit, a team limit).

Clean rule: **Playtest you revoke; Demo you constrain.** Applying Demo-logic (permanent, needs artificial limits) to the Playtest is the mistake — the Playtest doesn't need artificial limits because you can just switch it off.

Required for Next Fest: a demo qualifies, a playtest does **not**. Build the public Demo from the hardened Playtest build when the time comes.

---

## 4. Paid launch dynamics (single-player)

**Standalone, no locks.** The paid single-player franchise build runs locally with no Steam DRM check and no backend phone-home — so it runs on its own, offline, forever, like an OOTP direct purchase.

**Why deliberately unlocked:** Your anti-piracy protection should not live in the single-player build, because your *revenue* doesn't either:
- **Recruit packs** — content served/unlocked through your backend. A cracked single-player build can't fabricate legitimate pack content.
- **Subscription** (live PvP, tournaments, leaderboards, franchise-sharing) — 100% server-side, gated by your auth, untouched by whether the base build is DRM-free.

So the base franchise mode is effectively your on-ramp / "demo you also charge for," while durable revenue sits behind server auth a local crack can't reach. You can afford to be generous and DRM-light on single-player *precisely because that isn't the moat* — and the sim-purist audience actively prizes DRM-light ownership.

**Optional hardening (if ever wanted):** Steam's one-click DRM wrapper on the Steam build only (still runs offline once the client is open; known to be easy to strip — stops casual sharing, not determined piracy). Default recommendation: skip it.

---

## 5. Access dynamics: Steam vs. direct — the key distinction

Same conceptual game, but the number of locks in front of a user depends entirely on **how they got the build**, because Steam's lock only exists when Steam is the distributor.

### Playtest via Steam → TWO gates (both active simultaneously)
1. **Steam's access check** — revoke in Steamworks.
2. **Your backend auth** — reject the token server-side.

Both apply to the same user at the same time. They stack. **Killing either one alone stops the playtest.** This redundancy is why Steam-distributed playtest access is airtight.

### Playtest via direct site → ONE gate (yours only)
- **Your backend auth** — the sole gate, because Steam was never in the loop.

Bypassing Steam bypasses Steam's lock entirely. That's fine: your backend auth is the *decisive* lock anyway and is fully sufficient to revoke access on its own. You simply don't get the second, redundant Steam-side lock.

### Summary table

| Access path | Steam lock | Backend lock | Total gates | Revocable? |
|---|---|---|---|---|
| Playtest via Steam | Yes | Yes | **2** | Yes — either gate suffices |
| Playtest via direct site | No | Yes | **1** | Yes — backend gate suffices |
| Paid single-player (either channel) | No | No | **0** | No — runs forever, by design |

### The paid game, both channels
The purchase channel determines **who got paid and who verified ownership at install** — it does **not** determine the architecture. Ship one standalone build; direct buyers get it from you, Steam buyers get it from Steam, both run it locally offline. The recruit-pack and subscription layers authenticate to your backend identically regardless of where the base game was bought.

---

## 6. The work item this all implies

Whatever the single-player build's lock choice, the base build must be able to **talk to your backend for the online layers** (recruit-pack redemption, subscription features) for *both* direct and Steam customers. That requires your own account system that a Steam purchase can **link into** (a Steam buyer creates/links a GOB account to redeem packs and access subscription features).

That account bridge is the real engineering item — same work regardless of the DRM choice, and already implied by the monetization model, so not *new* scope. It's the piece that turns "one standalone build, sold two ways" into something wired to revenue.

---

## 7. One-sentence recall

- **Playtest:** backend-dependent build → revocable → generous scope → torn down before launch.
- **Demo:** permanent public build → not revocable → deliberately limited scope.
- **Paid single-player:** standalone, lockless → runs forever → moat lives in server-side packs + subscription, not in the build.
- **Steam access = an extra redundant lock; direct access = your backend lock only; both revoke fine.**
