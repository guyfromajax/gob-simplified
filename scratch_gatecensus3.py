"""READ-ONLY census, pass 3: THE DISCRIMINATOR. bugs.md item 17.

Passes 1-2 enumerated ~33 blocks gated on a render precondition that also touch non-render
state. Almost all are LOOKALIKES for one reason: the predicate IS the body's data dependency.
`if anim_steps:` guarding `result["time_elapsed"] = burn(anim_steps[0], anim_steps[-1])` is not
a hazard, it is a function of its argument -- with no steps there is no burn to compute, and
time_elapsed correctly keeps the resolver's value.

The one KNOWN true instance is shaped differently:

    turn_manager.py:2096   if ... result.get("skeleton"):
                               finalize_flss_post_emit(self.game, result)

`finalize_flss_post_emit(game, result)` never reads `result["skeleton"]`. It reads
`result["flss"]`, `game_state["time_remaining"]`, and `result["animation_steps"]` -- which it
guards ITSELF (eoq_clock_progression.py:584). So the predicate is not the dependency: the block
would have done correct, meaningful work had it run with the predicate False. That is what made
it silent-and-wrong rather than silent-and-vacuous.

DETECTOR: inside a render-gated block, find calls to BackEnd-defined functions where NO argument
carries the render payload named in the predicate. Those are the candidates whose dependency is
not the predicate. Everything else is a lookalike by construction.

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
    "_fsteps", "prefix_steps", "flss_steps", "dsteps", "_prefix",
}
RENDER_NAME_HINTS = ("animation", "skeleton", "_steps", "steps", "anim", "coords")

NONRENDER_HINTS = (
    "clock", "drain", "normalize_quarter", "finalize", "possession", "quarter",
    "score", "stat", "foul", "turnover", "chain", "teardown", "advance", "commit",
    "award", "free_throw", "rebound", "activate", "mark_", "clear_", "eoq",
)


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


def render_toks(node):
    t = toks(node)
    hit = set(x for x in t if x in RENDER_KEYS)
    hit |= set(x for x in t if any(h in x.lower() for h in RENDER_NAME_HINTS))
    return hit


def is_render_predicate(test):
    return bool(render_toks(test))


def collect_backend_defs():
    """name -> (file, lineno) for every function defined under BackEnd/."""
    defs = {}
    for path in sorted(BACKEND.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        rel = path.relative_to(REPO).as_posix()
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs.setdefault(n.name, (rel, n.lineno))
    return defs


def main():
    defs = collect_backend_defs()
    findings = []
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
            pred_render = render_toks(node.test)
            if not pred_render:
                continue
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    if not isinstance(sub, ast.Call):
                        continue
                    fn = sub.func
                    name = fn.attr if isinstance(fn, ast.Attribute) else (
                        fn.id if isinstance(fn, ast.Name) else "")
                    if not name or name not in defs:
                        continue
                    low = name.lower()
                    if not any(h in low for h in NONRENDER_HINTS):
                        continue
                    # does ANY argument carry a render payload?
                    argtoks = set()
                    for a in list(sub.args) + [k.value for k in sub.keywords]:
                        argtoks |= render_toks(a)
                    if argtoks:
                        continue  # predicate IS (or supplies) the dependency -> lookalike
                    findings.append({
                        "site": f"{rel}:{sub.lineno}",
                        "gate": f"{rel}:{node.lineno}",
                        "pred": ast.unparse(node.test)[:110],
                        "call": ast.unparse(sub)[:110],
                        "callee_def": f"{defs[name][0]}:{defs[name][1]}",
                    })

    # dedupe
    seen = set()
    uniq = []
    for f in findings:
        k = (f["site"], f["call"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(f)

    print("=" * 92)
    print("PASS 3 -- calls in a render-gated block whose arguments carry NO render payload")
    print("(i.e. the predicate is not the body's data dependency)")
    print("=" * 92)
    print(f"{len(uniq)} candidate call(s)\n")
    for f in uniq:
        print(f"gate {f['gate']}")
        print(f"    if {f['pred']}")
        print(f"  call {f['site']}:  {f['call']}")
        print(f"  callee defined at {f['callee_def']}")
        print()


if __name__ == "__main__":
    main()
