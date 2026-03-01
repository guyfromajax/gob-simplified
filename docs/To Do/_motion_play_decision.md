

In instances of a Motion play that hits the Shot Clock Violation / Force Shot calcualtion threshold

-Before running the Forced Shot or Shot Clock Violation logic, give the team a chance to recalibrate to a shot attempt on an earlier step to avoid te forced shot penalty or the shot clock violation

-recalibratoin chance logic

chemistry = offense team's chemistry attribute value (7-25)
discipine = offense team's discipline attribute value (-10 - 10)
- future, add playcall effectivness score to this

(chemistry * 3) + (discipline * 2) = recalibration score

die roll = random.randint(1,100)

if die roll < recalibration score, apply recalibration logic, else proceed to standard forced shot / shot clock violation check logic

recalibration logic
-final step = step number that forced the shot clock violation check
-choose a random step between step 3 and (final step -1)
-recalibrate the turn to be a shot attempt from the chosen random step
-choose the shot type (attack, inside, outside) with our standard process for choosing in motion plays. Note if any of the shots are not eligible due to no players being in a spot to shoot tha ttype of shot, remove it from teh calculatoin (example, if no players are located at an inside shot location, remove inside from the random calculation)
-recalibrate game clock and shot clock to elapse time to the newly chosen turn
-execute normal shot attempt system

--note this only applies to turns that reach teh shot clock 0. My assumption is no turn that is going to result in a steal, dead ball turnover, offensive foul or defensive shooting foul can also reach this point. LMK if that is not the case.