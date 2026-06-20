

**Shot Attempts**
- Inside Shots
    - Strong Inside Shot (player sprite moves 1 x spot toward the basket then animates shot)
    - Fade Away Inside Shot (player sprite moves 1 x spot away the basket then animates shot)
    - Up & Under Inside Shot (player sprite moves 1 x spot toward the basket, then 2 x spots away from the basket then animates shot)
    - Under & Up Inside Shot (player sprite moves 1 x spot away the basket, then 2 x spots toward from the basket then animates shot)
    - Straight Inside Shot (player sprite does not move, then 2 x spots away from the basket then animates shot)
- Attack Shots
    - Strong Attack Shots (any attack shot executed at a near basket spot)
        (player sprite moves 1 x spot toward the basket then animates shot)
    - Pullup Attack Shot (any attack shot not attempted at a near basket spot)
        (player sprite moves 1 x spot toward the basket then animates shot)
- Outside Shots
    - Set Outside Shot
    - Set Outside Shot with Pump Fake
    - Dribble & Shoot Outside Shot 
    - Dribble & Shoot Outside Shot with Pump Fake
    - Fade Away Outside Shot

**Near Basket Spots for Shot Attempt Execution**
- basketSpot, lower lowPost, upper lowPost
- any spot within this geometric area: lower lowPost to basketSpot to upper lowPost to one x grid spot closer to teh basket than upper midPost (same y as upper midPost) to one x grid spot closer to the basket than midLane (same y as midLane) to one x grid spot closer to the basket than lower midPost (same y as lower midPost) 

**Steal Attempts**
- Reach in to attempt steal (this can result in a steal or foul)

**Blocks**
- Defender

**Man on Man Defense**
- Post Up, have the post up offender and defender sprites rattling back and forth on each other
- Movement - implement later

**Screens**
- will implement later


