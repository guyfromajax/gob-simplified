# Computer timeout vs autoset lineup conditions (side-by-side)

Reference: **Insert into lineup** = `is_player_eligible_for_lineup` / `build_lineup_from_mongo` in `BackEnd/utils/db_utils.py`. **Call timeout** = `should_computer_call_timeout` in `BackEnd/models/turn_manager.py`.

---

## Fouls (per quarter)

| Quarter | Insert into lineup (max fouls allowed in lineup) | Call timeout (foul triggers) |
|---------|---------------------------------------------------|-------------------------------|
| **Q1**  | Max **1** foul (DEFAULT_FOUL_LIMITS_BY_QUARTER). 5+ = fouled out, never eligible. | **3 fouls** → 100% timeout.<br>**2 fouls** → 30% timeout. |
| **Q2**  | Max **2** fouls. 5+ = fouled out. | **4 fouls** → 100% timeout.<br>**3 fouls** → 90% timeout. |
| **Q3**  | Max **3** fouls. 5+ = fouled out. | **4 fouls** → 100% timeout.<br>**3 fouls** → 90% timeout. |
| **Q4**  | Max **3** fouls when `time_remaining > 240`; no per-quarter limit when `time_remaining ≤ 240` (only 5-foul out). 5+ = fouled out. | **4 fouls** → 90% timeout, **only if** `time_remaining > 60` s. |

**Q4 / OT note for lineup:** When `quarter == 4` and `time_remaining < 240` or `quarter > 4`, lineup eligibility drops the per-quarter foul cap (only 5-foul out applies) and energy threshold becomes **0.64** (see below).

---

## Energy (NG) – all quarters

| Aspect | Insert into lineup | Call timeout |
|--------|--------------------|--------------|
| **Default threshold** | NG **≥ 0.8** (80%) to be eligible. If **late Q4 or OT** (`quarter==4` and `time_remaining < 240`, or `quarter > 4`): NG **≥ 0.64** (64%). | Count **active lineup** players below 80%, 70%, 60% NG; each count can trigger (once per quarter) with a probability. |
| **Effect** | Players with NG &lt; 0.8 (or &lt; 0.64 in late Q4/OT) are **excluded** unless the lineup waterfall relaxes. | **3** players &lt; 80% NG → 50%; **4** → 75%; **5** → 90%.<br>**3** &lt; 70% → 80%; **4** → 90%; **5** → 95%.<br>**3** &lt; 60% → 100%. |

**Waterfall (lineup only):** If fewer than 5 eligible with default rules, eligibility is relaxed in steps: NG threshold 0.8 → 0.6 → 0.4 → 0.2 → 0, then foul limits per quarter increased by 1 per step (capped at 4). So a **relaxed** lineup can include players with NG &lt; 0.8 and thus **immediately** satisfy “3+ players &lt; 80% NG” (and lower thresholds) on the first BIP/SIP.

---

## Where they conflict (lineup can instantly meet timeout conditions)

1. **Q2:** Lineup allows up to **2** fouls. Timeout checks **3** and **4** fouls. So at start of Q2, no foul-based timeout from the lineup we just built. ✓ Aligned.
2. **Q3:** Lineup allows up to **3** fouls. Timeout has **3 fouls → 90%**. So we **can** put a 3-foul player in at quarter break; first BIP/SIP can trigger “3 fouls” timeout. **Misaligned.**
3. **Q4:** Lineup allows up to **3** fouls (when `time_remaining > 240`). Timeout only checks **4 fouls** (and only if `time_remaining > 60`). So at start of Q4 we don’t have 4-foul players in the lineup. ✓ Aligned for first dead ball.
4. **Q1:** Lineup allows max **1** foul. Timeout checks **2** and **3** fouls. So at quarter start we don’t put 2/3-foul players in. ✓ Aligned.
5. **Energy:** With **default** rules, lineup has everyone ≥ 80% NG, so we never have 3+ below 80% from a fresh build. With **waterfall** relaxation we can have many below 80% (and 70%, 60%), so we **can** instantly satisfy energy timeout conditions. **Misaligned when waterfall is used.**

---

## Summary table (per quarter)

| Quarter | Insert: max fouls | Call timeout: foul triggers | Aligned? | Insert: energy | Call timeout: energy | Aligned? |
|---------|-------------------|----------------------------|----------|---------------|----------------------|----------|
| Q1     | 1                 | 2 (30%), 3 (100%)          | ✓ Yes    | ≥ 0.8 (or 0.64 late) | 3+ &lt;80%, 3+ &lt;70%, 3 &lt;60% | ✓ Default; ✗ if waterfall |
| Q2     | 2                 | 3 (90%), 4 (100%)          | ✓ Yes    | same          | same                 | ✓ Default; ✗ if waterfall |
| Q3     | 3                 | 3 (90%), 4 (100%)          | ✗ **No** – 3-foul in lineup | same | same                 | ✓ Default; ✗ if waterfall |
| Q4     | 3 (or none if late) | 4 (90%, if time &gt; 60s)  | ✓ Yes    | same          | same                 | ✓ Default; ✗ if waterfall |

So the two concrete misalignments to fix in autolineup are:

- **Q3:** Do not put players with **3 fouls** in the lineup at quarter start (or otherwise avoid triggering the “3 fouls → 90%” check on the first dead ball), **or** tighten the timeout rule (e.g. don’t call for 3 fouls in the first minute of Q3).
- **Energy (any quarter):** When using the **waterfall**, avoid building a lineup that has 3+ players below 80% NG (or 3+ below 70%, or 3 below 60%) so the first BIP/SIP doesn’t instantly trigger an energy-based timeout. Options: tighten relaxed NG so we never put 3+ below 0.8 in the same lineup, or add a “minimum time elapsed” gate before evaluating energy timeouts.
