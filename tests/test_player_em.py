"""Player Emotion (EM) week-to-week bands: training focus/breaks, EOG table, FPD seed."""

from BackEnd.models.player import Player
from BackEnd.models.training_execution_v2 import (
    TRAINABLE_PLAYER_ATTRS,
    apply_training_points,
)
from BackEnd.utils.player_em import (
    apply_franchise_eog_player_em,
    apply_training_em,
    box_minutes,
    clamp_em,
    eog_em_delta,
    roster_rt,
    training_breaks_em_delta,
    training_focus_em_delta,
)


class _FakeRng:
    """Returns the low or high end of each randint band."""

    def __init__(self, end="lo"):
        self.end = end
        self.calls = []

    def randint(self, a, b):
        self.calls.append((a, b))
        return a if self.end == "lo" else b


def _player(em=50, mo=0, pid="p1"):
    return {
        "_id": pid,
        "first_name": "Test",
        "last_name": pid,
        "year": "junior",
        "attributes": {
            "SC": 50,
            "anchor_SC": 50,
            "SH": 50,
            "anchor_SH": 50,
            "ID": 50,
            "anchor_ID": 50,
            "OD": 50,
            "anchor_OD": 50,
            "PS": 50,
            "anchor_PS": 50,
            "BH": 50,
            "anchor_BH": 50,
            "RB": 50,
            "anchor_RB": 50,
            "ST": 50,
            "anchor_ST": 50,
            "AG": 50,
            "anchor_AG": 50,
            "ND": 50,
            "anchor_ND": 50,
            "IQ": 50,
            "anchor_IQ": 50,
            "FT": 50,
            "anchor_FT": 50,
            "CH": 50,
            "anchor_CH": 50,
            "EM": em,
            "anchor_EM": em,
            "MO": mo,
            "anchor_MO": mo,
            "NG": 1.0,
        },
    }


def _team():
    return {
        "shot_threshold": 90,
        "discipline": 0,
        "fight": 0,
        "rebound_modifier": 0.5,
        "momentum_score": 0,
        "offensive_efficiency": 0,
        "team_chemistry": 15,
        "defensive_efficiency": 0,
        "fb_efficiency": 0,
        "pt_efficiency": 0,
        "fb_opp_modifier": 0,
        "pt_opp_modifier": 0,
    }


class TestClampAndMinutes:
    def test_clamp_1_100(self):
        assert clamp_em(0) == 1
        assert clamp_em(-9) == 1
        assert clamp_em(101) == 100
        assert clamp_em(50) == 50

    def test_box_minutes_are_floor_seconds(self):
        assert box_minutes(0) == 0
        assert box_minutes(59) == 0
        assert box_minutes(60) == 1
        assert box_minutes(19 * 60 + 59) == 19
        assert box_minutes(20 * 60) == 20

    def test_roster_rt_is_max_slot(self):
        assert roster_rt({"position_ratings": {"PG": 48, "SG": 71, "SF": 60}}) == 71
        assert roster_rt({}) == 0


class TestTrainingFocusBands:
    def test_inspire(self):
        rng = _FakeRng("lo")
        assert training_focus_em_delta("culture-builder-inspire", rng) == 2
        assert rng.calls[-1] == (2, 5)

    def test_community_is_2_to_5(self):
        rng = _FakeRng("hi")
        assert training_focus_em_delta("culture-builder-community", rng) == 5
        assert rng.calls[-1] == (2, 5)

    def test_confidence(self):
        rng = _FakeRng("lo")
        assert training_focus_em_delta("culture-builder-confidence", rng) == 0
        assert rng.calls[-1] == (0, 2)

    def test_discipline(self):
        rng = _FakeRng("lo")
        assert training_focus_em_delta("authoritarian-discipline", rng) == -5
        assert rng.calls[-1] == (-5, 0)

    def test_execution(self):
        rng = _FakeRng("lo")
        assert training_focus_em_delta("authoritarian-execution", rng) == -3
        assert rng.calls[-1] == (-3, 0)

    def test_systems_coach_any_leaf(self):
        rng = _FakeRng("hi")
        assert training_focus_em_delta("systems-coach-offense", rng) == 0
        assert rng.calls[-1] == (-2, 0)
        rng = _FakeRng("lo")
        assert training_focus_em_delta("systems-coach-defense", rng) == -2

    def test_player_maximizer_any_leaf(self):
        rng = _FakeRng("hi")
        assert training_focus_em_delta("player-maximizer-top-3-attributes", rng) == 2
        assert rng.calls[-1] == (0, 2)

    def test_no_em_leaves(self):
        rng = _FakeRng("lo")
        assert training_focus_em_delta("authoritarian-rebounding", rng) == 0
        assert training_focus_em_delta("authoritarian-teamwork", rng) == 0
        assert training_focus_em_delta("culture-builder-teamwork", rng) == 0
        assert training_focus_em_delta(None, rng) == 0
        assert rng.calls == []


class TestTrainingBreaksBands:
    def test_breaks_0(self):
        rng = _FakeRng("lo")
        assert training_breaks_em_delta(0, rng) == -5
        assert rng.calls[-1] == (-5, -3)

    def test_breaks_1(self):
        rng = _FakeRng("hi")
        assert training_breaks_em_delta(1, rng) == 0
        assert rng.calls[-1] == (-2, 0)

    def test_breaks_2(self):
        rng = _FakeRng("lo")
        assert training_breaks_em_delta(2, rng) == 0
        assert rng.calls[-1] == (0, 2)

    def test_breaks_over_2(self):
        rng = _FakeRng("hi")
        assert training_breaks_em_delta(3, rng) == 5
        assert rng.calls[-1] == (2, 5)
        assert training_breaks_em_delta(5, rng) == 5

    def test_missing_breaks_is_zero_band(self):
        rng = _FakeRng("lo")
        assert training_breaks_em_delta(None, rng) == -5
        assert rng.calls[-1] == (-5, -3)


class TestTrainingApply:
    def test_each_player_own_two_rolls_then_clamp(self):
        rng = _FakeRng("lo")
        players = [_player(em=50, pid="a"), _player(em=50, pid="b")]
        apply_training_em(players, "culture-builder-inspire", 0, rng)
        # inspire lo +2, breaks 0 lo -5 → 47
        assert players[0]["attributes"]["EM"] == 47
        assert players[1]["attributes"]["EM"] == 47
        assert players[0]["attributes"]["anchor_EM"] == 47
        # 2 players × (focus + breaks)
        assert len(rng.calls) == 4

    def test_clamp_floor(self):
        rng = _FakeRng("lo")
        players = [_player(em=2)]
        apply_training_em(players, "authoritarian-discipline", 0, rng)
        # -5 + -5 = -10 → clamp 1
        assert players[0]["attributes"]["EM"] == 1

    def test_execution_not_discipline(self):
        rng = _FakeRng("lo")
        players = [_player(em=50)]
        apply_training_em(players, "authoritarian-execution", 2, rng)
        # execution -3 + breaks 2 lo 0 → 47
        assert players[0]["attributes"]["EM"] == 47
        assert rng.calls[0] == (-3, 0)


class TestTrainingReportOmitsEm:
    def test_inspire_moves_em_and_mo_but_report_omits_em(self):
        players = [_player(em=40, mo=0)]
        team = _team()
        allocations = {
            "player_drills": {
                "offense": {"inside": 0, "outside": 0},
                "defense": {"inside": 0, "outside": 0},
                "technical": {"passing": 0, "ball_handling": 0, "rebounding": 0},
                "weight_room": {"strength": 0, "agility": 0},
            },
            "team_drills": {
                "team_offense": {"install": 0},
                "team_defense": {"install": 0},
            },
            "general": {"breaks": 2},
        }
        updated, _team_out, report = apply_training_points(
            players, team, allocations, coaching_focus="culture-builder-inspire"
        )
        em = updated[0]["attributes"]["EM"]
        assert 1 <= em <= 100
        assert em != 40 or updated[0]["attributes"]["MO"] != 0
        changes = (report.get("player_changes") or report.get("player_logs") or {})
        # keyed by id or name depending on report shape
        for row in changes.values() if isinstance(changes, dict) else []:
            attrs = row.get("changes") if isinstance(row, dict) and "changes" in row else row
            if isinstance(attrs, dict):
                assert "EM" not in attrs
        assert "EM" not in TRAINABLE_PLAYER_ATTRS


class TestEogTable:
    def test_star_20_plus_range1(self):
        rng = _FakeRng("lo")
        assert eog_em_delta(70, 20, 70, rng) == 2
        assert rng.calls[-1] == (2, 5)

    def test_star_15_19_range2(self):
        rng = _FakeRng("hi")
        assert eog_em_delta(70, 15, 40, rng) == 1
        assert rng.calls[-1] == (-1, 1)

    def test_star_dnp_range3(self):
        rng = _FakeRng("lo")
        assert eog_em_delta(80, 0, 10, rng) == -7
        assert rng.calls[-1] == (-7, -3)

    def test_mid_rt_20_plus_range3(self):
        rng = _FakeRng("hi")
        assert eog_em_delta(50, 25, 39, rng) == 2
        assert rng.calls[-1] == (0, 2)

    def test_low_rt_15_19_range1(self):
        rng = _FakeRng("lo")
        assert eog_em_delta(49, 19, 100, rng) == 2
        assert rng.calls[-1] == (2, 5)

    def test_low_rt_bench_range2(self):
        rng = _FakeRng("hi")
        assert eog_em_delta(20, 10, 55, rng) == 0
        assert rng.calls[-1] == (-1, 0)


class _GamesCol:
    def __init__(self, doc):
        self.doc = doc
        self.updates = []

    def find_one(self, query):
        gid = query.get("_id")
        if gid == self.doc["_id"] or str(gid) == str(self.doc["_id"]):
            return dict(self.doc)
        return None

    def update_one(self, query, update):
        self.updates.append((query, update))
        self.doc.update(update.get("$set") or {})


class _FpdCol:
    def __init__(self, docs):
        self.docs = {str(d["player_id"]): dict(d) for d in docs}
        self.ops = []

    def find(self, query, projection=None):
        pids = set(query.get("player_id", {}).get("$in") or [])
        return [dict(self.docs[pid]) for pid in pids if pid in self.docs]

    def bulk_write(self, ops, ordered=False):
        self.ops = list(ops)
        for op in ops:
            filt = getattr(op, "_filter", None) or getattr(op, "filter", {})
            doc = getattr(op, "_doc", None) or getattr(op, "update", {})
            pid = str(filt.get("player_id"))
            sets = (doc or {}).get("$set") or {}
            if pid in self.docs:
                attrs = self.docs[pid].setdefault("attributes", {})
                if "attributes.EM" in sets:
                    attrs["EM"] = sets["attributes.EM"]
                if "attributes.anchor_EM" in sets:
                    attrs["anchor_EM"] = sets["attributes.anchor_EM"]


class TestEogPersist:
    def test_writes_fpd_and_is_idempotent(self):
        rng = _FakeRng("lo")
        game = {
            "_id": "g1",
            "mode": "franchise",
            "players": [
                {"playerId": "p1", "stats": {"MIN": 21 * 60}},
            ],
        }
        fpd = [
            {
                "player_id": "p1",
                "franchise_id": "f1",
                "attributes": {"EM": 50, "CH": 80},
                "position_ratings": {"PG": 80},
            }
        ]
        games = _GamesCol(game)
        fpds = _FpdCol(fpd)
        n = apply_franchise_eog_player_em(
            "g1", "f1", games_col=games, fpd_col=fpds, rng=rng
        )
        assert n == 1
        assert fpds.docs["p1"]["attributes"]["EM"] == 52  # star / 20+ / range1 lo +2
        assert games.doc.get("player_em_eog_applied") is True
        n2 = apply_franchise_eog_player_em(
            "g1", "f1", games_col=games, fpd_col=fpds, rng=rng
        )
        assert n2 == 0

    def test_skips_practice_squad(self):
        rng = _FakeRng("lo")
        game = {
            "_id": "ps1",
            "mode": "practice_squad",
            "players": [{"playerId": "p1", "stats": {"MIN": 1200}}],
        }
        fpd = [
            {
                "player_id": "p1",
                "franchise_id": "f1",
                "attributes": {"EM": 50, "CH": 80},
                "position_ratings": {"PG": 80},
            }
        ]
        n = apply_franchise_eog_player_em(
            "ps1", "f1", games_col=_GamesCol(game), fpd_col=_FpdCol(fpd), rng=rng
        )
        assert n == 0
        assert rng.calls == []


class TestPreserveEmotion:
    def test_preserve_keeps_em_rerolls_ch_zeros_mo(self, monkeypatch):
        rolls = iter([77, 88])  # unused if preserve; CH still rolls

        def _randint(a, b):
            return next(rolls)

        monkeypatch.setattr("BackEnd.models.player.random.randint", _randint)
        attrs = {"EM": 41, "anchor_EM": 41, "CH": 12, "MO": 4, "NG": 0.5}
        out = Player.randomize_game_attributes(dict(attrs), preserve_emotion=True)
        assert out["EM"] == 41
        assert out["anchor_EM"] == 41
        assert out["MO"] == 0
        assert out["NG"] == 1.0
        assert out["CH"] == 77

    def test_default_still_rolls_em(self, monkeypatch):
        monkeypatch.setattr("BackEnd.models.player.random.randint", lambda a, b: 33)
        out = Player.randomize_game_attributes({"EM": 41, "CH": 12})
        assert out["EM"] == 33
        assert out["anchor_EM"] == 33
        assert out["CH"] == 33
        assert out["MO"] == 0
