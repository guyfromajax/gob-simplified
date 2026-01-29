"""
EOS ↔ bracket_engine integration: initialize_eos_tournament uses shared engine,
save + advance flow produces correct bracket progression.
"""
from bson import ObjectId

from BackEnd.tournament.eos_tournament import (
    advance_tournament_round,
    initialize_eos_tournament,
    save_tournament_game_result,
)


class _MockTeamsCollection:
    def __init__(self, team_docs):
        self._by_id = {str(d["_id"]): d for d in team_docs}

    def find(self, query, projection=None):
        ids = query.get("_id", {}).get("$in", [])
        for tid in ids:
            d = self._by_id.get(str(tid))
            if d is None:
                continue
            if projection:
                yield {k: d[k] for k in projection if k in d}
            else:
                yield d


def test_eos_init_uses_bracket_engine():
    team_ids = [ObjectId() for _ in range(8)]
    teams = [{"_id": tid, "name": f"Team{i}"} for i, tid in enumerate(team_ids)]
    mock_teams = _MockTeamsCollection(teams)
    franchise_doc = {"results": {}}
    state = initialize_eos_tournament(franchise_doc, mock_teams, team_ids=team_ids)
    assert "bracket" in state
    assert state["current_round"] == 1
    assert state["completed"] is False
    assert state["champion"] is None
    r1 = state["bracket"]["round1"]
    assert len(r1) == 4
    assert len(state["bracket"]["round2"]) == 0
    assert len(state["bracket"]["final"]) == 0
    # 1v8, 4v5, 2v7, 3v6: seeds 1–8 from standings order
    seeds = state["seeds"]
    seed_order = [tid for tid, _ in sorted(seeds.items(), key=lambda x: x[1])]
    expect = [(seed_order[0], seed_order[7]), (seed_order[3], seed_order[4]), (seed_order[1], seed_order[6]), (seed_order[2], seed_order[5])]
    for i, (h, a) in enumerate(expect):
        assert r1[i]["home_team"] == h and r1[i]["away_team"] == a


def test_eos_save_advance_round1_to_2():
    team_ids = [ObjectId() for _ in range(8)]
    teams = [{"_id": tid, "name": f"Team{i}"} for i, tid in enumerate(team_ids)]
    mock_teams = _MockTeamsCollection(teams)
    franchise_doc = {"results": {}}
    state = initialize_eos_tournament(franchise_doc, mock_teams, team_ids=team_ids)
    franchise_doc["eos_tournament"] = state
    seeds = state["seeds"]
    seed_order = [tid for tid, _ in sorted(seeds.items(), key=lambda x: x[1])]
    winners = [str(seed_order[0]), str(seed_order[4]), str(seed_order[1]), str(seed_order[2])]
    for i in range(4):
        save_tournament_game_result(franchise_doc, 1, i, f"g{i}", winners[i], {"home": 70, "away": 60})
    updated = advance_tournament_round(franchise_doc, mock_teams)
    assert updated["current_round"] == 2
    r2 = updated["bracket"]["round2"]
    assert len(r2) == 2
    assert r2[0]["home_team"] == winners[0] and r2[0]["away_team"] == winners[1]
    assert r2[1]["home_team"] == winners[2] and r2[1]["away_team"] == winners[3]


def test_eos_save_advance_to_final_and_champion():
    team_ids = [ObjectId() for _ in range(8)]
    teams = [{"_id": tid, "name": f"Team{i}"} for i, tid in enumerate(team_ids)]
    mock_teams = _MockTeamsCollection(teams)
    franchise_doc = {"results": {}}
    state = initialize_eos_tournament(franchise_doc, mock_teams, team_ids=team_ids)
    franchise_doc["eos_tournament"] = state
    seeds = state["seeds"]
    seed_order = [tid for tid, _ in sorted(seeds.items(), key=lambda x: x[1])]
    w1 = [str(seed_order[0]), str(seed_order[4]), str(seed_order[1]), str(seed_order[2])]
    for i in range(4):
        save_tournament_game_result(franchise_doc, 1, i, f"g{i}", w1[i], {"home": 70, "away": 60})
    advance_tournament_round(franchise_doc, mock_teams)
    save_tournament_game_result(franchise_doc, 2, 0, "s0", w1[0], {"home": 80, "away": 70})
    save_tournament_game_result(franchise_doc, 2, 1, "s1", w1[1], {"home": 75, "away": 65})
    updated = advance_tournament_round(franchise_doc, mock_teams)
    assert updated["current_round"] == 3
    fin = updated["bracket"]["final"]
    assert len(fin) == 1
    assert fin[0]["home_team"] == w1[0] and fin[0]["away_team"] == w1[1]
    save_tournament_game_result(franchise_doc, 3, 0, "f0", w1[0], {"home": 90, "away": 85})
    updated = advance_tournament_round(franchise_doc, mock_teams)
    assert updated["completed"] is True
    assert updated["champion"] == w1[0]
