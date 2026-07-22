# file: app_menu.py
import displayio
import terminalio
from adafruit_display_text import label

class AppMenu:
    def __init__(self):
        # Hlavní grafická skupina pro menu
        self.group = displayio.Group()

        # Nadpis
        title = label.Label(terminalio.FONT, text="APLIKACE", color=0x00D0FF, scale=2, x=60, y=20)
        self.group.append(title)

        # 1. Ikona MOBLIN (Horní vlevo)
        moblin_lbl = label.Label(terminalio.FONT, text="[ MOBLIN ]", color=0xFF9600, scale=2, x=10, y=70)
        self.group.append(moblin_lbl)

        # 2. Ikona NOTIFIKACE (Horní vpravo)
        notif_lbl = label.Label(terminalio.FONT, text="[ NOTIF ]", color=0x03F830, scale=2, x=130, y=70)
        self.group.append(notif_lbl)

        # 3. Ikona HW TEST (Dolní vlevo)
        hw_lbl = label.Label(terminalio.FONT, text="[ HW TEST ]", color=0xFFD700, scale=2, x=5, y=160)
        self.group.append(hw_lbl)

        # 4. Tlačítko ZPĚT (Dolní vpravo)
        back_lbl = label.Label(terminalio.FONT, text="[ ZPET ]", color=0xFF4444, scale=2, x=140, y=160)
        self.group.append(back_lbl)

    def handle_tap(self, x, y):
        """
        Podle souřadnic X, Y vyhodnotí, na kterou ikonu bylo klepnuto.
        Vrací řetězec: 'MOBLIN', 'NOTIF', 'HWTEST', 'BACK' nebo None
        """
        if y < 120:
            if x < 120:
                return "MOBLIN"
            else:
                return "NOTIF"
        else:
            if x < 120:
                return "HWTEST"
            else:
                return "BACK"