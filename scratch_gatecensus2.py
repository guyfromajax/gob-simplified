"""READ-ONLY census, pass 2: false-negative bound for bugs.md item 17.

Pass 1 (scratch_gatecensus.py) used curated hints for "non-render work" and only looked at
`if` blocks. Two ways that under-counts:

  A. BROADENED BODY WORK -- any game_state write (any key), any write of a non-render key onto
     the turn dict, any call to a known state-mutating helper. Bounds how many candidates the
     curated hint list missed.

  B. EARLY-RETURN GUARDS -- `if not steps: return` at the top of a function whose REMAINDER
     does non-render work. Same hazard, inverted shape: the render precondition suppresses the
     non-render tail. Pass 1 could not see these because the non-render work is not in the
     if-body, it is after it.

No source file is written. Pure AST.
"""
import ast
import pathlib
from collections import defaultdict

REPO = pathlib.Path(__file__).resolve().parent
BACKEND = REPO / "BackEnd"

RENDER_KEYS = {
    "skeleton", "skeletons", "animation_steps", "animations", "steps", "anim",
    "has_animation_steps", "movement", "pos_actions", "coords", "animation",
    "emitted_steps", "schema_steps", "dr_steps", "anim_steps", "_fb_steps",
    "final_skeleton", "skeleton_steps", "available_steps", "_dsteps", "skel",
    "_fsteps",
}
RENDER_NAME_HINTS = ("animation", "skeleton", "_steps", "steps", "anim")
RENDER_RESULT_KEYS = {
    "skeleton", "animation_steps", "animations", "steps", "text", "sfx", "vo",
    "suppress_final_shot_sfx", "commentary", "animation", "skeleton_steps",
}


def toks(node):
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
    t = toks(test)
    if t & RENDER_KEYS:
        return True
    return any(any(h in x.lower() for h in RENDER_NAME_HINTS) for x in t)


def nonrender_work(stmts):
    """BROADENED: any game_state touch, any non-render turn-dict key write, any .pop/.clear."""
    found = defaultdict(set)
    for stmt in stmts:
        for sub in ast.walk(stmt):
            targets = []
            if isinstance(sub, ast.Assign):
                targets = sub.targets
            elif isinstance(sub, ast.AugAssign):
                targets = [sub.target]
            for t in targets:
                if isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant):
                    base = ast.unparse(t.value)
                    key = t.slice.value
                    if "game_state" in base:
                        found["game_state_write"].add(f"[{key!r}]")
                    elif isinstance(key, str) and key not in RENDER_RESULT_KEYS and (
                        base.endswith("result") or base in ("result", "turn_result")
                    ):
                        found["turn_write"].add(f"{base}[{key!r}]")
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                if sub.func.attr in ("pop", "clear", "update", "setdefault"):
                    base = ast.unparse(sub.func.value)
                    if "game_state" in base:
                        found["game_state_mutate"].add(f"{sub.func.attr}")
                if sub.func.attr in ("record_stat", "add_stat", "increment_stat"):
                    found["stat"].add(sub.func.attr)
    return found


def enclosing_funcs(tree):
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def main():
    broadened = []
    guards = []
    for path in sorted(BACKEND.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        rel = path.relative_to(REPO).as_posix()

        # --- A: broadened if-body sweep
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and is_render_predicate(node.test):
                w = nonrender_work(node.body)
                if w:
                    broadened.append((rel, node.lineno, ast.unparse(node.test)[:90],
                                      {k: sorted(v)[:4] for k, v in w.items()}))

        # --- B: early-return guard sweep
        for fn in enclosing_funcs(tree):
            for i, stmt in enumerate(fn.body):
                if not isinstance(stmt, ast.If) or not is_render_predicate(stmt.test):
                    continue
                # body is a bare return / return None only
                if not all(isinstance(s, ast.Return) and (s.value is None) for s in stmt.body):
                    continue
                if stmt.orelse:
                    continue
                tail = fn.body[i + 1:]
                w = nonrender_work(tail)
                if w:
                    guards.append((rel, stmt.lineno, fn.name, ast.unparse(stmt.test)[:90],
                                   {k: sorted(v)[:4] for k, v in w.items()}))

    print("=" * 90)
    print(f"A. BROADENED if-body sweep: {len(broadened)} candidates (pass 1 found 30)")
    print("=" * 90)
    byfile = defaultdict(int)
    for rel, ln, pred, w in broadened:
        byfile[rel] += 1
    for f, n in sorted(byfile.items(), key=lambda x: -x[1]):
        print(f"   {n:>3}  {f}")

    print()
    print("=" * 90)
    print(f"B. EARLY-RETURN GUARDS on a render precondition, non-render tail: {len(guards)}")
    print("=" * 90)
    for rel, ln, fn, pred, w in guards:
        print(f"{rel}:{ln}  in {fn}()")
        print(f"    if {pred}:  return")
        for k, v in w.items():
            print(f"      tail {k}: {v}")
        print()


if __name__ == "__main__":
    main()
