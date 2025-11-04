"""
Comprehensive validation of all play skeletons.

Checks:
1. One and only one ball handling action per step (handle_ball, pass, shoot, drive)
2. Every pass must have a receive
3. Every skeleton must end with a shoot in the final step
4. Shoot cannot be present in any steps except the final step
"""

from BackEnd.db import plays_collection

BALL_HANDLING_ACTIONS = ["handle_ball", "pass", "shoot", "drive"]

def validate_skeleton(play_name, variant_name, steps):
    """Validate a single skeleton variant"""
    
    errors = []
    warnings = []
    
    if not steps:
        return ["❌ No steps in skeleton"], []
    
    # Check each step
    for i, step in enumerate(steps, 1):
        is_final_step = (i == len(steps))
        pos_actions = step.get("pos_actions", {})
        
        # Track actions
        ball_handlers = []
        passers = []
        receivers = []
        shooters = []
        drivers = []
        
        for pos, action_info in pos_actions.items():
            action = action_info.get("action", "")
            
            if action == "handle_ball":
                ball_handlers.append(pos)
            elif action == "pass":
                passers.append(pos)
                ball_handlers.append(pos)
            elif action == "shoot":
                shooters.append(pos)
                ball_handlers.append(pos)
            elif action == "drive":
                drivers.append(pos)
                ball_handlers.append(pos)
            elif action == "receive":
                receivers.append(pos)
        
        # Rule 1: One and only one ball handling action per step
        if len(ball_handlers) == 0:
            errors.append(f"  Step {i}: ❌ No ball handler (need handle_ball, pass, shoot, or drive)")
        elif len(ball_handlers) > 1:
            errors.append(f"  Step {i}: ❌ Multiple ball handlers: {ball_handlers}")
        
        # Rule 2: Every pass must have a receive
        if len(passers) > 0:
            if len(passers) > 1:
                errors.append(f"  Step {i}: ❌ Multiple passers: {passers}")
            if len(receivers) == 0:
                errors.append(f"  Step {i}: ❌ Pass without receiver! Passer: {passers[0]}")
            elif len(receivers) > 1:
                errors.append(f"  Step {i}: ❌ Multiple receivers: {receivers}")
        
        # Rule 4: Shoot cannot be present except in final step
        if len(shooters) > 0:
            if not is_final_step:
                errors.append(f"  Step {i}: ❌ Shoot action in non-final step! Shooter: {shooters[0]}")
            if len(shooters) > 1:
                errors.append(f"  Step {i}: ❌ Multiple shooters: {shooters}")
        
        # Additional checks
        if len(drivers) > 1:
            errors.append(f"  Step {i}: ❌ Multiple drivers: {drivers}")
    
    # Rule 3: Skeleton must end with a shoot
    if steps:
        final_step = steps[-1]
        final_pos_actions = final_step.get("pos_actions", {})
        has_final_shoot = any(
            action_info.get("action") == "shoot" 
            for action_info in final_pos_actions.values()
        )
        if not has_final_shoot:
            errors.append(f"  Final Step: ❌ No shoot action in final step!")
    
    return errors, warnings


def validate_all_plays():
    """Validate all plays and all variants"""
    
    plays = list(plays_collection.find({}))
    print(f"🔍 Validating {len(plays)} plays × 4 variants = {len(plays) * 4} skeletons")
    print("=" * 80)
    
    total_errors = 0
    total_warnings = 0
    plays_with_errors = []
    
    for play in plays:
        play_name = play.get("name", "Unknown")
        skeletons = play.get("skeletons", {})
        
        play_has_errors = False
        
        for variant in ["successful", "mid_play_change", "contested", "broken"]:
            skeleton = skeletons.get(variant, {})
            steps = skeleton.get("steps", [])
            
            errors, warnings = validate_skeleton(play_name, variant, steps)
            
            if errors or warnings:
                if not play_has_errors:
                    print(f"\n🎮 {play_name}")
                    print("-" * 80)
                    play_has_errors = True
                
                print(f"\n📋 Variant: {variant} ({len(steps)} steps)")
                
                if errors:
                    for error in errors:
                        print(error)
                    total_errors += len(errors)
                
                if warnings:
                    for warning in warnings:
                        print(warning)
                    total_warnings += len(warnings)
        
        if play_has_errors:
            plays_with_errors.append(play_name)
            print()
    
    # Summary
    print("=" * 80)
    print(f"\n📊 Validation Summary:")
    print(f"  Total plays checked: {len(plays)}")
    print(f"  Total skeletons checked: {len(plays) * 4}")
    print(f"  Plays with errors: {len(plays_with_errors)}")
    print(f"  Total errors found: {total_errors}")
    print(f"  Total warnings found: {total_warnings}")
    
    if total_errors == 0:
        print(f"\n✅ All skeletons are valid! Ready for gameplay!")
    else:
        print(f"\n⚠️  Fix the errors above before testing gameplay")
        print(f"\n📝 Plays needing fixes:")
        for play_name in plays_with_errors:
            print(f"  - {play_name}")

if __name__ == "__main__":
    validate_all_plays()

