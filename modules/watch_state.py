import time


class WatchState:
    STATE_WATCHFACE = "WATCHFACE"
    STATE_MENU = "MENU"
    STATE_MOBLIN = "MOBLIN"
    STATE_HWTEST = "HWTEST"
    STATE_NOTIF = "NOTIF"

    def __init__(self, sleep_timeout_sec=10):
        now = time.monotonic()
        self.last_activity = now
        self.display_awake = True
        self.sleep_timeout_sec = sleep_timeout_sec
        self.wifi_sync_in_progress = False
        self.time_synchronized = False
        self.steps_today = 0
        self.last_date_str = ""
        self.ble_adv_start_time = now
        self.ble_pause_advertising = False
        self.last_magnitude = 1.0
        self.last_step_time = 0
        self.last_step_milestone = 0
        self.current_state = self.STATE_WATCHFACE

    def note_activity(self):
        self.last_activity = time.monotonic()

    def refresh_ble_advertising(self):
        self.ble_pause_advertising = False
        self.ble_adv_start_time = time.monotonic()

    def register_activity(self):
        self.note_activity()
        self.refresh_ble_advertising()

    def set_state(self, new_state):
        self.current_state = new_state
