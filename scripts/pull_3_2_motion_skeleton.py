#!/usr/bin/env python3
"""
Script to pull the 3-2 Motion play skeleton from MongoDB via API and save it to a file.
"""

import json
import sys
import os
import subprocess
from pathlib import Path

def pull_3_2_motion_skeleton():
    """Pull 3-2 Motion play skeleton from database via API and save to file."""
    
    play_name = "3-2 Motion"
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
        output_file = script_dir.parent / "docs" / "3_2_motion_skeleton.json"
        
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        print(f"✅ Skeleton data saved to: {output_file}")
        
        # Print summary
        if "base_loop" in skeletons:
            base_loop = skeletons["base_loop"]
            steps = base_loop.get("steps", [])
            print(f"\n📊 Base Loop Skeleton Summary:")
            print(f"   - Total steps: {len(steps)}")
            
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
            
            # Print step count breakdown
            print(f"\n📋 Step Breakdown (first 5 steps):")
            for i, step in enumerate(steps[:5]):
                pos_actions = step.get("pos_actions", {})
                timestamp = step.get("timestamp", "N/A")
                events = step.get("events", [])
                is_final = step.get("is_final_step", False)
                print(f"   Step {i}: {len(pos_actions)} player actions, timestamp={timestamp}, events={len(events)}, is_final={is_final}")
            if len(steps) > 5:
                print(f"   ... ({len(steps) - 5} more steps)")
        
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
    pull_3_2_motion_skeleton()
