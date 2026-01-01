LEGEND
"->" = flows to
Anything labled "Master" means it is a macro flow that is used often, I detail it once, then reference it as "Master ___" in the flow docs
Anything with a numbered list under a header means those are all options that could happen, but only one of those instances actually happens


Opening Tip (start of every game, and overtime quarter)
    -> Master HCO Flow

Master HCO Flow
1. Master Shot Attempt Flow
2. Master Turnover Flow (possession change)
3. Non-Shooting Foul
    1. Offensive Foul (possession change) 
        -> Side Inbound Pass -> HCO
    2. Defensive Foul
        In Bonus?
            Yes: -> Master Free Throw Flow (Bonus FT situation)
            No: -> Side Inbound Pass -> HCO

Master Turnover Flow
    1. Dead Ball Turnover
        -> Side Inbound Pass -> HCO
    2. Steal
        1. HCO
        2. Master Fast Break Flow

Master Fast Break Flow
    1. Defensive Stop -> HCO
    2. Master Shot Attempt Flow

Master Shot Attempt Flow
    1. Make
        1. Foul
            -> Master Free Throw Flow
        2. No Foul (possession change)
            -> Master Inbound Pass Flow
    2. Miss
        1. Foul
            -> Master Free Throw Flow
        2. No Foul
            -> Master Rebound Flow

Master Free Throw Flow
    Final Free Throw?
        1. No -> Shoot next free throw
        2. Yes
            1. Make (possession change)
                -> Master Inbound Pass Flow
            2. Miss
                -> Master Rebound Flow

Master Rebound Flow
    1. Offensive Rebound
        1. Kickout -> HCO
        2. Putback Attempt -> Master Shot Attempt Flow

    2. Defensive Rebound (possession change)
        1. Master HCO Flow
        2. Master Fast Break Flow

Master Inbound Pass Flow
    1. FCP
        1. Foul
            1. Offensive Foul (possession change) 
                -> Side Inbound Pass -> HCO
            2. Defensive Foul
                In Bonus?
                    Yes: -> Master Free Throw Flow (Bonus FT situation)
                    No: -> Side Inbound Pass -> HCO
        2. Master Turnover Flow (possession change)
        3. Press Break
            1. Master Shot Attempt Flow
            2. Master HCO Flow
    2. HCT
        1. Foul
            1. Offensive Foul (possession change) 
                -> Side Inbound Pass -> HCO
            2. Defensive Foul
                In Bonus?
                    Yes: -> Master Free Throw Flow (Bonus FT situation)
                    No: -> Side Inbound Pass -> HCO
        2. Master Turnover Flow (possession change)
        3. Trap Break
            1. Master Shot Attempt Flow
            2. Master HCO Flow
    3. Master HCO Flow
