# file: app_notifications.py
import displayio
import terminalio
from adafruit_display_text import label

class AppNotifications:
    def __init__(self, max_notif=15):
        self.group = displayio.Group()
        self.notifications = []
        self.current_index = 0
        self.max_notif = max_notif

        # Nadpis
        title = label.Label(terminalio.FONT, text="NOTIFIKACE", color=0x03F830, scale=2, x=10, y=18)
        self.group.append(title)

        # Počítadlo
        self.count_lbl = label.Label(terminalio.FONT, text="0 / 0", color=0xFF9600, scale=1, x=160, y=20)
        self.group.append(self.count_lbl)

        # Stav Bluetooth
        self.status_lbl = label.Label(terminalio.FONT, text="BLE: Cekam...", color=0x888888, scale=1, x=15, y=50)
        self.group.append(self.status_lbl)

        # Aplikace
        self.app_lbl = label.Label(terminalio.FONT, text="Aplikace: ---", color=0x00D0FF, scale=1, x=15, y=85)
        self.group.append(self.app_lbl)

        # Nadpis zprávy
        self.title_lbl = label.Label(terminalio.FONT, text="Zadna zprava", color=0xFFD700, scale=1, x=15, y=115)
        self.group.append(self.title_lbl)

        # Text zprávy
        self.msg_lbl = label.Label(terminalio.FONT, text="", color=0xFFFFFF, scale=1, x=15, y=140)
        self.group.append(self.msg_lbl)

        # Navigace
        self.prev_btn = label.Label(terminalio.FONT, text="[ < STARSI ]", color=0x00D0FF, scale=1, x=10, y=180)
        self.group.append(self.prev_btn)

        self.next_btn = label.Label(terminalio.FONT, text="[ NOVEJSI > ]", color=0x00D0FF, scale=1, x=140, y=180)
        self.group.append(self.next_btn)

        # Tlačítko ZPĚT
        back_lbl = label.Label(terminalio.FONT, text="[ ZPET DO MENU ]", color=0xFFFFFF, scale=2, x=20, y=215)
        self.group.append(back_lbl)

    def strip_diacritics(self, text):
        """Převede české znaky s diakritikou na čisté ASCII ekvivalenty"""
        if not text:
            return ""
        
        preklady = {
            'áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ':
            'acdeeinorstuuyzACDEEINORSTUUYZ'
        }
        
        # Jednoduchá výměna znaků
        vystup = []
        # Mapa pro rychlý převod
        smap = {
            'áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ'[i]: 'acdeeinorstuuyzACDEEINORSTUUYZ'[i]
            for i in range(len('áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ'))
        }
        
        for znak in text:
            vystup.append(smap.get(znak, znak))
            
        return "".join(vystup)

    def update_status(self, text, color=0xFFFFFF):
        self.status_lbl.text = f"BLE: {text}"
        self.status_lbl.color = color

    def add_notification(self, app_name, title, message=""):
        if "mobilephone" in app_name.lower():
            app_nazev = "Prichozi Hovor"
        elif "mobilesms" in app_name.lower():
            app_nazev = "Zprava SMS"
        else:
            app_nazev = app_name[:18]

        zobrazit_title = title if title else "Zprava"
        
        # Očistíme titulek i text zprávy od diakritiky
        cisty_title = self.strip_diacritics(zobrazit_title)
        cisty_msg = self.strip_diacritics(message)

        new_item = {
            "app": app_nazev,
            "title": cisty_title[:20],
            "msg": cisty_msg[:25] if cisty_msg else ""
        }
        self.notifications.insert(0, new_item)

        if len(self.notifications) > self.max_notif:
            self.notifications.pop()

        self.current_index = 0
        self.render_current()

    def clear_all(self):
        """Vymaže všechny notifikace z paměti"""
        self.notifications.clear()
        self.current_index = 0
        self.render_current()

    def render_current(self):
        total = len(self.notifications)
        if total == 0:
            self.count_lbl.text = "0 / 0"
            self.app_lbl.text = "Aplikace: ---"
            self.title_lbl.text = "Seznam smazan"
            self.msg_lbl.text = ""
            return

        item = self.notifications[self.current_index]
        self.count_lbl.text = f"{self.current_index + 1} / {total}"
        self.app_lbl.text = f"App: {item['app']}"
        self.title_lbl.text = f"{item['title']}"
        self.msg_lbl.text = f"{item['msg']}"

    def handle_tap(self, x, y):
        """Zpětná kompatibilita pro starší volání z code.py"""
        return self.handle_event("TAP", x, y)

    def handle_event(self, ev_type, x, y):
        """Obsluha klepnutí i gest švihu"""
        total = len(self.notifications)

        # GESTO 1: Švih shora dolů -> Smazat všechny notifikace
        if ev_type == "SWIPE_DOWN":
            self.clear_all()
            return "CLEARED"

        # GESTO 2: Švih zdola nahoru -> Návrat zpět
        elif ev_type == "SWIPE_UP":
            return "BACK"

        # KLEPNUTÍ (TAP)
        elif ev_type == "TAP":
            if 160 <= y <= 195 and x < 120:
                if self.current_index < total - 1:
                    self.current_index += 1
                    self.render_current()

            elif 160 <= y <= 195 and x >= 120:
                if self.current_index > 0:
                    self.current_index -= 1
                    self.render_current()

            elif y > 200:
                return "BACK"

        return None