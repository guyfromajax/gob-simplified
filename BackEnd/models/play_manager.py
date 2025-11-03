"""
Play Manager - Encapsulates offensive play logic with tempo-specific skeletons.

A Play represents a complete offensive sequence (e.g., "Pick and Roll", "High-Low Entry")
with variations for different tempo settings (slow/normal/fast).
"""

class Play:
    """
    Represents a single offensive play with animation skeletons.
    
    Attributes:
        name (str): Display name of the play (e.g., "Pick and Roll")
        play_type (str): Play category - "motion" or "set_play"
        play_focus (str): Play focus - "inside", "attack", "outside", "balanced"
        skeletons (dict): Animation skeletons - "successful", "mid_play_change", "contested", "broken"
        game_stats (dict): Per-game statistics
        season_stats (dict): Cross-game statistics (franchise/tournament mode)
    """
    
    def __init__(self, name, play_type, play_focus="balanced", skeletons=None):
        """
        Initialize a Play object.
        
        Args:
            name (str): Play name (e.g., "Pick and Roll")
            play_type (str): One of ["motion", "set_play"]
            play_focus (str): One of ["inside", "attack", "outside", "balanced"]
            skeletons (dict, optional): Pre-defined skeletons
                Expected structure: {"standard": {...}} (expandable in future)
        """
        self.name = name
        self.play_type = play_type
        self.play_focus = play_focus
        
        # Initialize skeletons dict
        if skeletons:
            self.skeletons = skeletons
        else:
            # Empty skeletons - will be populated later
            self.skeletons = {
                "successful": None,
                "mid_play_change": None,
                "contested": None,
                "broken": None
            }
        
        # Game-level stats (reset at start of each game)
        self.game_stats = {
            "times_run": 0,
            "shot_attempts": 0,
            "made_shots": 0,
            "turnovers": 0,
            "offensive_fouls": 0,
            "defensive_fouls": 0
        }
        
        # Season/Tournament stats (persist across games)
        self.season_stats = {
            "times_run": 0,
            "shot_attempts": 0,
            "made_shots": 0,
            "turnovers": 0,
            "offensive_fouls": 0,
            "defensive_fouls": 0
        }
    
    def get_skeleton(self, variant="successful"):
        """
        Get the appropriate skeleton based on variant.
        
        Args:
            variant (str): Skeleton variant - "successful", "mid_play_change", "contested", or "broken"
            
        Returns:
            dict: The skeleton with steps, or None if not defined
        """
        return self.skeletons.get(variant) or self.skeletons.get("successful")
    
    def record_execution(self, result_type, season_mode=False):
        """
        Record that this play was run and track the outcome.
        
        Args:
            result_type (str): The result of the play - "SHOT", "MAKE", "MISS", 
                              "O_FOUL", "D_FOUL", "TURNOVER", etc.
            season_mode (bool): If True, also update season_stats
        """
        # Update game stats
        self.game_stats["times_run"] += 1
        
        if result_type in ["SHOT", "MAKE", "MISS"]:
            self.game_stats["shot_attempts"] += 1
        if result_type == "MAKE":
            self.game_stats["made_shots"] += 1
        elif result_type in ["TURNOVER", "DEAD BALL"]:
            self.game_stats["turnovers"] += 1
        elif result_type == "O_FOUL":
            self.game_stats["offensive_fouls"] += 1
        elif result_type == "D_FOUL":
            self.game_stats["defensive_fouls"] += 1
        
        # Update season stats if applicable
        if season_mode:
            self.season_stats["times_run"] += 1
            if result_type in ["SHOT", "MAKE", "MISS"]:
                self.season_stats["shot_attempts"] += 1
            if result_type == "MAKE":
                self.season_stats["made_shots"] += 1
            elif result_type in ["TURNOVER", "DEAD BALL"]:
                self.season_stats["turnovers"] += 1
            elif result_type == "O_FOUL":
                self.season_stats["offensive_fouls"] += 1
            elif result_type == "D_FOUL":
                self.season_stats["defensive_fouls"] += 1
    
    def get_success_rate(self, season_mode=False):
        """
        Calculate success rate (made shots / shot attempts).
        
        Args:
            season_mode (bool): If True, use season_stats; otherwise use game_stats
            
        Returns:
            float: Success rate (0.0 - 1.0), or 0.0 if no attempts
        """
        stats = self.season_stats if season_mode else self.game_stats
        attempts = stats["shot_attempts"]
        if attempts == 0:
            return 0.0
        return stats["made_shots"] / attempts
    
    def reset_game_stats(self):
        """Reset game-level stats at the start of a new game."""
        self.game_stats = {
            "times_run": 0,
            "shot_attempts": 0,
            "made_shots": 0,
            "turnovers": 0,
            "offensive_fouls": 0,
            "defensive_fouls": 0
        }
    
    def to_dict(self):
        """
        Serialize Play to dictionary (for saving to JSON/MongoDB).
        
        Returns:
            dict: Complete play data including skeletons and stats
        """
        return {
            "name": self.name,
            "play_type": self.play_type,
            "play_focus": self.play_focus,
            "skeletons": self.skeletons,
            "game_stats": self.game_stats,
            "season_stats": self.season_stats
        }
    
    @classmethod
    def from_dict(cls, data):
        """
        Create Play instance from dictionary data.
        
        Args:
            data (dict): Play data with name, play_type, play_focus, skeletons, stats
            
        Returns:
            Play: Initialized Play instance
        """
        play = cls(
            name=data.get("name", "Unnamed Play"),
            play_type=data.get("play_type", "motion"),
            play_focus=data.get("play_focus", "balanced"),
            skeletons=data.get("skeletons")
        )
        
        # Restore stats if present
        if "game_stats" in data:
            play.game_stats = data["game_stats"]
        if "season_stats" in data:
            play.season_stats = data["season_stats"]
        
        return play
    
    def __repr__(self):
        return f"Play(name='{self.name}', type='{self.play_type}', focus='{self.play_focus}', game_runs={self.game_stats['times_run']})"


class PlayManager:
    """
    Manages a collection of offensive plays for a team.
    Handles play selection, stat tracking, and skeleton retrieval.
    """
    
    def __init__(self, plays=None):
        """
        Initialize PlayManager with a collection of plays.
        
        Args:
            plays (list[Play], optional): List of Play objects
        """
        self.plays = plays or []
        self.plays_by_name = {}
        self.plays_by_type = {
            "Inside": [],
            "Attack": [],
            "Outside": [],
            "Base": [],
            "Set": [],
            "Freelance": []
        }
        
        # Index plays for efficient lookup
        self._index_plays()
    
    def _index_plays(self):
        """Build lookup indices for plays by name and type."""
        self.plays_by_name = {}
        self.plays_by_type = {
            "motion": [],
            "set_play": []
        }
        self.plays_by_focus = {
            "inside": [],
            "attack": [],
            "outside": [],
            "balanced": []
        }
        
        for play in self.plays:
            self.plays_by_name[play.name] = play
            if play.play_type in self.plays_by_type:
                self.plays_by_type[play.play_type].append(play)
            if play.play_focus in self.plays_by_focus:
                self.plays_by_focus[play.play_focus].append(play)
    
    def add_play(self, play):
        """
        Add a play to the manager.
        
        Args:
            play (Play): Play object to add
        """
        self.plays.append(play)
        self._index_plays()
    
    def get_play_by_name(self, name):
        """
        Get a play by its name.
        
        Args:
            name (str): Play name
            
        Returns:
            Play or None: The play object, or None if not found
        """
        return self.plays_by_name.get(name)
    
    def get_plays_by_type(self, play_type):
        """
        Get all plays of a specific type.
        
        Args:
            play_type (str): One of ["motion", "set_play"]
            
        Returns:
            list[Play]: List of plays of that type
        """
        return self.plays_by_type.get(play_type, [])
    
    def get_plays_by_focus(self, play_focus):
        """
        Get all plays of a specific focus.
        
        Args:
            play_focus (str): One of ["inside", "attack", "outside", "balanced"]
            
        Returns:
            list[Play]: List of plays matching the focus
        """
        return self.plays_by_focus.get(play_focus, [])
    
    def select_play(self, play_type):
        """
        Select a random play from the specified type.
        
        Args:
            play_type (str): Play type to select from
            
        Returns:
            Play or None: Randomly selected play, or None if no plays of that type
        """
        import random
        plays = self.get_plays_by_type(play_type)
        if not plays:
            return None
        return random.choice(plays)
    
    def reset_all_game_stats(self):
        """Reset game stats for all plays (call at start of new game)."""
        for play in self.plays:
            play.reset_game_stats()
    
    def get_season_leaders(self, metric="made_shots", limit=10):
        """
        Get top plays by a specific season metric.
        
        Args:
            metric (str): Stat to rank by ("made_shots", "times_run", etc.)
            limit (int): Number of plays to return
            
        Returns:
            list[tuple]: List of (Play, stat_value) tuples, sorted descending
        """
        play_stats = [(play, play.season_stats.get(metric, 0)) for play in self.plays]
        play_stats.sort(key=lambda x: x[1], reverse=True)
        return play_stats[:limit]
    
    def to_dict(self):
        """
        Serialize all plays to dictionary.
        
        Returns:
            dict: Complete playbook data
        """
        return {
            "plays": [play.to_dict() for play in self.plays]
        }
    
    @classmethod
    def from_dict(cls, data):
        """
        Create PlayManager from dictionary data.
        
        Args:
            data (dict): Playbook data with plays array
            
        Returns:
            PlayManager: Initialized manager with all plays
        """
        plays = [Play.from_dict(p) for p in data.get("plays", [])]
        return cls(plays=plays)


def create_play_from_existing_skeleton(name, play_type, normal_skeleton):
    """
    Helper function to create a Play from an existing skeleton.
    Auto-generates slow/fast variants based on the normal skeleton.
    
    Args:
        name (str): Play name
        play_type (str): Play type
        normal_skeleton (dict): Existing skeleton (will be used as "normal" tempo)
        
    Returns:
        Play: New Play object with all three tempo variants
    """
    import copy
    
    # Use existing skeleton as normal tempo
    skeletons = {"normal": normal_skeleton}
    
    # Generate slow variant (add time, potentially add steps)
    # For now, just scale timestamps by 1.5x
    slow_skeleton = copy.deepcopy(normal_skeleton)
    for step in slow_skeleton.get("steps", []):
        step["timestamp"] = int(step["timestamp"] * 1.5)
    skeletons["slow"] = slow_skeleton
    
    # Generate fast variant (reduce time, potentially remove steps)
    # For now, just scale timestamps by 0.7x
    fast_skeleton = copy.deepcopy(normal_skeleton)
    for step in fast_skeleton.get("steps", []):
        step["timestamp"] = int(step["timestamp"] * 0.7)
    skeletons["fast"] = fast_skeleton
    
    return Play(name, play_type, skeletons)

