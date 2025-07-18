import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from BackEnd.models.training_manager import TrainingManager, TrainingCategory
from datetime import datetime

# Step 1: Initialize manager and load data
manager = TrainingManager("Four Corners")  # <-- replace with your actual team name
manager.load_team_and_players()

# Step 2: Create a training session
session = manager.create_training_session(session_type="preseason", date=datetime.now().strftime("%Y-%m-%d"))

# Step 3: Assign practice points (must total 24)
session.assign_points(TrainingCategory.OFFENSIVE_DRILLS.value, {"inside": 2, "outside": 1})
session.assign_points(TrainingCategory.DEFENSIVE_DRILLS.value, {"inside": 1, "outside": 2})
session.assign_points(TrainingCategory.TECHNICAL_DRILLS.value, {"PS": 2, "BH": 2, "RB": 1})
session.assign_points(TrainingCategory.WEIGHT_ROOM.value, {"ST": 1, "AG": 1})
session.assign_points(TrainingCategory.CONDITIONING.value, 3)
session.assign_points(TrainingCategory.FREE_THROWS.value, 2)
session.assign_points(TrainingCategory.TEAM_BUILDING.value, 3)
session.assign_points(TrainingCategory.BREAKS.value, 4)  # ← allows zeroing to be avoided

# Step 4: Run session and persist results
log = manager.run_and_save_session(session)

# Step 5: Print log to see what happened
print("\n--- TRAINING SESSION LOG ---")
for entry in log:
    print(entry)
