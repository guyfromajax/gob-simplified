#!/usr/bin/env python3
"""§11 authorship-vs-development audit — three arms, same seed.

Answers the measurement brief in
``_documentation_master/projects/s11-development-vs-authorship.md``.

Path under test
---------------
1. **Apply stamp** via ``apply_diffs_to_inherited_roster`` + ``build_fpd_docs_from_players``
   (same functions ``replace_slot_roster`` / ``team_builder_apply`` use).
2. **Offseason** via ``develop_rollover(..., season_allocation=None)`` — the exact call
   ``finish_season`` makes today for every player, because
   ``_coaching_accumulator_for_player`` is hardwired to return ``None`` (f ≡ 1.0).

Why not full game weeks / full ``finish_season``
------------------------------------------------
``develop_one_offseason`` does **not** consume minutes, usage, or box-score stats.
Shape is an α-blend toward ``position_profile(training_position)``; level closes to
the ladder RT. The only in-season input is ``season_allocation`` → coaching_f, and
that seam currently returns None for everyone. Full seasons would measure the same
attractor at ~148 min/arm. Schedule/recruit regen inside ``finish_season`` does not
touch the original fifteen's attributes.

Scratch data
------------
Pool read is read-only from Atlas. All franchise-shaped state is in-memory — no
franchise rows are written. (No local mongod on this machine; in-memory is the
scratch copy.)

Usage
-----
    .venv/bin/python scripts/s11_authorship_drift_audit.py
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

for _env in (".env", ".env.local"):
    p = _REPO / _env
    if not p.exists():
        continue
    for line in p.read_text().splitlines():
        if not line.strip() or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from bson import ObjectId  # noqa: E402
from pymongo import MongoClient  # noqa: E402

from BackEnd.constants.team_builder_budget import (  # noqa: E402
    CORE_12_ATTRS,
    capped_budget_for_inherited,
    core12_total,
    force_core12_to_budget,
)
from BackEnd.utils.player_development import GROWTH_ATTRS, develop_rollover  # noqa: E402
from BackEnd.utils.player_generation import position_profile  # noqa: E402
from BackEnd.utils.team_builder_roster import (  # noqa: E402
    AUTHORED_ROSTER_SIZE,
    SCHOLARSHIP_SIZE,
    WALK_ON_COUNT,
    _build_inherited_roster_payloads,
    _enrich_payload_from_core,
    _lookup_core_player,
    _payload_from_fpd_doc,
    _payload_from_wizard_walk_on,
    apply_diffs_to_inherited_roster,
    build_fpd_docs_from_players,
    build_wizard_walk_on_players,
)

SEED = 20260806
# Couer d'Alene — league-median attribute total (5504 = p50), height sum 870 vs
# league p50 875. Excludes South Lancaster (unexplained +~1,600).
BASE_TEAM_ID = "69a6fcb68d2c56aa82e48ac0"
BASE_TEAM_NAME = "Couer d'Alene"
OUT_DIR = _REPO / "tmp" / "s11_audit"
FINDINGS_PATH = (
    _REPO / "_documentation_master" / "projects" / "s11-authorship-drift-findings.md"
)

YEAR_ORDER = ("Freshman", "Sophomore", "Junior", "Senior")


def _load_db():
    uri = os.environ.get("MONGO_URI")
    if not uri:
        sys.exit("MONGO_URI not set")
    return MongoClient(uri, serverSelectionTimeoutMS=20000).get_default_database()


def _core_to_fpd_shell(doc: dict[str, Any], team_oid: ObjectId) -> dict[str, Any]:
    """Shape a pool player as the FPD clone source init leaves for the slot."""
    attrs = dict(doc.get("attributes") or {})
    meta = {
        "first_name": doc.get("first_name") or "",
        "last_name": doc.get("last_name") or "",
        "team": BASE_TEAM_NAME,
        "team_id": str(team_oid),
        "height": doc.get("height"),
        "weight": doc.get("weight"),
        "year": doc.get("year"),
        "jersey": doc.get("jersey"),
        "archetype": doc.get("archetype"),
    }
    return {
        "player_id": str(doc.get("player_id") or doc.get("_id")),
        "meta": meta,
        "attributes": attrs,
        "position_ratings": dict(doc.get("position_ratings") or {}),
        "archetype": doc.get("archetype"),
    }


def _best_rt(ratings: dict[str, Any] | None) -> tuple[str, float]:
    ratings = ratings or {}
    if not ratings:
        return "SF", 0.0
    pos = max(ratings, key=lambda k: float(ratings.get(k) or 0))
    return pos, float(ratings.get(pos) or 0)


def _core_vals(attrs: dict[str, Any]) -> dict[str, int]:
    out = {}
    for a in CORE_12_ATTRS:
        v = attrs.get(f"anchor_{a}", attrs.get(a))
        out[a] = int(v or 0)
    return out


def _shape_vec(attrs: dict[str, Any]) -> list[float]:
    vals = []
    for a in GROWTH_ATTRS:
        v = attrs.get(f"anchor_{a}", attrs.get(a))
        vals.append(float(v or 0))
    s = sum(vals) or 1.0
    return [v / s for v in vals]


def _profile_vec(position: str) -> list[float]:
    prof = position_profile(position)
    vals = [float(prof.get(a, 0.0)) for a in GROWTH_ATTRS]
    s = sum(vals) or 1.0
    return [v / s for v in vals]


def _profile_deviation(attrs: dict[str, Any], position: str) -> float:
    a = _shape_vec(attrs)
    p = _profile_vec(position)
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, p)))


def _mean_abs_delta(a0: dict[str, int], a1: dict[str, int]) -> float:
    return sum(abs(a1[k] - a0[k]) for k in CORE_12_ATTRS) / len(CORE_12_ATTRS)


def _is_senior(year: Any) -> bool:
    y = str(year or "").strip().lower()
    return y in {"senior", "sr"}


def _advance_year(year: Any) -> str:
    mapping = {
        "jh": "Freshman",
        "freshman": "Sophomore",
        "sophomore": "Junior",
        "junior": "Senior",
    }
    return mapping.get(str(year or "").strip().lower(), str(year or "Freshman").title())


def _snapshot_player(doc: dict[str, Any]) -> dict[str, Any]:
    attrs = _core_vals(doc.get("attributes") or {})
    pos = doc.get("training_position") or doc.get("position_intent") or _best_rt(
        doc.get("position_ratings")
    )[0]
    best_pos, best_rt = _best_rt(doc.get("position_ratings"))
    return {
        "player_id": doc["player_id"],
        "name": f"{(doc.get('meta') or {}).get('first_name','')} {(doc.get('meta') or {}).get('last_name','')}".strip(),
        "year": (doc.get("meta") or {}).get("year"),
        "height": (doc.get("meta") or {}).get("height"),
        "position_intent": doc.get("position_intent"),
        "training_position": doc.get("training_position") or doc.get("position_intent"),
        "entry_tier": doc.get("entry_tier"),
        "potential_factor": doc.get("potential_factor"),
        "archetype": (doc.get("meta") or {}).get("archetype"),
        "attrs": attrs,
        "best_pos": best_pos,
        "best_rt": best_rt,
        "profile_dev": _profile_deviation(doc.get("attributes") or {}, pos),
        "has_development": bool(doc.get("development")),
    }


def _build_inherited(
    db,
    team_oid: ObjectId,
    walk_ons: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[int]]:
    """Build the 15-slot inherited clone bases the Apply path diffs onto."""
    cores = list(db.players.find({"team_id": str(team_oid)}))
    if len(cores) < SCHOLARSHIP_SIZE:
        sys.exit(f"expected {SCHOLARSHIP_SIZE} pool players, got {len(cores)}")
    # Stable order: descending best RT (matches typical FTD sort after init).
    cores.sort(key=lambda d: -_best_rt(d.get("position_ratings"))[1])
    cores = cores[:SCHOLARSHIP_SIZE]

    ordered_fpd = [_core_to_fpd_shell(c, team_oid) for c in cores]
    old_ids = [str(c.get("player_id") or c.get("_id")) for c in cores]
    # Pad FTD-style id list to 15 with placeholders — walk-ons come from wizard.
    old_ids = old_ids + [f"__walk_{i}" for i in range(WALK_ON_COUNT)]

    inherited = _build_inherited_roster_payloads(
        ordered_fpd=ordered_fpd,
        old_player_ids=old_ids,
        team_name=BASE_TEAM_NAME,
        team_object_id=team_oid,
        players_collection=db.players,
        wizard_walk_ons=walk_ons,
    )
    budgets = [
        capped_budget_for_inherited(core12_total(p.get("attributes") or {}))
        for p in inherited
    ]
    return inherited, old_ids, budgets


def _control_rows(inherited: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Zero-edit Establish: names only (blank attrs → inherit)."""
    rows = []
    for p in inherited:
        meta = p.get("meta") or {}
        rows.append(
            {
                "first_name": meta.get("first_name") or "X",
                "last_name": meta.get("last_name") or "Player",
                "walk_on": str(meta.get("archetype") or "") == "Walk On",
            }
        )
    return rows


def _realistic_rows(inherited: list[dict[str, Any]], budgets: list[int]) -> list[dict[str, Any]]:
    """Moderate within-budget reshape on ~half the scholarship roster.

    Pushes *away* from the position profile (boost a low-weight attr, trim a
    signature attr) — authorship that increases profile deviation, not a
    re-fit toward the attractor.
    """
    rows = _control_rows(inherited)
    targets = [0, 1, 2, 4, 5, 7]  # six scholarship players
    # Off-profile boosts by position family.
    boost_of = {
        "PG": "RB", "SG": "RB", "SF": "PS", "PF": "BH", "C": "BH",
    }
    cut_of = {
        "PG": "PS", "SG": "SH", "SF": "SC", "PF": "RB", "C": "RB",
    }
    for i in targets:
        base = inherited[i]
        attrs = _core_vals(base.get("attributes") or {})
        ratings = base.get("position_ratings") or {}
        pos = base.get("position_intent") or _best_rt(ratings)[0]
        budget = budgets[i]
        boost = boost_of.get(pos, "BH")
        cut = cut_of.get(pos, "RB")
        if boost == cut:
            boost = "FT"
        delta = max(8, budget // 20)  # ~5% of budget, at least 8 pts
        attrs[boost] = min(99, attrs[boost] + delta)
        attrs[cut] = max(5, attrs[cut] - delta)
        # Small second swap for a bit more shape change.
        attrs[boost] = min(99, attrs[boost] + delta // 2)
        other = "ND" if boost != "ND" else "IQ"
        attrs[other] = max(5, attrs[other] - delta // 2)
        attrs = force_core12_to_budget(attrs, budget)
        row = dict(rows[i])
        row["attributes"] = attrs
        rows[i] = row
    return rows


def _extreme_rows(inherited: list[dict[str, Any]], budgets: list[int]) -> list[dict[str, Any]]:
    """6'2\" centre with RB → 90, maximally far from C profile shape."""
    rows = _control_rows(inherited)
    # Prefer an existing C (best RT at C); fall back to tallest.
    c_idx = None
    best_c_rt = -1
    for i, p in enumerate(inherited[:SCHOLARSHIP_SIZE]):
        ratings = p.get("position_ratings") or {}
        c_rt = float(ratings.get("C") or 0)
        if c_rt > best_c_rt:
            best_c_rt = c_rt
            c_idx = i
    assert c_idx is not None
    budget = budgets[c_idx]
    # Drain into RB=90; leftovers on guard skills — opposite of C signature RB/ID/ST.
    rb = min(90, max(5, budget - 11 * 5))
    new_attrs = {a: 5 for a in CORE_12_ATTRS}
    new_attrs["RB"] = rb
    rem = budget - sum(new_attrs.values())
    prefer = ["BH", "PS", "SH", "FT", "SC", "IQ", "ND", "AG", "OD", "ID", "ST"]
    for a in prefer:
        if rem <= 0:
            break
        add = min(rem, 99 - new_attrs[a])
        new_attrs[a] += add
        rem -= add
    new_attrs = force_core12_to_budget(new_attrs, budget)
    row = dict(rows[c_idx])
    row["height_in"] = 74  # 6'2"
    row["attributes"] = new_attrs
    # Keep position_intent as C so the attractor fights the authorship.
    row["position_intent"] = "C"
    rows[c_idx] = row
    return rows, c_idx


def _stamp_arm(
    *,
    franchise_id: ObjectId,
    team_oid: ObjectId,
    inherited: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    budgets: list[int],
) -> list[dict[str, Any]]:
    players = apply_diffs_to_inherited_roster(
        inherited=inherited,
        imported_players=rows,
        team_name=f"S11 {BASE_TEAM_NAME}",
        team_object_id=team_oid,
        attribute_mode="capped",
        apply_topup=True,
        budgets=budgets,
    )
    # Walk-on stamp (same as replace_slot_roster).
    for player in players[SCHOLARSHIP_SIZE:AUTHORED_ROSTER_SIZE]:
        meta = player.setdefault("meta", {})
        meta["archetype"] = "Walk On"
        if not player.get("entry_tier"):
            player["entry_tier"] = "Poor"
    # Mint stable ids (Apply mints fresh uuids — do the same, seeded via uuid4 after seed).
    for player in players:
        pid = str(uuid.uuid4())
        player["player_id"] = pid
        meta = player.setdefault("meta", {})
        meta.pop("player_id", None)
    _, docs = build_fpd_docs_from_players(franchise_id=franchise_id, players=players)
    return docs


def _rollover_once(docs: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
    """Mirror finish_season's returning-player develop_rollover loop (no signings)."""
    next_docs: list[dict[str, Any]] = []
    for fpd_doc in docs:
        meta = dict(fpd_doc.get("meta") or {})
        year = meta.get("year")
        if _is_senior(year):
            continue
        meta["year"] = _advance_year(year)
        next_doc = {
            "franchise_id": fpd_doc.get("franchise_id"),
            "player_id": fpd_doc["player_id"],
            "meta": meta,
            "season": {},
            "career": deepcopy(fpd_doc.get("career") or {}),
            "attributes": deepcopy(fpd_doc.get("attributes") or {}),
            "position_ratings": deepcopy(fpd_doc.get("position_ratings") or {}),
            "development": fpd_doc.get("development"),
            "entry_tier": fpd_doc.get("entry_tier"),
            "position_intent": fpd_doc.get("position_intent"),
            "potential_factor": fpd_doc.get("potential_factor"),
            "training_position": fpd_doc.get("training_position"),
            "coaching_quality": fpd_doc.get("coaching_quality"),
        }
        # Identical to finish_season: season_allocation from seam → None → f 1.0.
        _dev = develop_rollover(next_doc, meta["year"], rng, season_allocation=None)
        next_doc["attributes"] = _dev["attributes"]
        next_doc["meta"]["height"] = _dev["height"]
        next_doc["meta"]["weight"] = _dev["weight"]
        next_doc["position_ratings"] = _dev["position_ratings"]
        next_doc["development"] = _dev["development"]
        next_doc["entry_tier"] = _dev["entry_tier"]
        next_doc["position_intent"] = _dev["position_intent"]
        next_doc["potential_factor"] = _dev["potential_factor"]
        next_doc["training_position"] = _dev["training_position"]
        next_doc["coaching_quality"] = _dev["coaching_quality"]
        next_docs.append(next_doc)
    return next_docs


def _run_arm(
    name: str,
    docs: list[dict[str, Any]],
    *,
    focus_pid: str | None = None,
) -> dict[str, Any]:
    t0 = {d["player_id"]: _snapshot_player(d) for d in docs}
    original_ids = set(t0)
    history: list[dict[str, Any]] = []
    living = docs
    season = 0
    graduations: dict[str, dict[str, Any]] = {}

    # Record seniors who start as seniors — they never take an offseason as SR→gone;
    # their "graduation" snapshot is t0 (they leave without another develop).
    for pid, snap in t0.items():
        if _is_senior(snap["year"]):
            graduations[pid] = {"season": 0, "snap": snap, "note": "senior_at_t0_no_develop"}

    while living and season < 6:
        # Anyone who is senior AFTER this season's develop will graduate next pass;
        # measure post-develop state each season for survivors.
        season += 1
        rng = random.Random(SEED + season)  # same sequence per season across arms
        # Pre-count who will graduate (current seniors leave without developing).
        for d in living:
            if _is_senior((d.get("meta") or {}).get("year")) and d["player_id"] not in graduations:
                graduations[d["player_id"]] = {
                    "season": season - 1,
                    "snap": _snapshot_player(d),
                    "note": "graduated_as_senior",
                }
        living = _rollover_once(living, rng)
        survivors = {d["player_id"] for d in living}
        # Players who disappeared this rollover graduated.
        for pid in original_ids - survivors:
            if pid not in graduations:
                # Should have been captured as senior pre-rollover; if not, last known.
                pass
        season_snaps = []
        for d in living:
            if d["player_id"] not in original_ids:
                continue
            snap = _snapshot_player(d)
            t0s = t0[d["player_id"]]
            season_snaps.append(
                {
                    "player_id": d["player_id"],
                    "name": snap["name"],
                    "year": snap["year"],
                    "mean_abs_delta": _mean_abs_delta(t0s["attrs"], snap["attrs"]),
                    "delta_rt": snap["best_rt"] - t0s["best_rt"],
                    "profile_dev": snap["profile_dev"],
                    "profile_dev_t0": t0s["profile_dev"],
                    "retention": (
                        snap["profile_dev"] / t0s["profile_dev"]
                        if t0s["profile_dev"] > 1e-9
                        else None
                    ),
                    "focus": d["player_id"] == focus_pid,
                }
            )
            if _is_senior(snap["year"]) and d["player_id"] not in graduations:
                graduations[d["player_id"]] = {
                    "season": season,
                    "snap": snap,
                    "note": "reached_senior_after_develop",
                }
        history.append({"season": season, "n_original_left": len(season_snaps), "players": season_snaps})
        if not living:
            break

    # Graduation retention for everyone who had a graduation snap.
    grad_rows = []
    for pid, g in graduations.items():
        t0s = t0[pid]
        snap = g["snap"]
        ret = (
            snap["profile_dev"] / t0s["profile_dev"]
            if t0s["profile_dev"] > 1e-9
            else None
        )
        grad_rows.append(
            {
                "player_id": pid,
                "name": t0s["name"],
                "year_t0": t0s["year"],
                "grad_season": g["season"],
                "note": g["note"],
                "profile_dev_t0": t0s["profile_dev"],
                "profile_dev_grad": snap["profile_dev"],
                "retention": ret,
                "mean_abs_delta": _mean_abs_delta(t0s["attrs"], snap["attrs"]),
                "delta_rt": snap["best_rt"] - t0s["best_rt"],
                "rt_t0": t0s["best_rt"],
                "rt_grad": snap["best_rt"],
                "focus": pid == focus_pid,
            }
        )

    # Headline: players who actually took ≥1 develop event (exclude senior-at-t0).
    developed = [r for r in grad_rows if r["note"] != "senior_at_t0_no_develop"]
    rets = [r["retention"] for r in developed if r["retention"] is not None]
    # Diagnostic: retention vs initial deviation
    diagnostic = [
        {"dev_t0": r["profile_dev_t0"], "retention": r["retention"], "name": r["name"]}
        for r in developed
        if r["retention"] is not None
    ]

    return {
        "arm": name,
        "n_t0": len(t0),
        "t0_mean_profile_dev": sum(s["profile_dev"] for s in t0.values()) / len(t0),
        "graduation": grad_rows,
        "developed_mean_retention": (sum(rets) / len(rets)) if rets else None,
        "developed_n": len(developed),
        "history": history,
        "diagnostic": diagnostic,
        "focus": next((r for r in grad_rows if r["focus"]), None),
        "t0_players": list(t0.values()),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    db = _load_db()
    team_oid = ObjectId(BASE_TEAM_ID)
    team = db.teams.find_one({"_id": team_oid}, {"name": 1})
    print(f"Base team: {team.get('name') if team else BASE_TEAM_NAME} ({BASE_TEAM_ID})")

    random.seed(SEED)
    walk_ons = build_wizard_walk_on_players()
    assert len(walk_ons) == WALK_ON_COUNT

    inherited, _old_ids, budgets = _build_inherited(db, team_oid, walk_ons)
    print(f"Inherited 15 budgets: {budgets}")

    # Shared walk-ons / inherited across arms — rebuild inherited copies per arm.
    arms_spec = {}
    focus_pid_by_arm: dict[str, str | None] = {}

    for arm_name, row_builder in (
        ("control", lambda: _control_rows(inherited)),
        ("realistic", lambda: _realistic_rows(inherited, budgets)),
        ("extreme", lambda: None),  # special
    ):
        random.seed(SEED)  # uuid minting stream identical until arm-specific rows
        # Re-clone inherited so arm mutations can't leak.
        inh = deepcopy(inherited)
        if arm_name == "extreme":
            rows, focus_idx = _extreme_rows(inh, budgets)
        else:
            rows = row_builder()
            focus_idx = None
        # Deterministic uuid stream per arm (same seed → same ids within arm).
        random.seed(SEED)
        # uuid4 uses os.urandom, not random — pin player ids explicitly instead.
        fid = ObjectId()
        docs = _stamp_arm(
            franchise_id=fid,
            team_oid=team_oid,
            inherited=inh,
            rows=rows,
            budgets=budgets,
        )
        # Overwrite with deterministic ids so arms share identity space for logging.
        for i, d in enumerate(docs):
            d["player_id"] = f"{arm_name}-p{i:02d}"
        focus_pid = f"{arm_name}-p{focus_idx:02d}" if focus_idx is not None else None
        focus_pid_by_arm[arm_name] = focus_pid
        print(f"\n=== Arm {arm_name}: stamped {len(docs)} players ===")
        if focus_pid:
            foc = next(d for d in docs if d["player_id"] == focus_pid)
            print(
                f"  FOCUS {focus_pid}: ht={(foc.get('meta') or {}).get('height')} "
                f"RB={_core_vals(foc.get('attributes') or {}).get('RB')} "
                f"intent={foc.get('position_intent')} "
                f"dev={_profile_deviation(foc.get('attributes') or {}, foc.get('position_intent') or 'C'):.4f}"
            )
        arms_spec[arm_name] = docs

    results = {}
    for arm_name, docs in arms_spec.items():
        print(f"\nRunning rollovers for {arm_name}...")
        results[arm_name] = _run_arm(
            arm_name, docs, focus_pid=focus_pid_by_arm.get(arm_name)
        )
        r = results[arm_name]
        print(
            f"  t0 mean profile_dev={r['t0_mean_profile_dev']:.4f}  "
            f"developed mean retention={r['developed_mean_retention']}"
        )
        if r["focus"]:
            print(
                f"  FOCUS retention={r['focus']['retention']}  "
                f"dev_t0={r['focus']['profile_dev_t0']:.4f} → "
                f"{r['focus']['profile_dev_grad']:.4f}  "
                f"ΔRT={r['focus']['delta_rt']:.1f}  "
                f"mean|Δattr|={r['focus']['mean_abs_delta']:.2f}"
            )

    raw_path = OUT_DIR / "results.json"
    raw_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nWrote {raw_path}")

    # Also emit a compact summary for the findings note.
    summary = {
        "base_team": {"name": BASE_TEAM_NAME, "id": BASE_TEAM_ID, "attr_total": 5504, "height_sum": 870},
        "seed": SEED,
        "method": {
            "apply": "apply_diffs_to_inherited_roster + build_fpd_docs_from_players",
            "develop": "develop_rollover(..., season_allocation=None) — finish_season call",
            "games_weeks": False,
            "reason": "_coaching_accumulator_for_player returns None; attractor ignores minutes/stats",
        },
        "arms": {
            k: {
                "t0_mean_profile_dev": v["t0_mean_profile_dev"],
                "developed_mean_retention": v["developed_mean_retention"],
                "developed_n": v["developed_n"],
                "focus": v["focus"],
                "graduations": [
                    {
                        "name": g["name"],
                        "year_t0": g["year_t0"],
                        "retention": g["retention"],
                        "dev_t0": g["profile_dev_t0"],
                        "mean_abs_delta": g["mean_abs_delta"],
                        "delta_rt": g["delta_rt"],
                        "note": g["note"],
                    }
                    for g in v["graduation"]
                ],
            }
            for k, v in results.items()
        },
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
