

**Universal Collections**
-Players Collection
-Teams Collection
-Plays Collection
-Defense Plays Collection
-FCP_Skeletons
-HCT_Skeletons

**Game Mode Instance Collections**
-tournaments
-franchises
-games (Single Game Mode)

**Unknown**
-recruits
-training_sessions

**Items added to Game Mode collection docs**
--Franchise Mode
    _id
    schedule
    players
    applied_games
    franchie_teams
        1. attributes: team chemistry, offensive_efficiency, shot_threshold, discipline, fight, rebound_modifier, defensive_efficiency, fb_efficiency, pt_efficiency, fb_opp_modifier, pt_opp_modifier
        2. playcall_settings (we can deprecate this)
        3. strategy_settings: offense, inside, attack, outside, tempo, fast_breaks, defense, aggression, hc_trap, fc_press, rebounding
        4. plays: play_id, name, play_type, play_focus, effectieness, momentum, cloaking, 
            a. game_stats: times_run, successes, effectiveness, player_points
            b. season_stats: times_run, successes, effectiveness, player_points
        5. scouting_data
        6. playbook_settings
    training_status
    recruits
    created_at
    current_season
    stats (top 10 leaders)
    user_team_id
    user_team_object_id
    lastest_training
    results (all game results)

--Tournament Mode
    _id
    user_team_id
    user_team_object_id
    created_at
    bracket
    current_round
    stats (top 10 leaders)
    players
    teams
        1. attributes: team chemistry, offensive_efficiency, shot_threshold, discipline, fight, rebound_modifier, defensive_efficiency, fb_efficiency, pt_efficiency, fb_opp_modifier, pt_opp_modifier
        2. playcall_settings (we can deprecate this)
        3. strategy_settings: offense, inside, attack, outside, tempo, fast_breaks, defense, aggression, hc_trap, fc_press, rebounding
        4. plays: play_id, name, play_type, play_focus, effectieness, momentum, cloaking, 
            a. game_stats: times_run, successes, effectiveness, player_points
            b. season_stats: times_run, successes, effectiveness, player_points
        5. scouting_data
        6. playbook_settings
    applied_games
    completed
    leaderboard
    latet_training
    training_status