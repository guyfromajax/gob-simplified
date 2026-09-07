"""Precise by-construction check on pos_action WRITES.

Finds every assignment whose target subscripts a `*pos_actions*` map, then
reports the position-key vocabulary of the assigned value. Dict literals are
inspected directly; named values are resolved to their nearest prior literal
assignment in the same function.
"""
import ast
import pathlib
from collections import Counter

KEYS = ("coords", "location", "spot")
tally = Counter()
rows = []


def is_pos_actions_target(target):
    """True if `target` is a subscript of something whose name mentions pos_actions."""
    if not isinstance(target, ast.Subscript):
        return False
    base = target.value
    if isinstance(base, ast.Name) and "pos_action" in base.id:
        return True
    # step["pos_actions"][pos] = ...
    if isinstance(base, ast.Subscript):
        sl = base.slice
        if isinstance(sl, ast.Constant) and sl.value == "pos_actions":
            return True
    return False


def dict_keys(node):
    return {k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}


for path in sorted(pathlib.Path("BackEnd").rglob("*.py")):
    src = path.read_text()
    if "pos_action" not in src:
        continue
    tree = ast.parse(src)
    # index every literal dict assigned to a simple name, for resolving named values
    named = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    named.setdefault(t.id, []).append(node.value)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(is_pos_actions_target(t) for t in node.targets):
            continue
        val = node.value
        if isinstance(val, ast.Dict):
            found = dict_keys(val) & set(KEYS)
            kind = "literal"
            detail = "+".join(sorted(found)) if found else "NONE"
        elif isinstance(val, ast.Name) and val.id in named:
            found = set()
            for cand in named[val.id]:
                found |= dict_keys(cand) & set(KEYS)
            kind = f"name:{val.id}"
            detail = "+".join(sorted(found)) if found else "NONE"
        elif isinstance(val, ast.Call):
            fn = val.func
            fname = getattr(fn, "id", None) or getattr(fn, "attr", "?")
            kind = f"call:{fname}"
            detail = "CALL"
        else:
            kind = type(val).__name__
            detail = "UNRESOLVED"
        tally[detail] += 1
        rows.append((f"{path}:{node.lineno}", kind, detail))

print("=== pos_action WRITE sites: position-key vocabulary ===")
for detail, n in sorted(tally.items(), key=lambda kv: -kv[1]):
    print(f"  {detail:24s} {n:4d}")
print(f"  {'TOTAL':24s} {sum(tally.values()):4d}")

print()
print("=== sites needing manual resolution (CALL / UNRESOLVED / NONE) ===")
for loc, kind, detail in rows:
    if detail in ("CALL", "UNRESOLVED", "NONE"):
        print(f"  {detail:12s} {loc:52s} {kind}")
