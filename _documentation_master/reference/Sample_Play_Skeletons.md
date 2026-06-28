## Sample Play Skeletons (reference data)

A sampled, in-repo copy of play skeletons pulled **read-only** from `gob-staging` → `plays` collection (8 of 23 plays: all 4 motion + 4 representative set plays). Raw data: [Sample_Play_Skeletons.json](Sample_Play_Skeletons.json). Refresh with the script in the session scratchpad (`dump_skeletons.py`) if the collection changes.

### Document shape (`plays` collection)
```
play doc
├─ _id, name, play_type ("motion" | "set_play"), play_focus, target_shooter
└─ skeletons: { <variant>: { versions: [ { version, steps: [...] } ] } }
        motion   variants → "base_loop"
        set_play variants → "successful" | "mid_play_change" | "contested" | "broken"
        versions → a list (≥2) of alternate step-streams for that variant
step
├─ timestamp
├─ pos_actions: { <pos>: { location, action } }   # motion keys = PG/SG/...; set_play = pos1..pos5
└─ events
```

### Action vocabulary (seen in the sample)
`handle_ball` · `pass` · `receive` · `cut` · `screen` · `get_open` · `shoot` · `drift` · **`stationary`** · **`post_up`**

### ⭐ Hold-share finding (why HCO sprites read as "frozen")
**The holds are baked into the skeletons, not emergent from the dynamic resolver.** `stationary` + `post_up` dominate every play — off-ball players hold/space/post each step by design:

| play_type | play | holds (stationary+post_up) / total pos-actions |
|---|---|---|
| motion | PF Post Motion | 144 / 250 — **57%** |
| motion | 3-2 Motion | 114 / 260 — 43% |
| motion | 4-1 Motion | 96 / 160 — **60%** |
| motion | 5-0 Motion | 122 / 230 — 53% |
| set_play | Quick Midrange Jumper | 296 / 430 — **68%** |
| set_play | Double Screen Three – Wing | 210 / 550 — 38% |
| set_play | Base Post Play | 148 / 380 — 38% |
| set_play | Pick & Roll – Entry Pass | 216 / 520 — 41% |

**Implication:** ~40–68% of per-step player actions are holds. That's *correct* basketball spacing (only 1–2 players are active per beat; the rest hold position), but rendered as perfectly-still sprites it looks dead. The fix is **render-only idle micro-motion** on held sprites — NOT editing the skeletons (their stationary spacing + timing are intentional and shared by motion *and* set plays). See [Dynamic_HCO_System.md](../06_Gameplay_Systems/Dynamic_HCO_System.md).
