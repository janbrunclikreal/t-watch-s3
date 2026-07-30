import displayio
import terminalio
from adafruit_display_text import label


class WatchFaceUI:
    def __init__(self):
        self.group = displayio.Group()

        self.datum_label = label.Label(terminalio.FONT, text="01.01.", color=0xFFFFFF, x=5, y=15)
        self.status_label = label.Label(terminalio.FONT, text="W:off B:off", color=0x444444, x=55, y=15)
        self.bat_label = label.Label(terminalio.FONT, text="B:--% ", color=0xFF9600, x=160, y=15)
        self.cpu_label = label.Label(terminalio.FONT, text="C:00%", color=0x00D0FF, x=205, y=15)
        self.cas_label = label.Label(terminalio.FONT, text="00:00:00", color=0x03F830, scale=5, x=2, y=50)
        self.ntp_label = label.Label(terminalio.FONT, text="N: Off", color=0xFF9600, x=5, y=230)
        self.kroky_label = label.Label(terminalio.FONT, text="K: 0", color=0xFFD700, scale=1, x=60, y=230)
        self.ram_label = label.Label(terminalio.FONT, text="R: 0000k", color=0x00D0FF, x=130, y=230)
        self.mv_label = label.Label(terminalio.FONT, text="---- mV", color=0xFF4444, x=195, y=230)

        for item in (
            self.datum_label,
            self.status_label,
            self.bat_label,
            self.cpu_label,
            self.cas_label,
            self.ntp_label,
            self.kroky_label,
            self.ram_label,
            self.mv_label,
        ):
            self.group.append(item)

    def show_on(self, display):
        display.root_group = self.group

    def update_clock(self, rtc_time, cpu_pct):
        self.cas_label.text = f"{rtc_time.tm_hour:02d}:{rtc_time.tm_min:02d}:{rtc_time.tm_sec:02d}"
        self.datum_label.text = f"{rtc_time.tm_mday:02d}.{rtc_time.tm_mon:02d}."
        self.cpu_label.text = f"C:{cpu_pct:02d}%"

    def update_status(self, text, color=None):
        self.status_label.text = text
        if color is not None:
            self.status_label.color = color

    def update_ntp(self, text, color):
        self.ntp_label.text = text
        self.ntp_label.color = color

    def update_steps(self, steps):
        self.kroky_label.text = f"K: {min(steps, 999999)}"

    def update_memory(self, free_kb):
        self.ram_label.text = f"R: {free_kb}k"

    def update_battery(self, battery_text, voltage_text):
        self.bat_label.text = f"B:{battery_text}"
        self.mv_label.text = voltage_text
