from BackEnd.models.animator import Animator
from BackEnd.models.game_manager import GameManager
from BackEnd.models.player import Player


def _build_game():
    gm = GameManager('Home', 'Away')
    positions = ['PG', 'SG', 'SF', 'PF', 'C']
    for team in [gm.home_team, gm.away_team]:
        lineup = {}
        for i, pos in enumerate(positions):
            pdata = {
                '_id': f'{team.name}_{i}',
                'first_name': team.name,
                'last_name': pos,
                'team': team.name,
                'attributes': {k: 50 for k in ['SC','SH','ID','OD','PS','BH','RB','AG','ST','ND','IQ','FT','NG']},
            }
            lineup[pos] = Player(pdata)
        team.lineup = lineup
    return gm


def test_capture_halfcourt_animation_event_step_bounds():
    gm = _build_game()
    animator = Animator(gm)
    pg = gm.home_team.lineup['PG']
    roles = {
        'shooter': pg,
        'ball_handler': pg,
        'steps': [
            {'timestamp':0, 'pos_actions':{'PG':{'action':'handle_ball','spot':'key'}}, 'events': []},
            {'timestamp':100, 'pos_actions':{'PG':{'action':'handle_ball','spot':'key'}}, 'events': []},
        ],
        'action_timeline': {
            pg: [
                (0, 'handle_ball', 'key'),
                (100, 'handle_ball', 'key'),
                (200, 'pass', 'key'),  # extra timeline step beyond available steps
            ]
        },
    }
    # event_step truncates steps to one element; ensure no IndexError
    animator.capture_halfcourt_animation(roles, event_step=0)
