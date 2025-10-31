from BackEnd.db import teams_collection

# Note: Team attributes (shot_threshold, etc.) are now MALLEABLE per game instance
# They should NOT be stored in the universal teams collection.
# This script only handles BASE attributes (colors, mascot, etc.)

BASE_ATTRS = {
    # Only base attributes that don't change per game instance
    # Colors, mascot, etc. - but NOT malleable attributes like shot_threshold
}

def backfill_base_attributes():
    """Backfill only BASE team attributes (not malleable game-specific ones)."""
    # This script is kept for future base attribute backfilling if needed
    # Malleable attributes (shot_threshold, team_attributes, strategy_settings) 
    # should be generated per game instance and stored in game mode docs
    pass
