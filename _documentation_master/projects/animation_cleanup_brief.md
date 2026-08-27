##Objective
Evolve Play animation from clumsy and frustrating to elegant, rewarding, and true to basketball

##Symptoms
- many shot attempts are animated too slow, I'd like better control over when a shooter shoots. Immediatley when he receives the ball (which is offent the case) or after he holds or dribbles for a few beats
- some (but not all) steals, fouls, and interceptions are still happening by a defender who is not near the ball handler. I don't know fi we're incorreclty aassinging the ball handler or incorrectly assinging the stealer at the moment of the steal. Or if both assignments are correct and we're not correclty animating.
- we have puases between many turns. I know we've hard coded some of these but many other feel like a result of our current animation. Intended animation is not pauses between turns unless explicityly hard coded. We should generate a list of all hard codes puases into teh animation so I can review. Many of these may be legacy and no longer needed.
- fast break animations are still not consistenlty perfect. We still hit instances wehre all players form teh defensvie team stop animating while all offensie players animate through the end fo the turn. We've tried to fix this about 5 or 6 times now and the problem is not 100% solved, which tells me we have a systematic issue at play here (along with the rest of the animation)
- FB Outlet Pass denials are animating clumsily. The outlet passer moves to his spot, then all players hold excepte for the outlet pass denier who then moves inso position to deny the pass.
- Same for ball batted OOB in HCO tuns. Only teh batting ball defender moves to his spot then bats the pass. Ideally this is organic with all palyers moving. I do think this and the FB Outlet Pass Denial issue are how we've currenlty coded things, but LMK.
- Some passes seem to ahve too long of pauses both to shooters and in executing HCO turns.
- Right now on fast breaks we have a nice little jiggle move that a ball handler sometimes executes when he beats an defensive stop attempt. that is nice and I'd love more subtle, organic, and human moments like that. I referecned a few earlier with collisions, post ups, etc. Screens would also be great, as well as idle ball handlind, idle movement, and as I note below with shot attempt types, etc.

##So you're aware some things are are feeling good in current animation
- some shot attemtps and passes then shot attempts are truly crisp and rewarding
- free throw animations feel good
- having variety in shot attempt animation feels nice. straight line vs arc =- also teh flash animation on good shot attempts are nice
- the variablity of rim action by teh ball (swish, clank, airball, all fo teh rattles, banks, etc) feels awesome and is really rewarding
- FLSS shots from long range are animating nicely


##References
- NBA2K, with it's fluid player movement is the standard. I realize that is a physics based engine and ours is 2D animation of player sprites, but we should at least strive for the foundation of fluid player movmement that feels real. Even with out all of the detail that NBA2K has (like player's dribbling, doing specific movemetns, etc). 
-Retro Bowl is great for 2D fluid and reslistic and rewarding animation. That sould be our 2D animation standard, while striving for organic basketball movements in NBA2k as much as possible, realizing we cannot replicate their animation perfectly.
- Note I'll eventually want to add a bit of physics that are appropriate for 2D animation. Things like player sprites not stacking on the same locaiton, sprites bumpting into ech other when they collide, player post up and post defender battling for psoition, and more organic dribbling in plac emotion and idel motion than we have now. We can determin if that should be a part of this process or future. My gut says account for this now, but I'm nto an animation expert.
- I'll also eventually want to give players unique shot types, the same way OOTP gives batters unique swings and pitchers unique pitching motions with their 2D animation. Note we'll have less to work with than OOTP as OOTP has baseball player body sprite objects with movement for arms, legs, head, torso etc. And we'll be working with just a circle headshot sprite + ball, but we can do unique things with the ball movment on a shot, subtle sprite movement, etc. We've already introduced shot motion types and they're nice but they're pretty generic to shot type -- which is ok for now. This is definitely something to update once we get the core animation to where I want it.


##Note
I'd say this is about 70% working. I really want that final 30% (or a chunk the final 30%) to take this from functional to amazing or perfect, but I also want to have an honest discussion after you review things. If we risk a serious "throw the baby out with the bath water" issue with an animation overhaul, I'm open to having that discussion.

##Requirements
- Must adhere to Sim Perf Capstone -- we cannot slow teh pace of the game. Either full game sim or play quarter live play
- UESS System compliance -- all logic on the back end, front end is a pure renderer. Open to updating this system if needed.
- Must adhere to teh current timing -- i.e 350ms wall clock time = 1 game second. Note this is executed a bit sloppily right now so if there is opportuntity tighten this, that is great. But we must protect that scale in order to keep game stats realistic.


