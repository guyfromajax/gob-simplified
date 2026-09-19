# equiv-v3 references

Each file is a frozen baseline of the equiv-v3 worker at one tree: per-seed rows for
seeds 8000–8039, both arms, and (from `..._merged` onward) both footings in one file.

**Use the newest non-superseded reference.** A superseded file is kept, never deleted —
it is what the matching kill switch reproduces, which is how a rollback is verified.

## Footing (every reference)

equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id
`0xE0000+(seed-8000)`, n=40 seeds 8000–8039, CI = 1.96 × SEM. **sim arm** =
`_is_full_simulation` True throughout; **played arm** = False only inside the four gated
Animator methods at Pattern A.

## Current

| file | tree | what it baselines |
|---|---|---|
| **`equiv_v3_reference_ec4f5acfc_poslookup2.json`** | `ec4f5acfc` | **CURRENT, both arms.** Positions resolved by lineup identity across the backend (`GOB_LINEUP_POSITION_LOOKUP` ON). The played arm is byte-identical to the previous reference on both footings; the sim arm differs on exactly one seed per footing (8002 at `SEED_DEFENSES=1`, 8038 at `=0`), both from `turn_manager._execute_forced_shot` no longer letting an off-offense `last_ball_handler` take the forced shot under the PG label. |

## Superseded — kept deliberately

| file | tree | superseded by | reproduced today by |
|---|---|---|---|
| `equiv_v3_reference_456e2cdd9_reboundarrival.json` | `456e2cdd9` | `ec4f5acfc` | `GOB_LINEUP_POSITION_LOOKUP=0` — verified 40/40 on all four cells at `ec4f5acfc` |
| `equiv_v3_reference_bf7ed1181_crashmodela.json` | `bf7ed1181` | `456e2cdd9` | `GOB_REBOUND_FROM_ARRIVAL=0` — verified 40/40 on all four cells at that flip |
| `equiv_v3_reference_d91679bef_foulweight.json` | `d91679bef` | `bf7ed1181` | `GOB_CRASH_SHOT_AWARE=0` — verified 40/40 at that flip |
| `equiv_v3_reference_c1958f8f6_rings.json` | `c1958f8f6` | `d91679bef` | `GOB_FOUL_ON_BALL_WEIGHT=0` — verified 40/40 at that flip |
| `equiv_v3_reference_1fd08c080_zonesink.json` | `1fd08c080` | `c1958f8f6` | `GOB_ZONE_SINK=0` reproduces the pre-sink rings tree 40/40 |
| `equiv_v3_reference_29e6a6792_merged.json` | `29e6a6792` | `c1958f8f6` | the develop merge before the zone rings were repaired; kept so develop's own contribution stays separable |
| `equiv_v3_sim_reference_9910cd6fd.json` | `9910cd6fd` | `c1958f8f6` | **sim arm only.** The played reference of that era was the commit `d9a4f1517`, not a file. |
| `equiv_v3_sim_reference_4f856721a.json` | `4f856721a` | `9910cd6fd` | **no longer reachable.** `GOB_SIM_CRASH_APPLY=0 GOB_SIM_CRASH_CLOCK=0` still disables the crash work, but zone placement changed underneath it, so the flags-off path is a switch, not a time machine. |

## When you cut a new one

1. Verify the kill switch first: the previous reference must still reproduce **40/40 on
   all four cells** with the new flag off. If it does not, the change is not
   flag-isolated and the flip should stop.
2. Cut the reference, then **run the worker a second time and confirm the new reference
   reproduces 40/40 byte-identical** — a double re-baseline. A reference that cannot
   reproduce itself is not a reference.
3. Add the row above, move the old file to *Superseded*, and record which flag setting
   reproduces it. **Do not delete the old file.**
