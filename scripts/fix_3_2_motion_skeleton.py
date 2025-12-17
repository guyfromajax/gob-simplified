#!/usr/bin/env python3
"""
Script to fix the 3-2 Motion skeleton by adding two missing intermediate steps
for the final two passes to the key.

Pattern: When a player moves to lower wing, lower lowPost (PF) sets screen.
         When a player moves to upper wing, upper lowPost (C) sets screen.
"""

import json
import sys
import subprocess

def fix_skeleton():
    play_name = "3-2 Motion"
    api_url = f"http://localhost:8000/api/play/{play_name.replace(' ', '%20')}"
    
    print(f"🔍 Fetching '{play_name}' from API...")
    
    try:
        # Get current play data using curl
        result = subprocess.run(
            ["curl", "-s", api_url],
            capture_output=True,
            text=True,
            check=True
        )
        play_data = json.loads(result.stdout)
        
        if not play_data:
            print(f"❌ Play '{play_name}' not found in database")
            return False
        
        skeleton = play_data.get("skeletons", {}).get("base_loop")
        if not skeleton:
            print(f"❌ No 'base_loop' skeleton found for '{play_name}'")
            return False
        
        steps = skeleton.get("steps", [])
        print(f"📊 Current skeleton has {len(steps)} steps")
        
        # Find the steps that need fixing by their content
        # First fix: After Step 14 (PG cuts to midLane), before Step 15 (SG passes to SF at key, PG cuts to upper wing)
        # Second fix: After Step 18 (SF at midLane, PF sets screen), before Step 19 (PG passes to SG at key, SF cuts to lower wing)
        
        new_steps = []
        inserted_count = 0
        i = 0
        
        while i < len(steps):
            step = steps[i]
            timestamp = step.get("timestamp", 0)
            pos_actions = step.get("pos_actions", {})
            
            # Check if this is Step 14: PG cuts to midLane
            if (pos_actions.get("PG", {}).get("location") == "midLane" and 
                pos_actions.get("PG", {}).get("action") == "cut" and
                pos_actions.get("SG", {}).get("location") == "lower wing" and
                pos_actions.get("SG", {}).get("action") == "handle_ball"):
                # This is Step 14 - append it
                new_steps.append(step.copy())
                i += 1
                
                # Check if next step is Step 15: SG passes to SF at key, PG cuts to upper wing
                if i < len(steps):
                    next_step = steps[i]
                    next_pos_actions = next_step.get("pos_actions", {})
                    if (next_pos_actions.get("SG", {}).get("action") == "pass" and
                        next_pos_actions.get("SF", {}).get("location") == "key" and
                        next_pos_actions.get("SF", {}).get("action") == "receive" and
                        next_pos_actions.get("PG", {}).get("location") == "upper wing" and
                        next_pos_actions.get("PG", {}).get("action") == "cut"):
                        # Insert intermediate step before Step 15
                        print(f"🔧 Inserting intermediate step after Step 14 (timestamp {timestamp})")
                        intermediate_step = {
                            "timestamp": timestamp + 300,
                            "pos_actions": {
                                "PG": {
                                    "location": "midLane",
                                    "action": "stationary"
                                },
                                "SG": {
                                    "location": "lower wing",
                                    "action": "handle_ball"
                                },
                                "SF": {
                                    "location": "key",
                                    "action": "cut"
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
                        
                        # Update Step 15: shift timestamp and keep actions (they're already correct)
                        updated_step = next_step.copy()
                        updated_step["timestamp"] = timestamp + 600
                        new_steps.append(updated_step)
                        i += 1
                        
                        # Shift all subsequent steps by 300ms
                        shift_amount = 300
                        continue
                
            # Check if this is Step 18: SF stationary at midLane, PF sets screen at midLane
            elif (pos_actions.get("SF", {}).get("location") == "midLane" and
                  pos_actions.get("SF", {}).get("action") == "stationary" and
                  pos_actions.get("PF", {}).get("location") == "midLane" and
                  pos_actions.get("PF", {}).get("action") == "screen" and
                  pos_actions.get("SG", {}).get("location") == "key" and
                  pos_actions.get("SG", {}).get("action") == "cut"):
                # This is Step 18 - append it
                new_steps.append(step.copy())
                i += 1
                
                # Check if next step is Step 19: PG passes to SG at key, SF cuts to lower wing
                if i < len(steps):
                    next_step = steps[i]
                    next_pos_actions = next_step.get("pos_actions", {})
                    if (next_pos_actions.get("PG", {}).get("action") == "pass" and
                        next_pos_actions.get("SG", {}).get("location") == "key" and
                        next_pos_actions.get("SG", {}).get("action") == "receive" and
                        next_pos_actions.get("SF", {}).get("location") == "lower wing" and
                        next_pos_actions.get("SF", {}).get("action") == "cut"):
                        # Insert intermediate step before Step 19
                        print(f"🔧 Inserting intermediate step after Step 18 (timestamp {timestamp})")
                        intermediate_step = {
                            "timestamp": timestamp + 300,
                            "pos_actions": {
                                "PG": {
                                    "location": "upper wing",
                                    "action": "handle_ball"
                                },
                                "SG": {
                                    "location": "key",
                                    "action": "cut"
                                },
                                "SF": {
                                    "location": "midLane",
                                    "action": "stationary"
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
                        
                        # Update Step 19: shift timestamp and keep actions (they're already correct)
                        updated_step = next_step.copy()
                        updated_step["timestamp"] = timestamp + 600
                        new_steps.append(updated_step)
                        i += 1
                        
                        # Shift all subsequent steps by 300ms
                        shift_amount = 300
                        continue
            
            # For all other steps, check if we need to shift timestamps
            # If we've inserted steps, shift this step's timestamp
            if inserted_count > 0 and timestamp > 4500:  # Only shift steps after first insertion
                # Calculate how many 300ms shifts we need
                shifts_needed = inserted_count * 300
                updated_step = step.copy()
                updated_step["timestamp"] = timestamp + shifts_needed
                new_steps.append(updated_step)
            else:
                new_steps.append(step.copy())
            
            i += 1
        
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
        # Use curl to POST the update
        payload_json = json.dumps(update_payload)
        update_result = subprocess.run(
            ["curl", "-s", "-X", "POST", "-H", "Content-Type: application/json", "-d", payload_json, update_url],
            capture_output=True,
            text=True,
            check=True
        )
        update_response = json.loads(update_result.stdout)
        
        if update_response.get("message"):
            print(f"✅ Successfully updated '{play_name}' skeleton in database!")
        else:
            print(f"⚠️ Update response: {update_response}")
        print(f"📊 Summary:")
        print(f"   - Original steps: {len(steps)}")
        print(f"   - New steps: {len(new_steps)}")
        print(f"   - Intermediate steps added: {inserted_count}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error calling API: {e}")
        print(f"   stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = fix_skeleton()
    sys.exit(0 if success else 1)
