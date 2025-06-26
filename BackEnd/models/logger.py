class Logger:
    def __init__(self):
        self.events = []
        self.turn_results = []
        self.summary_data = {}
        self.metadata = {}


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

    def log_summary(self, summary_dict: dict):
        self.summary_data = summary_dict

    def log_metadata(self, key: str, value):
        self.metadata[key] = value

    def get_summary(self):
        return self.summary_data

    def get_metadata(self):
        return self.metadata
    
    def reset(self):
        self.events.clear()
        self.turn_results.clear()
        self.summary_data = {}
        self.metadata = {}

    def export_all_logs(self):
        return {
            "events": self.events,
            "turns": self.turn_results,
            "summary": self.summary_data,
            "metadata": self.metadata
        }



