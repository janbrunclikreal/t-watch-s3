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
        self.bat_lbl = label.Label(terminalio.FONT, text="Baterie: Cekam...", color=0xFF9600, scale=1, x=15, y=55)
        self.group.append(self.bat_lbl)

        # 2. Napětí v mV
        self.mv_lbl = label.Label(terminalio.FONT, text="Napeti: ---- mV", color=0xFF4444, scale=1, x=15, y=80)
        self.group.append(self.mv_lbl)

        # 3. RTC Čas
        self.rtc_lbl = label.Label(terminalio.FONT, text="RTC Cas: --:--:--", color=0x03F830, scale=1, x=15, y=105)
        self.group.append(self.rtc_lbl)

        # 4. Volná RAM paměť
        self.ram_lbl = label.Label(terminalio.FONT, text="Volna RAM: ---- kB", color=0x00D0FF, scale=1, x=15, y=130)
        self.group.append(self.ram_lbl)

        # 5. Vytížení CPU (NOVÉ)
        self.cpu_lbl = label.Label(terminalio.FONT, text="Vytizeni CPU: --%", color=0xFF00FF, scale=1, x=15, y=155)
        self.group.append(self.cpu_lbl)

        # Tlačítko ZPĚT v dolní části
        back_lbl = label.Label(terminalio.FONT, text="[ ZPET DO MENU ]", color=0xFFFFFF, scale=2, x=20, y=200)
        self.group.append(back_lbl)

    def update_data(self, bat_text, mv_text, cas_str, ram_kb, cpu_pct):
        """Metoda pro živou aktualizaci dat z hlavní smyčky code.py"""
        self.bat_lbl.text = f"Baterie: {bat_text}"
        self.mv_lbl.text = f"Napeti: {mv_text}"
        self.rtc_lbl.text = f"RTC Cas: {cas_str}"
        self.ram_lbl.text = f"Volna RAM: {ram_kb} kB"
        self.cpu_lbl.text = f"Vytizeni CPU: {cpu_pct}%"

    def handle_tap(self, x, y):
        # Stisk dolní části obrazovky vrací "BACK"
        if y > 175:
            return "BACK"
        return None