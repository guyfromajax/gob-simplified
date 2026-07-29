#!/usr/bin/env python3
"""Offline Monte Carlo for the player growth model (design §15). No DB, no
possessions, seeded/deterministic. Thin driver over BackEnd/utils/player_development
(the real offseason event) + player_generation (JH start) + position_ratings (RT)."""
from __future__ import annotations
import sys, statistics, random
from pathlib import Path
from collections import Counter, defaultdict
sys.path.insert(0, str(Path("/Users/jamesdavies/gob-simplified")))

from BackEnd.utils.player_generation import (
    JH_ANCHOR_BY_TIER, TIER_FREQUENCY, POSITIONS, generate_player, draw_position_intent, draw_tier,
)
from BackEnd.utils import player_development as dev
from BackEnd.utils.position_ratings import compute_position_ratings

N = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
rng = random.Random(SEED)
TIERS = list(TIER_FREQUENCY)

def p(v, q):
    v = sorted(v); i = (len(v)-1)*q/100; lo=int(i); hi=min(lo+1,len(v)-1); return v[lo]+(v[hi]-v[lo])*(i-lo)
def pct(x, d): return f"{100*x/d:.1f}%" if d else "n/a"

careers = []
# per-rung family growth share accumulators
fam_delta = {r: defaultdict(float) for r in dev.RUNG_TRANSITIONS}
peak_by_ch_decile = defaultdict(list)

for _ in range(N):
    tier = rng.choices(TIERS, weights=[TIER_FREQUENCY[t] for t in TIERS], k=1)[0]
    pos = draw_position_intent(rng)
    ch = rng.randint(1, 100)
    # step-by-step (thin driver) so we can capture per-rung attribute deltas
    jh = generate_player(pos, "JH", tier, rng, preserve_ch=ch)
    player = {"attributes": jh["attributes"], "height": jh["height"], "weight": jh["weight"],
              "position": pos, "training_position": pos, "tier": tier,
              "jh_anchor": JH_ANCHOR_BY_TIER[tier], "position_ratings": jh["position_ratings"],
              "class_year": "JH"}
    profile = dev.roll_growth_profile(ch, rng)
    jh_rt = player["position_ratings"][pos]
    a100_rung = {}
    for rung in dev.RUNG_TRANSITIONS:
        before = dict(player["attributes"])
        dev.develop_one_offseason(player, rung, profile, rng)
        for a in dev.GROWTH_ATTRS:
            fam_delta[rung][dev.FAMILY_OF[a]] += max(0, player["attributes"][a] - before.get(a, 0))
        a100_rung[rung] = 1 if max(player["attributes"][a] for a in dev.GROWTH_ATTRS) >= 100 else 0
    sr_rt = player["position_ratings"][pos]
    maxattr = max(player["attributes"][a] for a in dev.GROWTH_ATTRS)
    careers.append({"tier": tier, "pos": pos, "ch": ch, "peaks": profile["peak_count"],
                    "jh_rt": jh_rt, "sr_rt": sr_rt, "mult": sr_rt/jh_rt if jh_rt else 0,
                    "maxattr": maxattr, "profile": profile, "a100_rung": a100_rung})
    peak_by_ch_decile[min(9, ch//10)].append(profile["peak_count"])

# also capture class-year p50 via re-running Average tier snapshots
def class_rt_curve(tier, k=2000):
    r = random.Random(99); out = {rr: [] for rr in ("JH",)+dev.RUNG_TRANSITIONS}
    for _ in range(k):
        pos = draw_position_intent(r); ch = r.randint(1,100)
        pl = dev.simulate_career(pos, tier, ch, r)
        for rr, snap in pl["snapshots"].items():
            out[rr].append(snap[pos])
    return out

print(f"=== MC growth model: N={N}, seed={SEED} ===\n")

# 1. peak-count distribution
pk = Counter(c["peaks"] for c in careers)
print("1. peak-count dist:   " + " ".join(f"{k}:{pct(pk[k],N)}" for k in (0,1,2,3)) + "   (target 20/55/22/3)")
# CH monotonicity
print("   mean peaks by CH decile: " + " ".join(f"{d}:{statistics.mean(peak_by_ch_decile[d]):.2f}" for d in range(10)))

# 2. career multiple by peak count
print("\n2. career multiple by peak count (target 1.7/2.0/2.3/2.6):")
for k in (0,1,2,3):
    ms = [c["mult"] for c in careers if c["peaks"]==k]
    if ms: print(f"   {k} peaks: median {statistics.median(ms):.2f}x  (n={len(ms)})")
allm = [c["mult"] for c in careers]
print(f"   overall median multiple: {statistics.median(allm):.2f}x (target ~2.0)")

# 3. class-year p50 RT (Average)
avg = class_rt_curve("Average")
print("\n3. class-year p50 RT (Average tier, target 35/43/54/60):")
print("   " + " ".join(f"{rr}:{p(avg[rr],50):.0f}" for rr in ("FR","SO","JR","SR")))

# 4. senior p50 RT by tier
print("\n4. senior p50 RT by tier (target Poor40 BA50 Avg60 Good70 Great80 Elite100):")
for t in TIERS:
    srs = [c["sr_rt"] for c in careers if c["tier"]==t]
    print(f"   {t:<13} p50 {p(srs,50):.0f}  (n={len(srs)})")

# 5. ceiling
allsr = [c["sr_rt"] for c in careers]
over130 = sum(r > 132 for r in allsr)
print(f"\n5. RT ceiling: max {max(allsr):.0f}, p99 {p(allsr,99):.0f}, players >132: {over130} ({pct(over130,N)}) (target ~130, ~none above)")

# 6. any attr >=100 — pool-equivalent (mean over FR-SR, the rostered class years),
#    not senior-only. The 5.5% figure (§3.6.4) was measured on a mixed-class pool.
by_rung_100 = {r: sum(c["a100_rung"][r] for c in careers)/N for r in dev.RUNG_TRANSITIONS}
pool100 = statistics.mean(by_rung_100.values())*100
print(f"\n6. any attr >=100 by class year: " + " ".join(f"{r}:{by_rung_100[r]*100:.1f}%" for r in dev.RUNG_TRANSITIONS))
print(f"   POOL-equivalent (mean FR-SR): {pool100:.1f}%   senior-only: {pct(sum(c['maxattr']>=100 for c in careers),N)}   (target ~5.5%)")

# 7. per-family growth share by rung
print("\n7. per-family growth share by rung (physical early → mental late):")
print(f"   {'rung':<5}{'physical':>10}{'skill':>8}{'mental':>8}")
for rr in dev.RUNG_TRANSITIONS:
    tot = sum(fam_delta[rr].values()) or 1
    print(f"   {rr:<5}{fam_delta[rr]['physical']/tot*100:>9.0f}%{fam_delta[rr]['skill']/tot*100:>7.0f}%{fam_delta[rr]['mental']/tot*100:>7.0f}%")

# ch_seed independence from tier: corr(ch, tier-rank) should be ~0
tier_rank = {t:i for i,t in enumerate(TIERS)}
xs=[c["ch"] for c in careers]; ys=[tier_rank[c["tier"]] for c in careers]
mx=statistics.mean(xs); my=statistics.mean(ys)
num=sum((a-mx)*(b-my) for a,b in zip(xs,ys)); den=(sum((a-mx)**2 for a in xs)*sum((b-my)**2 for b in ys))**.5
print(f"\n   ch_seed vs tier-rank corr: {num/den:+.3f} (want ~0 — independence, §5.1 diamond-in-the-rough)")
