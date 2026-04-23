Rules to be involved in messaging. Note that all absolute values referned in the rules represent the final change, so they are inclusive of all multipliers

**Player Drill Attributes**
SC, SH, ID, OD, PS, BH, RB, AG, ST
-player's absolute gain must be > 3 or < -3

**Team Drill Attributes**
Offense Efficienty, Defense Efficiency, Fast Break Efficiency, P/T Efficiency, FB Opp Modifier, P/T Opp Modifer (scrimmage is excluded from this logic and has special logic below)
-Setting for the attribute traning must be > 1


**General Drill Attribures**
-ND, FT, and IQ -- same logic as Player Drills
-Breaks (special logic below)

**Breaks Logic**
-Setting for breaks must be > 0

**Scrimmages Logic**
-Setting for scrimmages must be > 0



**Player Attribute Message Structure**
"{Player Name} {description} in {setting}."
-Player Name is the player's name
-Description is detailed below
-Setting is either "in drills" or "in team scrimmages"
 - in order to say "in team scrimmages" for any attribute, scrimmages setting must be > 0
 - in order to say "in drills", we take that on an attribute by attribute basis and each attribute's drill setting must be > 0
 - if one of scrimmages or drills language is omitted, use the other for 100% of messages
 - if both are omitted, omit all messages for that attribute
 - note two attributes do not read "in team drills" as an option, rather they use the following:
    -ST: "in the weight room"
    -ND: "in conditioning"


**Descriptions by Attribute**
SC Positive
-is scoring well
-is dropping the ball through the hoop
-is showing great ball maneuvers near the basket
-is adjusting his inside shot well

SC Negative
-is laying bricks
-is clanking his shots
-does not look good scoring
-is stuggling to finish shots

SH Positive
-is draining 3s
-is nailing his outside shots
-is unguardable on the outside
-is shooting extremely well

SH Negative
-is bricking his 3s
-is missing everything from outside the arc
-is not shooting well
-is not feeling his shot today

ID Positive
-is guarding the rim well
-is playing great inside defense
-is looking strong on the inside, defensively,

ID Negative
-is looking weak on the inside, defensively,
-is getting pushed around on the inside
-is not guarding the rim well
-is not guarding the inside well

OD Positive
-is doing a great job guarding 3s
-is doing an awesome job guarding the perimeter
-is disrupting passing lanes

OD Negative
-is letting too many easy 3s get shot
-is playing poor outside defense
-is not guarding the perimeter well

PS Positive
-is delivering crips passes
-is doing a great job finding the open man
-is setting up the outside shot with is passing well

PS Negative
-is just off with is his passes
-is not passing well
-is missing open players

BH Positive

BH Negative

RB Positive

RB Negative

ST Positive

ST Negative

AG Positive

AG Negative

ND Positive

ND Negative

IQ Positive

IQ Negative

FT Positive

FT Negative


