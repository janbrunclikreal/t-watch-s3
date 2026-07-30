import json


class StepDatabase:
    def __init__(self, path, logger):
        self.path = path
        self.log = logger

    def load(self):
        try:
            with open(self.path, "r") as db_file:
                data = json.load(db_file)
                if isinstance(data, dict) and len(data) > 90:
                    sorted_keys = sorted(data.keys())
                    data = {key: data[key] for key in sorted_keys[-90:]}
                return data
        except (OSError, ValueError):
            return {}

    def save_day(self, date_str, step_count):
        data = self.load()
        data[date_str] = step_count
        try:
            with open(self.path, "w") as db_file:
                json.dump(data, db_file)
                db_file.flush()
            self.log(f"[DB] Uloženo na Flash: {date_str} -> {step_count} kroků")
        except OSError as err:
            if getattr(err, "errno", None) == 38:
                self.log("[DB] Připojeno k PC (Read-Only). Zápis přeskakuji.")
            else:
                self.log(f"[DB-ERR] Chyba zápisu: {err}")
