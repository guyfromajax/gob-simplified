

##Page Header##
Title: "GOB User Feedback"

##5 Multiple Choice Questions**
Title: "Give Us Your Opinion On Each of the Below 5 Items in GOB"

**Format**
- All five multiple choice questins are required to compolete teh form
- Question on left, occupies 1/3 of horizontal space -- wrap text if need be
- multiple choice slider to teh right in the same row as teh qustion
- slider has four points in this order: "N/A", "Awful", "Ok, but needs work", "Great"
    - all sliders start on N/A
    -color when user drags and drops to each point
        -N/A: black
        -Awful: red
        -Ok, but needs work: yellow
        -Great: green
- every slider has a text field below, 12px in height, with pre-existing copy that reads "Optional Feedback". If the user presses in teh field, a modal appears with a copy box that reads "Tell us more", and "Tell us more" goes away when the user presses inside the box. Hvae a "submit" button at the bottom that captures this feedback. This is optional, user is not required to fill it out to complete the form.
-apply the click-tiny.wav SFX as the user drags and releases on a new slider point.

Question 1: "Live Gameplay"
Question 2: "The Experience Between Games: Stats, Standings & Scouting"
Question 3: "Recruiting"
Question 4: "Franchise Mode: 26-Week Season + Tournaments"
Question 5: "High School Setting"
Question 6: "Onboarding Experience"


##2 Special Questions**
Title: "How Did You Feel About Each of the 2 Items Below?"

**Format**
- Both questions are required to complete the form
- Same question / slider / text field structure as above, with tweaks for slider copy and colors noted below each.

Question 7: "The time it took to play a single game was..."
Slider: "N/A", "Too Short", "Just Right", "Too Long"
Slider fill colors: black, red, green, red

Question 8: "The learning curve for this game is..."
Slider: "N/A", "Too Easy", "Just Right", "Too Hard"
Slider fill colors: black, red, green, red


##2 Open-Ended Questions & One Boolean**
Title: "Lastly, Give Us Your Opinion -- In Your Own Words"

**Format**
- All three questions are required
- The first two are simple text boxes with prefills "Tell Us What You Think"

Question 9: "What Is Your Favorite Thing About GOB?"
Question 10: What Is Your Least Favorite Thing About GOB?

Question 11: Would you recommend GOB to a friend: 
-Yes/No toggle
-Toggle starts neutral
-Yes highlight in green, no highlights in red


**Page UX**
-An always present bar at the bottom of the screen with a "Submit" button that is dead until the user completes all 11 required questions, then becomes orage. Also have a tracking bar at the bottom. 0/11, 1/ll, 2/11, etc -- with eleven dashes that start grey and become orage as teh user completes questions.

**Page wiring**
- All form submissions are saved to teh gob db (main) or gob-staging db (staging), in a newly created "alpha_feedback" collection for each db. Can we initiate this collection for each db lazily as the first user submits a form? or do we need to create these collections ahead of time.

**UX**
- All users (new & existing) are presented with a modal after they complete their second game after we push this live. it appears after the game and when they land on the FCC page (same behavor as teh archetype modal appearing after they finish their first game). 

- Modal copy "Now that you've played a couple games, we'd love to get your feedback to make the game better."
- Left button: Feedback (same purple design as the feedback button in the top nav)
- right button: Go To Locker Room (designed as secondary button -- not orage fill, ghost fill)

- if the user provided feedback, they are never presented with this modal again and Feedback button in top nav bar behavior remains as is.

- if the user does not provide feedback
    - we re-present this feedback to the suer one more time, after they complete their fifth game, changing copy in modal from "2" to "5"
    - until the user complete the feedback form once, rewire teh Feedback button in the top nav bar to go to this 11-question feedback form. Also place a purple highlight emitting from the button until the user has provided feedback. Make the highlight noticeable, but not obnoxious.