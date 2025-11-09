"""
Test that benched players don't appear in Q2 player data.

When a user changes their lineup between quarters, the old benched
players should NOT appear in the players array with pos: null.
This causes the frontend to filter them out, breaking sprite loading.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.main import simulate_quarter
from BackEnd.models.game_manager import GameManager
from BackEnd.utils.shared import summarize_game_state


def test_lineup_change_no_benched_players():
    """Test that benched players don't appear in saved game state."""
    print("\n" + "="*80)
    print("TEST: Lineup Change - No Benched Players in Q2")
    print("="*80)
    
    # Create a new game
    print("\n1. Creating GameManager...")
    gm = GameManager("Bentley-Truman", "Morristown", mode="single")
    game_id = "test_lineup_change_123"
    gm.game_id = game_id
    
    # Capture Q1 starting lineup
    q1_lineup_ids = {pos: player.player_id for pos, player in gm.home_team.lineup.items()}
    print(f"\n   Q1 Lineup Player IDs:")
    for pos, player_id in q1_lineup_ids.items():
        player = gm.home_team.lineup[pos]
        print(f"     {pos}: {player.name} ({player_id})")
    
    # Simulate Q1 (full simulation to get real data)
    print("\n2. Simulating Quarter 1...")
    simulate_quarter(gm, turn_by_turn_mode=False)
    
    print(f"   ✅ Q1 completed")
    
    # Save game state (this is what gets sent to DB and loaded by frontend)
    print("\n3. Saving game state (exclude_animations=True, as in turn-by-turn mode)...")
    saved_state = summarize_game_state(gm, exclude_animations=True)
    
    # Check players in saved state
    saved_players = saved_state.get('players', [])
    print(f"   ✅ Saved state includes {len(saved_players)} players")
    
    # List Q1 players
    q1_player_ids = set(q1_lineup_ids.values())
    print(f"\n   Q1 Players in saved state:")
    for player in saved_players:
        player_id = player.get('playerId')
        name = player.get('name')
        pos = player.get('pos')
        team = player.get('team')
        
        if team == 'home':
            in_q1_lineup = "✓" if player_id in q1_player_ids else "❌ BENCHED"
            print(f"     {name} ({player_id}) - pos: {pos} {in_q1_lineup}")
    
    # Verify no players have pos: null
    benched_players = [p for p in saved_players if p.get('pos') is None and p.get('team') == 'home']
    
    if benched_players:
        print(f"\n   ❌ ERROR: {len(benched_players)} home players with pos: null found!")
        for p in benched_players:
            print(f"      - {p.get('name')} ({p.get('playerId')})")
    else:
        print(f"\n   ✅ No home players with pos: null (correct!)")
    
    # Now simulate a lineup change for Q2
    print("\n4. Simulating lineup change for Q2 (user changes roster)...")
    
    # In the real game, user can select ANY player from the team roster
    # For this test, we'll manually create 2 "new" players to simulate bench players
    # coming in (this mimics what happens when user changes lineup between quarters)
    
    from BackEnd.models.player import Player
    
    # Create 2 "bench" players
    new_pg = Player("New PG Test", "PG")
    new_pg.player_id = "bench_pg_test_id"
    new_pg.jersey = "99"
    new_pg.attributes = {"NG": 1.0}
    new_pg.stats = {"game": {}}
    
    new_c = Player("New C Test", "C")
    new_c.player_id = "bench_c_test_id"
    new_c.jersey = "98"
    new_c.attributes = {"NG": 1.0}
    new_c.stats = {"game": {}}
    
    print(f"   Simulating 2 bench players coming in for Q2...")
    
    if True:  # Always run this test
        # Change 2 positions (simulate user making lineup changes)
        # Bench the PG and C, bring in 2 bench players
        old_pg = gm.home_team.lineup['PG']
        old_c = gm.home_team.lineup['C']
        
        new_pg = bench_players[0]
        new_c = bench_players[1] if len(bench_players) > 1 else bench_players[0]
        
        # Update lineup
        gm.home_team.lineup['PG'] = new_pg
        gm.home_team.lineup['C'] = new_c
        
        print(f"\n   Lineup changes:")
        print(f"     PG: {old_pg.name} → {new_pg.name}")
        print(f"     C: {old_c.name} → {new_c.name}")
        
        # Capture Q2 lineup
        q2_lineup_ids = {pos: player.player_id for pos, player in gm.home_team.lineup.items()}
        
        # Save game state AGAIN with new lineup
        print("\n5. Saving game state with Q2 lineup...")
        saved_state_q2 = summarize_game_state(gm, exclude_animations=True)
        
        saved_players_q2 = saved_state_q2.get('players', [])
        print(f"   ✅ Q2 saved state includes {len(saved_players_q2)} players")
        
        # List Q2 players
        q2_player_ids = set(q2_lineup_ids.values())
        print(f"\n   Q2 Players in saved state:")
        for player in saved_players_q2:
            player_id = player.get('playerId')
            name = player.get('name')
            pos = player.get('pos')
            team = player.get('team')
            
            if team == 'home':
                in_q2_lineup = "✓" if player_id in q2_player_ids else "❌ BENCHED"
                print(f"     {name} ({player_id}) - pos: {pos} {in_q2_lineup}")
        
        # Verify no benched players in Q2 state
        benched_players_q2 = [p for p in saved_players_q2 if p.get('pos') is None and p.get('team') == 'home']
        
        print("\n6. Verifying Q2 state has no benched players...")
        
        errors = []
        
        if benched_players_q2:
            errors.append(f"❌ {len(benched_players_q2)} home players with pos: null in Q2 state")
            for p in benched_players_q2:
                errors.append(f"   - {p.get('name')} ({p.get('playerId')})")
        else:
            print(f"   ✅ No home players with pos: null in Q2 state")
        
        # Verify old PG and C are NOT in Q2 saved state
        old_pg_in_q2 = any(p.get('playerId') == old_pg.player_id for p in saved_players_q2 if p.get('team') == 'home')
        old_c_in_q2 = any(p.get('playerId') == old_c.player_id for p in saved_players_q2 if p.get('team') == 'home')
        
        if old_pg_in_q2:
            old_pg_data = next(p for p in saved_players_q2 if p.get('playerId') == old_pg.player_id and p.get('team') == 'home')
            if old_pg_data.get('pos') is None:
                errors.append(f"❌ Benched PG {old_pg.name} still in Q2 state with pos: null")
            else:
                errors.append(f"❌ Benched PG {old_pg.name} still in Q2 state with pos: {old_pg_data.get('pos')}")
        else:
            print(f"   ✅ Benched PG {old_pg.name} NOT in Q2 state (correct!)")
        
        if old_c_in_q2:
            old_c_data = next(p for p in saved_players_q2 if p.get('playerId') == old_c.player_id and p.get('team') == 'home')
            if old_c_data.get('pos') is None:
                errors.append(f"❌ Benched C {old_c.name} still in Q2 state with pos: null")
            else:
                errors.append(f"❌ Benched C {old_c.name} still in Q2 state with pos: {old_c_data.get('pos')}")
        else:
            print(f"   ✅ Benched C {old_c.name} NOT in Q2 state (correct!)")
        
        # Verify new PG and C ARE in Q2 saved state
        new_pg_in_q2 = any(p.get('playerId') == new_pg.player_id for p in saved_players_q2 if p.get('team') == 'home')
        new_c_in_q2 = any(p.get('playerId') == new_c.player_id for p in saved_players_q2 if p.get('team') == 'home')
        
        if not new_pg_in_q2:
            errors.append(f"❌ New PG {new_pg.name} NOT in Q2 state")
        else:
            print(f"   ✅ New PG {new_pg.name} in Q2 state")
        
        if not new_c_in_q2:
            errors.append(f"❌ New C {new_c.name} NOT in Q2 state")
        else:
            print(f"   ✅ New C {new_c.name} in Q2 state")
        
        # Print results
        print("\n" + "="*80)
        if errors:
            print("❌ TEST FAILED")
            print("="*80)
            for error in errors:
                print(f"   {error}")
            return False
        else:
            print("✅ TEST PASSED - Lineup change handled correctly!")
            print("="*80)
            return True


if __name__ == "__main__":
    print("\n🧪 Running Lineup Change Sprite Test...\n")
    
    passed = test_lineup_change_no_benched_players()
    
    if passed:
        print("\n🎉 TEST PASSED!")
        sys.exit(0)
    else:
        print("\n💥 TEST FAILED - This is the bug causing sprite animation issues!")
        sys.exit(1)

