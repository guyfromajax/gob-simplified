"""READ-ONLY census: conditional blocks gated on a RENDER PRECONDITION that also do non-render work.

bugs.md item 17. Enumeration only -- this script proposes candidates, it does not judge them.
Every candidate is reviewed by hand against the lookalike test afterwards.

No source file is written. Nothing is executed from BackEnd/; this is pure AST.
"""
import ast
import pathlib
import sys
from collections import defaultdict

REPO = pathlib.Path(__file__).resolve().parent
BACKEND = REPO / "BackEnd"

# --- what makes a PREDICATE a render precondition -------------------------------------
# It asks whether animation output exists / is well-formed.
RENDER_KEYS = {
    "skeleton", "skeletons", "animation_steps", "animations", "steps", "anim",
    "has_animation_steps", "movement", "pos_actions", "coords", "oDestinations",
    "animation", "emitted_steps", "schema_steps",
}
RENDER_NAME_HINTS = (
    "animation_steps", "has_animation", "anim_steps", "skeleton", "animations",
    "emit_steps", "steps",
)

# --- what makes BODY WORK non-render ---------------------------------------------------
NONRENDER_CALL_HINTS = (
    "clock", "drain", "normalize_quarter", "finalize", "possession", "quarter_end",
    "score", "stat", "foul", "turnover", "chain", "teardown", "advance", "commit",
    "switch_possession", "update_clock", "mark_late", "clear_late", "resolve_shot",
    "award", "free_throw", "rebound",
)
NONRENDER_RESULT_KEYS = {
    "next_play_type", "next_turn", "possession_flips", "quarter_ends_after",
    "clock", "clock_start", "clock_end", "time_elapsed", "time_remaining",
    "offensive_state", "next_defensive_setup", "hco_setup", "final_turn",
    "score", "points", "result_type", "free_throws", "free_throws_remaining",
}
# render-side writes -- present in the body but NOT evidence of non-render work
RENDER_RESULT_KEYS = set(RENDER_KEYS) | {"text", "sfx", "vo", "suppress_final_shot_sfx"}


def strings_in(node):
    out = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            out.add(sub.value)
        elif isinstance(sub, ast.Attribute):
            out.add(sub.attr)
        elif isinstance(sub, ast.Name):
            out.add(sub.id)
    return out


def is_render_predicate(test):
    """Predicate asks about the existence/shape of animation output."""
    toks = strings_in(test)
    if toks & RENDER_KEYS:
        return True
    low = {t.lower() for t in toks}
    return any(any(h in t for h in RENDER_NAME_HINTS) for t in low)


def body_nonrender_work(body):
    """Named non-render effects performed directly in this block's body."""
    found = defaultdict(list)
    for stmt in body:
        for sub in ast.walk(stmt):
            # calls whose name suggests non-render work
            if isinstance(sub, ast.Call):
                fn = sub.func
                name = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else "")
                low = name.lower()
                if any(h in low for h in NONRENDER_CALL_HINTS):
                    found["call"].append(name)
            # writes to game_state[...]
            targets = []
            if isinstance(sub, ast.Assign):
                targets = sub.targets
            elif isinstance(sub, ast.AugAssign):
                targets = [sub.target]
            for t in targets:
                if isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant):
                    key = t.slice.value
                    base = ast.unparse(t.value)
                    if "game_state" in base:
                        found["game_state_write"].append(f"{base}[{key!r}]")
                    elif isinstance(key, str) and key in NONRENDER_RESULT_KEYS:
                        found["turn_write"].append(f"{base}[{key!r}]")
            # game_state.pop(...)
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == "pop":
                base = ast.unparse(sub.func.value)
                if "game_state" in base:
                    found["game_state_pop"].append(ast.unparse(sub)[:60])
    return found


def main():
    cands = []
    for path in sorted(BACKEND.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        rel = path.relative_to(REPO).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            if not is_render_predicate(node.test):
                continue
            work = body_nonrender_work(node.body)
            if not work:
                continue
            cands.append({
                "file": rel,
                "line": node.lineno,
                "pred": ast.unparse(node.test)[:150],
                "work": {k: sorted(set(v))[:6] for k, v in work.items()},
                "size": (node.end_lineno or node.lineno) - node.lineno,
            })
    cands.sort(key=lambda c: (-sum(len(v) for v in c["work"].values()), c["file"], c["line"]))
    print(f"CANDIDATES (pre-review): {len(cands)}\n")
    for c in cands:
        print(f"{c['file']}:{c['line']}  ({c['size']} lines)")
        print(f"    if {c['pred']}")
        for k, v in c["work"].items():
            print(f"      {k}: {v}")
        print()
    print(f"total: {len(cands)}")
    byfile = defaultdict(int)
    for c in cands:
        byfile[c["file"]] += 1
    print("\nby file:")
    for f, n in sorted(byfile.items(), key=lambda x: -x[1]):
        print(f"   {n:>3}  {f}")


if __name__ == "__main__":
    main()
