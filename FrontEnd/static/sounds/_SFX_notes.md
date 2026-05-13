Wire the noted components with the SFX specified. If anything is unclear, please ask. I'm happy to clarify.

**Sound name → file (use these exact filenames in code)**

| Short name       | Filename           |
|-----------------|--------------------|
| click-strong    | click-strong.wav   |
| click-tiny      | click-tiny.wav     |
| click-beep      | click-beep.wav     |
| click-handgun   | click-handgun.mp3  |
| click-soft      | click-soft.mp3     |
| x-back          | x-back.mp3         |
| positive-beep   | positive-beep.wav  |
| positive-slide  | positive-slide.wav |
| positive-plop   | positive-plop.wav  |
| confirm-1       | confirm-1-lowervol.wav      |
| confirm-2       | confirm-2-lowervol.wav      |
| movement-cycle  | movement-cycle.mp3 |
| chaotic-choice  | chaotic-choice.wav |
| whistle-3       | whistle-3.mp3      |

---

Homepage
- Play Alpha button -- click-strong (WORKING)

Top Nav Bar
-Tutorials and Feedback buttons: click-tiny (WORKING INCONSISTENTLY)

Tutorials
- add movement-cycle when closing or opening a section in the Tutorials tabs (WORKING)
- Back link: x-back (NOT WORKING)

Mode-Select
- Play Now (all three modes): click-strong (NOW NOT WORKING)
- New Tournament or New Franchise: click-beep (WORKING)

Team-Select
- Team buttons (Single Game mode): click-handgun (WORKING)
- Team buttons (T & F modes): click-beep (WORKING)
- Play Now (SG mode): click-beep (WORKING)

FCC / TCC
- Exit Tournament / Exit Franchise: x-back (NOT WORKING)
- Set Game Plan, Playbooks: positive-beep (NOT WORKING)
- Scouting Report: positive-slide (WORKING)
- Play Next Game / Run Training: confirm-1 (WORKING)
- Tab Headers: click-tiny (WORKING)

Game Plan
- Save Game Plan: confirm-2 (WORKING)
- move & release a slider: click-tiny (WORKING)
- Back To Locker Room: x-back (NOT WORKING)
- Play Game: confirm-1 (WORKING)

Playbooks
- Save Playbooks: confirm-2 (WORKING)
- Even Distribution (on/off): click-handgun (WORKING)
- Playcall Center assignment buttons (1-6): click-tiny (WORKING)
- Percentage increments up and down: click-tiny (WORKING)
- Percentages added manually: click-soft (WORKING)
- Standard / PG / SG / SF / PF / C buttons: positive-plop (WORKING)
- Back To Lineup: x-back (NOT WORKING)

Scouting Report Pop-Up
- X to close: x-back (WORKING)

Lineup Screen
- Add player to lineup either via press or drag & drop: click-soft (WORKING)
- Remove from lineup via Red X button: x-back (WORKING)
- Drag & Drop within the lineup containers: click-soft (WORKING)
- Game Plan, Playbooks: positive-beep (NOT WORKING)
- Box Score: positive-slide (NOT WORKING)
- Autoset Lineup: chaotic-choice (WORKING)
- Grid View / Player View toggle: click-tiny (WORKING)
- Play Game: confirm-1 (WORKING)

Gameplay Buttons Popup on court.html
- Play Quarter: positive-slide (WORKING)
- Sim Full Game / Sim Rest of Game: positive-plop (WORKING)
- Sim Quarter: positive-beep (WORKING)

Defense Matchups Popup on court.html
- Drag & Drop players: click-soft (WORKING)
- Submit Defense Matchups: confirm-1 (WORKING)
- Don't show this op up again this game check box: click-tiny (WORKING)

Playcall Center on court.html
- Offense Play select: confirm-2 (WORKING)
- up & down toggle arrows for offensive plays: click-tiny (WORKING)
- Defense Play Select or Aggression Setting: confirm-2 (WORKING)
- Red X for all three (offense plays, defense plays, aggression): x-back (WORKING)

Court.html
- Timeout (UI Button): click-beep (WORKING)
- Pause/Resume (UI Button): click-tiny (WORKING)
- Speed (UI Button): click-tiny (WORKING)
- Skip To End (UI Button, when we enable it): positive-plop (WORKING)
- All In-game pop up buttons (timeout, quarter break, player foul out, EOG): click-tiny (WORKING)

Box Score
- Team tabs: click-tiny (WORKING)
- Back: x-back (NOT WORKING)

Training
- Auto-Train: chaotic-choice (only; coaching-style sound is skipped when Auto-Train triggers the random selection)
- Submit Training: confirm-2 (WORKING)
- move & release a slider: click-tiny (WORKING)
- Choose a coaching style / focus: 
    - Authoritarian (any of the four): whistle-3 (WORKING)
    - Systems Coach (any of the four): positive-slide (WORKING)
    - Player Maximizer (any of the four): positive-plop (WORKING)
    - Culture Builder (any of the four): positive-beep (WORKING)
- Close button in auto-training pop up: click-tiny (WORKING)

Training Report
- Attributes / Training Changes toggle: click-tiny (WORKING)
- Go To Locker Room: click-strong (NOT WORKING)
