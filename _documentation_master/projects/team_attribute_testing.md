# Team Attribute Testing — rail distribution across a season

Tracks where the **core-8 team attributes** sit as a season runs, under CPU identity-driven
training. The question is whether teams develop distinct personalities (spread toward both
rails) or converge (everyone pinned at the same ceiling).

**Franchise:** `6a7f1acc7d319324cd3259ab` — created 2026-08-14 on `15be0e8b1`, the first
franchise to run an entire season on one configuration (identity-driven allocation, two modes,
1-skill focus emphasis, 16 rotating coaching focuses).

**Range:** all core-8 attributes clamp to `(-20, 20)`. 128 teams × 8 attributes = **1,024
attribute slots** per snapshot.

**Saturation taper:** allocation stops spending on an install once its target attribute nears
the ceiling — full points below +17, capped at +18/+19, dropped at +20. Allocation-side only;
the clamp already discarded those points, this just stops wasting them.

---

## Week 13 — midseason

| attribute | ≤ −20 | −19..−17 | +17..19 | ≥ +20 | mean |
|---|--:|--:|--:|--:|--:|
| `offensive_efficiency` | 6 | 2 | 33 | **31** | +8.0 |
| `defensive_efficiency` | 4 | 4 | 16 | **47** | +9.7 |
| `pt_efficiency` | **18** | 5 | 14 | 25 | +1.6 |
| `discipline` | 5 | 5 | 12 | 5 | +3.3 |
| `fb_efficiency` | 1 | 4 | 11 | 15 | −0.8 |
| `fight` | 3 | 0 | 8 | 4 | +3.1 |
| `pt_opp_modifier` | 0 | 0 | 21 | 19 | +3.4 |
| `fb_opp_modifier` | 0 | 0 | 0 | 0 | −5.3 |

**Totals:** bottom (≤ −17) **57/1024 = 6%** · top (≥ +17) **261/1024 = 25%**
**37 floored at −20 · 146 maxed at +20**

### Read

**The league drifts upward.** Six of eight attributes have a positive mean, and the top rail is
four times as populated as the bottom. Teams gain more than they lose.

**`pt_efficiency` is the only genuinely bipolar attribute** — 18 floored *and* 25 maxed. Press
teams build it hard while everyone else lets it rot. That is the clearest evidence in the table
that identity is producing personalities rather than a uniform league.

**`fb_opp_modifier` never moves** — 0 at either rail, no team above +17, mean −5.3. The only
attribute developing no personality at all. Either nothing trains it meaningfully or its EOG
band is much weaker than the rest. **Open question.**

### What to watch in the back half

At 146 maxed by week 13, if that reaches 300+ by week 26 then most of the league is pinned at
the ceiling on its identity attributes — and identity stops differentiating, because every press
team is equally maxed. The taper redirects those points rather than wasting them, so the risk is
flattening, not waste. May self-limit; unknown.

---

## Week 26 — end of regular season

| attribute | ≤ −20 | −19..−17 | +17..19 | ≥ +20 | mean |
|---|--:|--:|--:|--:|--:|
| `offensive_efficiency` | 22 | 5 | 35 | **40** | +7.5 |
| `defensive_efficiency` | 14 | 2 | 38 | **46** | +10.3 |
| `pt_efficiency` | **32** | 5 | 17 | 28 | +1.3 |
| `discipline` | 12 | 12 | 19 | 33 | +4.7 |
| `fb_efficiency` | **31** | **22** | 16 | 14 | −5.6 |
| `fight` | 10 | 3 | 19 | 30 | +7.0 |
| `pt_opp_modifier` | 2 | 8 | 25 | 19 | +0.2 |
| `fb_opp_modifier` | 4 | 11 | **0** | **0** | **−10.8** |

**Totals:** bottom (≤ −17) **195/1024 = 19%** · top (≥ +17) **379/1024 = 37%**
**127 floored at −20 · 210 maxed at +20**

### Week 13 → 26: the league SPREAD, it did not converge

| | wk 13 | wk 26 | change |
|---|--:|--:|--:|
| bottom (≤ −17) | 57 (6%) | **195 (19%)** | **3.4x** |
| top (≥ +17) | 261 (25%) | 379 (37%) | 1.5x |
| floored at −20 | 37 | **127** | **3.4x** |
| maxed at +20 | 146 | 210 | 1.4x |

**The midseason risk did not materialise.** The week-13 watch was that 146 maxed might reach
300+ and flatten identity — every press team equally pinned at the ceiling. Instead the top grew
only 1.4x while **the bottom tripled**. Teams are separating in BOTH directions, which is the
personality outcome the system exists to produce.

`pt_efficiency` remains the most bipolar attribute (32 floored, 28 maxed) — press teams build it,
everyone else abandons it. `discipline` and `fight` developed real spread in the back half
(5 → 33 and 4 → 30 maxed), so authoritarian-family focuses are landing.

### 🐛 `fb_opp_modifier` is untrainable — CONFIRMED BUG

Zero teams above +17 at BOTH snapshots, and the mean fell −5.3 → **−10.8** across the season.
It is the only attribute with no upside at all.

**Cause: no vision installs it.** `fast_breaks.defense_install` → `fb_opp_modifier` appears in
**zero** entries of the §3.5 vision table, while every other core-8 attribute has at least one:

| install slot | attribute | visions installing it |
|---|---|--:|
| `T_DEF` | defensive_efficiency | 4 |
| `T_OFF` | offensive_efficiency | 3 |
| `FB_OFF` | fb_efficiency | 1 |
| `PT_DEF` | pt_efficiency | 1 |
| `PT_OFF` | pt_opp_modifier | 1 |
| **`FB_DEF`** | **fb_opp_modifier** | **0** |

So no CPU team ever trains fast-break defense. EOG moves the attribute down; nothing moves it
up. A full season of data made this obvious in a way reading the table did not — the week-13
snapshot already showed it (0 above +17) and it was logged as an open question rather than
chased.

**Proposed fix (not applied):** give `FB_DEF` to **Contain**, whose identity is conservative
transition defence — getting back rather than gambling. It currently installs `T_DEF` + `BREAKS`.
Needs a decision, because changing the vision table shifts every downstream number in this doc.

### Also worth noting

`fb_efficiency` inverted in the back half — mean −0.8 → **−5.6**, with 53 teams at or near the
floor against 30 at the top. Only Run and Gun installs it (1 vision), so most of the league
lets it rot. Same shape as `fb_opp_modifier` but one degree less severe: thinly installed rather
than never installed.

---

## Method

Read directly from `ftd.team_attributes` across all 128 FTD docs — a point-in-time snapshot, not
a delta. No sim or dry run involved, so nothing here depends on the measurement caveats that
apply to training-gain numbers (see `cpu_identity_training_design.md` and
`scripts/cpu_training_mode_ab.py`).

```
GOB_DB_ACCESS=read python3 -c "
from BackEnd.db import db
from bson import ObjectId
import statistics, collections
fid=ObjectId('6a7f1acc7d319324cd3259ab')
CORE=('offensive_efficiency','defensive_efficiency','fb_efficiency','fb_opp_modifier',
      'pt_efficiency','pt_opp_modifier','discipline','fight')
vals=collections.defaultdict(list)
for d in db['franchise_team_data'].find({'franchise_id':{'\$in':[fid,str(fid)]}},{'team_attributes':1}):
    ta=d.get('team_attributes') or {}
    for a in CORE:
        v=ta.get(a)
        if isinstance(v,(int,float)): vals[a].append(v)
for a in CORE:
    v=vals[a]
    print(a, sum(1 for x in v if x<=-20), sum(1 for x in v if -20<x<=-17),
          sum(1 for x in v if 17<=x<20), sum(1 for x in v if x>=20), round(statistics.mean(v),1))
"
```

## Related

* [`cpu_identity_training_design.md`](./cpu_identity_training_design.md) — the allocation system producing these
* [`../06_Gameplay_Systems/CPU_Team_Identity_System.md`](../06_Gameplay_Systems/CPU_Team_Identity_System.md) — vision assignment and surface status
* [`../06_Gameplay_Systems/End_Of_Game_System.md`](../06_Gameplay_Systems/End_Of_Game_System.md) — the EOG bands that move these attributes per game
