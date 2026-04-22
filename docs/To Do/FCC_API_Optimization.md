# FCC API & Load Experience — Optimization Notes

Context: The Franchise Command Center (FCC) is driven primarily by a single **`GET /franchise/command-center/data`** call (often with **`profile=1`**). That response is large and gates first paint, including secondary UI such as the **Inbox** tab (e.g. `last_training_report_week`). This doc captures a sensible phased approach to improving perceived and actual performance—no implementation commitment yet.

---

## Short term — loading UX & critical path

**Problem addressed:** Subpar *perceived* experience—misleading empty states, stale-looking tabs, or chrome that appears before data is authoritative—not raw server speed.

**Direction:**

- Define what **“FCC ready”** means for the user: the minimum set needed to show the shell honestly (team identity, week, season, training status, Inbox/training-report pointer, primary CTAs).
- Until that subset is available, use a **full-page or focused overlay** (or consistent skeletons) so users do not see incorrect copy (e.g. “Inbox is empty” while the command-center request is still in flight).
- Optionally gate only on **critical** fields rather than waiting for every key in the current mega-payload, so the spinner does not unnecessarily track the slowest optional sections.

**Tradeoff:** A long wait still feels long if the single endpoint remains heavy; this does not reduce backend work by itself.

---

## Medium term — API / payload restructuring

**Problem addressed:** **Actual latency**, payload size, and maintainability as the FCC grows.

**Direction:**

- **Split the monolith** into a small **bootstrap** response (fast, stable shape) vs **lazy or tab-scoped** endpoints for expensive blocks (e.g. full rankings tables, recruiting lists, playbooks summary, EOS bracket snapshots, leaders, etc.).
- Allow **parallel fetches** where independent, and **cache-friendly** reads for data that changes rarely within a session.
- Keep a clear contract for what loads on first paint vs when a tab is first shown.

**Tradeoff:** More endpoints (or bootstrap + enrich pattern), more client orchestration, and discipline about dependencies between calls.

---

## Both together — recommended long-term shape

**Why both:** Loading UX fixes **confusing intermediate states**; API restructuring **reduces time-to-interactive** and failure blast radius. Doing only one leaves a gap: either the app still feels slow, or it still lies to the user briefly.

**Suggested combination:**

1. **Bootstrap endpoint (or slimmed command-center payload)** — Everything required for header, week, training/Inbox hints, and navigation integrity in one small, fast response.
2. **Honest loading** — Overlay or skeleton until bootstrap succeeds; tab-specific loaders for deferred data.
3. **Lazy tab loads** — Heavy sections fetch on first tab open (or in parallel after bootstrap) without blocking the whole FCC.

This yields a **fast enough first paint** and an **honest UX** without one giant spinner tied to the entire season’s worth of aggregated data.

---

## Reference — current behavior (as of this writing)

- FCC JS typically calls **`/franchise/command-center/data?franchise_id=…&profile=1`** as the main load.
- **Inbox** content (`last_training_report_week`, etc.) is rendered from that response **after** it completes; session restore repaints much of the FCC but does not prime Inbox from cache in the same way.
- Training submit does not currently **optimistically** update Inbox; returning to the FCC waits on the same command-center round trip unless enhanced later.

---

## Related files (implementation, when pursued)

- Backend: `BackEnd/api/franchise_routes.py` — `command_center_data`, training/Inbox fields.
- Frontend: `FrontEnd/static/franchise-command-center.js`, `FrontEnd/static/franchise-command-center.html`.
