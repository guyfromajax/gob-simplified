class AnimationManager:
    def __init__(self):
        self.step_counter = 0
        self.step_limit = 8  # or whatever constant you've set

    def reset_step_counter(self):
        self.step_counter = 0

    def increment_step_counter(self):
        self.step_counter += 1

    def movement_needed(self, start_coords, end_coords):
        """
        Calculates if any movement is needed.
        """
        return start_coords != end_coords

    def generate_movement_steps(self, player_coords, destination_coords):
        """
        Generate animation steps using sixMovement() logic.
        """
        path = []
        current = player_coords.copy()
        while self.step_counter < self.step_limit and current != destination_coords:
            dx = destination_coords["x"] - current["x"]
            dy = destination_coords["y"] - current["y"]

            step_x = max(-6, min(6, dx))
            remaining = 8 - abs(step_x)
            step_y = max(-remaining, min(remaining, dy))

            current["x"] += step_x
            current["y"] += step_y
            path.append({"x": current["x"], "y": current["y"]})
            self.increment_step_counter()

        return path


    def build_animation_for_turn(self, start_coords_dict, end_coords_dict):
        """
        Build a dict of player animation steps keyed by position.
        """
        animations = {}
        self.reset_step_counter()

        for pos in start_coords_dict:
            start = start_coords_dict[pos]
            end = end_coords_dict.get(pos, start)  # fallback to no movement

            if self.movement_needed(start, end):
                animations[pos] = self.generate_movement_steps(start, end)
            else:
                animations[pos] = [start] * self.step_limit  # stationary hold

        return animations

    def capture(self, result):
        start_coords = result.get("start_coords", {})
        end_coords = result.get("end_coords", {})
        result["animations"] = self.build_animation_for_turn(start_coords, end_coords)
