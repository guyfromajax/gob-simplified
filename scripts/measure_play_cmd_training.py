"""Measure how much a play's CMD (effectiveness) moves in a real training week.

Read-only measurement against a loopback server (the offline engine on SQLite); it
changes no engine code and writes only to the scratch database that server was started on.

Two passes:

  matrix   Many single training sessions on fresh franchises: different programs, coaching
           focuses, install spreads and playbook modes. Records, for every play and every
           defense, the CMD before and after the session (what the Training Report's
           Playbook Summary marks).
  season   One franchise played for real: training, the user's game, the week's finish.
           Records the training change AND the end-of-game change per play, week by week,
           so drops (CMD only falls at end of game) are measured on evolved scores.

Start a server first, for example:

  GOB_DESKTOP_E2E_SQLITE=/tmp/cmd-camp.sqlite PORT=8781 \
      .venv/bin/python tests/e2e/helpers/seed_and_serve_desktop.py
  FRANCHISE_START_WEEK=10 GOB_DESKTOP_E2E_SQLITE=/tmp/cmd-season.sqlite PORT=8782 \
      .venv/bin/python tests/e2e/helpers/seed_and_serve_desktop.py

  python scripts/measure_play_cmd_training.py matrix --base http://127.0.0.1:8781 --label camp --out camp.jsonl
  python scripts/measure_play_cmd_training.py matrix --base http://127.0.0.1:8782 --label in-season --out season.jsonl
  python scripts/measure_play_cmd_training.py season --base http://127.0.0.1:8781 --weeks 6 --out weeks.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request

SLIDERS = [
    ("player_drills", "offense", "inside"), ("player_drills", "offense", "outside"),
    ("player_drills", "defense", "inside"), ("player_drills", "defense", "outside"),
    ("player_drills", "technical", "passing"), ("player_drills", "technical", "ball_handling"),
    ("player_drills", "technical", "rebounding"),
    ("player_drills", "weight_room", "strength"), ("player_drills", "weight_room", "agility"),
    ("team_drills", "fast_breaks", "offense_install"), ("team_drills", "fast_breaks", "defense_install"),
    ("team_drills", "scrimmages", None),
    ("team_drills", "presses_traps", "defense_install"), ("team_drills", "presses_traps", "offense_install"),
    ("general", "conditioning", None), ("general", "free_throws", None),
    ("general", "film_study", None), ("general", "breaks", None),
]

FOCUSES = [
    "systems-coach-offense", "systems-coach-defense", "authoritarian-execution",
    "authoritarian-teamwork", "authoritarian-discipline", "player-maximizer-top-3",
    "culture-builder-inspire", "systems-coach-fast-breaks",
]

# (offense install, defense install): the points a coach puts on Scheme Installs > Core.
INSTALLS = [(5, 5), (5, 0), (0, 5), (3, 3), (2, 1), (1, 2), (4, 2), (2, 4), (1, 1), (3, 0), (0, 3), (0, 0)]


def http(method, url, body=None, timeout=900):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, {"detail": raw[:300]}


def allocation(budget, offense, defense, rng):
    """A full training payload that spends exactly `budget` points."""
    data = {
        "player_drills": {"offense": {}, "defense": {}, "technical": {}, "weight_room": {}},
        "team_drills": {
            "team_offense": {"install": offense}, "team_defense": {"install": defense},
            "fast_breaks": {}, "scrimmages": 0, "presses_traps": {},
        },
        "general": {},
    }
    values = {slot: 0 for slot in SLIDERS}
    left = budget - offense - defense
    order = SLIDERS[:]
    rng.shuffle(order)
    while left > 0:
        moved = False
        for slot in order:
            if left <= 0:
                break
            if values[slot] < 5:
                step = min(left, rng.choice([1, 1, 2, 3]), 5 - values[slot])
                values[slot] += step
                left -= step
                moved = True
        if not moved:
            raise SystemExit("cannot place the budget")
    for (group, key, sub), value in values.items():
        if sub is None:
            data[group][key] = value
        else:
            data[group].setdefault(key, {})[sub] = value
    return data


def snapshot(base, fid, tid):
    """Every play's and every defense's CMD right now, from the team's own data."""
    status, body = http("GET", f"{base}/franchise/team-data?franchise_id={fid}&team_id={tid}")
    if status != 200:
        raise SystemExit(f"team-data {status} {body}")
    plays = {}
    for key, row in (body.get("plays_data") or {}).items():
        if isinstance(row, dict):
            plays[str(key)] = {
                "name": row.get("name") or str(key), "type": row.get("play_type"), "focus": row.get("play_focus"),
                "play_id": row.get("play_id"), "cmd": row.get("effectiveness", 0) or 0,
            }
    defenses = {}
    for key, row in ((body.get("scouting_data") or {}).get("defense") or {}).items():
        if isinstance(row, dict):
            defenses[str(key)] = {"name": str(key), "cmd": row.get("effectiveness", 0) or 0}
    return plays, defenses


def rows_from(before, after, kind, meta):
    out = []
    for key, row in after.items():
        was = (before.get(key) or {}).get("cmd", 0)
        out.append(dict(meta, kind=kind, play=row["name"], type=row.get("type"), focus=row.get("focus"),
                        before=was, after=row["cmd"], delta=row["cmd"] - was))
    return out


def team_ids(base, fid):
    status, nxt = http("POST", f"{base}/franchise/play-next-game", {"franchise_id": fid})
    if status != 200:
        raise SystemExit(f"play-next-game {status} {nxt}")
    return nxt


def run_matrix(args):
    rng = random.Random(args.seed)
    status, teams = http("GET", f"{args.base}/teams")
    names = [t.get("name") for t in teams if t.get("name")]
    rng.shuffle(names)
    out = open(args.out, "a")
    sessions = 0
    for i in range(args.sessions):
        team = names[i % len(names)]
        offense, defense = INSTALLS[i % len(INSTALLS)]
        focus = FOCUSES[(i // 2) % len(FOCUSES)]
        mode = "custom" if i % 5 == 4 else "current-playbooks"
        status, created = http("POST", f"{args.base}/franchise/select-team", {"team_name": team})
        if status != 200:
            print("select-team", team, status, str(created)[:120], flush=True)
            continue
        fid = created["franchise_id"]
        try:
            nxt = team_ids(args.base, fid)
            tid = str(nxt["home_id"] if nxt.get("home") == team else nxt["away_id"])
            status, points = http("GET", f"{args.base}/franchise/training-points?franchise_id={fid}")
            budget = int(points.get("training_points") or 0)
            week = int(points.get("week") or 1)
            before_plays, before_defs = snapshot(args.base, fid, tid)
            data = allocation(budget, offense, defense, rng)
            data["coaching_focus"] = focus
            data["playbook_training_mode"] = mode
            picked = None
            if mode == "custom":
                offense_ids = [str(p["play_id"] or key) for key, p in before_plays.items() if p["type"] in ("motion", "set_play")]
                rng.shuffle(offense_ids)
                picked = {"offense": offense_ids[: rng.choice([2, 4, 8])], "defense": list(before_defs.keys())[: rng.choice([1, 2, 3])]}
                data["training_playbook_focus"] = picked
            status, result = http("POST", f"{args.base}/franchise/run-training/user",
                                  {"franchise_id": fid, "training_data": data})
            if status != 200:
                print("training", team, status, str(result)[:200], flush=True)
                continue
            after_plays, after_defs = snapshot(args.base, fid, tid)
            meta = {"pass": "matrix", "label": args.label, "week": week, "team": team, "coaching_focus": focus,
                    "offense_install": offense, "defense_install": defense, "mode": mode,
                    "custom": len(picked["offense"]) if picked else 0, "budget": budget}
            for row in rows_from(before_plays, after_plays, "offense", meta) + rows_from(before_defs, after_defs, "defense", meta):
                out.write(json.dumps(row) + "\n")
            out.flush()
            sessions += 1
            print(f"{args.label} {sessions}/{args.sessions} {team} wk{week} o{offense} d{defense} {focus} {mode}", flush=True)
        finally:
            http("DELETE", f"{args.base}/franchise/{fid}")
    print("sessions:", sessions)


def run_season(args):
    rng = random.Random(args.seed)
    team = args.team
    status, created = http("POST", f"{args.base}/franchise/select-team", {"team_name": team})
    if status != 200:
        raise SystemExit(f"select-team {status} {created}")
    fid = created["franchise_id"]
    out = open(args.out, "a")
    try:
        for n in range(args.weeks):
            nxt = team_ids(args.base, fid)
            mine_home = nxt.get("home") == team
            tid = str(nxt["home_id"] if mine_home else nxt["away_id"])
            status, points = http("GET", f"{args.base}/franchise/training-points?franchise_id={fid}")
            week = int(points.get("week") or nxt.get("week") or 1)
            budget = int(points.get("training_points") or 0)
            offense, defense = INSTALLS[n % 8]
            focus = FOCUSES[n % len(FOCUSES)]
            start_plays, start_defs = snapshot(args.base, fid, tid)
            data = allocation(budget, offense, defense, rng)
            data["coaching_focus"] = focus
            data["playbook_training_mode"] = "current-playbooks"
            status, result = http("POST", f"{args.base}/franchise/run-training/user", {"franchise_id": fid, "training_data": data})
            if status != 200:
                raise SystemExit(f"training week {week}: {status} {str(result)[:200]}")
            http("POST", f"{args.base}/franchise/run-training/cpu-train", {"franchise_id": fid}, timeout=1800)
            trained_plays, trained_defs = snapshot(args.base, fid, tid)
            meta = {"pass": "season", "label": "camp" if week == 1 else "in-season", "week": week, "team": team,
                    "coaching_focus": focus, "offense_install": offense, "defense_install": defense,
                    "mode": "current-playbooks", "custom": 0, "budget": budget}
            for row in rows_from(start_plays, trained_plays, "offense", dict(meta, step="training")) \
                    + rows_from(start_defs, trained_defs, "defense", dict(meta, step="training")):
                out.write(json.dumps(row) + "\n")

            # The user's game, simmed quarter by quarter, then the week's finish.
            status, init = http("POST", f"{args.base}/api/init-game", {
                "home_team": nxt["home"], "away_team": nxt["away"], "home_id": nxt["home_id"], "away_id": nxt["away_id"],
                "mode": "franchise", "franchise_id": fid, "user_team_side": "home" if mine_home else "away"})
            game_id = str(init.get("game_id"))
            sim = {}
            for quarter in range(1, 9):
                status, sim = http("POST", f"{args.base}/api/simulate-quarter", {
                    "game_id": game_id, "home_team": nxt["home"], "away_team": nxt["away"], "quarter": quarter,
                    "mode": "franchise", "franchise_id": fid, "full_sim": True}, timeout=1800)
                if status != 200:
                    raise SystemExit(f"simulate-quarter {quarter}: {status} {str(sim)[:200]}")
                if sim.get("is_final") or sim.get("game_over") or sim.get("final"):
                    break
            score = sim.get("score") or {}
            home_score = int(score.get(nxt["home"]) or score.get("home") or 0)
            away_score = int(score.get(nxt["away"]) or score.get("away") or 0)
            http("POST", f"{args.base}/franchise/complete-week/start-cpu-sims", {"franchise_id": fid, "week": week}, timeout=3000)
            status, done = http("POST", f"{args.base}/franchise/complete-week/phase-a", {
                "franchise_id": fid, "week": week, "game_id": game_id,
                "result": {"team1_id": nxt["away_id"], "team2_id": nxt["home_id"], "team1_score": away_score, "team2_score": home_score}},
                timeout=3000)
            if status != 200:
                raise SystemExit(f"phase-a week {week}: {status} {str(done)[:200]}")
            played_plays, played_defs = snapshot(args.base, fid, tid)
            for row in rows_from(trained_plays, played_plays, "offense", dict(meta, step="game")) \
                    + rows_from(trained_defs, played_defs, "defense", dict(meta, step="game")):
                out.write(json.dumps(row) + "\n")
            out.flush()
            http("POST", f"{args.base}/franchise/complete-week/phase-b", {"franchise_id": fid, "week": week}, timeout=3000)
            print(f"week {week}: o{offense} d{defense} {focus} score {home_score}-{away_score} quarters {quarter}", flush=True)
    finally:
        if not args.keep:
            http("DELETE", f"{args.base}/franchise/{fid}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    matrix = sub.add_parser("matrix")
    matrix.add_argument("--base", required=True)
    matrix.add_argument("--label", required=True)
    matrix.add_argument("--out", required=True)
    matrix.add_argument("--sessions", type=int, default=48)
    matrix.add_argument("--seed", type=int, default=20261002)
    season = sub.add_parser("season")
    season.add_argument("--base", required=True)
    season.add_argument("--out", required=True)
    season.add_argument("--weeks", type=int, default=6)
    season.add_argument("--team", default="Lancaster")
    season.add_argument("--seed", type=int, default=20261002)
    season.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    started = time.time()
    (run_matrix if args.cmd == "matrix" else run_season)(args)
    print(f"done in {time.time() - started:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
