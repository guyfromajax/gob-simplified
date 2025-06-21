class Logger:
    def __init__(self):
        self.events = []
        self.turn_results = []

    def log(self, message: str):
        self.events.append(message)

    def log_turn_result(self, result: dict):
        self.turn_results.append(result)

    def get_game_log(self):
        return self.events

    def get_turn_logs(self):
        return self.turn_results

    def reset(self):
        self.events.clear()
        self.turn_results.clear()