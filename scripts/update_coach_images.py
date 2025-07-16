import os

# Define base path to the coach image folders
base_path = "FrontEnd/static/images/coaches"

# Loop through each team folder
for team_folder in os.listdir(base_path):
    team_path = os.path.join(base_path, team_folder)

    # Skip if not a folder
    if not os.path.isdir(team_path):
        continue

    # Loop through each image file in the team folder
    for filename in os.listdir(team_path):
        old_path = os.path.join(team_path, filename)

        # Skip non-files
        if not os.path.isfile(old_path):
            continue

        # Replace spaces with dashes
        new_filename = filename.replace(" ", "-")
        new_path = os.path.join(team_path, new_filename)

        # Rename only if different
        if old_path != new_path:
            os.rename(old_path, new_path)
            print(f"✅ Renamed: {filename} → {new_filename}")
