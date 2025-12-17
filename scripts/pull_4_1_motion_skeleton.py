#!/usr/bin/env python3
"""
Script to pull the 4-1 Motion play skeleton from MongoDB via API and save it to a file.
"""

import json
import sys
import os
import subprocess
from pathlib import Path

def pull_4_1_motion_skeleton():
    """Pull 4-1 Motion play skeleton from database via API and save to file."""
    
    play_name = "4-1 Motion"
    # URL encode the play name (space becomes %20)
    encoded_name = play_name.replace(" ", "%20")
    
    # Use curl to fetch from API
    api_url = f"http://localhost:8000/api/play/{encoded_name}"
    
    print(f"🔍 Fetching '{play_name}' from API: {api_url}")
    
    try:
        result = subprocess.run(
            ["curl", "-s", api_url],
            capture_output=True,
            text=True,
            check=True
        )
        
        play_data = json.loads(result.stdout)
        
        if not play_data:
            print(f"❌ Play '{play_name}' not found in database")
            return
        
        print(f"✅ Found play: {play_data.get('name', 'N/A')}")
        print(f"   - Play Type: {play_data.get('play_type', 'N/A')}")
        print(f"   - Play Focus: {play_data.get('play_focus', 'N/A')}")
        
        # Extract skeleton data
        skeletons = play_data.get("skeletons", {})
        
        if not skeletons:
            print(f"❌ No skeletons found for '{play_name}'")
            return
        
        print(f"   - Available skeleton variants: {list(skeletons.keys())}")
        
        # Create output structure
        output = {
            "play_name": play_data.get("name"),
            "play_type": play_data.get("play_type"),
            "play_focus": play_data.get("play_focus"),
            "skeletons": skeletons
        }
        
        # Save to file
        script_dir = Path(__file__).parent
        output_file = script_dir.parent / "docs" / "4_1_motion_skeleton.json"
        
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        print(f"✅ Skeleton data saved to: {output_file}")
        
        # Print summary
        if "base_loop" in skeletons:
            base_loop = skeletons["base_loop"]
            steps = base_loop.get("steps", [])
            print(f"\n📊 Base Loop Skeleton Summary:")
            print(f"   - Total steps: {len(steps)}")
            print(f"   - Steps 1-10 available: {len(steps) >= 11}")
            
            # Check for final step
            final_step_found = False
            for i, step in enumerate(steps):
                if step.get("is_final_step"):
                    print(f"   - Final step marked at index {i}")
                    print(f"   - Loop back to: {step.get('loop_back_to', 'N/A')}")
                    final_step_found = True
                    break
            
            if not final_step_found:
                print(f"   - ⚠️ No final step marked (is_final_step flag not found)")
            
            # Print step count breakdown for steps 1-10
            print(f"\n📋 Step Breakdown (steps 1-10):")
            steps_to_show = steps[1:11] if len(steps) > 1 else []
            for i, step in enumerate(steps_to_show):
                step_index = i + 1  # Step 1-10 (excluding step 0)
                pos_actions = step.get("pos_actions", {})
                timestamp = step.get("timestamp", "N/A")
                events = step.get("events", [])
                is_final = step.get("is_final_step", False)
                print(f"   Step {step_index}: {len(pos_actions)} player actions, timestamp={timestamp}, events={len(events)}, is_final={is_final}")
            if len(steps) < 11:
                print(f"   ⚠️ Only {len(steps)} total steps (need at least 11 for steps 1-10)")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error calling API: {e}")
        print(f"   Make sure the backend server is running on http://localhost:8000")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON response: {e}")
        print(f"   Response: {result.stdout[:200] if 'result' in locals() else 'N/A'}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    pull_4_1_motion_skeleton()

