"""
Debug script to inspect a specific play's skeleton
"""

from BackEnd.db import plays_collection
import json

def debug_play_skeleton(play_name, variant="mid_play_change"):
    """Print skeleton details for debugging"""
    
    play = plays_collection.find_one({"name": play_name})
    
    if not play:
        print(f"❌ Play '{play_name}' not found")
        return
    
    print(f"🎮 Play: {play_name}")
    print(f"📋 Variant: {variant}")
    print("=" * 80)
    
    skeletons = play.get("skeletons", {})
    skeleton = skeletons.get(variant, {})
    steps = skeleton.get("steps", [])
    
    if not steps:
        print(f"❌ No steps in {variant} variant")
        return
    
    print(f"\n✅ Found {len(steps)} steps\n")
    
    for i, step in enumerate(steps, 1):
        print(f"Step {i} (timestamp: {step.get('timestamp', 0)}):")
        print("-" * 40)
        
        pos_actions = step.get("pos_actions", {})
        
        # Track who has the ball
        passers = []
        receivers = []
        shooters = []
        ball_handlers = []
        
        for pos, action_info in pos_actions.items():
            action = action_info.get("action", "")
            location = action_info.get("location", "")
            
            print(f"  {pos:3s}: {action:15s} @ {location}")
            
            if action == "pass":
                passers.append(pos)
            elif action == "receive":
                receivers.append(pos)
            elif action == "shoot":
                shooters.append(pos)
            elif action == "handle_ball":
                ball_handlers.append(pos)
        
        # Check for issues
        issues = []
        if len(passers) > 1:
            issues.append(f"⚠️ Multiple passers: {passers}")
        if len(passers) == 1 and len(receivers) == 0:
            issues.append(f"⚠️ Pass without receiver! Passer: {passers[0]}")
        if len(receivers) > 1:
            issues.append(f"⚠️ Multiple receivers: {receivers}")
        if len(shooters) > 1:
            issues.append(f"⚠️ Multiple shooters: {shooters}")
        
        if issues:
            for issue in issues:
                print(f"  {issue}")
        
        print()

if __name__ == "__main__":
    # Check all variants of 3-2 Motion
    play_name = "3-2 Motion"
    
    print("\n" + "=" * 80)
    print(f"Checking all variants of '{play_name}'")
    print("=" * 80)
    
    for variant in ["successful", "mid_play_change", "contested", "broken"]:
        print("\n")
        debug_play_skeleton(play_name, variant)
        print("\n" + "=" * 80)

