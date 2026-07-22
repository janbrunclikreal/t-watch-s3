# file: app_moblin.py
import displayio
import terminalio
from adafruit_display_text import label

class AppMoblin:
    def __init__(self):
        # Hlavní grafická skupina aplikace Moblin
        self.group = displayio.Group()

        # Nadpis
        title = label.Label(terminalio.FONT, text="MOBLIN STREAM", color=0xFF9600, scale=2, x=25, y=20)
        self.group.append(title)

        # Stav připojení
        self.status_lbl = label.Label(terminalio.FONT, text="Status: Offline", color=0xFF4444, scale=1, x=20, y=70)
        self.group.append(self.status_lbl)

        # Poslední alert
        self.alert_lbl = label.Label(terminalio.FONT, text="Cekam na alert...", color=0xFFFFFF, scale=1, x=20, y=110)
        self.group.append(self.alert_lbl)

        # Tlačítko ZPĚT v dolní části
        back_lbl = label.Label(terminalio.FONT, text="[ ZPET DO MENU ]", color=0x00D0FF, scale=2, x=20, y=190)
        self.group.append(back_lbl)

    def set_status(self, text, color=0xFFFFFF):
        self.status_lbl.text = f"Status: {text}"
        self.status_lbl.color = color

    def show_alert(self, text):
        self.alert_lbl.text = text

    def handle_tap(self, x, y):
        """
        Pokud uživatel klepne v dolní části obrazovky (Y > 160), vrátí 'BACK'.
        """
        if y > 160:
            return "BACK"
        return None