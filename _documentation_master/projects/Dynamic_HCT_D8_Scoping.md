# Dynamic HCT — D8 Scoping (Fouls / Steals / Turnovers / Interceptions)

**Status:** ✅ **Core built (Cut 2 / D8a).** The attribute-driven moment model
(`STEAL` / `DEAD BALL` / `O_FOUL` in the defense-wins region, `D_FOUL` in the
offense-wins region) is implemented in `BackEnd/engine/dynamic_hct.py`
(`_resolve_moment` + the loop's `_apply_moment_outcome`), wired through the
wrapper (`_resolve_half_court_trap_dynamic_first_cut` — stats, foul-out, bonus
free-throw routing, steal→fast-break, possession flips) and the emitter
(`_resolve_final_step_next` → `STEAL` / `FOUL` turn-stops). Hold's
defender-reaches path now uses the same contest engine (Hold unification).
**Deferred to D8b (still open in §6):** D11 mid-flight interception, D20
over-and-back, and final coefficient calibration (Q7).

**Parent specs:** `Dynamic_HCT_Turns.md` (§5 moment resolution, §8 outcomes),
`Dynamic_HCT_Cut2_Plan.md`. **Closes:** the foul/steal-stat parity folded out of
D16, plus D11 (mid-flight interception) and the detection half of D20
(over-and-back).

---

## 0. Decisions log (resolved with design owner)

- **Trigger style (was Q1): ATTRIBUTE-DRIVEN.** Outcomes are derived from player +
  team attributes each moment (not a flat weighted-random table). See §3.
- **Where outcomes fire (Q7):** every **pressure/trap moment** (fouls + steals +
  dead balls) **+ pass interception (D11)**. Drive-contact fouls (charge / strip on
  a drive) **deferred** — the attack/drive path already books **shooting fouls** on
  the shot.
- **Per-moment evaluation:** the check runs at **every** moment (compute is
  negligible — it's arithmetic on scores we already compute). The real control is a
  **global per-moment rate scalar** so multi-moment possessions don't compound into
  too many turnovers.
- **Foul attribution:** literal — the **actual involved participant** from the
  moment (the trapper / BH-defender for `D_FOUL`, the BH for `O_FOUL`). The dynamic
  loop knows the real participants, so we don't need the skeleton's positional
  guess (`select_foul_player`).
- **Model mechanics:** attributes set per-event **odds**; a single RNG draw picks
  the outcome (variety preserved; better rosters genuinely foul/steal less/more).
- **Team attributes in play:** def `discipline` (↓ → more reach fouls; ↑ → cleaner
  steals / drawn charges), def `pt_efficiency` (↑ → more forced steals/TOs), off
  `pt_opp_modifier` (↑ → better ball security, fewer self-TOs).
- **Aggression game-plan dial:** the 0–4 `aggression` slider (resolved per turn to
  `aggression_call` ∈ passive/normal/aggressive via `STRATEGY_CALL_DICTS`) is the
  **established defensive lever** for steals/fouls elsewhere (HCO steal rate, help
  defense ±20%, post-steal fast break).   D8 wires it as a **trade-off** multiplier
  `AGG_MULT` (passive 0.7 / normal 1.0 / aggressive 1.3) on the **event-fire rate**
  (§3.1a), the **steal share** (§3.1b), **and** `p_dfoul` (§3.2). So aggression
  **does not change the chance of winning the moment**, but a winning aggressive
  defense forces a takeaway **more often** and skews it toward **steals**, while a
  *beaten* aggressive defense **fouls more**. Passive = fewer takeaways, fewer fouls,
  contain. Distinct from roster attributes (discipline / pt_efficiency = *who the
  players are*; aggression = *the dial the coach turns*). Also governs the steal →
  fast-break aftermath (Q3).
- **Offense `fight` (resists takeaways):** the **offense** team's `fight` (centered at
  0, ±10) reduces the chance that **any** D-wins event (steal / dead ball / o-foul)
  fires, applied at the **event-fire gate** `p_event` (§3.1a) with `W_FIGHT = 0.04` —
  the **same scale** as defense `discipline` on D_FOUL. `+10 fight → ~40% fewer`
  takeaways on a D-win; `−10 → ~40% more`. It does **not** change the mix among the
  three (it sits at the gate, above the normalized split). **Only offense `fight`** is
  used; defense `fight` is intentionally excluded.
- **Hold reconciliation (one contest engine):** Hold's "a defender reaches the BH"
  currently uses a *separate* 50/50 steal → 50/50 foul hardcode (spec §5 Hold
  resolution). D8 **unifies** this with Attack: when a defender (or a second
  defender → trap) reaches the held BH, run the **same attribute-driven
  `_resolve_moment` calculation** (§3) instead of the old 50/50. So steal/foul/TO
  odds come from attributes regardless of whether the contact arose from an
  **attack** decision or a **hold**. (Hold still has its own *structure* — the 1–3s
  window, who-arrives gating, and the "no defender arrives → broken-HCT attack"
  branch; only the *contest math* is unified.)

> Terminology note: the **resolution** logic (stat recording, FT/bonus routing,
> steal aftermath) is plain reusable functions — no animation "skeleton" needed.
> The **animation** of a foul/steal is built **procedurally in the emitter** (the
> dynamic path sets `skeleton = {}`); there is no pre-authored skeleton to reuse.

---

## 1. Goal

The dynamic HCT loop currently produces only two terminal non-shot outcomes:
**DEAD BALL** (turnover) and **HCO** (trap broken). D8 adds the remaining
*emergent* outcomes that the old skeleton path produced from a weighted-random
table, so the dynamic loop reaches behavioral + stat parity with the skeleton and
with real basketball:

| Outcome | Who/what | Stat effects | Next play |
| --- | --- | --- | --- |
| `D_FOUL` (defensive foul) | a trapping/pressuring defender | `F` + `team_fouls` (def), foul-out check, bonus → FTs | FREE_THROW (in bonus) or SIDE_INBOUND |
| `O_FOUL` (offensive foul) | BH (charge/push-off) | `F` + `team_fouls` (off), foul-out check; def HCT success | SIDE_INBOUND (possession flips) |
| `STEAL` | BH defender / trapper | BH `TO`, defender `STL`, `last_stealer`(+coords); def HCT success | FAST_BREAK or HCO |
| **Mid-flight interception (D11)** | an off-ball defender on a pass in the air | passer `TO`, defender `STL`; def HCT success | FAST_BREAK or HCO |
| **Over-and-back detection (D20)** | BH (illegal backward pass past x=50) | BH `TO`; def HCT success | SIDE_INBOUND |

(DEAD BALL and HCO already exist and are untouched except where noted.)

---

## 2. Current state — the seam

All non-shot outcomes are decided in **one** function:

```334:373:BackEnd/engine/dynamic_hct.py
def _resolve_moment(... ) -> Tuple[str, float]:
    ...
    if d_score > o_score + 2 * (off_chem + pt_opp):
        return "DEAD BALL", random.uniform(0.2, 0.8)
    if o_score >= d_score + 2 * (def_chem + pt_eff):
        return "POS_O", 1.0
    return "NEUTRAL", 1.0
```

- **`d_score`** = `calculate_defender_pressure_score(bh_defender, "man")` (+ `0.5×`
  trapper on a trap) + `pt_eff × rand(1,6)`.
  Pressure formula: `OD*0.3 + AG*0.3 + IQ*0.2 + CH*0.2`, `×rand(1,6)`, zone `×0.9`.
- **`o_score`** = `calculate_ball_handling_score(BH)` (`BH*0.5 + AG*0.2 + IQ*0.2 +
  CH*0.1`), optionally `× (pt_opp × rand(1,6))`.

D8's foul/steal branches attach **here** (the `DEAD BALL` and `POS_O` bands are the
natural homes — see §3). The wrapper (`phase_resolution._assemble_*` /
`_resolve_half_court_trap_dynamic_first_cut`) then needs to translate the new
result_types into the same downstream fields the skeleton sets.

### Skeleton reference (what we're matching)

```7489:7499:BackEnd/engine/phase_resolution.py
    if (offenseScore + BSM) > defenseScore:
        if offenseScore - defenseScore > DST:
            result_type = random.choices(["D_FOUL", "HCO", "SHOT"], weights=[0.3, 0.4, 0.3])[0]
        else:
            result_type = "HCO"
    else:
        result_type = random.choices(["O_FOUL", "DEAD_BALL_TURNOVER", "STEAL"], weights=[0.2, 0.5, 0.3])[0]
```

So in the skeleton: **failure → {O_FOUL 20% / DEAD_BALL 50% / STEAL 30%}**;
**dominant success → {D_FOUL 30% / HCO 40% / SHOT 30%}**. The reusable aftermath
helpers already exist: `select_foul_player`, `check_and_handle_foul_out`,
`fast_break_probability_from_slider`, `last_stealer`/`last_stealer_coords`, and the
Steal-FB setup.

---

## 3. Resolved model — attribute-driven per-moment resolution

The loop already computes, at every moment (`_resolve_moment`):

- `m = d_score − o_score` — the **contest margin** (positive ⇒ defense winning).
- The existing **band gates** stay as the structural fork:
  - **defense-wins** region: `m > GATE_D`, `GATE_D = 2*(off_chem + pt_opp)`
  - **offense-wins** region: `o_score ≥ d_score + 2*(def_chem + pt_eff)` → POS_O
  - else **neutral** (no foul/steal — the "re-read" beat).

Inside the defense-wins / offense-wins regions we now compute **attribute-derived
event odds** instead of forcing a single result.

### 3.1 Defense-wins region → {STEAL, DEAD BALL, O_FOUL, no-event}

Two-step: (a) does *anything* terminal happen this moment, (b) if so, which event.

**(a) Does an event fire?**

```
m_norm   = clamp(m / M_REF, 0, 1)                  # how decisively D won the moment
p_event  = clamp(DEF_WIN_BASE * m_norm
                 * AGG_MULT[aggression_call]       # aggressive D forces MORE total events
                 * (1 - W_FIGHT * fight_off)       # gritty OFFENSE (fight↑) resists ALL D-wins events
                 * GLOBAL_SCALAR, 0, P_EVENT_MAX)
# fight_off = OFFENSE team `fight` (centered at 0, ±10). Applied at the gate (not the
# per-event scores) so it lowers the chance ANY steal/db/o-foul fires — equally — which
# is why it can't sit inside the normalized split. W_FIGHT == W_DISC_REACH (same scale
# as defense `discipline` on D_FOUL). Defense `fight` is NOT used.
```

Roll `random() < p_event`. If false → **no-event** (BH retains; falls through to the
normal advance/hold re-read). This is the per-moment rate knob. Aggression scales it,
so an aggressive defense forces a takeaway/foul **more often** (not just a different
mix). Note steals therefore get **double leverage** from aggression — more total
events (here) **and** a larger share of them (`steal_factor`, §3.1b) — which is the
intended "gamble hard for steals" behavior (one tunable `AGG_MULT`).

**(b) Which event** — **anchored baseline weights × attribute factors**, normalized,
one draw. Each factor is **centered at 1.0 for an even matchup**, so an average
defender vs. average BH (and team attrs ≈ 0) reproduces the baseline split exactly;
better/worse players swing it from there.

```
# Baseline weights for an even matchup (design owner: DB 50 / STEAL 30 / O_FOUL 20)
DB_W0, STEAL_W0, OFOUL_W0 = 50, 30, 20

defr = bh_defender                                   # (trap: the steal-credit defender)

# Player attribute composites (same ~0..100 scale as the attrs):
def_steal = OD*0.4 + AG*0.4 + IQ*0.2     [defr]      # defender's strip ability
bh_secure = CH*0.4 + BH*0.4 + IQ*0.2     [BH]        # BH's ball security
bh_handle = BH*0.4 + CH*0.3 + IQ*0.3     [BH]        # BH's clean-handle (self-TO resistance)

# Factors centered at 1.0 (clamped to [F_MIN, F_MAX]):
steal_factor = clamp((1 + S_SENS  * (def_steal - bh_secure)/REF
                        + W_PTEFF * pt_efficiency)
                       * AGG_MULT[aggression_call],        F_MIN, F_MAX)   # gap + def pressure + game-plan dial
db_factor    = clamp(1 + DB_SENS * (REF - bh_handle)/REF
                       - W_PTOPP * pt_opp_modifier,        F_MIN, F_MAX)   # weak handle, minus ball-protection
ofoul_factor = clamp(1 + O_SENS_IQ   * (IQ[defr] - IQ[BH])/REF            # smart D vs reckless BH draws charge
                       + O_SENS_DISC  * discipline / DISC_SCALE,  F_MIN, F_MAX)

steal_w = STEAL_W0 * steal_factor
db_w    = DB_W0    * db_factor
ofoul_w = OFOUL_W0 * ofoul_factor
P(event) = w / (steal_w + db_w + ofoul_w)
```

Result types: `STEAL` (live ball), `DEAD BALL` (dead, self-TO), `O_FOUL` (offensive
foul, possession flips).

> **Centering caveat:** `steal_factor` uses a *difference* between two players, so it
> is robust to the absolute scale (an even matchup → 1.0 regardless of league mean).
> `db_factor` and the `ofoul` IQ term use an absolute reference `REF` — set `REF` to
> the **league-average attribute value** during calibration so an average BH actually
> lands on the baseline. (`discipline` is already centered at 0, so its term needs no
> reference.)

### 3.2 Offense-wins region → mostly POS_O, small D_FOUL

When the BH decisively beats the pressure, the beaten defender occasionally hacks:

```
beaten_norm = clamp((o_score - d_score) / M_REF, 0, 1)
agility_gap = clamp(AG[BH] - AG[defr], 0, REF)            # how badly the D got beaten
p_dfoul = clamp( DFOUL_BASE * beaten_norm
               * (1 - W_DISC_REACH * discipline_def)      # discipline centered at 0:
                                                          #   undisciplined (<0) → more reach fouls
               * (1 + W_AG_BEATEN  * agility_gap / REF)   # slow/beaten defender → reach
               * AGG_MULT[aggression_call]                # game-plan dial: aggressive → more reach fouls
               * GLOBAL_SCALAR, 0, P_DFOUL_MAX )
```

Roll `random() < p_dfoul` → **D_FOUL** (the involved defender; bonus → FTs, else
SIDE_INBOUND). Else → **POS_O** (advance, unchanged). Baseline (even matchup,
`discipline = 0`, decisive blow-by): `p_dfoul ≈ DFOUL_BASE`.

### 3.3 First-pass tunable constants (calibrate against sim output)

| Const | Meaning | First-pass |
| --- | --- | --- |
| `DB_W0 / STEAL_W0 / OFOUL_W0` | **even-matchup baseline split** (→ 50% / 30% / 20%) | `50 / 30 / 20` |
| `AGG_MULT` | game-plan aggression dial → steal weight + D_FOUL prob | `passive 0.7 / normal 1.0 / aggressive 1.3` |
| `GLOBAL_SCALAR` | master per-moment event-frequency knob | `1.0` |
| `DEF_WIN_BASE` | base P(any event) when defense fully wins a moment | `0.35` |
| `P_EVENT_MAX` | cap on per-moment event prob | `0.60` |
| `M_REF` | margin that counts as a "decisive" win | `25` |
| `REF` | league-average attribute (centering for absolute terms) | `50` |
| `F_MIN / F_MAX` | clamp on each attribute factor | `0.3 / 2.5` |
| `S_SENS` | steal sensitivity to (defender − BH) gap | `1.2` |
| `DB_SENS` | dead-ball sensitivity to weak BH handle | `1.0` |
| `O_SENS_IQ` | charge sensitivity to (defender IQ − BH IQ) | `0.8` |
| `O_SENS_DISC` | charge sensitivity to team `discipline` | `0.5` |
| `DISC_SCALE` | discipline normalizer (team attrs ≈ ±10) | `20` |
| `W_PTEFF` | def `pt_efficiency` → steal factor | `0.04` |
| `W_PTOPP` | off `pt_opp_modifier` → resist self-TO | `0.04` |
| `DFOUL_BASE` | base P(D_FOUL) on a decisive blow-by | `0.12` |
| `P_DFOUL_MAX` | cap on D_FOUL prob | `0.25` |
| `W_DISC_REACH` | team `discipline` → fewer reach fouls (D_FOUL) | `0.04` |
| `W_FIGHT` | OFFENSE `fight` → fewer D-wins events (steal/db/o-foul) | `0.04` (= `W_DISC_REACH`) |
| `W_AG_BEATEN` | defender AG deficit vs BH → reach foul | `0.6` |

> All coefficients live in one constants block so balancing is a single-file edit.
> `pt_opp_modifier == 0` / `pt_efficiency == 0` / `discipline == 0` are no-ops
> (factor 1), consistent with team attrs being centered at 0.

### 3.4 Resulting percentages (what these constants produce)

**Defense-wins region** — two layers:

- **Does anything fire?** At a *decisive* win (`m ≥ M_REF`), `normal` aggression:
  `0.35` → **~35% an event fires, ~65% no-event** (BH retains, loop continues).
  Scales down with a narrower margin (`m_norm = 0.5` → ~17.5%), **with
  aggression** (passive ~24.5%, aggressive ~45.5%), and **with offense `fight`**
  (`+10 → ~21%`, `−10 → ~49%` at normal aggression — the gritty offense protects the
  ball).
- **Which event** (given one fires), worked examples:

| Matchup | STEAL | DEAD BALL | O_FOUL |
| --- | --- | --- | --- |
| **Average / even** (baseline) | **30%** | **50%** | **20%** |
| Elite ball-stopper (OD/AG/IQ ≈ 80) vs avg BH | ~40% | ~39% | ~21% |
| Weak ball handler (BH/CH ≈ 30) vs avg defender | ~32% | ~50% | ~17% |

> Combined (unconditional, decisive D-win): multiply by ~35% — e.g. baseline ≈ STEAL
> 10.5% / DEAD BALL 17.5% / O_FOUL 7% per decisive-win moment, with ~65% no-event.

> **Aggression swing.** `AGG_MULT` scales **both** the event-fire rate (§3.1a) **and**
> the steal share (§3.1b). Unconditional per decisive-win moment, even matchup:
>
> | Aggression | event fires | STEAL | DEAD BALL | O_FOUL | no-event |
> | --- | --- | --- | --- | --- | --- |
> | passive (×0.7) | ~24.5% | ~5.7% | ~13.4% | ~5.4% | ~75.5% |
> | normal (×1.0) | ~35% | ~10.5% | ~17.5% | ~7.0% | ~65% |
> | aggressive (×1.3) | ~45.5% | ~16.3% | ~20.9% | ~8.3% | ~54.5% |
>
> So aggressive = more of **every** takeaway type (steals most of all), at the cost of
> more reach fouls when beaten (below).

**Offense-wins region** — `D_FOUL` vs clean POS_O:

| Matchup | D_FOUL | clean POS_O |
| --- | --- | --- |
| Even, decisive blow-by, `discipline = 0` | **~12%** | ~88% |
| Undisciplined D (`discipline = −10`), big AG gap | up to **25%** (cap) | ≥75% |
| Disciplined D (`discipline = +10`) | ~7% | ~93% |

> `AGG_MULT` also scales D_FOUL: the even-matchup ~12% becomes ~15.6% (aggressive)
> or ~8.4% (passive).

> These are **first-pass**; final values get tuned against simulated possession-level
> turnover/foul/steal rates (open item §6 Q7). `agility_gap` (§3.2) =
> `clamp(AG[BH] − AG[defr], 0, REF)`.

### 3.5 Foul attribution (resolved — literal)

- `D_FOUL` → the **involved defender** (`bh_defender`; on a trap, the participant
  the model credited). `record_stat("F")`, `def_team.team_fouls += 1`, foul-out
  check, bonus routing.
- `O_FOUL` → the **BH**. `record_stat("F")`, `off_team.team_fouls += 1`, foul-out
  check; counts as a defensive HCT success.

---

## 4. Mid-flight interception (D11) & over-and-back (D20)

These don't live in `_resolve_moment`; they attach to the **pass** path:

- **D11 (interception):** when the §6 pass fires, roll whether an off-ball
  defender on/near the pass lane picks it off mid-flight. Needs: which defenders
  are eligible (proximity to the passing lane), the trigger formula, where the
  ball/defender ends up, and the post-steal routing (FB vs HCO). Reuses the steal
  aftermath. *(Open: do we model lane geometry, or approximate with a flat/per-
  defender probability for the first cut? — Q5.)*
- **D20 (detection):** the *preventive guard* already exists (`_select_pass_receiver`
  avoids a backward pass when a forward option exists). D8 adds the **violation**
  for the residual case — BH has crossed x=50 and the *only* available/forced pass
  is backward (to x<50 home / x>50 away). Tag it over-and-back → DEAD BALL → SIP.
  *(Open: is "no legal forward option" actually reachable, and is the fallback a
  forced violation or a held ball? — Q6.)*

---

## 5. Implementation sketch (post-sign-off)

1. **Engine** (`dynamic_hct.py`):
   - Extend `_resolve_moment` to return the new result_types (e.g.
     `"STEAL" | "O_FOUL" | "D_FOUL"` alongside `DEAD BALL`/`POS_O`/`NEUTRAL`),
     carrying the chosen offender/defender + (for steal) the live-ball flag.
   - Pass path: add the D11 interception check; add the D20 forced-backward check.
2. **Resolvers / wrapper** (`phase_resolution.py` / `dynamic_hct_shot.py`):
   - New assembler branches that set `foul_team`, foul player (`F`, `team_fouls`,
     foul-out, bonus→FREE_THROW), `STL`/`TO`/`last_stealer`(+coords), `turnover_type`
     where relevant, `possession_flips`, and `next_play_type`
     (FREE_THROW / SIDE_INBOUND / FAST_BREAK / HCO) — porting the skeleton blocks at
     `phase_resolution.py:7733-7798` & `7858-7869`.
3. **Emitter** (`dynamic_hct_emitter`): stopper/foul/steal end-steps (reuse the
   skeleton's stopper-step + Steal-FB choreography).
4. **Stats:** falls out automatically once the outcomes exist → closes the D16
   foul/steal leftovers.
5. **Verify:** offline smoke tests forcing each band/outcome (monkeypatch the
   sub-split RNG/formula), assert stat deltas + `next_play_type`.

---

## 6. Open questions

### Resolved (see §0 decisions log)

- **Q1 trigger style** → attribute-driven (§3).
- **Q2 band weights** → superseded by §3 attribute formulas + tunable constants.
- **Q7 where outcomes fire** → moments + pass interception; drive fouls deferred.
- **Q8 foul attribution** → literal involved participant (§3.5).
- **Per-moment evaluation + global rate scalar** → yes (`GLOBAL_SCALAR`, §3.3).
- **Model mechanics** → attribute-derived odds + single roll; first-pass
  coefficients in §3.3 to calibrate against sim output.

### Still open (defaults proposed; confirm or override)

3. **Steal → fast break.** Reuse `fast_break_probability_from_slider(def
   aggression)` exactly as the skeleton does? **Default:** yes.
4. **Foul → free throws.** Reuse the skeleton's bonus logic verbatim (≥10 = 2 FT,
   5–9 = 1-and-1, <5 = possession/SIDE_INBOUND)? **Default:** yes.
5. **D11 interception model.** Lane-geometry-based eligibility + formula, or a
   simpler per-eligible-defender probability (attribute-scaled like §3) for the
   first cut? **Default:** attribute-scaled probability for the nearest off-ball
   defender to the pass line, refine geometry later.
6. **D20 forced backward pass.** Is "BH past half + only backward option" actually
   reachable given the preventive guard? If so, is the outcome a **violation**
   (turnover → SIP) or a **held ball** (re-loop)? **Default:** forced backward pass
   = over-and-back violation; no target at all = hold/re-loop.
7. **Coefficient calibration.** Sign off on the §3.3 first-pass constants as a
   starting point (then tune against sim turnover/foul/steal rates)? **Default:**
   yes, ship the first-pass values and calibrate empirically.

---

## 7. Out of scope for D8

- Per-tick energy decay (D12), seeded RNG (D13), distant-sim short-circuit (D14).
- Drive-contact fouls (offensive charge / strip on a drive) — deferred per Q7;
  the attack/drive path already books **shooting** fouls on the shot.
- Lane-geometry interception model (D11 ships attribute-scaled first; geometry later).
