"""EOQ TRACE WORKER — one game per process, PLAYED arm (animations actually build).

Aimed at Jamie's description: partial animation (some players move, some do not), clock
stops with time still on it, next quarter fine, intermittent.

Instruments, all read-only:
  A. final_turn_pacing._step_action_coords -- returns None when a pos_action carries only
     "spot" (it reads coords then location, never spot). This feeds _slowest_offense_move_seconds,
     i.e. travel time, i.e. the final turn's pacing. Counts calls, Nones, and the keys present
     when it returns None.
  B. evaluate_final_turn_pacing -- what it decided, per boundary.
  C. build_all_animations -- per call, how many of the ten players got a waypoint, and how many
     pos_actions were dropped by the new "decline to place" path.
  D. every turn: quarter, clock, result_type, next_turn, animation_steps presence and per-step
     player coverage.

ARM is fixed to played. Invoked as: SEED=8000 OUT=path python scratch_eoq_run.py
"""
import os, sys, json, hashlib, random as _stdlib
from collections import Counter, defaultdict

os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_DB_NAME", "gob-test")
# Keep production behaviour: the fallthrough declines rather than raising, which is what
# Jamie is running. Raising here would mask the symptom as a crash.
os.environ["GOB_STRICT_POS_ACTION_KEYS"] = "false"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("PYTHONHASHSEED") != "0":
    raise SystemExit("run with PYTHONHASHSEED=0")

SEED = int(os.environ["SEED"])
OUT = os.environ["OUT"]

from BackEnd.db import players_collection, teams_collection
from tests.roster_fixtures import seed_universal_rosters
seed_universal_rosters(teams_collection, players_collection)

from BackEnd.utils import sim_random, training_random
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter
import BackEnd.engine.final_turn_pacing as FTP
import BackEnd.engine.defender_placement as DP
import BackEnd.models.animator as AN

PAC = Counter()
PAC_NONE_KEYS = Counter()
PACING_CALLS = []
BUILDS = []
DECLINED = Counter()
DECLINE_KEYS = Counter()
DRAIN = []
NORM = []
FINAL = Counter()
SYNTH = []
QEA_TRACE = []
NOSCHEMA = []
ZERO_CTX = []
QS_FLAG = [0]
FLSS = []
MICRO = Counter()
ROUTE = Counter()

POSITIONS = ("PG", "SG", "SF", "PF", "C")


def _install_pacing_probe():
    """A. Does the EOQ pacing resolver fail to resolve spot-authored positions?"""
    orig = FTP._step_action_coords

    def probed(step, pos, *, is_away_offense):
        out = orig(step, pos, is_away_offense=is_away_offense)
        PAC["calls"] += 1
        action_info = (step.get("pos_actions") or {}).get(pos) or {}
        if out is None:
            PAC["none"] += 1
            keys = [k for k in ("coords", "location", "spot") if k in action_info]
            PAC_NONE_KEYS["+".join(keys) if keys else "NONE"] += 1
            if "spot" in action_info and "location" not in action_info:
                PAC["none_but_spot_present"] += 1
        else:
            PAC["resolved"] += 1
        return out
    FTP._step_action_coords = probed


def _install_eval_probe():
    """B. What the pacing evaluation decided at each boundary."""
    orig = FTP.evaluate_final_turn_pacing

    def probed(*a, **k):
        out = orig(*a, **k)
        try:
            rec = dict(out) if isinstance(out, dict) else {"_repr": str(out)[:200]}
        except Exception:
            rec = {"_unreadable": True}
        PACING_CALLS.append({k2: v for k2, v in list(rec.items())[:14]})
        return out
    FTP.evaluate_final_turn_pacing = probed


def _install_build_probe():
    """C. Per build: player coverage, and how many pos_actions the converter declined."""
    orig = DP.build_all_animations

    def probed(game, skeleton, off_lineup, def_lineup, **k):
        # count what the skeleton ASKED for, before the build
        asked = Counter()
        steps = (skeleton or {}).get("steps") or []
        for step in steps:
            for pos, pa in ((step.get("pos_actions") or {})).items():
                if not isinstance(pa, dict):
                    continue
                which = [x for x in ("coords", "location", "spot") if x in pa]
                asked["+".join(which) if which else "NONE"] += 1
                if not which:
                    DECLINED["keyless_pos_actions"] += 1
                    DECLINE_KEYS["|".join(sorted(pa.keys()))[:70]] += 1

        animations, zones = orig(game, skeleton, off_lineup, def_lineup, **k)

        # coverage: waypoints per player vs steps in the skeleton
        wp = {str(a.get("playerId")): len(a.get("movement") or []) for a in (animations or [])}
        BUILDS.append({
            "n_steps": len(steps),
            "n_players": len(wp),
            "waypoints": sorted(wp.values(), reverse=True)[:12],
            "min_wp": min(wp.values()) if wp else 0,
            "max_wp": max(wp.values()) if wp else 0,
            "short_players": sum(1 for v in wp.values() if v < len(steps)),
            "asked": dict(asked),
        })
        return animations, zones

    probed.__probed__ = True
    DP.build_all_animations = probed
    if getattr(AN, "build_all_animations", None) is orig:
        AN.build_all_animations = probed


def _install_clock_probes():
    """Did the quarter-end clock drain actually FIRE for the turns that left time?

    ensure_quarter_end_clock_drain forces the residual clock onto the turn, but only when
    `terminal` is true: quarter_ends_after already set, OR (no continuation AND result_type in
    {MAKE, MISS, BLOCK, PUTBACK_MAKE, PUTBACK_MISS, RUN_OUT_CLOCK}). DREB is absent from that
    set. normalize_quarter_end_after_clock_update is the second chance, but it returns early
    while time_remaining > 0.
    """
    import BackEnd.utils.eoq_clock_progression as ECP

    TERMINAL_SET = {"MAKE", "MISS", "BLOCK", "PUTBACK_MAKE", "PUTBACK_MISS", "RUN_OUT_CLOCK"}

    orig_drain = ECP.ensure_quarter_end_clock_drain

    def drain(game, result):
        gs = getattr(game, "game_state", {}) or {}
        before = int(gs.get("time_remaining") or 0)
        rt = str((result or {}).get("result_type") or "").upper()
        qea = bool((result or {}).get("quarter_ends_after"))
        cont = ((result or {}).get("next_play_type") is None
                and (result or {}).get("next_turn") is None)
        terminal = qea or (cont and rt in TERMINAL_SET)
        out = orig_drain(game, result)
        DRAIN.append({"rt": rt, "qea": qea, "no_cont": cont, "terminal": terminal,
                      "clk_before": before,
                      "te_after": (result or {}).get("time_elapsed"),
                      "ce_after": (result or {}).get("clock_end")})
        return out
    ECP.ensure_quarter_end_clock_drain = drain

    orig_norm = ECP.normalize_quarter_end_after_clock_update

    def norm(game, result):
        gs = getattr(game, "game_state", None) or {}
        before = int(gs.get("time_remaining") or 0)
        rt = str((result or {}).get("result_type") or "").upper()
        out = orig_norm(game, result)
        NORM.append({"rt": rt, "clk_at_entry": before, "bailed": before > 0})
        return out
    ECP.normalize_quarter_end_after_clock_update = norm

    # Does the DREB-specific finalizer (the one that WOULD call the drain) ever fire?
    for fname in ("finalize_terminal_dreb_turn", "finalize_flss_post_emit"):
        of = getattr(ECP, fname, None)
        if of is None:
            continue

        def mk(of=of, fname=fname):
            def w(game, result, *a, **k):
                FINAL[fname + "|" + str((result or {}).get("result_type") or "?").upper()] += 1
                return of(game, result, *a, **k)
            return w
        setattr(ECP, fname, mk())
        for modname in ("BackEnd.models.turn_manager", "BackEnd.models.game_manager"):
            m = sys.modules.get(modname)
            if m is not None and getattr(m, fname, None) is of:
                setattr(m, fname, getattr(ECP, fname))

    # rebind by-value importers
    for modname in ("BackEnd.models.turn_manager", "BackEnd.models.game_manager",
                    "BackEnd.engine.phase_resolution"):
        m = sys.modules.get(modname)
        if m is None:
            continue
        if getattr(m, "ensure_quarter_end_clock_drain", None) is orig_drain:
            m.ensure_quarter_end_clock_drain = drain
        if getattr(m, "normalize_quarter_end_after_clock_update", None) is orig_norm:
            m.normalize_quarter_end_after_clock_update = norm


def _install_path_probes():
    """WHICH finalization path does each turn take, and which EOQ gate was open?

    run_micro_turn STEP 4 does drain -> update -> normalize.
    game_manager._finalize_synthesized_clock_turn does update -> normalize ONLY (no drain);
    its own docstring calls these "bypass" turns.

    Also records the gates that decide whether the terminal-DREB path is even reachable:
    game_state["late_clock_eoq_chain_active"], and terminal_dreb_eoq / flss_after_dreb on
    the source turn.
    """
    import BackEnd.models.game_manager as GM
    import BackEnd.models.turn_manager as TM

    orig_synth = GM.GameManager._finalize_synthesized_clock_turn

    def synth(self, turn, **k):
        gs = self.game_state or {}
        SYNTH.append({
            "rt": str((turn or {}).get("result_type") or "").upper(),
            "clk_before": int(gs.get("time_remaining") or 0),
            "qea": bool((turn or {}).get("quarter_ends_after")),
            "term_dreb": bool((turn or {}).get("terminal_dreb_eoq")),
            "flss_dreb": bool((turn or {}).get("flss_after_dreb")),
            "chain": bool(gs.get("late_clock_eoq_chain_active")),
            "npt": (turn or {}).get("next_play_type"),
            "nt": (turn or {}).get("next_turn"),
        })
        return orig_synth(self, turn, **k)
    GM.GameManager._finalize_synthesized_clock_turn = synth

    orig_micro = TM.TurnManager.run_micro_turn

    def micro(self):
        out = orig_micro(self)
        if isinstance(out, dict):
            MICRO[str(out.get("result_type") or "?").upper()] += 1
        return out
    TM.TurnManager.run_micro_turn = micro

    # Was the DREB routing gate reached at all, and which way did it branch?
    import BackEnd.utils.eoq_clock_progression as ECP
    orig_route = ECP.apply_post_miss_rebound_routing

    def route(*a, **k):
        out = orig_route(*a, **k)
        res = next((x for x in a if isinstance(x, dict)), None) or {}
        ROUTE[(str(res.get("result_type") or "?").upper(),
               "term" if res.get("terminal_dreb_eoq") else
               "flss" if res.get("flss_after_dreb") else "neither")] += 1
        return out
    ECP.apply_post_miss_rebound_routing = route
    for mn in ("BackEnd.models.shot_manager", "BackEnd.models.turn_manager"):
        m = sys.modules.get(mn)
        if m is not None and getattr(m, "apply_post_miss_rebound_routing", None) is orig_route:
            m.apply_post_miss_rebound_routing = route


def _install_played_arm():
    GATED = ("capture_fast_break_animation", "capture_free_throw_animation",
             "capture_halfcourt_animation", "skeleton_to_animations")
    depth = [0]
    flag = {}
    for meth in GATED:
        o = getattr(AN.Animator, meth)

        def mk(o=o):
            def wrapped(self, *a, **k):
                gs = self.game.game_state
                if depth[0] == 0:
                    flag["had"] = "_is_full_simulation" in gs
                    flag["prev"] = gs.get("_is_full_simulation")
                gs["_is_full_simulation"] = False
                depth[0] += 1
                try:
                    return o(self, *a, **k)
                finally:
                    depth[0] -= 1
                    if depth[0] == 0:
                        if flag["had"]:
                            gs["_is_full_simulation"] = flag["prev"]
                        else:
                            gs.pop("_is_full_simulation", None)
            return wrapped
        setattr(AN.Animator, meth, mk())


def _steps_coverage(turn):
    """D. Per animation_step: how many players carry coords, and whether any of them MOVE.

    Schema (discovered, not assumed): animation_steps[i]["end"]["coords"] is {player_id: {x,y}},
    same shape under ["start"].
    """
    steps = turn.get("animation_steps") or []
    per = []
    for s in steps:
        start = ((s.get("start") or {}).get("coords") or {})
        end = ((s.get("end") or {}).get("coords") or {})
        moved = 0
        for pid, e in end.items():
            st = start.get(pid)
            if not isinstance(st, dict) or not isinstance(e, dict):
                continue
            if abs(float(e.get("x", 0)) - float(st.get("x", 0))) > 1e-6 or \
               abs(float(e.get("y", 0)) - float(st.get("y", 0))) > 1e-6:
                moved += 1
        endd = s.get("end") or {}
        per.append({"n": len(end), "ns": len(start), "moved": moved,
                    "t": endd.get("time_elapsed"), "clk": endd.get("clock")})
    return per

def _install_noschema_probe():
    """Capture the [SHOT-NO-SCHEMA] diagnostic AND the caller's live `result` dict.

    Question being answered: which upstream HCO branch yields a shot carrying neither a
    skeleton nor roles, so the legacy fallback assigns animations=[] (turn_manager.py:2283)
    and nothing renders. "Quick Shot fallback" is a HYPOTHESIS until this says so.
    """
    import logging as _lg
    import sys as _sys

    FIELDS = ("result_type", "current_turn", "play_type", "play_name", "play",
              "offensive_state", "shot_type", "shot_spot", "event_step", "fast_break",
              "fast_break_play", "final_turn", "flss", "next_play_type", "quick_shot",
              "is_quick_shot", "set_play", "playcall", "lean", "phase")

    def _capture(a):
        rec = {"args": a}
        # the warning is emitted inline in the caller's frame; `result` is a local there
        f = _sys._getframe(2)
        for _ in range(4):
            if f is None:
                break
            r = f.f_locals.get("result")
            if isinstance(r, dict):
                rec["fields"] = {k: (str(r.get(k))[:40] if r.get(k) is not None else None)
                                 for k in FIELDS if k in r}
                rec["keys"] = sorted(r.keys())
                sk = r.get("skeleton")
                rec["skeleton"] = ("absent" if sk is None
                                   else f"dict/{len(sk.get('steps') or [])}steps" if isinstance(sk, dict)
                                   else type(sk).__name__)
                rec["roles"] = (sorted(r.get("roles").keys()) if isinstance(r.get("roles"), dict)
                                else repr(r.get("roles"))[:30])
                break
            f = f.f_back
        rec["quick_shot_fallback_this_turn"] = QS_FLAG[0]
        ZERO_CTX.append(rec)

    for target in ("module", "root"):
        pass

    orig = _lg.warning

    def warn(msg, *a, **k):
        if isinstance(msg, str):
            if "[SHOT-NO-SCHEMA]" in msg:
                NOSCHEMA.append(a)
                if a[9] == 0:
                    _capture(a)
            elif "No outside set plays found" in msg:
                QS_FLAG[0] += 1
        return orig(msg, *a, **k)
    _lg.warning = warn


def _install_flss_probe():
    """Does resolve_flss_shot_logic always author a skeleton?

    turn_manager.py:2096 gates the ENTIRE FLSS emit block on `result.get("skeleton")`.
    No skeleton -> no animation_steps, and the legacy fallback then needs `roles`.
    Record which return path each FLSS resolution took.
    """
    import BackEnd.engine.eoq_perfection as EP
    orig = EP.resolve_flss_shot_logic

    def wrapped(game, *a, **k):
        out = orig(game, *a, **k)
        if isinstance(out, dict):
            sk = out.get("skeleton")
            if os.environ.get("POISON_FLSS") and isinstance(sk, dict):
                # SPC principle 8: draws moved, so an exact diff does not apply. Poison the
                # geometry the emission half newly supplies and see whether the game notices.
                # If outcomes are identical under poison, the payload is decorative.
                def _nudge(o):
                    if isinstance(o, dict):
                        if "x" in o and "y" in o:
                            try:
                                o["x"] = 94.0 - float(o["x"])
                            except (TypeError, ValueError):
                                pass
                        for v in o.values():
                            _nudge(v)
                    elif isinstance(o, list):
                        for v in o:
                            _nudge(v)
                _nudge(sk)
            FLSS.append({
                "rt": str(out.get("result_type") or "?").upper(),
                "skeleton": ("absent" if sk is None else
                             f"steps={len(sk.get('steps') or [])}" if isinstance(sk, dict) else type(sk).__name__),
                "roles": sorted(out.get("roles").keys()) if isinstance(out.get("roles"), dict) else None,
                "zone": out.get("flss_zone"),
                "airball": out.get("flss_airball"),
                "keys": len(out.keys()),
                "has_steps": len(out.get("animation_steps") or []),
            })
        return out
    EP.resolve_flss_shot_logic = wrapped
    for mn in ("BackEnd.models.turn_manager", "BackEnd.models.game_manager"):
        m = sys.modules.get(mn)
        if m is not None and getattr(m, "resolve_flss_shot_logic", None) is orig:
            m.resolve_flss_shot_logic = wrapped


def _install_qea_tracer():
    """Catch the LATE write of quarter_ends_after on a synthesized rebound turn.

    At _finalize_synthesized_clock_turn time these turns carry quarter_ends_after=False
    and a live continuation, so the drain predicate would be False even if called there.
    Yet the persisted record has quarter_ends_after=True. Whoever sets it later is the
    only place that knows the turn is terminal AND could still drain -- i.e. the real
    call site. Find it by traceback, not by reading.
    """
    import traceback
    import BackEnd.models.game_manager as GM

    class TracingTurn(dict):
        def __setitem__(self, k, v):
            if k in ("quarter_ends_after", "next_play_type", "next_turn", "clock_end"):
                QEA_TRACE.append({
                    "key": k, "val": repr(v)[:40],
                    "rt": str(self.get("result_type") or "?").upper(),
                    "stack": [f"{f.filename.split('/')[-1]}:{f.lineno} {f.name}"
                              for f in traceback.extract_stack()[-7:-1]],
                })
            dict.__setitem__(self, k, v)

        def pop(self, k, *a):
            if k in ("next_play_type", "next_turn"):
                QEA_TRACE.append({
                    "key": f"pop:{k}", "val": "-",
                    "rt": str(self.get("result_type") or "?").upper(),
                    "stack": [f"{f.filename.split('/')[-1]}:{f.lineno} {f.name}"
                              for f in traceback.extract_stack()[-7:-1]],
                })
            return dict.pop(self, k, *a)

    orig = GM.GameManager._build_dreb_turn_from_miss

    def build(self, *a, **k):
        out = orig(self, *a, **k)
        return TracingTurn(out) if isinstance(out, dict) else out
    GM.GameManager._build_dreb_turn_from_miss = build


if __name__ == "__main__":


    _install_clock_probes()
    _install_path_probes()
    _install_qea_tracer()
    _install_flss_probe()
    _install_noschema_probe()
    _install_pacing_probe()
    _install_eval_probe()
    _install_build_probe()
    _install_played_arm()

    sim_random.seed(SEED)
    training_random.seed(SEED)
    _stdlib.seed(SEED)
    gm = GameManager("Lancaster", "Bentley-Truman")
    d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2,
         "hc_trap": 5, "fc_press": 5}
    gm.home_team.strategy_settings = d.copy()
    gm.away_team.strategy_settings = d.copy()

    err = None
    q_marks = []
    for q in range(4):
        try:
            simulate_quarter(gm, game_id="%024x" % (0xE0000 + SEED))
        except Exception as e:
            err = f"Q{q+1} {type(e).__name__}: {e}"
            break
        q_marks.append(len(gm.turns or []))

    turns = gm.turns or []
    # discover the field names once, so nothing is assumed
    keyset = sorted(turns[0].keys())[:60] if turns else []

    # per-turn compact record
    recs = []
    for i, t in enumerate(turns):
        recs.append({
            "i": i,
            "q": t.get("quarter") or t.get("period"),
            "rt": str(t.get("result_type") or ""),
            "nt": str(t.get("next_turn") or ""),
            "ct": str(t.get("current_turn") or ""),
            "clk": t.get("clock"),
            "clk_s": t.get("clock_start"), "clk_e": t.get("clock_end"),
            "tr": t.get("time_remaining"), "gclk": t.get("game_clock"),
            "nqe": t.get("near_quarter_end"),
            "qea": bool(t.get("quarter_ends_after")),
            "term_dreb": bool(t.get("terminal_dreb_eoq")),
            "flss_dreb": bool(t.get("flss_after_dreb")),
            "lceoq": bool(t.get("late_clock_eoq")),
            "flss": bool(t.get("flss")),
            "roc": bool(t.get("run_out_clock")),
            "cexp": bool(t.get("clock_expired_no_action")),
            "te": t.get("time_elapsed"),
            "has_anim": bool(t.get("animations")),
            "n_anim": len(t.get("animations") or []),
            "has_steps": bool(t.get("animation_steps")),
            "n_steps": len(t.get("animation_steps") or []),
            "cov": _steps_coverage(t),
        })

    raw = {}
    for i in [m - 1 for m in q_marks] + [102]:
        if i >= len(turns):
            continue
        steps = turns[i].get("animation_steps") or []
        raw[str(i)] = {
            "rt": str(turns[i].get("result_type") or ""),
            "n": len(steps),
            "step0": json.loads(json.dumps(steps[0], default=str)) if steps else None,
        }

    json.dump({
        "seed": SEED, "error": err, "turns": len(turns),
        "q_marks": q_marks, "turn_keys": keyset,
        "pacing": dict(PAC), "pacing_none_keys": dict(PAC_NONE_KEYS),
        "pacing_calls": PACING_CALLS[:40],
        "declined": dict(DECLINED), "decline_keys": dict(DECLINE_KEYS),
        "builds_n": len(BUILDS),
        "builds_short": sum(1 for b in BUILDS if b["short_players"]),
        "builds_sample": BUILDS[:6],
        "asked_total": dict(sum((Counter(b["asked"]) for b in BUILDS), Counter())),
        "recs": recs,
        "raw": raw,
        "drain": DRAIN, "norm": NORM, "final": dict(FINAL),
        "synth": SYNTH, "micro": dict(MICRO), "qea_trace": QEA_TRACE, "noschema": NOSCHEMA, "zero_ctx": ZERO_CTX, "qs_total": QS_FLAG[0], "flss": FLSS,
        "route": {f"{a}|{b}": v for (a, b), v in ROUTE.items()},
    }, open(OUT, "w"))
