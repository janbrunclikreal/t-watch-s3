import displayio
import terminalio
from adafruit_display_text import label

# Statická převodní mapa pro diakritiku (vytvoří se jen jednou v RAM)
_CZ_MAP = {
    ord(c): r for c, r in zip(
        'áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ',
        'acdeeinorstuuyzACDEEINORSTUUYZ'
    )
}

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
        self.app_lbl = label.Label(terminalio.FONT, text="App: ---", color=0x00D0FF, scale=1, x=15, y=75)
        self.group.append(self.app_lbl)

        # Titulek/Odesílatel
        self.title_lbl = label.Label(terminalio.FONT, text="Zadna zprava", color=0xFFD700, scale=1, x=15, y=100)
        self.group.append(self.title_lbl)

        # Text zprávy (s podporou více řádků pro delší text)
        self.msg_lbl = label.Label(terminalio.FONT, text="", color=0xFFFFFF, scale=1, x=15, y=125, line_spacing=1.1)
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
        """Rychlé odstranění české diakritiky bez zbytečné alokace RAM"""
        if not text:
            return ""
        return str(text).translate(_CZ_MAP)

    def _wrap_text(self, text, max_chars_per_line=26, max_lines=3):
        """Jednoduché zalamování textu na více řádků bez složitých knihoven"""
        if not text:
            return ""
        words = text.split(" ")
        lines = []
        current_line = ""

        for word in words:
            if len(current_line) + len(word) + 1 <= max_chars_per_line:
                current_line += (" " if current_line else "") + word
            else:
                lines.append(current_line)
                current_line = word
                if len(lines) >= max_lines:
                    break
        if current_line and len(lines) < max_lines:
            lines.append(current_line)

        return "\n".join(lines)

    def update_status(self, text, color=0xFFFFFF):
        self.status_lbl.text = f"BLE: {text}"
        self.status_lbl.color = color

    def add_notification(self, app_name, title, message=""):
        """Přidá notifikaci. Bezpečně zvládá 2 i 3 argumenty."""
        # Pokud přišel f-string ze starého runtime: "Titul: Zpráva" v argumentu 'title'
        if not message and ":" in title:
            parts = title.split(":", 1)
            title = parts[0].strip()
            message = parts[1].strip()

        app_lower = app_name.lower()
        if "mobilephone" in app_lower:
            app_nazev = "Prichozi Hovor"
        elif "mobilesms" in app_lower:
            app_nazev = "Zprava SMS"
        elif "picaboo" in app_lower or "snapchat" in app_lower:
            app_nazev = "Snapchat"
        else:
            app_nazev = app_name[:16]

        zobrazit_title = title if title else "Zprava"
        
        # Očistíme texty od diakritiky
        cisty_title = self.strip_diacritics(zobrazit_title)
        cisty_msg = self.strip_diacritics(message)

        # Zalamování zprávy na 3 řádky (max ~75 znaků)
        formatted_msg = self._wrap_text(cisty_msg, max_chars_per_line=26, max_lines=3)

        new_item = {
            "app": app_nazev,
            "title": cisty_title[:22],
            "msg": formatted_msg
        }
        
        # Vložení na začátek (nejnovější první)
        self.notifications.insert(0, new_item)

        # Ochrana paměti (Prstencový buffer)
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
            self.app_lbl.text = "App: ---"
            self.title_lbl.text = "Seznam smazan"
            self.msg_lbl.text = ""
            return

        item = self.notifications[self.current_index]
        self.count_lbl.text = f"{self.current_index + 1} / {total}"
        self.app_lbl.text = f"App: {item['app']}"
        self.title_lbl.text = f"{item['title']}"
        self.msg_lbl.text = f"{item['msg']}"

    def handle_tap(self, x, y):
        return self.handle_event("TAP", x, y)

    def handle_event(self, ev_type, x, y):
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
            # Tlačítko STARŠÍ
            if 160 <= y <= 195 and x < 120:
                if self.current_index < total - 1:
                    self.current_index += 1
                    self.render_current()

            # Tlačítko NOVĚJŠÍ
            elif 160 <= y <= 195 and x >= 120:
                if self.current_index > 0:
                    self.current_index -= 1
                    self.render_current()

            # Zpět do menu
            elif y > 200:
                return "BACK"

        return None