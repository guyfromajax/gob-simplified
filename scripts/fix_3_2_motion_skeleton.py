#!/usr/bin/env python3
"""
Script to fix the 3-2 Motion skeleton by adding two missing intermediate steps
for the final two passes to the key.

Pattern: When a player moves to lower wing, lower lowPost (PF) sets screen.
         When a player moves to upper wing, upper lowPost (C) sets screen.
"""

import requests
import json
import sys

def fix_skeleton():
    play_name = "3-2 Motion"
    api_url = f"http://localhost:8000/api/play/{play_name.replace(' ', '%20')}"
    
    print(f"🔍 Fetching '{play_name}' from API...")
    
    try:
        # Get current play data
        response = requests.get(api_url)
        response.raise_for_status()
        play_data = response.json()
        
        if not play_data:
            print(f"❌ Play '{play_name}' not found in database")
            return False
        
        skeleton = play_data.get("skeletons", {}).get("base_loop")
        if not skeleton:
            print(f"❌ No 'base_loop' skeleton found for '{play_name}'")
            return False
        
        steps = skeleton.get("steps", [])
        print(f"📊 Current skeleton has {len(steps)} steps")
        
        # Find the indices where we need to insert steps
        # Step 15 (4500ms) -> Step 16 (4800ms) needs intermediate step
        # Step 19 (5700ms) -> Step 20 (6000ms) needs intermediate step
        
        # Create a new steps array
        new_steps = []
        inserted_count = 0
        
        for i, step in enumerate(steps):
            timestamp = step.get("timestamp", 0)
            updated_step = step.copy()
            
            # Check if we need to insert an intermediate step after this one
            if timestamp == 4500:
                # Step 15: SG passes to SF at key, PG cuts to upper wing
                # Append current step as-is
                new_steps.append(updated_step)
                
                # Insert intermediate step: PG cuts to key, C sets screen at midLane
                print(f"🔧 Inserting intermediate step after step {i+1} (timestamp {timestamp})")
                intermediate_step = {
                    "timestamp": 4800,
                    "pos_actions": {
                        "PG": {
                            "location": "key",
                            "action": "cut"
                        },
                        "SG": {
                            "location": "lower wing",
                            "action": "stationary"
                        },
                        "SF": {
                            "location": "key",
                            "action": "handle_ball"
                        },
                        "PF": {
                            "location": "lower lowPost",
                            "action": "post_up"
                        },
                        "C": {
                            "location": "midLane",
                            "action": "screen"
                        }
                    },
                    "events": []
                }
                new_steps.append(intermediate_step)
                inserted_count += 1
                
            elif timestamp == 4800:
                # This is the old Step 16, need to update it
                # Change PG from "upper wing" receive to "key" receive
                # And update timestamp to 5100
                print(f"🔧 Updating step {i+1} (old timestamp {timestamp}) to new timestamp 5100")
                updated_step["timestamp"] = 5100
                updated_pos_actions = step["pos_actions"].copy()
                
                # Change PG from upper wing receive to key receive
                updated_pos_actions["PG"] = {
                    "location": "key",
                    "action": "receive"
                }
                
                # SF passes (stays the same)
                # SG should cut to upper wing (since PG is now at key)
                updated_pos_actions["SG"] = {
                    "location": "upper wing",
                    "action": "cut"
                }
                
                updated_step["pos_actions"] = updated_pos_actions
                new_steps.append(updated_step)
                
            elif timestamp == 5100:
                # This is the old Step 17, need to shift it to 5400
                print(f"🔧 Shifting step {i+1} from timestamp {timestamp} to 5400")
                updated_step["timestamp"] = 5400
                new_steps.append(updated_step)
                
            elif timestamp == 5400:
                # This is the old Step 18, need to shift it to 5700
                print(f"🔧 Shifting step {i+1} from timestamp {timestamp} to 5700")
                updated_step["timestamp"] = 5700
                new_steps.append(updated_step)
                
            elif timestamp == 5700:
                # Step 19: PG passes to SG at key, SF cuts to lower wing
                # Append current step as-is
                new_steps.append(updated_step)
                
                # Insert intermediate step: SF cuts to key, PF sets screen at midLane
                print(f"🔧 Inserting intermediate step after step {i+1} (timestamp {timestamp})")
                intermediate_step = {
                    "timestamp": 6000,
                    "pos_actions": {
                        "PG": {
                            "location": "upper wing",
                            "action": "stationary"
                        },
                        "SG": {
                            "location": "key",
                            "action": "handle_ball"
                        },
                        "SF": {
                            "location": "key",
                            "action": "cut"
                        },
                        "PF": {
                            "location": "midLane",
                            "action": "screen"
                        },
                        "C": {
                            "location": "upper lowPost",
                            "action": "post_up"
                        }
                    },
                    "events": []
                }
                new_steps.append(intermediate_step)
                inserted_count += 1
                
            elif timestamp == 6000:
                # This is the old Step 20, need to update it
                # Change SF from "lower wing" receive to "key" receive
                # And update timestamp to 6300
                print(f"🔧 Updating step {i+1} (old timestamp {timestamp}) to new timestamp 6300")
                updated_step["timestamp"] = 6300
                updated_pos_actions = step["pos_actions"].copy()
                
                # Change SF from lower wing receive to key receive
                updated_pos_actions["SF"] = {
                    "location": "key",
                    "action": "receive"
                }
                
                # SG passes (stays the same)
                # PF should cut to lower wing (since SF is now at key)
                updated_pos_actions["PF"] = {
                    "location": "lower lowPost",
                    "action": "cut"
                }
                
                updated_step["pos_actions"] = updated_pos_actions
                new_steps.append(updated_step)
                
            elif timestamp >= 6300:
                # Shift remaining steps by 300ms
                new_timestamp = timestamp + 300
                print(f"🔧 Shifting step {i+1} from timestamp {timestamp} to {new_timestamp}")
                updated_step["timestamp"] = new_timestamp
                new_steps.append(updated_step)
            else:
                # All other steps: append as-is
                new_steps.append(updated_step)
        
        # Update the skeleton
        skeleton["steps"] = new_steps
        print(f"✅ Updated skeleton now has {len(new_steps)} steps (added {inserted_count} intermediate steps)")
        
        # Update the play in the database using POST /api/plays (upsert by name)
        update_url = "http://localhost:8000/api/plays"
        
        # Prepare update payload - need to include all required fields
        update_payload = play_data.copy()
        update_payload["skeletons"] = {
            "base_loop": skeleton
        }
        # Remove _id if present (API will handle it)
        if "_id" in update_payload:
            del update_payload["_id"]
        
        print(f"💾 Updating play in database...")
        update_response = requests.post(update_url, json=update_payload)
        update_response.raise_for_status()
        
        print(f"✅ Successfully updated '{play_name}' skeleton in database!")
        print(f"📊 Summary:")
        print(f"   - Original steps: {len(steps)}")
        print(f"   - New steps: {len(new_steps)}")
        print(f"   - Intermediate steps added: {inserted_count}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error calling API: {e}")
        return False
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = fix_skeleton()
    sys.exit(0 if success else 1)

