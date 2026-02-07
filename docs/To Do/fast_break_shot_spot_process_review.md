# Fast Break Shot Spot: Why It Works Sometimes and Not Others (Process Review)

## Goal

Explain why the fast break shot animates from **near the rim** in some cases and from the **defensive-stop / top-of-key** area in others, and map the paths so we can consider streamlining toward a single source of truth (SS&S).

---

## When It Works vs When It Fails

### ✅ **Works (shot from near rim)**

| Scenario | Why it works |
|----------|--------------|
| **Defender contested, ball handler beat them** (`ball_handler_beats_defender` + `stopper_id`) | Frontend takes the **WithStopper** path and **ignores backend position**. It always uses a **locally computed** shot spot near the rim. Backend also sets `bh_end` near rim, but the frontend never uses it for this path. |
| **No outlet position** (rare: animator fallback) | Backend has no `ball_handler_outlet_x/y`, so animator uses the **fallback** branch: for shot attempt (`hold_up` False), `bh_end` = shot spot near rim. `shot_spot` is set from that. Frontend uses `turnData.shot_spot` → correct. |
| **Fast break routed to FAST_BREAK but no `shot_spot`** | Frontend `animateFastBreakShot` uses **local random** near rim when `turnData.shot_spot` is missing. So even if backend sent a bad value, we’d only use it when we trust it (when it’s present). |

### ❌ **Fails (shot from defensive-stop / top-of-key area)**

| Scenario | Why it fails |
|----------|--------------|
| **Outlet (or steal entry) + shot attempt, no “beats defender”** | Backend animator has `ball_handler_outlet_x/y` set and **does not** have `ball_handler_beats_defender`. It uses the **“outlet + additional_move”** branch: `bh_end` = outlet + 5–10 x steps. That’s a short run from outlet (often top-of-key). Phase_resolution sets `turn_result["shot_spot"]` from `_bh_final_x/y` (same value). Frontend **trusts** `turnData.shot_spot` and moves shooter there, then shoots → wrong spot. |
| **Fast break turn routed to SHOT_ATTEMPT** | Top-level `fast_break` is missing or wrong on the turn. Frontend routes to **handleShotAttempt** → **ShotAnimationSystem**. That runs **backend `animations`** step-by-step (no “run to rim” step) and shoots from the shooter’s **current position**. Backend animations for this case end at “outlet + 5–10” → shot from wrong spot. |

So:

- It **works** when: (1) we use the **WithStopper** path (frontend owns shot spot), or (2) backend happens to send a **rim** shot spot (no outlet or fallback), or (3) we don’t have `shot_spot` and frontend uses local rim.
- It **fails** when: (1) backend sends **outlet + 5–10** as `shot_spot` and frontend uses it, or (2) the turn goes to **SHOT_ATTEMPT** and we follow backend animations that end at outlet + 5–10.

---

## Why the Same “Fast Break Shot” Can Take Different Paths

Conceptually there is one thing: **fast break shot attempt**. In code it’s split across **routing**, **backend shot position**, and **frontend shot position**.

### 1. **Routing (who handles the turn)**

- **FAST_BREAK handler**  
  - Used when `turnData.fast_break === true` (or `"true"`) or `turnData.result_type === "FAST_BREAK"`.  
  - Does **not** consider `turnData.roles?.is_fast_break`.  
  - So if `fast_break` is missing or wrong, a fast break shot is handled as a normal shot.

- **SHOT_ATTEMPT handler**  
  - Runs **backend animations** and shoots from **current position**.  
  - No “move to shot spot near basket” step.

So **one** logical event (fast break shot) can be handled in **two** completely different ways depending on a single top-level flag.

### 2. **Backend shot position (animator)**

One place decides the ball handler’s end position and thus `shot_spot`:

- **`ball_handler_beats_defender`** (hold_up and ball handler beat defender)  
  → `bh_end` = **shot spot near rim**.  
  (Frontend often doesn’t use this for the WithStopper path; it uses its own spot.)

- **`ball_handler_outlet_x/y` set** (outlet pass or steal entry)  
  → `bh_end` = **outlet + 5–10 x** (and small y).  
  Used for **both** defensive stop and shot attempt. So for **shot attempts with outlet**, we still put the shooter only a short run from the outlet (top-of-key area), not at the rim.

- **Else (no outlet)**  
  → Shot attempt: `bh_end` = **near rim** (fallback).  
  Defensive stop: top of key.

So **same “shot attempt” outcome** can get **rim** (no outlet or fallback) or **outlet+5–10** (outlet set), depending on whether outlet was set and whether we’re in the “beats defender” branch.

### 3. **Frontend shot position (fastBreak.js)**

Once we’re in the fast break handler:

- **WithStopper path**  
  - Uses a **local** shot spot (computed in `animateFastBreakShotWithStopper`).  
  - **Does not use** backend `shot_spot` or backend animations for where to shoot from.  
  - So backend shot position is irrelevant for this path.

- **Normal shot path** (`animateFastBreakShot`)  
  - **If `turnData.shot_spot` is present**: use it (backend is SS&S).  
  - **If not**: use **local random** near rim.  
  - So we only get “wrong” spot when backend sends a wrong `shot_spot` and we trust it.

So we have **two sources of shot position**: backend (`shot_spot` / animator) and frontend (local). Which one is used depends on (1) which handler we’re in and (2) which branch (WithStopper vs normal, and presence of `shot_spot`).

---

## Path Overview (Why It Feels Non–SS&S)

```
Backend (phase_resolution + animator)
├── resolve_fast_break_logic
│   ├── event_type DEFENSIVE_STOP → return (no shot)
│   └── event_type SHOT
│       ├── resolve_shot() → turn_result (MAKE/MISS/etc.)
│       ├── turn_result["animations"] = capture_fast_break_animation(...)
│       ├── turn_result["fast_break"] = True
│       └── turn_result["shot_spot"] = _bh_final_x/y  (only if not hold_up)
│
└── capture_fast_break_animation (animator)
    └── Ball handler end (bh_end):
        ├── ball_handler_beats_defender → near rim ✅
        ├── ball_handler_outlet_x/y set → outlet + 5–10  ❌ (used for shot attempt too!)
        └── else → hold_up ? top_key : near rim ✅
```

```
Frontend
├── determineHandler(turnData)
│   ├── isFastBreak (fast_break === true or result_type === "FAST_BREAK")
│   │   → handleFastBreak → runFastBreakSequence
│   └── else, isShotAttempt
│       → handleShotAttempt → ShotAnimationSystem (backend animations, shoot from current pos)
│
└── runFastBreakSequence (fastBreak.js)
    ├── result === "MAKE" | "MISS"
    │   ├── roles.ball_handler_beats_defender && stopper_id
    │   │   → animateFastBreakShotWithStopper  [IGNORES backend; local shot spot] ✅
    │   └── else
    │       → animateFastBreakShot  [Uses turnData.shot_spot if present, else local] ⚠️
    └── ...
```

So:

- **Two handlers** can see the same “fast break shot” (FAST_BREAK vs SHOT_ATTEMPT), and only one of them has a “move to rim then shoot” step.
- **Two places** define “where the shot is from”: backend animator (`bh_end` → `shot_spot`) and frontend (local in WithStopper; optional `shot_spot` in normal path).
- **One backend branch** (“outlet + additional_move”) is used for both defensive stop and shot attempt, so shot attempts with an outlet get a non-rim shot spot.

That’s why it works in some instances and fails in others, and why the process doesn’t feel SS&S.

---

## Streamlining Toward SS&S (Options to Consider)

### Option A: Backend as single source of “shot spot”

- **Backend:** For **shot attempts** (not hold_up), **always** set ball handler end (and `shot_spot`) to a **shot spot near the rim**, never “outlet + 5–10”. Use “outlet + 5–10” only for defensive-stop / non-shot outcomes.
- **Frontend:** Always use `turnData.shot_spot` when present for fast break shots; remove local random for shot position when we have a fast_break shot (so backend is the only source when it’s set).
- **Routing:** Ensure every fast break shot turn has a top-level `fast_break: true` (and optionally treat `roles.is_fast_break` as fallback so routing is robust). Then every fast break shot goes through the fast break handler and uses one source (backend) for shot position.

Effect: One place (backend) defines “where the fast break shot is taken”; frontend just displays it. Same path for all fast break shots.

### Option B: Frontend as single source of “shot spot”

- **Frontend:** For **all** fast break shot attempts (both WithStopper and normal), compute shot spot **locally** (near rim) and **ignore** `turnData.shot_spot` for positioning. Use backend only for outcome (MAKE/MISS), defender id, etc.
- **Backend:** Can keep current animator for analytics/consistency but frontend no longer uses `shot_spot` for fast break shot position.

Effect: One place (frontend fast break code) defines “where the fast break shot is taken”; backend drives outcome and roles, not position.

### Option C: Single handler + explicit “move to shot spot” step

- **Routing:** Ensure all fast break shots use the FAST_BREAK handler (e.g. always set `fast_break` and/or fallback to `roles.is_fast_break`).
- **Handler:** In that single handler, **always** do “move shooter (and defender) to shot spot near basket, then shoot.” Shot spot can be either from backend (if we fix backend to always send rim for shot attempts) or from frontend; pick one and stick to it.
- **SHOT_ATTEMPT:** Do **not** use backend step-by-step animations for fast break turns. Either never route fast break shots to SHOT_ATTEMPT, or have SHOT_ATTEMPT detect fast_break and delegate to the same “move to rim then shoot” logic.

Effect: One code path for “fast break shot”: one handler and one consistent “move to spot then shoot” step.

---

## Summary Table (Current Behavior)

| Backend: outlet set? | Backend: beats_defender? | Frontend route   | Frontend path        | shot_spot / position used     | Result   |
|----------------------|---------------------------|------------------|-----------------------|-------------------------------|----------|
| No                   | N/A                       | FAST_BREAK       | animateFastBreakShot  | Fallback / local rim          | ✅       |
| Yes                  | Yes                       | FAST_BREAK       | WithStopper           | Local rim (ignores backend)    | ✅       |
| Yes                  | No                        | FAST_BREAK       | animateFastBreakShot  | Backend shot_spot = outlet+5–10 | ❌     |
| Any                  | Any                       | SHOT_ATTEMPT     | ShotAnimationSystem   | Backend animations (outlet+5–10) | ❌   |

So: **shot spot animates properly** when we either ignore the backend (WithStopper) or when the backend sends a rim spot (no outlet or fallback). It **fails** when we trust the backend’s “outlet + 5–10” or when we follow backend animations in SHOT_ATTEMPT. Streamlining means choosing one owner for “where the fast break shot is taken” and one path that always runs the “move to shot spot near basket” step.
