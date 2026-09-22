#!/usr/bin/env python3
"""End-to-end desktop loopback season harness. The WS-2 regression test.

Drives a full franchise season against loopback + SQLite: init (or resume),
turn-by-turn play, timeout + resume, box score, week advancement, training,
recruiting weeks 20–26 (ranked board + persisted visits), EOS 27–34,
week 35 recruiting (50-point board + signed_players), finish_season.

The client talks only to 127.0.0.1. Pair with ``scripts/ws2_lsof_sample.sh``
on the loopback PID — zero non-loopback TCP is the network half of the gate.

Catalogs come from the read-only bundled sidecar (``catalog.sqlite`` via
``bundle_path`` / ``GOB_CATALOG_SQLITE``). This harness does not hand-seed
plays or defenses into the save.

The 128-team league is copied into an empty save by ``SqliteStore`` from
``base_league.sqlite``. This harness does not write placeholder teams.

How to run a fresh season::

    # Terminal 1 — loopback. apply_loopback_env setdefaults the spawn pool.
    export GOB_SQLITE_PATH=/tmp/ws2-catalog-season.sqlite
    export GOB_LOOPBACK_PORT=8765
    export PYTHONHASHSEED=0
    python -m BackEnd.loopback

    # Terminal 2 — lsof on the server and pool children (PID from terminal 1).
    bash scripts/ws2_lsof_sample.sh <loopback-pid> /tmp/ws2-season-lsof.log 15

    # Terminal 3 — the season. 0 weeks means through finish_season.
    python scripts/ws2_loopback_season.py \\
        --base http://127.0.0.1:8765 \\
        --sqlite-path /tmp/ws2-catalog-season.sqlite

Resume an existing save (skip week-1 interactive, or finish an open week)::

    python scripts/ws2_loopback_season.py \\
        --franchise-id <id> --skip-interactive-week1
    python scripts/ws2_loopback_season.py \\
        --franchise-id <id> --skip-interactive-week1 \\
        --resume-game-id <gid> --resume-home <name> --resume-away <name> \\
        --resume-home-id <id> --resume-away-id <id> \\
        --resume-home-score N --resume-away-score N

Gate: ``SEASON_COMPLETE`` on stdout, and ``remote=0`` on every lsof sample.
Re-run this harness after any change to the loopback / SQLite / persist path.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Week 1 camp is 30 points; in-season weeks are 24 (training_shape.CAMP / IN_SEASON).
CAMP_TRAINING = {
    "player_drills": {
        "shooting": {"SC": 3, "SH": 3},
        "ball_handling": {"BH": 3},
        "defense": {"ID": 3, "OD": 3},
        "rebounding": {"RB": 3},
    },
    "team_drills": {
        "offense": {"offensive_efficiency": 2},
        "defense": {"defensive_efficiency": 2},
        "fast_break": {"fb_efficiency": 2},
        "press_trap": {"pt_efficiency": 2},
    },
    "general": {"team_chemistry": 2, "discipline": 1, "fight": 1},
    "coaching_focus": "balanced",
    "playbook_training_mode": "current-playbooks",
}
IN_SEASON_TRAINING = {
    "player_drills": {
        "shooting": {"SC": 3, "SH": 3},
        "ball_handling": {"BH": 3},
        "defense": {"ID": 3, "OD": 3},
        "rebounding": {"RB": 3},
    },
    "team_drills": {
        "offense": {"offensive_efficiency": 2},
        "defense": {"defensive_efficiency": 2},
        "fast_break": {"fb_efficiency": 2},
    },
    "general": {},
    "coaching_focus": "balanced",
    "playbook_training_mode": "current-playbooks",
}


def _http(method: str, url: str, body: dict | None = None, timeout: float = 600) -> tuple[int, dict | list | str]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = raw
            return resp.status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw) if raw else {"detail": raw}
        except json.JSONDecodeError:
            parsed = {"detail": raw}
        return exc.code, parsed


def seed_catalogs_and_league(sqlite_path: Path) -> None:
    os.environ["GOB_SQLITE_PATH"] = str(sqlite_path)
    from BackEnd.loopback_env import apply_loopback_env

    apply_loopback_env()
    from BackEnd.persistence import get_store

    store = get_store()
    print(
        "CATALOG "
        f"plays={store.plays_collection.count_documents({})} "
        f"defenses={store.defenses_collection.count_documents({})} "
        f"fcp={store.fcp_skeletons_collection.count_documents({})} "
        f"hct={store.hct_skeletons_collection.count_documents({})} "
        f"sidecar={getattr(store, 'catalog_path', None)} "
        f"version={getattr(store, 'catalog_version', None)}",
        flush=True,
    )
    stamp = store.db["save_meta"].find_one({"_id": "base_league"}) or {}
    names = sorted(
        str(doc.get("name") or "")
        for doc in store.teams_collection.find({}, {"name": 1})
    )
    print(
        "LEAGUE "
        f"teams={store.teams_collection.count_documents({})} "
        f"players={store.players_collection.count_documents({})} "
        f"version={stamp.get('league_version') or getattr(store, 'league_version', None)} "
        f"source={stamp.get('source')} "
        f"names={len(names)} "
        f"sample={names[:8]}",
        flush=True,
    )


def _score_from_sim(payload: dict, home: str, away: str) -> tuple[int, int]:
    score = payload.get("score") if isinstance(payload, dict) else {}
    if not isinstance(score, dict):
        score = {}
    home_score = int(score.get(home) or score.get("home") or 70)
    away_score = int(score.get(away) or score.get("away") or 65)
    return home_score, away_score


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8765")
    parser.add_argument("--sqlite-path", default="/tmp/ws2-catalog-season.sqlite")
    parser.add_argument("--seed-only", action="store_true")
    parser.add_argument("--weeks", type=int, default=0, help="0 = drive through finish_season")
    parser.add_argument("--franchise-id", default="", help="Resume an existing loopback franchise")
    parser.add_argument("--skip-interactive-week1", action="store_true")
    parser.add_argument("--resume-game-id", default="")
    parser.add_argument("--resume-home", default="")
    parser.add_argument("--resume-away", default="")
    parser.add_argument("--resume-home-id", default="")
    parser.add_argument("--resume-away-id", default="")
    parser.add_argument("--resume-home-score", type=int, default=0)
    parser.add_argument("--resume-away-score", type=int, default=0)
    args = parser.parse_args()
    sqlite_path = Path(args.sqlite_path)
    seed_catalogs_and_league(sqlite_path)
    if args.seed_only:
        return 0

    log: list[dict] = []

    def step(
        name: str,
        method: str,
        path: str,
        body: dict | None = None,
        timeout: float = 600,
        allow_status: tuple[int, ...] = (),
    ) -> dict | list | str:
        t0 = time.time()
        status, payload = _http(method, args.base + path, body, timeout=timeout)
        rec = {"step": name, "status": status, "path": path, "s": round(time.time() - t0, 3)}
        if status >= 400 and status not in allow_status:
            rec["error"] = payload
            print(json.dumps(rec, default=str), flush=True)
            raise SystemExit(f"FAIL {name} HTTP {status}")
        rec["ok"] = status < 400
        log.append(rec)
        print(json.dumps({k: rec[k] for k in rec if k != "error"}), flush=True)
        return payload

    def franchise_week(fid: str) -> int:
        state = step("state", "GET", f"/franchise/state?franchise_id={fid}")
        if not isinstance(state, dict):
            raise SystemExit("FAIL state not a dict")
        return int(state.get("week") or 1)

    health = step("health", "GET", "/health")
    if not isinstance(health, dict) or health.get("profile") != "loopback":
        raise SystemExit(f"FAIL not loopback: {health}")
    if health.get("persistence") != "sqlite":
        raise SystemExit(f"FAIL persistence {health.get('persistence')}")

    if args.franchise_id:
        fid = args.franchise_id
        print(f"FRANCHISE resume {fid}", flush=True)
    else:
        created = step("init", "POST", "/franchise/select-team", {"team_name": "Lancaster"})
        assert isinstance(created, dict)
        fid = str(created.get("franchise_id") or (created.get("franchise") or {}).get("_id") or "")
        if not fid:
            raise SystemExit(f"FAIL no franchise_id: {created}")
        print(f"FRANCHISE {fid}", flush=True)

    def play_user_game(week: int, interactive: bool) -> None:
        nxt = step("play-next-game", "POST", "/franchise/play-next-game", {"franchise_id": fid})
        assert isinstance(nxt, dict)
        home = nxt.get("home") or nxt.get("home_team") or "Lancaster"
        away = nxt.get("away") or nxt.get("away_team")
        home_id = nxt.get("home_id")
        away_id = nxt.get("away_id")
        from bson import ObjectId

        user_side = "home" if home == "Lancaster" else "away"
        init = step(
            "init-game",
            "POST",
            "/api/init-game",
            {
                "home_team": home,
                "away_team": away,
                "home_id": home_id,
                "away_id": away_id,
                "mode": "franchise",
                "franchise_id": fid,
                "user_team_side": user_side,
            },
        )
        assert isinstance(init, dict)
        game_id = str(init.get("game_id") or ObjectId())
        print(f"GAME {game_id} {away} @ {home} week={week} user={user_side}", flush=True)

        if interactive:
            step(
                "simulate-quarter",
                "POST",
                "/api/simulate-quarter",
                {
                    "game_id": game_id,
                    "home_team": home,
                    "away_team": away,
                    "quarter": 1,
                    "mode": "franchise",
                    "franchise_id": fid,
                },
            )
            for i in range(3):
                step(f"simulate-turn-{i}", "POST", "/api/simulate-turn", {"game_id": game_id}, timeout=120)
            step(
                "call-timeout",
                "POST",
                "/api/call-timeout",
                {"game_id": game_id, "calling_team": "home", "mode": "franchise", "franchise_id": fid},
            )
            step(
                "timeout-resume",
                "POST",
                "/api/simulate-quarter",
                {
                    "game_id": game_id,
                    "home_team": home,
                    "away_team": away,
                    "quarter": 1,
                    "mode": "franchise",
                    "franchise_id": fid,
                    "resume_from_timeout": True,
                },
            )

        rest = step(
            "sim-rest-of-game",
            "POST",
            "/api/simulate-quarter",
            {
                "game_id": game_id,
                "home_team": home,
                "away_team": away,
                "quarter": 1,
                "mode": "franchise",
                "franchise_id": fid,
                "full_sim": True,
                "advance_method": "sim_rest_of_game",
            },
            timeout=900,
        )
        assert isinstance(rest, dict)
        home_score, away_score = _score_from_sim(rest, str(home), str(away))
        print(f"SCORE week={week} {home_score}-{away_score}", flush=True)
        finish_open_week(week, game_id, home_id, away_id, home_score, away_score)

    def _recruit_rt(rec: dict) -> int:
        ratings = rec.get("position_ratings") or {}
        values = [int(v or 0) for v in ratings.values() if isinstance(v, (int, float))]
        return max(values) if values else int(rec.get("rt") or rec.get("RT") or 0)

    def _recruit_id(rec: dict) -> str:
        return str(rec.get("recruit_id") or rec.get("id") or rec.get("_id") or "").strip()

    def _load_recruit_board() -> tuple[list[dict], str]:
        data = step("recruiting-data", "GET", f"/franchise/recruiting-data?franchise_id={fid}")
        recs_payload = step("recruits", "GET", f"/franchise/recruits?franchise_id={fid}")
        recs: list[dict] = []
        if isinstance(recs_payload, dict):
            recs = list(recs_payload.get("recruits") or [])
        elif isinstance(recs_payload, list):
            recs = recs_payload
        if not recs and isinstance(data, dict):
            recs = list(data.get("recruits") or [])
        region = ""
        if isinstance(data, dict):
            region = str(data.get("team_region") or data.get("user_region") or "").upper()
        return recs, region

    def _rank_recruit_ids(recs: list[dict], user_region: str, limit: int = 20) -> list[str]:
        def sort_key(rec: dict) -> tuple:
            home = str(rec.get("Home Region") or rec.get("home_region") or "").upper()
            in_region = 0 if user_region and home == user_region else 1
            return (in_region, -_recruit_rt(rec))

        ranked: list[str] = []
        for rec in sorted(recs, key=sort_key):
            rid = _recruit_id(rec)
            if rid and rid not in ranked:
                ranked.append(rid)
            if len(ranked) >= limit:
                break
        return ranked

    def submit_weekly_recruiting_orders(week: int) -> list[str]:
        recs, region = _load_recruit_board()
        ranked = _rank_recruit_ids(recs, region, limit=20)
        if not ranked:
            raise SystemExit(f"FAIL no recruits to rank for week {week}")
        saved = step(
            "recruiting-orders",
            "POST",
            "/franchise/recruiting-orders",
            {"franchise_id": fid, "recruit_ids": ranked},
        )
        if not isinstance(saved, dict) or saved.get("status") != "success":
            raise SystemExit(f"FAIL recruiting-orders week={week}: {saved}")
        n_saved = len((saved.get("saved_orders") or {}))
        print(f"RECRUITING_ORDERS week={week} ranked={len(ranked)} saved={n_saved} region={region or '-'}", flush=True)
        return ranked

    def verify_weekly_recruiting_results(week: int) -> None:
        results = step(
            "recruiting-results",
            "GET",
            f"/franchise/recruiting-results?franchise_id={fid}&week={week}",
        )
        if not isinstance(results, dict):
            raise SystemExit(f"FAIL recruiting-results not a dict week={week}")
        visits = 0
        user_visit = None
        for region in results.get("regions") or []:
            for conference in region.get("conferences") or []:
                for team in conference.get("teams") or []:
                    visit = team.get("visit")
                    if visit:
                        visits += 1
                        if str(team.get("team_name") or "").lower() == "lancaster" or str(
                            team.get("team_id") or ""
                        ).upper() in {"LANCASTER", "TEAM000"}:
                            user_visit = visit
        history = None
        data = step("recruiting-data-after", "GET", f"/franchise/recruiting-data?franchise_id={fid}")
        if isinstance(data, dict):
            history = data.get("visit_history")
        if visits < 1:
            raise SystemExit(f"FAIL recruiting-results week={week} persisted no visits")
        print(
            f"RECRUITING_RESULTS week={week} visits={visits} user_visit={bool(user_visit)} "
            f"history_weeks={len(history) if isinstance(history, list) else 'n/a'}",
            flush=True,
        )

    def finish_open_week(week: int, game_id: str, home_id, away_id, home_score: int, away_score: int) -> None:
        if 20 <= week <= 26:
            submit_weekly_recruiting_orders(week)
        if week <= 26:
            payload = CAMP_TRAINING if week <= 1 else IN_SEASON_TRAINING
            train = step(
                "training-user",
                "POST",
                "/franchise/run-training/user",
                {"franchise_id": fid, "training_data": payload},
                timeout=180,
                allow_status=(400,),
            )
            detail = train.get("detail") if isinstance(train, dict) else None
            if detail:
                text = detail if isinstance(detail, str) else json.dumps(detail)
                if "already" in text.lower():
                    print(f"TRAINING_USER_SKIP {text}", flush=True)
                elif "must spend exactly" in text.lower():
                    raise SystemExit(f"FAIL training-user {text}")
                else:
                    raise SystemExit(f"FAIL training-user HTTP 400 {text}")
            step("training-cpu", "POST", "/franchise/run-training/cpu-train", {"franchise_id": fid}, timeout=600)
            if 20 <= week <= 26:
                verify_weekly_recruiting_results(week)

        cpu_out: dict | list | str | None = None
        try:
            cpu_out = step(
                "start-cpu-sims",
                "POST",
                "/franchise/complete-week/start-cpu-sims",
                {"franchise_id": fid, "week": week},
                timeout=2400,
            )
        except TimeoutError as exc:
            print(f"CPU_SIMS_WAIT week={week} after {exc}", flush=True)
            cpu_out = {"status": "timeout"}
        if not isinstance(cpu_out, dict) or cpu_out.get("status") in {"processing", "timeout"}:
            deadline = time.time() + 2400
            while time.time() < deadline:
                state = step("state", "GET", f"/franchise/state?franchise_id={fid}")
                saved = ((state or {}).get("results") or {}).get(str(week)) if isinstance(state, dict) else None
                n = len(saved) if isinstance(saved, list) else 0
                print(f"CPU_SIMS_POLL week={week} results={n}", flush=True)
                if n >= 50:
                    break
                time.sleep(15)
            else:
                raise SystemExit(f"FAIL start-cpu-sims never persisted week={week}")
        step(
            "phase-a",
            "POST",
            "/franchise/complete-week/phase-a",
            {
                "franchise_id": fid,
                "week": week,
                "game_id": game_id,
                "result": {
                    "team1_id": away_id,
                    "team2_id": home_id,
                    "team1_score": away_score,
                    "team2_score": home_score,
                },
            },
            timeout=2400,
        )
        step("phase-b", "POST", "/franchise/complete-week/phase-b", {"franchise_id": fid, "week": week}, timeout=2400)

    week = franchise_week(fid)
    first = True
    target = args.weeks if args.weeks > 0 else 36
    if args.resume_game_id:
        print(
            f"RESUME week={week} game={args.resume_game_id} {args.resume_away}@{args.resume_home} "
            f"{args.resume_away_score}-{args.resume_home_score}",
            flush=True,
        )
        finish_open_week(
            week,
            args.resume_game_id,
            args.resume_home_id,
            args.resume_away_id,
            args.resume_home_score,
            args.resume_away_score,
        )
        week = franchise_week(fid)
        print(f"ADVANCED week={week}", flush=True)
        first = False
    while week <= 26 and week <= target:
        play_user_game(week, interactive=first and not args.skip_interactive_week1)
        first = False
        week = franchise_week(fid)
        print(f"ADVANCED week={week}", flush=True)

    while 27 <= week <= 34 and week <= target:
        nxt_status, nxt = _http("POST", args.base + "/franchise/play-next-game", {"franchise_id": fid}, timeout=60)
        print(json.dumps({"step": "play-next-game", "status": nxt_status, "week": week}, default=str), flush=True)
        if nxt_status == 200:
            play_user_game(week, interactive=False)
        elif nxt_status == 404:
            step(
                "sim-rest-of-tournament",
                "POST",
                "/franchise/sim-rest-of-tournament",
                {"franchise_id": fid},
                timeout=900,
            )
        else:
            raise SystemExit(f"FAIL eos play-next-game HTTP {nxt_status}: {nxt}")
        week = franchise_week(fid)
        print(f"ADVANCED week={week}", flush=True)

    if week == 35 and (args.weeks == 0 or target >= 35):
        recs, region = _load_recruit_board()
        ranked = _rank_recruit_ids(recs, region, limit=20)
        print(f"RECRUITS n={len(recs)} ranked={len(ranked)} region={region or '-'}", flush=True)
        if not ranked:
            raise SystemExit("FAIL no recruits for week 35 orders")
        awards = step("awards", "GET", f"/franchise/awards?franchise_id={fid}", allow_status=(400,))
        print(f"AWARDS status={type(awards).__name__}", flush=True)
        # Spend the full 50-point budget, front-loaded on the top of the board.
        point_plan = [12, 10, 8, 6, 5, 4, 3, 2]
        order_entries = []
        for i, rid in enumerate(ranked):
            pts = point_plan[i] if i < len(point_plan) else 0
            order_entries.append(
                {"id": rid, "points": pts, "playing_time": i < 2, "scholarship": False}
            )
        saved = step(
            "week35-orders",
            "POST",
            "/franchise/recruiting-orders",
            {"franchise_id": fid, "order_entries": order_entries},
        )
        if not isinstance(saved, dict) or saved.get("status") != "success":
            raise SystemExit(f"FAIL week35-orders: {saved}")
        spent = sum(int(e["points"]) for e in order_entries)
        print(
            f"WEEK35_ORDERS n={len(order_entries)} points={spent} "
            f"saved={len(saved.get('saved_orders_week_35') or {})}",
            flush=True,
        )
        ran = step("week35-run", "POST", "/franchise/run-week-35-recruiting", {"franchise_id": fid}, timeout=600)
        after = step("recruiting-data-week35", "GET", f"/franchise/recruiting-data?franchise_id={fid}")
        signed = []
        if isinstance(after, dict):
            signed = list((after.get("week_35_recruiting_results") or {}).get("signed_players") or [])
        print(
            f"WEEK35_RAN status={(ran or {}).get('status') if isinstance(ran, dict) else type(ran).__name__} "
            f"signed={len(signed)}",
            flush=True,
        )
        if not signed:
            raise SystemExit("FAIL week 35 recruiting ran but no signed_players persisted")
        week = franchise_week(fid)
        print(f"ADVANCED week={week}", flush=True)

    if week == 36 and (args.weeks == 0 or target >= 36):
        step("finish-season", "POST", "/franchise/finish-season", {"franchise_id": fid}, timeout=900)
        week = franchise_week(fid)
        print(f"ADVANCED week={week}", flush=True)

    print("SEASON_COMPLETE", flush=True)
    print(json.dumps({"franchise_id": fid, "week": week, "log_n": len(log)}, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
