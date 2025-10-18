#!/usr/bin/env python3
"""
Update MongoDB players collection with photo field based on renamed image files.
"""
import os
import re
from BackEnd.db import players_collection

# Path to player images
IMAGES_DIR = "FrontEnd/static/images/players"

def main():
    """Update all players in MongoDB with their photo field"""
    if not os.path.exists(IMAGES_DIR):
        print(f"❌ Directory not found: {IMAGES_DIR}")
        return
    
    # Get all image files that are in player_id format
    files = [f for f in os.listdir(IMAGES_DIR) if f.endswith('.png') or f.endswith('.PNG')]
    
    # Filter to only UUID-formatted filenames (player_id.png)
    uuid_pattern = r'^([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\.png$'
    player_images = []
    
    for filename in files:
        match = re.match(uuid_pattern, filename, re.I)
        if match:
            player_id = match.group(1)
            player_images.append((player_id, filename))
    
    print(f"📁 Found {len(player_images)} player images in player_id format")
    print()
    
    updated_count = 0
    not_found_count = 0
    already_set_count = 0
    
    for player_id, filename in sorted(player_images):
        # Find player in MongoDB
        player = players_collection.find_one({"player_id": player_id})
        
        if player:
            # Check if photo field already exists and matches
            photo_path = f"/static/images/players/{filename}"
            
            if player.get('photo') == photo_path:
                print(f"⏭️  SKIP: {player['first_name']} {player['last_name']} (photo already set)")
                already_set_count += 1
            else:
                # Update the player document
                result = players_collection.update_one(
                    {"player_id": player_id},
                    {"$set": {"photo": photo_path}}
                )
                
                if result.modified_count > 0:
                    print(f"✅ UPDATED: {player['first_name']} {player['last_name']}")
                    print(f"           Photo: {photo_path}")
                    updated_count += 1
                else:
                    print(f"⚠️  NO CHANGE: {player['first_name']} {player['last_name']}")
        else:
            print(f"❌ NOT FOUND IN DB: {player_id}")
            not_found_count += 1
    
    print()
    print("=" * 60)
    print(f"📊 Summary:")
    print(f"   ✅ Updated: {updated_count}")
    print(f"   ⏭️  Already set: {already_set_count}")
    print(f"   ❌ Not found in DB: {not_found_count}")
    print(f"   📁 Total: {len(player_images)}")
    
    # Verify the updates
    print()
    print("🔍 Verification:")
    total_with_photos = players_collection.count_documents({"photo": {"$exists": True}})
    print(f"   Total players with photos in DB: {total_with_photos}")

if __name__ == "__main__":
    main()

