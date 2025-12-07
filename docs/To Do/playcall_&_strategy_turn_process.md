

###At each game's init###
-create a strtegy_calls field for each team that contains the following:

offense_call: null
offense_flagged: false

defense_call: null
defense_flagged: false

aggression_call: null
aggression_flagged: false

tempo_call: null
tempo_flagged: false

press_call: null
press_flagged: false

trap_call: null
trap_flagged: false



###Turn progression using this system

Instances where the user's team is the offense team

1. Check offense team object strategy calls for the following:
-if offense_flagged == True:
    1. game_state[current_playcall] = offense team's strategy_calls[offense_call]
    2. set offense_flagged to False so it doesn't carry over to teh next turn
    3. Highlight the offense playcall in the Playcall Center until that turn compoletes, then unhighlight it 
-else
    1. game_state[current_playcall] is set via our current process of chekcing teh offense team's offense setting from strategy settings, choosing motion or tempo, then choosing inside, attack, or outside based on the offense team's strategy settings and choosign a play call.

Instances where the user's team is teh defense team

1. Check the defense team object strategy calls for teh following:
-if defense_flagged == True
    1. game_state[defense_playcall] = Zone or Man based on the defense_call value
        a. If zone -- use our system for randomly choosing a zone defense (2-3, 3-2, or 1-3-1)
    2. Set defense flagged to False so it doesn't carry over to teh next turn
    3. Highlight the defense playcall in the Playcall Center until that turn completes, then unhighlight it
-else:
    1. game_state[defense_playcall] is set via our current process of checkgin the defense team's defense setting from strategy settings then choosign man or zone, and choosing a zone defense if it is zone

-if aggression_flagged == True
    1. Same process applies here as teh previous two detailed above -- tell me if you don't understand it.

#Note, we'll add tempo, press, and trap functionality later


Playcall Center
- If the user selects an offense call, defense call or aggression call, keep that item highlighted in the front end UI until the turn that it is used in completes. LMK if you need more explicty direction on this. Examples below

Turn 21: user team is on defense, user presses the 3-2 Motion Offense call in teh Playcall Center

-Update settings in user team's strategy_calls section of the team object:
    -offense_call = 3-2 Motion
    -offense_flagged = True
-Immediately highlight the 3-2 Motion Playcall container in teh Playcall Center
-Keep it highlighted throughout the current turn where user team is on defense, and all continual turns until the playcall is used in a turn where the user team is on offense
-The next turn when the user is on offense, assign game state current playcall to equal the team object strategy settings offense_call
-Keep the container highlighted throughout the HCO turn where that playcall is used
-Once that HCO turn ends, rgarless of outcome, remove teh highlight from the container

--Note this will not impact computer team's playcalls and strategy calls. We will continue to use teh curernt system for computer team. Only changes will be macro game engine changes for SS&S if we agree to make any.

---

## Database Persistence for strategy_calls

**Issue:** `strategy_calls` (including `offense_call` and `defense_call`) are currently only stored in memory. When a game is reloaded from the database (e.g., after server restart, or when `ongoing_games` doesn't have the game), a new `GameManager` is created, which creates new `TeamManager` objects with default `strategy_calls` (all `None`). This causes user playcall overrides to be lost.

**Solution:** Persist `strategy_calls` to the database when saving game state, and restore them when loading a game from the database.

**Implementation Notes:**
- Save `strategy_calls` in the game document (likely in the `teams` object structure)
- Restore `strategy_calls` when creating `TeamManager` objects from saved game data
- Ensure `is_user_team` flag is also preserved/restored correctly
- Test that overrides persist across server restarts and game reloads

