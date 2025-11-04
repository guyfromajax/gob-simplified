"""
Verify that all universal plays have all 4 variants built.
Shows which variants are complete and which are missing/empty.
"""

from BackEnd.db import plays_collection

def verify_play_variants():
    """Check all plays for variant completeness"""
    
    plays = list(plays_collection.find({}))
    print(f"📊 Checking {len(plays)} plays for variant completeness\n")
    print("=" * 80)
    
    all_complete = True
    total_variants = 0
    complete_variants = 0
    
    for play in plays:
        play_name = play.get("name", "Unknown")
        skeletons = play.get("skeletons", {})
        
        print(f"\n🎮 {play_name}")
        print("-" * 80)
        
        variants = ['successful', 'mid_play_change', 'contested', 'broken']
        
        for variant in variants:
            total_variants += 1
            variant_data = skeletons.get(variant, {})
            steps = variant_data.get("steps", [])
            is_complete = variant_data.get("complete", False)
            
            # Check if variant has steps
            if len(steps) > 0:
                complete_variants += 1
                status = "✅" if is_complete else "🟡"
                status_text = "Complete" if is_complete else "In Progress"
                print(f"  {status} {variant:20s} | {len(steps):2d} steps | {status_text}")
            else:
                all_complete = False
                print(f"  ❌ {variant:20s} | Empty (no steps)")
    
    print("\n" + "=" * 80)
    print(f"\n📈 Summary:")
    print(f"  Total plays: {len(plays)}")
    print(f"  Total variants: {total_variants}")
    print(f"  Variants with steps: {complete_variants}/{total_variants} ({complete_variants/total_variants*100:.1f}%)")
    print(f"  Empty variants: {total_variants - complete_variants}")
    
    if all_complete:
        print(f"\n🎉 All variants are built! Ready for gameplay!")
    else:
        print(f"\n⚠️  Some variants are still empty. Continue building!")
    
    # Show breakdown by variant type
    print(f"\n📊 Breakdown by Variant Type:")
    for variant in variants:
        count = sum(1 for play in plays if play.get("skeletons", {}).get(variant, {}).get("steps", []))
        print(f"  {variant:20s}: {count}/{len(plays)} plays built")

if __name__ == "__main__":
    verify_play_variants()

