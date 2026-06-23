"""Phase 2 tests — Dynamic HCO Motion per-step decision engine (brief Step 2)."""
from BackEnd.engine import motion_step_decision as D
from BackEnd.engine.motion_step_decision import decide_step_action

_ATTR_KEYS = ["SC", "ST", "AG", "SH", "ID", "OD", "IQ", "CH"]


class _FakePlayer:
    def __init__(self, pid, **overrides):
        self.player_id = pid
        self.attributes = {k: 50 for k in _ATTR_KEYS}
        self.attributes.update(overrides)


class _FakeTeam:
    def __init__(self, **attrs):
        self.team_attributes = {
            "discipline": 0, "fight": 0, "offensive_efficiency": 0,
            "defensive_efficiency": 0, "team_chemistry": 7,
        }
        self.team_attributes.update(attrs)
        self.strategy_calls = {"aggression_call": "normal", "tempo_call": "normal"}


class _FakeGame:
    def __init__(self, off_team, def_team, shot_clock=30, defense_playcall="Man"):
        self.offense_team = off_team
        self.defense_team = def_team
        self.game_state = {"shot_clock_remaining": shot_clock, "defense_playcall": defense_playcall}


class FakeRng:
    """Scripted RNG. randint pops from a queue (defaults to 3 when empty)."""
    def __init__(self, randints=None, random_val=0.0, choice_idx=0):
        self._randints = list(randints or [])
        self.random_val = random_val
        self.choice_idx = choice_idx

    def randint(self, a, b):
        v = self._randints.pop(0) if self._randints else 3
        return min(max(v, a), b)

    def random(self):
        return self.random_val

    def choice(self, seq):
        seq = list(seq)
        return seq[self.choice_idx % len(seq)]


def _step(locations):
    return {"pos_actions": {pos: {"location": loc, "action": "handle_ball"} for pos, loc in locations.items()}}


def _lineup(**by_pos):
    return by_pos


# ---------------------------------------------------------------- neutral

def test_neutral_branch_pass_vs_subtle():
    # Huge eff+chem buffers on both sides → neither score can win → neutral branch.
    off = _FakeTeam(offensive_efficiency=10, team_chemistry=25)
    deff = _FakeTeam(defensive_efficiency=10, team_chemistry=25)
    game = _FakeGame(off, deff)
    bh = _FakePlayer("bh")                 # raw_read 50, ×roll 3 → 150
    defender = _FakePlayer("def")          # pressure raw 50, ×roll 3 → 150
    off_lineup = _lineup(PG=bh)
    step = _step({"PG": "key"})            # outside spot → pressure defense

    pass_dec = decide_step_action(game, step, "PG", defender, off_lineup, {},
                                  rng=FakeRng(randints=[3, 3], random_val=0.0))
    assert pass_dec["action"] == D.PASS_IMMEDIATE
    subtle_dec = decide_step_action(game, step, "PG", defender, off_lineup, {},
                                    rng=FakeRng(randints=[3, 3], random_val=0.95))
    assert subtle_dec["action"] == D.SUBTLE_MOVEMENT


# ---------------------------------------------------------------- offense wins → hot read

def _offense_wins_setup(read_map, bh_loc="key", teammates=None):
    off = _FakeTeam()
    deff = _FakeTeam()
    game = _FakeGame(off, deff)
    bh = _FakePlayer("bh", IQ=100, CH=100)   # raw_read 100, ×3 → 300
    defender = _FakePlayer("def", OD=0, AG=0, IQ=0, CH=0, ID=0, ST=0)  # raw_def 0 → defense_score 0
    locs = {"PG": bh_loc}
    lineup = {"PG": bh}
    for pos, (pid, loc) in (teammates or {}).items():
        lineup[pos] = _FakePlayer(pid)
        locs[pos] = loc
    return game, _step(locs), "PG", defender, lineup, read_map


def test_hot_read_self_executes():
    game, step, bh_pos, defender, lineup, rm = _offense_wins_setup(
        read_map={"bh": {"inside": False, "attack": True, "outside": False}}, bh_loc="key")
    dec = decide_step_action(game, step, bh_pos, defender, lineup, rm,
                             rng=FakeRng(randints=[3, 3], random_val=0.0))  # execute (<0.5)
    assert dec["action"] == D.HOT_READ_SHOOT
    assert dec["shooter_pos"] == "PG" and dec["shot_type"] == "attack" and dec["via_pass"] is False


def test_hot_read_not_executed_falls_back_to_subtle():
    # Offense wins the read but passes up the hot read → subtle (no longer a plain advance).
    game, step, bh_pos, defender, lineup, rm = _offense_wins_setup(
        read_map={"bh": {"inside": False, "attack": True, "outside": False}})
    dec = decide_step_action(game, step, bh_pos, defender, lineup, rm,
                             rng=FakeRng(randints=[3, 3], random_val=0.9))  # >=0.5 → not executed
    assert dec["action"] == D.SUBTLE_MOVEMENT


def test_offense_wins_no_hot_read_falls_back_to_subtle():
    # Offense wins the read but there's no opening to seize → subtle (probe).
    game, step, bh_pos, defender, lineup, rm = _offense_wins_setup(read_map={})
    dec = decide_step_action(game, step, bh_pos, defender, lineup, rm,
                             rng=FakeRng(randints=[3, 3], random_val=0.0))
    assert dec["action"] == D.SUBTLE_MOVEMENT


# ---------------------------------------------------------------- turn-level condition matrix

def test_condition2_unopposed_executes_hot_read_when_available():
    # offense reading, defense NOT pressuring → hot read if available + executed.
    game, step, bh_pos, defender, lineup, rm = _offense_wins_setup(
        read_map={"bh": {"inside": False, "attack": True, "outside": False}})
    dec = decide_step_action(game, step, bh_pos, defender, lineup, rm,
                             rng=FakeRng(randints=[3], random_val=0.0),
                             offense_reads=True, defense_pressure=False)
    assert dec["action"] == D.HOT_READ_SHOOT


def test_condition2_unopposed_falls_back_to_subtle():
    # offense reading, defense NOT pressuring, no read available → subtle (never advance).
    game, step, bh_pos, defender, lineup, rm = _offense_wins_setup(read_map={})
    dec = decide_step_action(game, step, bh_pos, defender, lineup, rm,
                             rng=FakeRng(randints=[3], random_val=0.0),
                             offense_reads=True, defense_pressure=False)
    assert dec["action"] == D.SUBTLE_MOVEMENT


def test_condition3_defense_pressures_unreading_offense_loses_to_disruption():
    # offense NOT reading, defense pressuring. Strong defender beats weak ball handler → disruption.
    off = _FakeTeam(); deff = _FakeTeam()
    game = _FakeGame(off, deff)
    bh = _FakePlayer("bh", BH=0, IQ=50, CH=50)                     # read 50 (skips desperation); ball_handling 20
    defender = _FakePlayer("def", OD=100, AG=100, IQ=100, CH=100)  # pressure raw 100
    dec = decide_step_action(game, _step({"PG": "key"}), "PG", defender, {"PG": bh}, {},
                             rng=FakeRng(randints=[3, 3, 3], random_val=0.0),
                             offense_reads=False, defense_pressure=True)
    assert dec["action"] == D.SUBTLE_MOVEMENT  # disruption → subtle (random_val 0.0)


def test_condition3_unreading_offense_beats_pressure_advances():
    # offense NOT reading, defense pressuring. Weak defender → offense wins/neutral → advance.
    off = _FakeTeam(); deff = _FakeTeam()
    game = _FakeGame(off, deff)
    bh = _FakePlayer("bh", BH=80, IQ=80, CH=80)                    # strong ball handler
    defender = _FakePlayer("def", OD=0, AG=0, IQ=0, CH=0, ID=0, ST=0)  # no pressure
    dec = decide_step_action(game, _step({"PG": "key"}), "PG", defender, {"PG": bh}, {},
                             rng=FakeRng(randints=[3, 3, 3], random_val=0.0),
                             offense_reads=False, defense_pressure=True)
    assert dec["action"] == D.ADVANCE


def test_hot_read_teammate_when_bh_has_none():
    # BH no read; teammate SG at wing has an outside read → pass-and-shoot.
    game, step, bh_pos, defender, lineup, rm = _offense_wins_setup(
        read_map={"sg": {"inside": False, "attack": False, "outside": True}},
        teammates={"SG": ("sg", "upper wing")})
    dec = decide_step_action(game, step, bh_pos, defender, lineup, rm,
                             rng=FakeRng(randints=[3, 3], random_val=0.0))
    assert dec["action"] == D.HOT_READ_SHOOT
    assert dec["shooter_pos"] == "SG" and dec["shot_type"] == "outside" and dec["via_pass"] is True


# ---------------------------------------------------------------- defense wins → disruption

def _defense_wins_setup():
    off = _FakeTeam()                               # off_eff 0, off_chem 7
    deff = _FakeTeam()
    game = _FakeGame(off, deff, shot_clock=30)
    bh = _FakePlayer("bh", IQ=0, CH=0)              # raw_read 0 → offense_score 0 (<110 → desperation)
    defender = _FakePlayer("def")                   # pressure raw 50, ×3 → 150
    # randints: offense roll (any), desperation roll (≤120 so it falls through), defense roll 3
    return game, _step({"PG": "key"}), "PG", defender, {"PG": bh}


def test_defense_wins_subtle():
    game, step, bh_pos, defender, lineup = _defense_wins_setup()
    dec = decide_step_action(game, step, bh_pos, defender, lineup, {},
                             rng=FakeRng(randints=[1, 50, 3], random_val=0.0))
    assert dec["action"] == D.SUBTLE_MOVEMENT


def test_defense_wins_freelance_forced():
    game, step, bh_pos, defender, lineup = _defense_wins_setup()
    dec = decide_step_action(game, step, bh_pos, defender, lineup, {},
                             rng=FakeRng(randints=[1, 50, 3], random_val=0.6))  # 0.5..0.7 → FF
    assert dec["action"] == D.FREELANCE_FORCED


def test_defense_wins_no_effect_advances():
    game, step, bh_pos, defender, lineup = _defense_wins_setup()
    dec = decide_step_action(game, step, bh_pos, defender, lineup, {},
                             rng=FakeRng(randints=[1, 50, 3], random_val=0.85))  # >=0.7 → none
    assert dec["action"] == D.ADVANCE


# ---------------------------------------------------------------- desperation

def test_desperation_forced_inside_shot():
    off = _FakeTeam()
    deff = _FakeTeam()
    game = _FakeGame(off, deff, shot_clock=5)       # 4*5 = 20 threshold
    bh = _FakePlayer("bh")                          # raw_read 50, ×roll 1 → 50 (<110)
    step = _step({"PG": "basketSpot"})              # inside spot
    # offense roll 1 → 50<110; desperation roll 50 (>20) → forced; random 0.0 (<0.75) → bh shot
    dec = decide_step_action(game, step, "PG", _FakePlayer("def"), {"PG": bh}, {},
                             rng=FakeRng(randints=[1, 50], random_val=0.0))
    assert dec["action"] == D.SHOOT and dec["shooter_pos"] == "PG" and dec["shot_type"] == "inside"


def test_desperation_kickout_catch_and_shoot():
    off = _FakeTeam()
    deff = _FakeTeam()
    game = _FakeGame(off, deff, shot_clock=5)
    bh = _FakePlayer("bh")
    sg = _FakePlayer("sg")
    # BH at key (64,25); SG at topLane (74,25) → exactly 10 grid spots (within KICKOUT_MAX_DIST).
    step = _step({"PG": "key", "SG": "topLane"})
    dec = decide_step_action(game, step, "PG", _FakePlayer("def"),
                             {"PG": bh, "SG": sg}, {},
                             rng=FakeRng(randints=[1, 50], random_val=0.9))  # >=0.75 → kick-out
    assert dec["action"] == D.KICKOUT_SHOOT and dec["shooter_pos"] == "SG"


def test_desperation_low_roll_falls_through_to_progression():
    # offense_score<110 but desperation roll ≤ 4*shot_clock → no forced shot; falls to progression.
    off = _FakeTeam(offensive_efficiency=10, team_chemistry=25)
    deff = _FakeTeam(defensive_efficiency=10, team_chemistry=25)
    game = _FakeGame(off, deff, shot_clock=30)      # 4*30 = 120
    bh = _FakePlayer("bh")                          # raw_read 50 ×1 = 50 (<110)
    defender = _FakePlayer("def")                   # ×3 → 150; buffers huge → neutral
    dec = decide_step_action(game, _step({"PG": "key"}), "PG", defender, {"PG": bh}, {},
                             rng=FakeRng(randints=[1, 10, 3], random_val=0.0))  # desp roll 10 ≤120
    assert dec["action"] in (D.PASS_IMMEDIATE, D.SUBTLE_MOVEMENT)  # reached progression (neutral)


# ---------------------------------------------------------------- aggression deltas

def test_offense_aggressive_raises_pass_share_in_neutral():
    off = _FakeTeam(offensive_efficiency=10, team_chemistry=25)
    off.strategy_calls["aggression_call"] = "aggressive"   # pass_pct 0.70
    deff = _FakeTeam(defensive_efficiency=10, team_chemistry=25)
    game = _FakeGame(off, deff)
    bh = _FakePlayer("bh")
    defender = _FakePlayer("def")
    # random 0.6: < 0.70 → pass under aggressive (would be subtle at normal 0.50)
    dec = decide_step_action(game, _step({"PG": "key"}), "PG", defender, {"PG": bh}, {},
                             rng=FakeRng(randints=[3, 3], random_val=0.6))
    assert dec["action"] == D.PASS_IMMEDIATE
