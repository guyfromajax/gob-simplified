"""Regenerate recruit_sets set_0001 at 450 (300 reused + 150 new), gob-staging, replace-in-place.

The record of how the 450 came to exist and how to reproduce them (deterministic at seed 42, λ=0
i.e. no height-continuity penalty). Reused 300 keep recruit_id / name / Home Region (preserves the
R2 portrait keyed by recruit_id) and blend their attributes toward the current position profile at
IDENTITY_STRENGTH; everything else — year (55/15/15/15 drawn), entry_tier (drawn from 7/20/40/20/11/2,
NOT RT-derived), attribute-fit position_intent, grow-into-frame height, continuous-curve weight,
16 synced anchors, drawn potential_factor, recomputed position_ratings — is generated clean.
has_portrait flags the 150 new (false) for the borrow-pool fail-safe fallback (see recruit_sets.py).

Default dry-run (self-check + CSVs); --commit backs up (recruit_sets_backups) then writes. gob-staging
asserted twice; touches no other collection. See _documentation_master/projects/recruit_set_0001_regen/.
"""
import os, sys, csv, uuid, argparse, statistics, random
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
ROOT=Path("/Users/jamesdavies/gob-simplified"); os.chdir(ROOT); sys.path.insert(0,str(ROOT))
def le(fp):
    if fp.exists():
        for l in fp.read_text().splitlines():
            l=l.strip()
            if l and not l.startswith("#") and "=" in l:
                k,v=l.split("=",1); os.environ.setdefault(k.strip(),v.strip().strip('"').strip("'"))
for f in (ROOT/".env.local",ROOT/".env"): le(f)
from pymongo import MongoClient
from BackEnd.utils.player_generation import (POSITIONS, CORE_ATTRS, HEIGHT_IDEAL_IN, draw_height, weight_from_height,
    generate_core_attributes, position_profile, target_rt, draw_tier, draw_potential_factor, normalize_year,
    HT_REMAINING_SHARE_BY_YEAR, HT_TOTAL_MEAN)
from BackEnd.utils.position_ratings import compute_position_ratings, POSITION_WEIGHTS, height_fitness
from BackEnd.constants import LEAGUE_MEDIAN_HEIGHT_IN
from BackEnd.models.franchise_manager import RecruitManager, choose_franchise_first_name

DB_NAME="gob-staging"; COLL="recruit_sets"; SETID="set_0001"; SEED=42; NEW=150
IDS=0.15; ARCH=1.30; YEAR_W=[("JH",.55),("FR",.15),("SO",.15),("JR",.15)]
SP=ROOT/"_documentation_master/projects/recruit_set_0001_regen"
ap=argparse.ArgumentParser(); ap.add_argument("--commit",action="store_true"); A=ap.parse_args()

db=MongoClient(os.environ["MONGO_URI"],serverSelectionTimeoutMS=20000)[DB_NAME]
if db.name!=DB_NAME: raise SystemExit(f"Refusing: db is {db.name!r}")   # GUARD 1
setdoc=db[COLL].find_one({"set_id":SETID}) or {}
existing=setdoc.get("recruits") or []
assert len(existing)==300, f"expected 300 got {len(existing)}"
regions=sorted({str(r.get("Home Region") or "H") for r in existing})
rm=RecruitManager(db)

def draw_year(rng):
    x=rng.random(); c=0.0
    for y,w in YEAR_W:
        c+=w
        if x<c: return y
    return "JH"
def skill_fit(a,p): return sum(POSITION_WEIGHTS[p].get(k,0.0)*float(a.get(k,0) or 0) for k in POSITION_WEIGHTS[p])
def arch_pos(r):
    a=str((r or {}).get("archetype") or ""); return a.split()[1] if a.startswith("Classic ") and a.split()[1] in POSITIONS else None
def blended(intent,old):
    clean=position_profile(intent); shp={a:float(old.get(f"anchor_{a}",old.get(a,0)) or 0) for a in CORE_ATTRS}
    m=statistics.mean(shp.values()) if any(shp.values()) else 0.0
    return {a:max(0.05,clean[a]*(1.0+IDS*((shp[a]/m)-1.0))) for a in CORE_ATTRS} if m>0 else None

# ----- generate (per-recruit rng; order height,core,weight preserved from validated manifest) -----
slots=[{"reuse":True,"old":r,"rng":random.Random(SEED*100003+i)} for i,r in enumerate(existing)]
namerng=random.Random(SEED*7+1)
for j in range(NEW):
    slots.append({"reuse":False,"old":None,"rng":random.Random(SEED*100003+10000+j),
                  "recruit_id":str(uuid.uuid4()),
                  "name":f"{choose_franchise_first_name(rm.first_names,rm.first_name_weights)} {namerng.choice(rm.last_names).title()}",
                  "home":namerng.choice(regions)})
for s in slots:
    s["year"]=draw_year(s["rng"]); s["tier"]=draw_tier(s["rng"])
N=len(slots); upper=round(0.22*N); lower=round(0.18*N); counts={p:0 for p in POSITIONS}
reused=[s for s in slots if s["reuse"]]
for s in reused:
    old=s["old"]; oh=float(old.get("height") or LEAGUE_MEDIAN_HEIGHT_IN); apz=arch_pos(old)
    s["_fit"]={p: skill_fit(old.get("attributes") or {},p)*(height_fitness(p,oh) or 1.0)*(ARCH if p==apz else 1.0) for p in POSITIONS}
    s["_rank"]=sorted(POSITIONS,key=lambda p:-s["_fit"][p])
def margin(s): f=sorted(s["_fit"].values(),reverse=True); return f[0]-f[1]
for s in sorted(reused,key=margin,reverse=True):
    for p in s["_rank"]:
        if counts[p]<upper: s["intent"]=p; counts[p]+=1; break
    else: s["intent"]=s["_rank"][0]; counts[s["intent"]]+=1
for s in [x for x in slots if not x["reuse"]]:
    p=min(POSITIONS,key=lambda q:counts[q]); s["intent"]=p; counts[p]+=1
for _ in range(N):
    under=[p for p in POSITIONS if counts[p]<lower]
    if not under: break
    b=min(under,key=lambda p:counts[p]); mv=[s for s in reused if s["intent"]!=b and counts[s["intent"]]>lower]
    if not mv: break
    best=max(mv,key=lambda s:s["_fit"][b]); counts[best["intent"]]-=1; best["intent"]=b; counts[b]+=1
for s in slots:
    rng=s["rng"]; it=s["intent"]
    s["height"]=draw_height(it,rng,s["year"])
    core=generate_core_attributes(it,s["height"],target_rt(s["tier"],s["year"]),rng,relative_order=(blended(it,s["old"].get("attributes") or {}) if s["reuse"] else None))
    s["weight"]=weight_from_height(s["height"],rng)   # weight drawn right after core (matches manifest)
    attrs=dict(core)
    for a in CORE_ATTRS: attrs[f"anchor_{a}"]=attrs[a]      # sync all 16 anchors
    if s["reuse"]:
        oa=s["old"].get("attributes") or {}; ch=int(float(oa.get("CH",oa.get("anchor_CH",rng.randint(1,100))) or rng.randint(1,100)))
    else: ch=rng.randint(1,100)
    attrs["CH"]=ch; attrs["anchor_CH"]=ch; attrs["EM"]=rng.randint(1,100); attrs["anchor_EM"]=attrs["EM"]
    attrs["MO"]=0; attrs["anchor_MO"]=0; attrs["NG"]=1.0; attrs["anchor_NG"]=1.0
    s["attributes"]=attrs
    s["position_ratings"]=compute_position_ratings({"attributes":attrs,"height":s["height"]})
    s["potential_factor"]=draw_potential_factor(rng)
    s["entry_tier"]=s["tier"]; s["archetype"]=RecruitManager._recruit_display_archetype(it,s["tier"])
    if s["reuse"]:
        s["recruit_id"]=s["old"]["recruit_id"]; s["name"]=s["old"]["name"]; s["home"]=s["old"].get("Home Region") or "H"

# ----- manifest self-check (must reproduce the reported numbers) -----
yc=Counter(s["year"] for s in slots); tc=Counter(s["entry_tier"] for s in slots); ic=Counter(s["intent"] for s in slots)
h=next((s for s in reused if "Hector Cain" in s["name"]),None)
print(f"SELF-CHECK  year JH/FR/SO/JR = "+"/".join(f"{100*yc[y]/N:.1f}" for y in ['JH','FR','SO','JR'])+
      f" | tiers "+"/".join(f"{100*tc[t]/N:.1f}" for t in ['Poor','BelowAverage','Average','Good','Great','Elite'])+
      f" | intent "+"/".join(f"{100*ic[p]/N:.1f}" for p in POSITIONS)+f" | Hector={h['intent'] if h else '?'}")
print("            expected  54.0/15.1/14.2/16.7 | 6.4/21.1/40.0/19.1/11.3/2.0 | 22.0/22.0/18.7/18.7/18.7 | Hector=SG")

# ----- build docs -----
def doc(s):
    return {"recruit_id":s["recruit_id"],"name":s["name"],"year":s["year"],"archetype":s["archetype"],
            "height":s["height"],"weight":s["weight"],"attributes":s["attributes"],
            "position_ratings":s["position_ratings"],"Home Region":s["home"],
            "entry_tier":s["entry_tier"],"position_intent":s["intent"],"potential_factor":s["potential_factor"],
            # Fail-safe fallback for the R2 borrow-pool filter: true for the 300 reused (kits exist),
            # false for the 150 new (no kit until art uploaded). R2 file-existence is primary.
            "has_portrait":bool(s["reuse"])}
docs=[doc(s) for s in slots]
assert len(docs)==450
assert all(docs[i]["recruit_id"]==existing[i]["recruit_id"] and docs[i]["name"]==existing[i]["name"]
           and docs[i]["Home Region"]==(existing[i].get("Home Region") or "H") for i in range(300)), "reused identity mismatch"

# ----- CSVs -----
def band(hh): hh=float(hh); return "guard" if hh<75 else ("wing" if hh<77 else "big")
with open(SP/"set0001_reused_movers.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["recruit_id","name","old_year","new_year","intent","tier","old_h","new_h","dh","old_w","new_w","dw","old_band","new_band","crossed","bands_crossed"])
    bi={"guard":0,"wing":1,"big":2}
    for s in sorted(reused,key=lambda s:-(abs(s["height"]-float(s["old"]["height"]))+abs(s["weight"]-float(s["old"]["weight"]))/8.0)):
        o=s["old"]; ob=band(o["height"]); nb=band(s["height"])
        w.writerow([s["recruit_id"],s["name"],normalize_year(o.get("year")),s["year"],s["intent"],s["tier"],o["height"],s["height"],s["height"]-float(o["height"]),o["weight"],s["weight"],s["weight"]-float(o["weight"]),ob,nb,int(ob!=nb),abs(bi[nb]-bi[ob])])
with open(SP/"set0001_new150_portraits.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["recruit_id","name","year","intent","height","weight","entry_tier"])
    for s in [x for x in slots if not x["reuse"]]: w.writerow([s["recruit_id"],s["name"],s["year"],s["intent"],s["height"],s["weight"],s["tier"]])
print("CSVs written to scratchpad.")

print(f"\nMODE: {'COMMIT' if A.commit else 'DRY-RUN (no writes)'}")
if A.commit:
    assert db.name==DB_NAME, "guard bypassed"   # GUARD 2
    ts=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"); bkid=f"set_0001_backup_{ts}"
    # Backup into a SEPARATE collection so it is never a drawable set (load_unused_set_or_generate
    # lists set_ids in `recruit_sets`; a backup there would be selectable by a franchise).
    BK="recruit_sets_backups"
    db[BK].insert_one({**{k:v for k,v in setdoc.items() if k!="_id"},"set_id":bkid,"backup_of":SETID,"backed_up_at":datetime.now(timezone.utc)})
    assert db[BK].count_documents({"set_id":bkid})==1 and len((db[BK].find_one({"set_id":bkid}) or {}).get("recruits",[]))==300, "backup verify failed"
    print(f"BACKUP  {SETID} (300) → {BK}.{bkid} (count-verified, non-drawable collection)")
    res=db[COLL].update_one({"set_id":SETID},{"$set":{"recruits":docs,"recruit_count":450}})
    print(f"WROTE   {SETID}: matched={res.matched_count} modified={res.modified_count}")
    chk=db[COLL].find_one({"set_id":SETID}); print(f"VERIFY  recruit_count={chk.get('recruit_count')} len(recruits)={len(chk.get('recruits'))}")
else:
    print("  (re-run with --commit to back up + write)")
