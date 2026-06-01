> **Superseded by** [`05_Features/SFX_System.md`](../../05_Features/SFX_System.md) § Sound library strategy. Full brief retained here.

**The Task**
Create a library of SFX files to serve and enhance the user's experience in GOB.

**Strategy**
The SFX need to tell the story of the moment without using any words or numbers. Given the nature of GOB as a deep tactcial sports sim game, the user experience is already loaded with text, numbers and data. The SFX will be a primary tool to intuitively communicate the feel and tone of the game at given moments -- without the need for text, numbers or data.

**3 Pillars of SFX**
1. In-Game SFX (5 sub-pillars)
    a. Big Moments: these are the most impactful and exciting moments of any game
        -Made Shot
            -Regular Make
            -And 1 Make (where the shooter is fouled and he makes the shot)
            -Clutch Make (final minute of a close game -- Q4 and OT only)
        -Rebound
            -Offensive
            -Defensive
        -Steal / Interception
        -Block
    b. Mico+ Moments: these are bigger than micro moments, but not as big as Big Moments
        -Oulet Pass (Fast Break only)
        -Foul
        -Dead Ball Turnover
        -Executing a Trap
        -High Momentum player makes a shot
        -High Momentum player misses a shot
    c. Micro Moments: these are common moments within gameplay
        -Player grabs opening tip
        -Pass
        -Receive (from passer)
        -Screen
        -Shoot a Shot
            -Inside
            -Attack
            -Outside
            -Free Throw
            **have 3 levels for each (weak, medium, strong) based on the shooter's pre_defense_shot_score
        -Make a Shot
            -Have variations (clean swish, hit the back of the rim and drop in, heavy rattle around the rim and go in, normal rattle around the rim and go in, bank off the back board, bounce around the rim a little, bounce around the rim a lot, rattle around the rim - bounce of the backboard - then go in the basket)
        -Miss a Shot
            - Have variations (good shot that rims out, normal shot that rims out, bounce around the rim a little and miss, bounce around the rim a lot and miss, missed bank shot of the backboard, bad brick off the front of the rim, bad brick off the back of the rim, normal brick off the back of the rim, airball)
        -Fast Break Outlet denied
        -Ball Batted OOB (by Defense)
    d. Announce key moments (these will pair with an announcement from our Announcement System)
        -HC Trap
        -FC Press
        -Fast Break
        -Quick Shot (end of game)
        -Slow It Down (end of game)
        -Quick Foul (end of game)
        -Final Shot (end of quarter, end of game)
        -In play audible
        -End of Quarter -- have an airhorn SFX
        -Timeout -- have an airhorn SFX
    e.In-game atmosphere
        -General crowd noise
            -Need to determine variation strategy (by week? by quarter? Close game vs Blowout? Home winning vs home losing?)
        -Timeout ambience: plays while the user is on the set lineup screen during a timeout and quarter break
            -Options to consider: crowd noise, music, high school band, cheerleading

2.Non-Gameplay SFX
    -Plays when the user is in non-gameplay experience. 
        -Examples: Roster page, Stats page, Scouting Repports page, Recruits page, Game Plan editing page, Playbooks editing page, etc
    -These need to contrast nicely and naturally to In-Game SFX. In-Game SFX are intense and action-packed and the heart of the gameplay. These screens are the game within the game (particulalry for our target audience). They need to feel more relaxing, rewarding, and like study time.

3. Functional SFX
    -Add endorptions and a positive feel to mundane and everyday in-game navigation. Moving from screen to screen, tab to tab, running training, saving playbooks, etc.
    -Note most of these are built and in good shape.

4. Speical Case: Tournaments
    -We have three rounds of tournaments in teh game: Conference, Region, and Nationals. We need to determine what we'll do from a SFX and sometimes accompnanying visual perspective to make these feel special. 
        -Some ideas: pre-game hype like strobe lights around the area, more intense crowd noise, more intense band or music playing, etc.
    -Note also when we have big regular season games (#1 ranked team playing #2 ranked team, etc) we can employ some of these special moments as well.


**SFX Mandatories**
1. All sounds must be authentic to basketball, authentic to gaming, or both.
2. All sounds must have a clear role in the game experience.
3. Each sound must be distince in role and sound distinctly different from other sounds in game.
4. Sounds must fit the brand tone: strategic, elegant, and premium.


**Questions At This Point**
1. Big Moments -- should these be SFX only, Crowd Noise / Crowd Reaction Only, Either Depending On Use-Case, or a combiation of SFX + Crowd?
2. Do we pair visuals with these? I think for some of them we should. We have a cool ball-trail visual effect for well executed FB Outlet passes that pairs very nicely with the current sound effect. We should determine which moments have visual support and which do not. I think we can base this on the moment itself, as well as the sound effect itsefl.

**Notes**
-This proect is for design of the soudns and files only. I am working with Cursor to implement these into teh game engine.
-File formats
    -Use WAV for all short gameplay and UI sound effects.
    -Use WAV for any sound that must sync to an exact visual moment.
    -Use MP3 only for long background audio, music, ambient beds, or loops.
    Length Guidelines

    -WAV or MP3
        -0-5 seconds: WAV
        -5-10 seconds: WAV if timing matters, MP3 if it is ambient/background
        -10+ seconds: MP3 unless exact sync is required
    -WAV Settings
        -44.1 kHz or 48 kHz
        -16-bit or 24-bit
        -Trim leading silence
        -Loudness-match related sounds as a set
        -Mono is fine for simple effects; stereo only when spatial width matters
    -MP3 Settings
        -44.1 kHz or 48 kHz
        -192 kbps minimum
        -256-320 kbps preferred for music
        -Trim leading silence
        -Loudness-match related tracks


