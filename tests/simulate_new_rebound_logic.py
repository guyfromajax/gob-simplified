"""
Simulate 20 rebound instances with NEW rebound logic.

Settings:
- Offense team rebounding = 2 (75% chance one player gets back)
- Defense team tempo = 2 (50% chance one player releases for fast break)

Teams:
- Offense: Bentley-Truman
- Defense: Lancaster
"""
import random

# Player attributes from team JSON files
# Offense: Little York
offense_players = {
    "PG": {"name": "Smith", "RB": 29, "ST": 10, "IQ": 98},
    "SG": {"name": "Buford", "RB": 63, "ST": 36, "IQ": 75},
    "SF": {"name": "Largefoot", "RB": 46, "ST": 66, "IQ": 61},
    "PF": {"name": "Farrabee", "RB": 89, "ST": 85, "IQ": 82},
    "C": {"name": "Landraneau", "RB": 88, "ST": 89, "IQ": 20}
}

# Defense: South Lancaster
defense_players = {
    "PG": {"name": "F. Steele", "RB": 26, "ST": 25, "IQ": 94},
    "SG": {"name": "F. Steele", "RB": 25, "ST": 44, "IQ": 74},
    "SF": {"name": "Crawford", "RB": 40, "ST": 31, "IQ": 40},
    "PF": {"name": "Celaya", "RB": 46, "ST": 90, "IQ": 45},
    "C": {"name": "Baldwin", "RB": 87, "ST": 65, "IQ": 90}
}

# Settings will be randomized per simulation
# (Moved to simulate_rebound function)


def calculate_rebound_score(player):
    """Calculate player rebound score with die roll."""
    attr = player
    base_score = attr["RB"] * 0.5 + attr["ST"] * 0.3 + attr["IQ"] * 0.2
    die_roll = random.randint(1, 6)
    return base_score * die_roll


def determine_players_involved(shooter_pos, offense_rebounding, defense_tempo):
    """Determine which players are involved in rebound vs getting back/releasing."""
    
    # Defense: Determine if one player releases for fast break (based on TEMPO)
    defense_release_chances = {
        0: 0.0,   # 100% all stay
        1: 0.25,  # 25% one releases
        2: 0.5,   # 50% one releases
        3: 0.75,  # 75% one releases
        4: 1.0    # 100% one releases
    }
    
    release_chance = defense_release_chances[defense_tempo]
    defense_releases = random.random() < release_chance
    
    # Determine which defender releases (PG unless PG is guarding shooter, then SG)
    release_pos = "PG" if shooter_pos != "PG" else "SG"
    
    if defense_releases:
        defense_rebounders = [pos for pos in defense_players.keys() if pos != release_pos]
    else:
        defense_rebounders = list(defense_players.keys())
    
    # Offense: Determine if players get back on defense (based on REBOUNDING)
    offense_getback_chances = {
        0: {"none": 1.0, "one": 0.0, "two": 0.0},     # 100% all crash
        1: {"none": 0.5, "one": 0.5, "two": 0.0},     # 50% all crash / 50% one gets back
        2: {"none": 0.25, "one": 0.75, "two": 0.0},   # 25% all crash / 75% one gets back
        3: {"none": 0.1, "one": 0.8, "two": 0.1},     # 10% all / 80% one / 10% two
        4: {"none": 0.0, "one": 0.5, "two": 0.5}      # 50% one / 50% two
    }
    
    chances = offense_getback_chances[offense_rebounding]
    rand = random.random()
    
    if rand < chances["none"]:
        num_getback = 0
    elif rand < chances["none"] + chances["one"]:
        num_getback = 1
    else:
        num_getback = 2
    
    # Determine which offensive players get back
    getback_positions = []
    if num_getback >= 1:
        # First player: PG (unless shooter), then SG
        if shooter_pos != "PG":
            getback_positions.append("PG")
        else:
            getback_positions.append("SG")
    
    if num_getback >= 2:
        # Second player: SG (unless shooter or already getting back), then SF
        if shooter_pos != "SG" and "SG" not in getback_positions:
            getback_positions.append("SG")
        else:
            getback_positions.append("SF")
    
    offense_rebounders = [pos for pos in offense_players.keys() if pos not in getback_positions]
    
    return {
        "offense_rebounders": offense_rebounders,
        "defense_rebounders": defense_rebounders,
        "offense_getback": getback_positions,
        "defense_release": [release_pos] if defense_releases else []
    }


def simulate_rebound(iteration, shooter_pos="SF", offense_rebounding=2, defense_tempo=2, off_mod=1.0, def_mod=1.0, verbose=True):
    """Simulate one rebound instance."""
    if verbose:
        print(f"\n{'='*80}")
        print(f"SIMULATION #{iteration} - Shooter: {shooter_pos}")
        print(f"Settings: Off Reb={offense_rebounding}, Def Tempo={defense_tempo}, Off Mod={off_mod}, Def Mod={def_mod}")
        print(f"{'='*80}")
    
    # Step 1: Determine players involved
    players = determine_players_involved(shooter_pos, offense_rebounding, defense_tempo)
    
    if verbose:
        print(f"\n📊 PLAYERS INVOLVED:")
        print(f"   Offense Rebounders ({len(players['offense_rebounders'])}): {players['offense_rebounders']}")
        print(f"   Offense Getting Back ({len(players['offense_getback'])}): {players['offense_getback']}")
        print(f"   Defense Rebounders ({len(players['defense_rebounders'])}): {players['defense_rebounders']}")
        print(f"   Defense Releasing ({len(players['defense_release'])}): {players['defense_release']}")
    
    # Step 2: Calculate base def_prob with player advantage
    def_prob = 0.7
    player_advantage = len(players['defense_rebounders']) - len(players['offense_rebounders'])
    def_prob += (player_advantage * 0.05)
    
    if verbose:
        print(f"\n🎲 BASE CALCULATION:")
        print(f"   Starting def_prob: 0.7")
        print(f"   Player advantage: {player_advantage:+d} ({len(players['defense_rebounders'])} D vs {len(players['offense_rebounders'])} O)")
        print(f"   Adjusted def_prob: {def_prob:.2f}")
    
    # Step 3: Calculate rebound scores for all players
    if verbose:
        print(f"\n💪 REBOUND SCORES:")
    
    o_scores = {}
    for pos in players['offense_rebounders']:
        player = offense_players[pos]
        score = calculate_rebound_score(player)
        o_scores[pos] = score
        if verbose:
            print(f"   [O] {pos:2s} {player['name']:12s}: RB={player['RB']:2d} ST={player['ST']:3d} IQ={player['IQ']:3d} → Score={score:.1f}")
    
    d_scores = {}
    for pos in players['defense_rebounders']:
        player = defense_players[pos]
        score = calculate_rebound_score(player)
        d_scores[pos] = score
        if verbose:
            print(f"   [D] {pos:2s} {player['name']:12s}: RB={player['RB']:2d} ST={player['ST']:3d} IQ={player['IQ']:3d} → Score={score:.1f}")
    
    # Step 4: Pick best rebounders from each side
    if not o_scores:
        if verbose:
            print(f"\n   ⚠️ No offensive rebounders (all got back) - AUTO DREB")
        return {"result": "DREB", "d_weight": 1.0, "players": players}
    
    if not d_scores:
        if verbose:
            print(f"\n   ⚠️ No defensive rebounders (all released) - AUTO OREB")
        return {"result": "OREB", "d_weight": 0.0, "players": players}
    
    o_best_pos = max(o_scores, key=o_scores.get)
    d_best_pos = max(d_scores, key=d_scores.get)
    
    o_rebounder_score = o_scores[o_best_pos]
    d_rebounder_score = d_scores[d_best_pos]
    
    if verbose:
        print(f"\n🏆 BEST REBOUNDERS:")
        print(f"   Offense: {o_best_pos} {offense_players[o_best_pos]['name']} (Score: {o_rebounder_score:.1f})")
        print(f"   Defense: {d_best_pos} {defense_players[d_best_pos]['name']} (Score: {d_rebounder_score:.1f})")
    
    # Step 5: Apply team bias
    bias = def_mod - off_mod
    new_prob = min(0.95, max(0.35, def_prob + bias))
    
    if verbose:
        print(f"\n⚖️ TEAM BIAS:")
        print(f"   Def Mod: {def_mod}, Off Mod: {off_mod}")
        print(f"   Bias: {bias:+.1f}")
        print(f"   New Prob: {new_prob:.2f} (def_prob {def_prob:.2f} + bias {bias:+.1f}, capped 0.35-0.95)")
    
    # Step 6: Calculate final weights
    total_score = d_rebounder_score + o_rebounder_score
    d_weight = d_rebounder_score / total_score if total_score > 0 else 0.5
    d_weight += (new_prob - 0.5)  # OPTION A: Changed from -0.3 to -0.5
    d_weight = min(0.95, d_weight)
    
    if verbose:
        print(f"\n📐 FINAL WEIGHT CALCULATION:")
        print(f"   Total Score: {total_score:.1f}")
        print(f"   D_weight (from scores): {d_rebounder_score / total_score:.2f}")
        print(f"   D_weight (after bias): {d_weight:.2f} (added {new_prob - 0.5:+.2f})")
    
    # Step 7: Zone penalty (assume Man defense for this simulation)
    defense_call = "Man"  # Can change this
    if defense_call == "Zone":
        d_weight *= 0.9
        if verbose:
            print(f"   D_weight (after zone penalty): {d_weight:.2f}")
    
    # Step 8: Determine winner
    roll = random.random()
    is_dreb = roll < d_weight
    
    if verbose:
        print(f"\n🎲 RESULT:")
        print(f"   Roll: {roll:.3f}")
        print(f"   D_weight: {d_weight:.3f}")
        print(f"   Result: {'DREB' if is_dreb else 'OREB'} ({'✓ Defense' if is_dreb else '✓ Offense'})")
    
    if is_dreb:
        rebounder = d_best_pos
        rebounder_name = defense_players[d_best_pos]['name']
        if verbose:
            print(f"   Rebounder: {rebounder} {rebounder_name} (Defense)")
        return {
            "result": "DREB",
            "d_weight": d_weight,
            "rebounder": rebounder,
            "players": players,
            "roll": roll
        }
    else:
        rebounder = o_best_pos
        rebounder_name = offense_players[o_best_pos]['name']
        if verbose:
            print(f"   Rebounder: {rebounder} {rebounder_name} (Offense)")
        return {
            "result": "OREB",
            "d_weight": d_weight,
            "rebounder": rebounder,
            "players": players,
            "roll": roll
        }


def run_simulations():
    """Run 100 rebound simulations with randomized parameters."""
    print("\n" + "="*80)
    print("REBOUND SIMULATION - NEW LOGIC (100 ITERATIONS)")
    print("="*80)
    print(f"Teams: Little York (O) vs South Lancaster (D)")
    print(f"Randomized Parameters:")
    print(f"  - Offense Rebounding: 0-4 (random)")
    print(f"  - Defense Tempo: 0-4 (random)")
    print(f"  - Team Rebound Mods: [0.8, 0.9, 1.0, 1.1, 1.2] (random)")
    
    results = {"DREB": 0, "OREB": 0}
    d_weights = []
    lowest_d_weight = 1.0
    highest_d_weight = 0.0
    
    # Track results by scenario
    scenarios = {
        "5v5": {"DREB": 0, "OREB": 0},
        "5v4": {"DREB": 0, "OREB": 0},
        "4v5": {"DREB": 0, "OREB": 0},
        "4v4": {"DREB": 0, "OREB": 0},
        "3v5": {"DREB": 0, "OREB": 0},
        "5v3": {"DREB": 0, "OREB": 0}
    }
    
    # Vary shooter position for realism
    shooter_positions = ["SF", "PF", "C", "PG", "SG"] * 20  # 100 total
    
    for i in range(1, 101):
        # Randomize parameters
        offense_rebounding = random.randint(0, 4)
        defense_tempo = random.randint(0, 4)
        off_mod = random.choice([0.8, 0.9, 1.0, 1.1, 1.2])
        def_mod = random.choice([0.8, 0.9, 1.0, 1.1, 1.2])
        
        shooter_pos = shooter_positions[i-1]
        result_data = simulate_rebound(
            i, shooter_pos, 
            offense_rebounding=offense_rebounding,
            defense_tempo=defense_tempo,
            off_mod=off_mod,
            def_mod=def_mod,
            verbose=False  # Suppress individual simulation output
        )
        
        result_type = result_data["result"]
        d_weight = result_data["d_weight"]
        players = result_data["players"]
        
        results[result_type] += 1
        d_weights.append(d_weight)
        
        if d_weight < lowest_d_weight:
            lowest_d_weight = d_weight
        if d_weight > highest_d_weight:
            highest_d_weight = d_weight
        
        # Track by scenario (D rebounders vs O rebounders)
        num_d = len(players["defense_rebounders"])
        num_o = len(players["offense_rebounders"])
        scenario_key = f"{num_o}v{num_d}"
        if scenario_key in scenarios:
            scenarios[scenario_key][result_type] += 1
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY - 100 SIMULATIONS")
    print("="*80)
    print(f"\nOVERALL RESULTS:")
    print(f"  DREB: {results['DREB']} ({results['DREB']/100*100:.0f}%)")
    print(f"  OREB: {results['OREB']} ({results['OREB']/100*100:.0f}%)")
    
    print(f"\nD_WEIGHT STATISTICS:")
    print(f"  Average: {sum(d_weights)/len(d_weights):.3f}")
    print(f"  Lowest: {lowest_d_weight:.3f}")
    print(f"  Highest: {highest_d_weight:.3f}")
    
    print(f"\nRESULTS BY SCENARIO:")
    for scenario, counts in sorted(scenarios.items()):
        if counts["DREB"] + counts["OREB"] > 0:
            total = counts["DREB"] + counts["OREB"]
            dreb_pct = counts["DREB"] / total * 100
            print(f"  {scenario:4s} ({total:2d} games): DREB {counts['DREB']:2d} ({dreb_pct:4.0f}%), OREB {counts['OREB']:2d} ({100-dreb_pct:4.0f}%)")
    
    print(f"\nExpected DREB%: ~70-85% (varies by settings)")
    print("="*80)


if __name__ == "__main__":
    run_simulations()

