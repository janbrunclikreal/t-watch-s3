# file: app_hwtest.py
import displayio
import terminalio
from adafruit_display_text import label

class AppHwTest:
    def __init__(self):
        self.group = displayio.Group()

        # Nadpis
        title = label.Label(terminalio.FONT, text="HW DIAGNOSTIKA", color=0xFFD700, scale=2, x=15, y=20)
        self.group.append(title)

        # 1. Baterie / Napájení
        self.bat_lbl = label.Label(terminalio.FONT, text="Baterie: Cekam...", color=0xFF9600, scale=1, x=15, y=65)
        self.group.append(self.bat_lbl)

        # 2. Napětí v mV
        self.mv_lbl = label.Label(terminalio.FONT, text="Napeti: ---- mV", color=0xFF4444, scale=1, x=15, y=90)
        self.group.append(self.mv_lbl)

        # 3. RTC Čas
        self.rtc_lbl = label.Label(terminalio.FONT, text="RTC Cas: --:--:--", color=0x03F830, scale=1, x=15, y=115)
        self.group.append(self.rtc_lbl)

        # 4. Volná RAM paměť
        self.ram_lbl = label.Label(terminalio.FONT, text="Volna RAM: ---- kB", color=0x00D0FF, scale=1, x=15, y=140)
        self.group.append(self.ram_lbl)

        # Tlačítko ZPĚT v dolní části
        back_lbl = label.Label(terminalio.FONT, text="[ ZPET DO MENU ]", color=0xFFFFFF, scale=2, x=20, y=195)
        self.group.append(back_lbl)

    def update_data(self, bat_text, mv_text, cas_str, ram_kb):
        """Metoda pro živou aktualizaci dat z hlavní smyčky code.py"""
        self.bat_lbl.text = f"Baterie: {bat_text}"
        self.mv_lbl.text = f"Napeti: {mv_text}"
        self.rtc_lbl.text = f"RTC Cas: {cas_str}"
        self.ram_lbl.text = f"Volna RAM: {ram_kb} kB"

    def handle_tap(self, x, y):
        # Stisk dolní části obrazovky vrací "BACK"
        if y > 160:
            return "BACK"
        return None