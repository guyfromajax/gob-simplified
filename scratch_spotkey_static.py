"""By-construction check: does every authored offense pos_action carry one of
coords / location / spot? If yes, the else branch at defender_placement.py:196
is unreachable by construction and may raise rather than invent (50,25).

Walks the static skeleton modules (which supply 99.5% of builds) exhaustively,
then AST-scans the dynamic authors for pos_action dict literals.
"""
import ast
import importlib
import pathlib
from collections import Counter

OFFENSE = {"PG", "SG", "SF", "PF", "C"}
KEYS = ("coords", "location", "spot")

tally = Counter()
missing = []


def walk(obj, trail):
    """Find every dict that looks like a skeleton step and inspect pos_actions."""
    if isinstance(obj, dict):
        pa = obj.get("pos_actions")
        if isinstance(pa, dict):
            for pos, action in pa.items():
                if not isinstance(action, dict):
                    continue
                off = pos in OFFENSE
                tally[("offense" if off else "other", "total")] += 1
                which = [k for k in KEYS if k in action]
                if which:
                    tally[("offense" if off else "other", "+".join(which))] += 1
                else:
                    tally[("offense" if off else "other", "NONE")] += 1
                    if off:
                        missing.append((trail, pos, sorted(action.keys())))
        for k, v in obj.items():
            walk(v, f"{trail}.{k}" if not isinstance(k, int) else trail)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            walk(v, f"{trail}[{i}]")


mods = sorted(
    p.stem
    for p in pathlib.Path("BackEnd/playcall_skeletons").glob("*.py")
    if not p.stem.startswith("__") and " copy" not in p.stem
)
print("=== STATIC SKELETON MODULES ===")
for name in mods:
    mod = importlib.import_module(f"BackEnd.playcall_skeletons.{name}")
    before = tally[("offense", "total")]
    for attr in dir(mod):
        if attr.startswith("__"):
            continue
        walk(getattr(mod, attr), f"{name}.{attr}")
    print(f"  {name:26s} offense pos_actions: {tally[('offense','total')] - before}")

print()
print("=== KEY VOCABULARY, offense pos_actions ===")
tot = tally[("offense", "total")]
for (scope, key), n in sorted(tally.items(), key=lambda kv: -kv[1]):
    if scope != "offense" or key == "total":
        continue
    print(f"  {key:24s} {n:7d}  {100.0*n/max(tot,1):5.1f}%")
print(f"  {'TOTAL':24s} {tot:7d}")

print()
print("=== OFFENSE pos_actions WITH NO POSITION KEY AT ALL (would hit the else) ===")
if not missing:
    print("  none — every authored offense pos_action carries coords, location or spot")
else:
    for trail, pos, keys in missing[:25]:
        print(f"  {trail} [{pos}] keys={keys}")
    print(f"  ({len(missing)} total)")

# --- AST pass over the dynamic authors: any pos_action dict literal built with
# an action but none of the three position keys?
print()
print("=== DYNAMIC AUTHORS (AST scan for action-bearing dict literals) ===")
dyn = [
    p for p in pathlib.Path("BackEnd").rglob("*.py")
    if "playcall_skeletons" not in str(p) and "pos_actions" in p.read_text()
]
suspect = []
for path in dyn:
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        lits = {k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        if "action" in lits and not (lits & set(KEYS)):
            suspect.append((path, node.lineno, sorted(lits)))
print(f"  files scanned: {len(dyn)}")
if not suspect:
    print("  none — every action-bearing dict literal also carries a position key")
else:
    for path, lineno, lits in suspect:
        print(f"  {path}:{lineno} keys={lits}")
