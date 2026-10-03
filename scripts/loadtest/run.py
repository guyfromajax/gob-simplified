#!/usr/bin/env python3
"""Staging load runner: replay real franchise weeks for the seeded LOADTEST users.

STAGING ONLY (base URL is hard-checked). Reads users/tokens/franchises written by
seed.py. Each user runs its weeks sequentially; users run concurrently (asyncio).

Week types (the real client sequences; see reports/load-test-2026-09-30.md):
  sim     FCC -> [training gate] -> [week-1 cut] -> play-next-game -> set-lineup
          (init-game, autoset) -> court "Sim Game": start-cpu-sims (fire&forget) +
          serial /api/simulate-quarter full_sim/sim_full_game until is_final ->
          phase-a -> end-of-game popup GETs -> phase-b (awaited, Locker Room) -> FCC
  played  same, but court "Play Game": per quarter /api/simulate-quarter (animated
          mode) + /api/simulate-turn loop, set-lineup round trip at each quarter break

Auth headers are replicated per call exactly as the FE sends them (several court and
week calls send NO Authorization header, which changes their rate-limit key).

Every request -> requests.jsonl (epoch start/end, latency, status); every week ->
weeks.jsonl; aggregate -> summary.json. Output: reports/loadtest/<run-id>/.

    ../gob-simplified/.venv/bin/python scripts/loadtest/run.py --users 1 --plan sim,sim,sim,played
    ../gob-simplified/.venv/bin/python scripts/loadtest/run.py --users 2 --weeks 2 --mix 0.7
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from common import ROOT, STAGING_BASE_URL, load_users, require_staging_url

REPORTS = ROOT / "reports" / "loadtest"
DEFAULT_TIMEOUT = 240.0        # phase-b may wait up to 150 s server-side on an in-flight claim
CPU_SIMS_TIMEOUT = 900.0       # start-cpu-sims sims the whole CPU slate inside the request
TRAINING_POLL_MIN_S = 0.25


def now() -> float:
    return time.time()


def pct(values: list[float], p: float) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    k = max(0, min(len(s) - 1, math.ceil(p / 100 * len(s)) - 1))
    return round(s[k], 3)


class Recorder:
    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        self._req = open(out_dir / "requests.jsonl", "a", buffering=1)
        self._wk = open(out_dir / "weeks.jsonl", "a", buffering=1)
        self.requests: list[dict] = []
        self.weeks: list[dict] = []

    def request(self, row: dict) -> None:
        self.requests.append(row)
        self._req.write(json.dumps(row) + "\n")

    def week(self, row: dict) -> None:
        self.weeks.append(row)
        self._wk.write(json.dumps(row) + "\n")

    def close(self) -> None:
        self._req.close()
        self._wk.close()


class WeekFailed(Exception):
    pass


class Session:
    """One tagged user driving one franchise, exactly like the browser client."""

    def __init__(self, client: httpx.AsyncClient, rec: Recorder, user: dict, run_id: str, turn_think: float):
        self.c = client
        self.rec = rec
        self.u = user
        self.run_id = run_id
        self.turn_think = turn_think
        self.fid = user["franchise_id"]
        self.ctx: dict[str, Any] = {}
        self.pending: list[asyncio.Task] = []

    # --- transport ------------------------------------------------------------
    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.u['token']}"}

    async def call(self, method: str, path: str, *, step: str, auth: bool, template: str | None = None,
                   json_body: Any = None, params: dict | None = None, timeout: float = DEFAULT_TIMEOUT) -> httpx.Response | None:
        headers = self._auth() if auth else {}
        t0 = now()
        status, err, size = 0, None, 0
        resp = None
        try:
            resp = await self.c.request(method, path, json=json_body, params=params, headers=headers, timeout=timeout)
            status, size = resp.status_code, len(resp.content)
        except Exception as e:  # transport error / timeout
            err = f"{type(e).__name__}: {e}"[:300]
        t1 = now()
        self.rec.request({
            "run": self.run_id, "user": self.u["n"], "franchise_id": self.fid,
            "week": self.ctx.get("week"), "week_type": self.ctx.get("week_type"), "step": step,
            "method": method, "path": template or path, "status": status, "error": err,
            "t_start": round(t0, 3), "t_end": round(t1, 3), "latency_s": round(t1 - t0, 3), "bytes": size,
        })
        return resp

    async def json(self, *a, expect=(200,), **k) -> Any:
        r = await self.call(*a, **k)
        if r is None or r.status_code not in expect:
            detail = "" if r is None else r.text[:300]
            raise WeekFailed(f"{k.get('step')}: {None if r is None else r.status_code} {detail}")
        try:
            return r.json()
        except Exception:
            return None

    def fire(self, coro) -> None:
        """Fire-and-forget exactly like the FE (still recorded)."""
        self.pending.append(asyncio.create_task(coro))

    # --- page loads ---------------------------------------------------------------
    async def fcc_load(self) -> dict:
        await self.call("GET", "/app-config", step="fcc", auth=False)
        cc = await self.json("GET", "/franchise/command-center/data", step="fcc", auth=True,
                             params={"franchise_id": self.fid})
        tid = cc.get("team_id")
        self.ctx["team_id"] = tid
        await self.call("GET", "/franchise/team-data", step="fcc", auth=True,
                        params={"franchise_id": self.fid, "team_id": tid})
        await self.call("GET", "/teams", step="fcc", auth=True, params={"franchise_id": self.fid})
        await self.call("GET", f"/roster/{tid}", template="/roster/{team_id}", step="fcc", auth=True,
                        params={"franchise_id": self.fid})
        await self.call("GET", "/franchise/standings", step="fcc", auth=True,
                        params={"franchise_id": self.fid, "scope": "user_region", "team_id": tid})
        await self.call("GET", "/api/gameplan", step="fcc", auth=True,
                        params={"mode": "franchise", "franchise_id": self.fid, "team_id": tid})
        return cc

    # --- week gates -----------------------------------------------------------------
    @staticmethod
    def allocation(budget: int) -> dict:
        """Spend exactly `budget` whole points, 0-5 per leaf, over the FE's leaves."""
        tree = {
            "player_drills": {"offense": {"inside": 0, "outside": 0}, "defense": {"inside": 0, "outside": 0},
                              "technical": {"passing": 0, "ball_handling": 0, "rebounding": 0},
                              "weight_room": {"strength": 0, "agility": 0}},
            "team_drills": {"team_offense": {"install": 0}, "team_defense": {"install": 0},
                            "fast_breaks": {"offense_install": 0, "defense_install": 0}, "scrimmages": 0,
                            "presses_traps": {"defense_install": 0, "offense_install": 0}},
            "general": {"conditioning": 0, "free_throws": 0, "film_study": 0, "breaks": 0},
        }
        leaves: list[tuple[dict, str]] = []

        def walk(node):
            for k, v in node.items():
                if isinstance(v, dict):
                    walk(v)
                else:
                    leaves.append((node, k))
        walk(tree)
        left, i = budget, 0
        while left > 0:
            parent, key = leaves[i % len(leaves)]
            if parent[key] < 5:
                parent[key] += 1
                left -= 1
            i += 1
        return tree

    async def training(self) -> None:
        tp = await self.json("GET", "/franchise/training-points", step="training", auth=False,
                             params={"franchise_id": self.fid})
        if tp.get("training_unavailable"):
            return
        data = {**self.allocation(int(tp["training_points"])), "coaching_focus": None,
                "playbook_training_mode": "current-playbooks", "training_playbook_focus": None}
        await self.json("POST", "/franchise/run-training/user", step="training", auth=True,
                        json_body={"franchise_id": self.fid, "team_id": self.ctx["team_id"], "training_data": data})
        while True:  # cpu-train polls while practice-squad games run (training.js:1621-1645)
            r = await self.json("POST", "/franchise/run-training/cpu-train", step="training", auth=True,
                                json_body={"franchise_id": self.fid})
            if (r or {}).get("status") != "processing":
                break
            await asyncio.sleep(max(TRAINING_POLL_MIN_S, float((r or {}).get("retry_after_ms") or 1000) / 1000))

    async def cut(self, cut_count: int) -> None:
        roster = await self.json("GET", f"/roster/{self.ctx['team_id']}", template="/roster/{team_id}",
                                 step="cut", auth=True, params={"franchise_id": self.fid})
        players = sorted(roster.get("players") or [], key=lambda p: float(p.get("rt") or 0))
        ids = [str(p["_id"]) for p in players[:cut_count]]
        await self.json("POST", "/franchise/cut-players", step="cut", auth=True,
                        json_body={"franchise_id": self.fid, "player_ids": ids})

    # --- game -------------------------------------------------------------------------
    async def set_lineup(self, game: dict, quarter: int) -> dict:
        """set-lineup page for this quarter; returns the user's autoset lineup."""
        await self.call("GET", "/franchise/command-center/data", step="set-lineup", auth=True,
                        params={"franchise_id": self.fid})
        roster = await self.json("GET", f"/roster/{self.ctx['team_id']}", template="/roster/{team_id}",
                                 step="set-lineup", auth=True, params={"franchise_id": self.fid, "profile": 1})
        if quarter == 1 and not game.get("game_id"):
            init = await self.json("POST", "/api/init-game", step="init-game", auth=True, json_body={
                "home_team": game["home"], "away_team": game["away"], "mode": "franchise",
                "home_id": game["home_id"], "away_id": game["away_id"],
                "user_team_side": game["my_team"], "franchise_id": self.fid})
            game["game_id"] = init["game_id"]
        await self.call("GET", f"/api/game/{game['game_id']}", template="/api/game/{id}", step="set-lineup",
                        auth=True, params={"quarter": quarter, "source": "db"})
        await self.call("GET", "/api/playbooks", step="set-lineup", auth=True, params={
            "mode": "franchise", "team_id": self.ctx["team_id"], "franchise_id": self.fid, "game_id": game["game_id"]})
        if quarter == 1:
            self.fire(self.call("POST", "/player-image/warm-teams", step="set-lineup", auth=True,
                                json_body={"franchise_id": self.fid, "teams": [game["home_id"], game["away_id"]]}))
        lineup = await self.autoset(roster, quarter)
        return lineup

    async def autoset(self, roster: dict, quarter: int, *, franchise_scoped: bool = True) -> dict:
        players = [{"_id": str(p.get("_id")), "first_name": p.get("first_name", ""), "last_name": p.get("last_name", ""),
                    "name": p.get("name"), "attributes": p.get("attributes") or {},
                    "position_ratings": p.get("position_ratings") or {}, "stats": {}}
                   for p in (roster.get("players") or [])]
        body = {"players": players, "game_state": {"quarter": quarter, "time_remaining": 240 if quarter > 4 else 480},
                "team_chemistry": roster.get("team_chemistry")}
        if franchise_scoped:
            body.update({"franchise_id": self.fid, "team_id": self.ctx["team_id"]})
        r = await self.json("POST", "/api/autoset-lineup", step="autoset", auth=True, json_body=body)
        return (r or {}).get("lineup") or {}

    async def court_chrome(self, game: dict) -> tuple[dict, dict, dict, dict]:
        """court.html load: chrome GETs, start-cpu-sims (fire&forget), gameplan/playbooks/rosters."""
        await self.call("GET", f"/api/game/{game['game_id']}/resume-state", template="/api/game/{id}/resume-state",
                        step="court", auth=True)
        await self.call("GET", "/franchise/command-center/data", step="court", auth=True, params={"franchise_id": self.fid})
        self.fire(self.call("POST", "/franchise/complete-week/start-cpu-sims", step="start-cpu-sims", auth=True,
                            json_body={"franchise_id": self.fid, "week": game["week"]}, timeout=CPU_SIMS_TIMEOUT))
        gp = await self.json("GET", "/api/gameplan", step="court", auth=False, params={
            "mode": "franchise", "team_id": self.ctx["team_id"], "game_id": game["game_id"], "franchise_id": self.fid})
        pb = await self.json("GET", "/api/playbooks", step="court", auth=False, params={
            "mode": "franchise", "team_id": self.ctx["team_id"], "franchise_id": self.fid, "game_id": game["game_id"], "profile": 1})
        home_r, away_r = await asyncio.gather(
            self.json("GET", f"/roster/{game['home']}", template="/roster/{name}", step="court", auth=False,
                      params={"franchise_id": self.fid, "profile": 1}),
            self.json("GET", f"/roster/{game['away']}", template="/roster/{name}", step="court", auth=False,
                      params={"franchise_id": self.fid, "profile": 1}),
        )
        return gp or {}, pb or {}, home_r or {}, away_r or {}

    @staticmethod
    def _strategy(gp: dict) -> dict:
        s = gp.get("strategy_settings") if isinstance(gp, dict) else None
        return s if isinstance(s, dict) else {}

    async def sim_game(self, game: dict) -> dict:
        """court_start=sim: serial simulate-quarter full_sim loop (bootGame.js:3110-3230)."""
        user_lineup = await self.set_lineup(game, 1)
        gp, _pb, home_r, away_r = await self.court_chrome(game)
        side = game["my_team"]
        quarter, last = 1, {}
        while True:
            body = {"home_team": game["home"], "away_team": game["away"], "home_id": game["home_id"],
                    "away_id": game["away_id"], "quarter": quarter, "game_id": game["game_id"], "mode": "franchise",
                    "franchise_id": self.fid, "week": game["week"], "full_sim": True,
                    "advance_method": "sim_full_game", "user_team_side": side,
                    "strategy_settings": self._strategy(gp)}
            if quarter == 1:
                body[f"{side}_lineup"] = user_lineup
            else:
                hl, al = await asyncio.gather(self.autoset(home_r, quarter, franchise_scoped=False),
                                              self.autoset(away_r, quarter, franchise_scoped=False))
                body.update({"home_lineup": hl, "away_lineup": al, "start_with_inbound": True,
                             "starting_possession": random.choice(["home", "away"])})
            last = await self.json("POST", "/api/simulate-quarter", step="game", auth=False, json_body=body)
            game["game_id"] = last.get("game_id") or game["game_id"]
            if last.get("is_final"):
                return last
            quarter += 1
            if quarter > 12:
                raise WeekFailed("game did not finish by quarter 12")

    async def played_game(self, game: dict) -> dict:
        """court_start=play: simulate-quarter (animated) + simulate-turn loop per quarter."""
        quarter = 1
        while True:
            user_lineup = await self.set_lineup(game, quarter)
            gp, pb, _h, _a = await self.court_chrome(game)
            side = game["my_team"]
            body = {"home_team": game["home"], "away_team": game["away"], "home_id": game["home_id"],
                    "away_id": game["away_id"], "quarter": quarter, "game_id": game["game_id"], "mode": "franchise",
                    "franchise_id": self.fid, "user_team_side": side, "strategy_settings": self._strategy(gp),
                    "playbook_settings": pb if isinstance(pb, dict) else {}, "lineup_checkpoint": True,
                    f"{side}_lineup": user_lineup}
            await self.json("POST", "/api/simulate-quarter", step="game", auth=False, json_body=body)
            turns = 0
            while True:
                t = await self.json("POST", "/api/simulate-turn", step="game-turn", auth=False,
                                    json_body={"game_id": game["game_id"], "offense_override": None,
                                               "defense_override": None, "mode": "franchise"})
                turns += 1
                if self.turn_think:
                    await asyncio.sleep(self.turn_think)
                if t.get("is_final"):
                    return await self.json("GET", f"/api/game/{game['game_id']}", template="/api/game/{id}",
                                           step="finalize", auth=True)
                if t.get("quarter_complete") or float(t.get("time_remaining") or 0) <= 0 or turns > 400:
                    break
            quarter += 1
            if quarter > 12:
                raise WeekFailed("game did not finish by quarter 12")

    @staticmethod
    def _final_doc(final: dict) -> dict:
        doc = final.get("final_game_document") if isinstance(final, dict) else None
        return doc if isinstance(doc, dict) else final

    @staticmethod
    def _scores(doc: dict, game: dict) -> tuple[int, int]:
        teams = doc.get("teams") or {}
        smap = doc.get("final_score") or doc.get("score") or {}

        def pick(side_id: str, name: str) -> int:
            for key in (side_id, name):
                if key in smap and smap[key] is not None:
                    return int(smap[key])
            t = teams.get(side_id) or {}
            return int(t.get("score") or 0)
        return pick(game["away_id"], game["away"]), pick(game["home_id"], game["home"])

    async def finalize(self, game: dict, final: dict) -> None:
        doc = self._final_doc(final)
        away_score, home_score = self._scores(doc, game)
        gid = str(doc.get("game_id") or doc.get("_id") or game["game_id"])
        week = int(doc.get("week") or game["week"])
        await self.json("POST", "/franchise/complete-week/phase-a", step="phase-a", auth=False, json_body={
            "franchise_id": self.fid, "week": week, "game_id": gid,
            "result": {"team1_id": game["away_id"], "team2_id": game["home_id"],
                       "team1_score": away_score, "team2_score": home_score},
            "game_document": doc})
        await self.call("GET", "/franchise/championship-moments/context", step="popup", auth=True,
                        params={"franchise_id": self.fid, "game_id": gid})
        await self.call("GET", f"/api/game/{gid}", template="/api/game/{id}", step="popup", auth=True)
        # FE fires phase-b when the popup renders; Locker Room awaits the same promise.
        await self.json("POST", "/franchise/complete-week/phase-b", step="phase-b", auth=True,
                        json_body={"franchise_id": self.fid, "week": week}, timeout=DEFAULT_TIMEOUT)

    # --- one week -----------------------------------------------------------------------
    async def run_week(self, week_type: str) -> dict:
        self.ctx["week_type"] = week_type
        t0 = now()
        marks: dict[str, float] = {}
        row: dict = {"run": self.run_id, "user": self.u["n"], "franchise_id": self.fid, "week_type": week_type}
        try:
            cc = await self.fcc_load()
            week = int(cc.get("week") or 1)
            self.ctx["week"] = week
            row["week"] = week
            if cc.get("cpu_sim_resume") and (cc["cpu_sim_resume"] or {}).get("phase_b_required"):
                await self.json("POST", "/franchise/complete-week/phase-b", step="phase-b-resume", auth=True,
                                json_body={"franchise_id": self.fid, "week": cc["cpu_sim_resume"].get("week", week)})
                cc = await self.fcc_load()
                week = int(cc.get("week") or week)
                self.ctx["week"] = week
                row.update({"week": week, "resumed_phase_b": True})
            if week > 19:
                raise WeekFailed(f"week {week}: recruiting/EOS gates are out of scope for this tool")
            t = now()
            if not cc.get("training_completed") and not cc.get("training_disabled_for_eos"):
                await self.training()
                cc = await self.fcc_load()
            marks["training_s"] = now() - t
            if cc.get("cut_required"):
                t = now()
                await self.cut(int(cc.get("cut_count") or 0))
                cc = await self.fcc_load()
                marks["cut_s"] = now() - t
            t = now()
            nxt = await self.json("POST", "/franchise/play-next-game", step="play-next-game", auth=True,
                                  json_body={"franchise_id": self.fid})
            tid = str(self.ctx["team_id"])
            game = {"home": nxt["home"], "away": nxt["away"], "home_id": str(nxt["home_id"]),
                    "away_id": str(nxt["away_id"]), "week": int(nxt.get("week") or week),
                    "my_team": "home" if str(nxt["home_id"]) == tid else "away", "game_id": None}
            final = await (self.sim_game(game) if week_type == "sim" else self.played_game(game))
            marks["game_s"] = now() - t
            t = now()
            await self.finalize(game, final)
            marks["advance_s"] = now() - t
            if self.pending:
                await asyncio.gather(*self.pending, return_exceptions=True)
                self.pending.clear()
            await self.fcc_load()
            row["ok"] = True
        except WeekFailed as e:
            row["ok"], row["error"] = False, str(e)[:500]
        except Exception as e:
            row["ok"], row["error"] = False, f"{type(e).__name__}: {e}"[:500]
        finally:
            if self.pending:
                await asyncio.gather(*self.pending, return_exceptions=True)
                self.pending.clear()
        row.update({k: round(v, 2) for k, v in marks.items()})
        row.update({"t_start": round(t0, 3), "t_end": round(now(), 3), "wall_s": round(now() - t0, 2)})
        self.rec.week(row)
        return row


def summarize(rec: Recorder, meta: dict) -> dict:
    by_ep: dict[str, list[float]] = defaultdict(list)
    codes: dict[str, int] = defaultdict(int)
    for r in rec.requests:
        by_ep[f"{r['method']} {r['path']}"].append(r["latency_s"])
        codes[str(r["status"])] += 1
    ok_weeks = [w for w in rec.weeks if w.get("ok")]
    walls = [w["wall_s"] for w in ok_weeks]
    total = len(rec.requests) or 1
    five = sum(v for k, v in codes.items() if k.startswith("5"))
    summary = {
        **meta,
        "weeks": len(rec.weeks), "weeks_ok": len(ok_weeks),
        "week_wall_s": {"p50": pct(walls, 50), "p95": pct(walls, 95), "max": max(walls) if walls else None},
        "by_week_type": {
            t: {"n": len(ws), "p50": pct([w["wall_s"] for w in ws], 50), "max": max([w["wall_s"] for w in ws], default=None)}
            for t in ("sim", "played") for ws in [[w for w in ok_weeks if w["week_type"] == t]] if ws
        },
        "status_codes": dict(codes), "n429": codes.get("429", 0), "n5xx": five,
        "rate_5xx": round(five / total, 4), "n_transport_errors": codes.get("0", 0),
        "max_request_s": max((r["latency_s"] for r in rec.requests), default=None),
        "endpoints": {
            ep: {"n": len(v), "p50": pct(v, 50), "p95": pct(v, 95), "max": round(max(v), 3), "sum": round(sum(v), 2)}
            for ep, v in sorted(by_ep.items(), key=lambda kv: -sum(kv[1]))
        },
        "week_rows": rec.weeks,
    }
    (rec.out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


async def run_step(users: list[dict], plan_for, *, label: str, turn_think: float, out_dir: Path) -> dict:
    base = require_staging_url(STAGING_BASE_URL)
    rec = Recorder(out_dir)
    run_id = out_dir.name
    t0 = now()
    limits = httpx.Limits(max_connections=max(10, 8 * len(users)), max_keepalive_connections=max(10, 4 * len(users)))
    async with httpx.AsyncClient(base_url=base, limits=limits, http2=False) as client:
        async def one(u: dict):
            s = Session(client, rec, u, run_id, turn_think)
            for wt in plan_for(u):
                w = await s.run_week(wt)
                if not w.get("ok"):
                    break
        await asyncio.gather(*(one(u) for u in users))
    meta = {"run_id": run_id, "label": label, "users": len(users), "t_start": round(t0, 3),
            "t_end": round(now(), 3),
            "t_start_iso": datetime.fromtimestamp(t0, timezone.utc).isoformat(),
            "t_end_iso": datetime.now(timezone.utc).isoformat()}
    s = summarize(rec, meta)
    rec.close()
    return s


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--users", type=int, required=True, help="Use seeded users 1..N concurrently.")
    p.add_argument("--plan", help="Explicit per-user week types, e.g. sim,sim,sim,played.")
    p.add_argument("--weeks", type=int, default=2, help="Weeks per user when --plan is not given.")
    p.add_argument("--mix", type=float, default=0.7, help="Fraction of sim weeks (rest played).")
    p.add_argument("--turn-think", type=float, default=0.0, help="Seconds between simulate-turn calls (animation).")
    p.add_argument("--label", default="run")
    p.add_argument("--seed", type=int, default=1)
    args = p.parse_args()

    users = [u for u in load_users() if u.get("franchise_id") and u["n"] <= args.users]
    if len(users) < args.users:
        raise SystemExit(f"only {len(users)} seeded users with franchises; run seed.py --n {args.users}")
    rng = random.Random(args.seed)
    if args.plan:
        plan = [x.strip() for x in args.plan.split(",") if x.strip()]
        plan_for = lambda u: plan
    else:
        plans = {u["n"]: ["sim" if rng.random() < args.mix else "played" for _ in range(args.weeks)] for u in users}
        plan_for = lambda u: plans[u["n"]]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = REPORTS / f"{stamp}-{args.label}-n{args.users}"
    summary = asyncio.run(run_step(users, plan_for, label=args.label, turn_think=args.turn_think, out_dir=out))
    brief = {k: summary[k] for k in ("run_id", "users", "weeks", "weeks_ok", "week_wall_s", "by_week_type",
                                     "n429", "n5xx", "rate_5xx", "n_transport_errors", "max_request_s")}
    print(json.dumps(brief, indent=2))
    for w in summary["week_rows"]:
        print({k: w.get(k) for k in ("user", "week", "week_type", "ok", "wall_s", "training_s", "cut_s",
                                     "game_s", "advance_s", "error")})
    top = list(summary["endpoints"].items())[:8]
    print("top endpoints by total time:")
    for ep, v in top:
        print(f"  {ep}: n={v['n']} sum={v['sum']}s p50={v['p50']} p95={v['p95']} max={v['max']}")
    print(f"output: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
