"""Unit tests for franchise championship increments on users collection."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import patch
from bson import ObjectId


def test_conf_rs_awards_when_seed_one():
    from BackEnd.utils import franchise_championships as fc

    user_id = str(ObjectId())
    team_id = ObjectId()
    conf_tournaments = {
        "3": {
            "seeds": {str(team_id): 1},
        }
    }
    with patch.object(fc, "users_collection") as uc, patch.object(fc, "db") as db_mock, patch.object(
        fc, "geek_points_team_key_for_franchise_user", return_value="BYKEY"
    ):
        db_mock.teams.find_one.return_value = {"conference": 3}
        fc.maybe_award_conference_rs_championship(
            owner_user_id=user_id,
            user_team_id_str=str(team_id),
            conference_tournaments=conf_tournaments,
        )
        uc.update_one.assert_called_once()
        call = uc.update_one.call_args
        assert call[0][0] == {"_id": ObjectId(user_id)}
        inc = call[0][1]["$inc"]
        assert inc["championships_total.conf_rs"] == 1
        assert inc["championships_by_team.BYKEY.conf_rs"] == 1


def test_conf_rs_skips_when_not_seed_one():
    from BackEnd.utils import franchise_championships as fc

    user_id = str(ObjectId())
    team_id = ObjectId()
    conf_tournaments = {"2": {"seeds": {str(team_id): 2}}}
    with patch.object(fc, "users_collection") as uc, patch.object(fc, "db") as db_mock:
        db_mock.teams.find_one.return_value = {"conference": 2}
        fc.maybe_award_conference_rs_championship(
            owner_user_id=user_id,
            user_team_id_str=str(team_id),
            conference_tournaments=conf_tournaments,
        )
        uc.update_one.assert_not_called()


def test_eos_title_conf_t():
    from BackEnd.utils import franchise_championships as fc

    user_id = str(ObjectId())
    tid = ObjectId()
    with patch.object(fc, "users_collection") as uc, patch.object(
        fc, "geek_points_team_key_for_franchise_user", return_value="TESTU"
    ):
        fc.maybe_award_franchise_eos_title_championship(
            owner_user_id=user_id,
            user_team_id_str=str(tid),
            winner_team_id=tid,
            week=29,
            eos_game_meta={"phase": "conference", "round": 3},
        )
        inc = uc.update_one.call_args[0][1]["$inc"]
        assert inc["championships_total.conf_t"] == 1
        assert inc["championships_by_team.TESTU.conf_t"] == 1


def test_eos_title_increments_active_roster_fpd():
    from BackEnd.utils import franchise_championships as fc

    user_id = str(ObjectId())
    tid = ObjectId()
    fid = ObjectId()
    with patch.object(fc, "users_collection") as uc, patch.object(
        fc, "geek_points_team_key_for_franchise_user", return_value="TESTU"
    ), patch.object(fc, "franchise_team_data_collection") as ftd, patch.object(
        fc, "franchise_players_data_collection"
    ) as fpd:
        ftd.find_one.return_value = {"players": ["p-active", "p-two"]}
        fc.maybe_award_franchise_eos_title_championship(
            owner_user_id=user_id,
            user_team_id_str=str(tid),
            winner_team_id=tid,
            week=29,
            eos_game_meta={"phase": "conference", "round": 3},
            franchise_id=fid,
        )
        uc.update_one.assert_called_once()
        ftd.find_one.assert_called_once()
        fpd.update_many.assert_called_once()
        query, update = fpd.update_many.call_args[0]
        assert query["franchise_id"] == str(fid)
        assert set(query["player_id"]["$in"]) == {"p-active", "p-two"}
        assert update["$inc"]["titles.conf_t"] == 1


def test_eos_title_skips_player_increment_without_franchise_id():
    from BackEnd.utils import franchise_championships as fc

    tid = ObjectId()
    with patch.object(fc, "users_collection") as uc, patch.object(
        fc, "geek_points_team_key_for_franchise_user", return_value="TESTU"
    ), patch.object(fc, "franchise_players_data_collection") as fpd:
        fc.maybe_award_franchise_eos_title_championship(
            owner_user_id=str(ObjectId()),
            user_team_id_str=str(tid),
            winner_team_id=tid,
            week=29,
            eos_game_meta={"phase": "conference", "round": 3},
        )
        uc.update_one.assert_called_once()
        fpd.update_many.assert_not_called()


def test_eos_title_skips_wrong_round():
    from BackEnd.utils import franchise_championships as fc

    with patch.object(fc, "users_collection") as uc:
        tid = ObjectId()
        fc.maybe_award_franchise_eos_title_championship(
            owner_user_id=str(ObjectId()),
            user_team_id_str=str(tid),
            winner_team_id=tid,
            week=28,
            eos_game_meta={"phase": "conference", "round": 2},
        )
        uc.update_one.assert_not_called()
