"""
Rename player headshot images from name-based filenames to player_id.png
Matches images by player name (first + last) to find the correct player_id from MongoDB
"""
import os
import re
from BackEnd.db import players_collection

# Path to player images
IMAGES_DIR = "FrontEnd/static/images/players"

# Manual name corrections (image filename -> database name)
NAME_CORRECTIONS = {
    "VICTOR LIGHTFOOT": "VICTOR LARGEFOOT",
    "JERRY ONEAL": "JERRY O'NEAL",
    "SONNY CORROZZA": "SONNY CARROZZA",
    "PRINVE BAEZ": "PRINCE BAEZ",
    "TIMMY DEPAZ": "TMMY DEPAZ",  # DB has "Tmmy" typo (missing 'i')
    "KENT MCMANUS": "KENT MCMANUS",
    "PETE DELFINO": "PETE DEL FINO",
    "ELLIS CLEMENS": "ELLIS CLEMONS",  # DB has "Clemons" not "Clemens"
    "EMERY LANDRENEAU": "EMERY LANDRANEAU",
    "LEONARD TIBBITS": "LEONARD TIBBITS",
    "M BLEEKER": "MALCOLM BLEEKER",
    "JEREMY JOHNSON": "JEREMY JOHNSON",
    "JIMMY PILOT": "JIMMY PILOT",
    "DAMON MARTIN": "DAMON MARTIN",
    "CEDRICK MCBURNS": "CEDRICK MCBURNS",
    "JAYSON DUTTA": "JAYSON DUTTA",
    "MICHAEL GARZA": "MICHAEL GARZA",
    "NOLAN FORTRESS": "NOLAN FORTRESS",
    "B PRESTON": "BOOKER PRESTON",
    "FORREST RUTHERFORD": "FORREST RUTHERFORD",
    "GRANVILLE DAMORE": "GRANVILLE D'AMORE",
    "PHILLIP ALI": "PHILLIP ALI",
    "DEANTHONY HAYES III": "DEANTHONY HAYES III",
    "KENNETH OCALLAHAN": "KENNETH O'CALLAHAN",
    "SIRAN STANHOPE": "SIRAN STANHOPE",
    "WALLACE FARABEE": "WALLACE FARRABEE",
    "NATE REARDON": "NATE REARDON",
    "S MARTINEZ": "STEVEN MARTINEZ",  # Guessing "S" = "Steven"
    "SID BODIN": "SID BODIN",
}

def normalize_name(name):
    """Normalize name for matching: remove numbers, spaces, underscores, make uppercase"""
    # Remove file extension first
    name = name.replace('.png', '').replace('.PNG', '')
    # Remove leading numbers and spaces (e.g., "1 Jesse Jamison" -> "Jesse Jamison")
    name = re.sub(r'^\d+\s+', '', name)
    # Remove team prefixes (e.g., "BT_", "FC_", "LAN_", etc.)
    name = re.sub(r'^[A-Z]{2,3}_', '', name)
    # Remove trailing numbers (e.g., "2" from "Kent_McManus2")
    name = re.sub(r'\d+$', '', name)
    # Replace underscores and hyphens with spaces
    name = name.replace('_', ' ').replace('-', ' ')
    # Strip and uppercase
    name = name.strip().upper()
    return name

def find_player_by_name(normalized_name):
    """Find player in MongoDB by matching first + last name"""
    # Apply manual corrections first
    if normalized_name in NAME_CORRECTIONS:
        normalized_name = NAME_CORRECTIONS[normalized_name]
    
    # Try to split into first and last name
    parts = normalized_name.split()
    
    if len(parts) >= 2:
        first = parts[0]
        last = ' '.join(parts[1:])  # Handle multi-word last names
        
        # Try exact match
        player = players_collection.find_one({
            "first_name": {"$regex": f"^{first}$", "$options": "i"},
            "last_name": {"$regex": f"^{last}$", "$options": "i"}
        })
        if player:
            return player
        
        # Try reversed (last name first)
        player = players_collection.find_one({
            "first_name": {"$regex": f"^{last}$", "$options": "i"},
            "last_name": {"$regex": f"^{first}$", "$options": "i"}
        })
        if player:
            return player
    
    # Try full name match
    player = players_collection.find_one({
        "$or": [
            {"first_name": {"$regex": normalized_name, "$options": "i"}},
            {"last_name": {"$regex": normalized_name, "$options": "i"}}
        ]
    })
    return player

def main():
    """Rename all player images to player_id.png format"""
    if not os.path.exists(IMAGES_DIR):
        print(f"❌ Directory not found: {IMAGES_DIR}")
        return
    
    files = [f for f in os.listdir(IMAGES_DIR) if f.endswith('.png') or f.endswith('.PNG')]
    
    print(f"📁 Found {len(files)} image files")
    print()
    
    renamed_count = 0
    not_found_count = 0
    skipped_count = 0
    
    for filename in sorted(files):
        # Skip if already in UUID format
        if re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\.png$', filename, re.I):
            print(f"⏭️  SKIP: {filename} (already in player_id format)")
            skipped_count += 1
            continue
        
        normalized = normalize_name(filename)
        player = find_player_by_name(normalized)
        
        if player:
            player_id = player['player_id']
            new_filename = f"{player_id}.png"
            old_path = os.path.join(IMAGES_DIR, filename)
            new_path = os.path.join(IMAGES_DIR, new_filename)
            
            # Check if target already exists
            if os.path.exists(new_path):
                print(f"⚠️  EXISTS: {filename} -> {new_filename} (target already exists, skipping)")
                skipped_count += 1
            else:
                os.rename(old_path, new_path)
                print(f"✅ RENAMED: {filename}")
                print(f"        -> {new_filename}")
                print(f"        Player: {player['first_name']} {player['last_name']} ({player['team']})")
                renamed_count += 1
        else:
            print(f"❌ NOT FOUND: {filename} (normalized: {normalized})")
            not_found_count += 1
    
    print()
    print("=" * 60)
    print(f"📊 Summary:")
    print(f"   ✅ Renamed: {renamed_count}")
    print(f"   ⏭️  Skipped: {skipped_count}")
    print(f"   ❌ Not found: {not_found_count}")
    print(f"   📁 Total: {len(files)}")

if __name__ == "__main__":
    main()

