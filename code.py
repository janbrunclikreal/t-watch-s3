import os
import time
import board
import displayio
import terminalio
import wifi
import socketpool
import gc
import json
import asyncio
import math
import adafruit_ntp
import microcontroller
import supervisor
import _bleio
import sys

sys.path.append("/modules")

from adafruit_display_text import label
from adafruit_pcf8563.pcf8563 import PCF8563
from axp2101 import AXP2101
from adafruit_drv2605 import DRV2605, Effect
import bma423

# --- BLE ANCS IMPORTY & INICIALIZACE ---
radio = None
ble_dostupne = False
try:
    import adafruit_ble
    from adafruit_ble.advertising.standard import SolicitServicesAdvertisement
    import adafruit_ble_apple_notification_center as ancs
    radio = adafruit_ble.BLERadio()
    ble_dostupne = True
except Exception:
    ble_dostupne = False

# --- IMPORTY GUI A DOTYKOVÝCH MODULŮ ---
from touch import TouchController
from app_menu import AppMenu
from app_moblin import AppMoblin
from app_hwtest import AppHwTest
from app_notifications import AppNotifications

# --- INICIALIZACE S BĚHOVOU OCHRANOU PMU & RTC ---
i2c = board.I2C()

# 1. Probudíme napájecí čip PMU a sepneme napájení obvodů
try:
    pmu = AXP2101(i2c)
    for m in ["enable_aldo1", "enable_aldo2", "enable_aldo3", "enable_aldo4", "enable_dldo1"]:
        if hasattr(pmu, m):
            try:
                getattr(pmu, m)()
            except Exception:
                pass
except Exception as e:
    print(f"[PMU-INIT-ERR] {e}")

time.sleep(0.1)

# 2. Inicializace RTC hodin
rtc_hw = None
try:
    rtc_hw = PCF8563(i2c)
except Exception as e:
    print(f"[RTC-INIT-ERR] {e}")

# --- POMOCNÁ FUNKCE PRO LOGOVÁNÍ A SPRÁVU PAMĚTI ---
def log(zprava):
    """Vytiskne zprávu s přesným časovým razítkem [HH:MM:SS.mmm]"""
    try:
        t = rtc_hw.datetime
        ms = int((time.monotonic() % 1) * 1000)
        cas_str = f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}.{ms:03d}"
    except Exception:
        mono = time.monotonic()
        s = int(mono)
        ms = int((mono % 1) * 1000)
        cas_str = f"{s}s.{ms:03d}"
    print(f"[{cas_str}] {zprava}")

def memory_cleanup(reason=""):
    """Event-driven uvolnění paměti pro zamezení micro-stutteringu"""
    volno_pred = gc.mem_free()
    gc.collect()
    volno_po = gc.mem_free()
    duvod_str = f" ({reason})" if reason else ""
    log(f"[MEM]{duvod_str} Uvolněno: {(volno_po - volno_pred)//1024} kB | Volno: {volno_po//1024} kB")

# --- OPTIMALIZACE SPOTŘEBY ---
try:
    microcontroller.cpu.frequency = 80000000
    log("[POWER] CPU podtaktováno na 80 MHz.")
except Exception as e:
    log(f"[POWER] Nelze změnit frekvenci CPU: {e}")

# --- KONFIGURACE WI-FI & ČASU ---
WIFI_SSID = os.getenv("CIRCUITPYTHON_WIFI_SSID")
WIFI_PASS = os.getenv("CIRCUITPYTHON_WIFI_PASSWORD")
CASOVE_PASMO_HODIN = int(os.getenv("TIMEZONE_OFFSET", "2"))
DB_FILE = "/kroky_db.json"

# --- GLOBÁLNÍ STAVY A PROMĚNNÉ ---
posledni_aktivita = time.monotonic()
displej_vzhuru = True
TIMEOUT_SPANKU_SEC = 10
wifi_sync_probha = False
cas_synchronizovan = False
kroky_dnes = 0
posledni_datum_str = ""

# --- HAPTIKA DRV2605 ---
try:
    drv = DRV2605(i2c)
    drv.sequence[0] = Effect(1)
    drv.play()
except Exception as e:
    log(f"[DRV-ERR] Nelze inicializovat haptiku: {e}")

# --- DISPLEJ A GRAFICKÁ SKUPINA ---
display = board.DISPLAY
main_group = displayio.Group()

datum_label = label.Label(terminalio.FONT, text="01.01.", color=0xFFFFFF, x=5, y=15)
status_label = label.Label(terminalio.FONT, text="W:off B:off", color=0x444444, x=55, y=15)
bat_label = label.Label(terminalio.FONT, text="B:--%", color=0xFF9600, x=210, y=15)
cas_label = label.Label(terminalio.FONT, text="00:00:00", color=0x03F830, scale=5, x=2, y=50)
ntp_label = label.Label(terminalio.FONT, text="N: Off", color=0xFF9600, x=5, y=230)
kroky_label = label.Label(terminalio.FONT, text="K: 0", color=0xFFD700, scale=1, x=60, y=230)
ram_label = label.Label(terminalio.FONT, text="R: 0000k", color=0x00D0FF, x=130, y=230)
mv_label = label.Label(terminalio.FONT, text="---- mV", color=0xFF4444, x=195, y=230)

main_group.append(datum_label)
main_group.append(status_label)
main_group.append(bat_label)
main_group.append(cas_label)
main_group.append(ntp_label)
main_group.append(kroky_label)
main_group.append(ram_label)
main_group.append(mv_label)

# --- APLE/MODULY GUI ---
tc = TouchController()
menu_app = AppMenu()
moblin_app = AppMoblin()
hwtest_app = AppHwTest()
notif_app = AppNotifications()

STATE_WATCHFACE = "WATCHFACE"
STATE_MENU = "MENU"
STATE_MOBLIN = "MOBLIN"
STATE_HWTEST = "HWTEST"
STATE_NOTIF = "NOTIF"

current_state = STATE_WATCHFACE
display.root_group = main_group

def nastav_jas(procenta):
    display.brightness = procenta / 100

def probud_displej():
    global displej_vzhuru, posledni_aktivita
    posledni_aktivita = time.monotonic()
    if not displej_vzhuru:
        for jas in range(0, 91, 20):
            nastav_jas(jas)
        displej_vzhuru = True

# --- DATABÁZE KROKŮ ---
def nacti_databazi_kroku():
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}

def uloz_kroky_do_db(datum_str, pocet_kroku):
    data = nacti_databazi_kroku()
    data[datum_str] = pocet_kroku
    try:
        with open(DB_FILE, "w") as f:
            json.dump(data, f)
            f.flush()
        log(f"[DB] Uloženo na Flash: {datum_str} -> {pocet_kroku} kroků")
    except OSError as e:
        if e.errno == 38:
            log("[DB] Připojeno k PC (Read-Only). Zápis přeskakuji.")
        else:
            log(f"[DB-ERR] Chyba zápisu: {e}")

# --- AKCELEROMETR BMA423 ---
bma_sensor = None
posledni_magnitude = 1.0
posledni_krok_cas = 0

def bma423_init():
    global bma_sensor
    try:
        bma_sensor = bma423.BMA423(i2c)
        log("[BMA423] Akcelerometr v režimu G-Force inicializován.")
    except Exception as e:
        log(f"[BMA423-ERR] {e}")

def bma423_merit_kroky():
    global kroky_dnes, posledni_magnitude, posledni_krok_cas
    if bma_sensor:
        try:
            x, y, z = bma_sensor.acceleration
            magnitude = math.sqrt(x*x + y*y + z*z)
            nyni = time.monotonic()
            if magnitude > 1.18 and posledni_magnitude <= 1.18:
                if (nyni - posledni_krok_cas) > 0.33:
                    kroky_dnes += 1
                    posledni_krok_cas = nyni
                    if magnitude > 2.50:
                        try:
                            drv.sequence[0] = Effect(47)
                            drv.play()
                        except Exception:
                            pass
                    else:
                        try:
                            drv.sequence[0] = Effect(14)
                            drv.play()
                        except Exception:
                            pass
            posledni_magnitude = magnitude
        except Exception:
            pass
    return kroky_dnes

bma423_init()

# =========================================================================
# ASYNCHRONNÍ TASKY
# =========================================================================

async def wifi_cas_sync_task():
    """NTP synchronizace času"""
    global cas_synchronizovan, wifi_sync_probha, posledni_aktivita
    try:
        if rtc_hw and rtc_hw.datetime.tm_year >= 2026:
            t_RTC = rtc_hw.datetime
            log(f"[RTC-OK] Čas z RTC je platný ({t_RTC.tm_mday:02d}.{t_RTC.tm_mon:02d}.{t_RTC.tm_year} {t_RTC.tm_hour:02d}:{t_RTC.tm_min:02d}). Wi-Fi přeskočena!")
            ntp_label.text = "N: RTC"
            ntp_label.color = 0x03F830
            cas_synchronizovan = True
            return
    except Exception as e:
        log(f"[RTC-WARN] {e}")

    await asyncio.sleep(1)
    wifi_sync_probha = True
    status_label.text = "W:SYNC B:off"
    log("[NTP-Sync] Připojuji se k Wi-Fi...")
    try:
        wifi.radio.connect(WIFI_SSID, WIFI_PASS)
        status_label.text = "W:WIFI B:off"
        pool = socketpool.SocketPool(wifi.radio)
        ntp = adafruit_ntp.NTP(pool, server="europe.pool.ntp.org", tz_offset=0)
        try:
            ntp_cas_utc = ntp.datetime
            sekundy_utc = time.mktime(ntp_cas_utc)
            lokalni_cas = time.localtime(sekundy_utc + (CASOVE_PASMO_HODIN * 3600))
            if rtc_hw:
                rtc_hw.datetime = lokalni_cas
            log(f"[NTP-Sync] RTC aktualizováno: {lokalni_cas.tm_hour:02d}:{lokalni_cas.tm_min:02d}")
            cas_synchronizovan = True
            ntp_label.text = "N: OK"
            ntp_label.color = 0x03F830
        except (ValueError, OSError) as e:
            log(f"[NTP-Sync-WARN] Neúplný NTP paket: {e}")
            ntp_label.text = "N: Err"
            ntp_label.color = 0xFF0000
    except Exception as e:
        log(f"[NTP-Sync-ERR] {e}")
        ntp_label.text = "N: Err"
        ntp_label.color = 0xFF0000

    try:
        wifi.radio.enabled = False
    except Exception:
        pass
    status_label.text = "W:off B:off"
    wifi_sync_probha = False
    memory_cleanup("Po Wi-Fi sync")


async def ble_ancs_task():
    """Robustní BLE ANCS task pro příchozí notifikace z iOS/Androidu"""
    global posledni_aktivita, displej_vzhuru, radio
    if not ble_dostupne or radio is None:
        log("[BLE-WARN] Knihovny adafruit_ble nebo ANCS chybí!")
        return

    log("[Task] Nativní BLE ANCS Notifikační task spuštěn.")
    a = SolicitServicesAdvertisement()
    a.solicited_services.append(ancs.AppleNotificationCenterService)

    while True:
        try:
            log("[BLE] Spouštím inzerci pro ANCS...")
            status_label.text = "W:off B:adv-iOS"
            radio.start_advertising(a)

            while not radio.connected:
                await asyncio.sleep(0.5)

            log("[BLE] Telefon připojen!")
            status_label.text = "W:off B:iOS-OK"
            radio.stop_advertising()

            for connection in radio.connections:
                if ancs.AppleNotificationCenterService not in connection:
                    continue

                try:
                    if not connection.paired:
                        log("[BLE] Dojednávám šifrování relace...")
                        connection.pair()
                        log("[BLE] Spárováno!")
                except Exception as e:
                    log(f"[BLE-PAIR-WARN] {e}")

                posledni_zname_notifikace = set()

                while connection.connected:
                    try:
                        ans = connection[ancs.AppleNotificationCenterService]
                        active_notifs = ans.active_notifications

                        if len(active_notifs) > 0:
                            for notif_id in active_notifs:
                                if notif_id not in posledni_zname_notifikace:
                                    posledni_zname_notifikace.add(notif_id)
                                    notif = active_notifs[notif_id]
                                    
                                    app_id = notif.app_id or "Aplikace"
                                    title = notif.title or ""
                                    msg = notif.message or ""
                                    
                                    log(f"[ANCS-NOTIF] {app_id} | {title}: {msg}")

                                    try:
                                        drv.sequence[0] = Effect(14)
                                        drv.play()
                                    except Exception:
                                        pass

                                    probud_displej()

                                    try:
                                        notif_app.add_notification(app_id, f"{title}: {msg}")
                                    except Exception:
                                        pass

                    except (_bleio.BluetoothError, AttributeError, KeyError):
                        await asyncio.sleep(1.0)
                    except Exception as e:
                        log(f"[ANCS-ERR] {e}")
                        await asyncio.sleep(1.0)

                    await asyncio.sleep(0.3)

            log("[BLE] Spojení ztraceno. Obnovuji inzerci...")
            status_label.text = "W:off B:off"
            memory_cleanup("Po odpojení BLE")
            await asyncio.sleep(1)

        except Exception as e:
            log(f"[BLE-GLOBAL-ERR] {e}")
            await asyncio.sleep(2)


async def hlidac_korunky_task():
    """Obsluha HW tlačítka / korunky přes PMU AXP2101"""
    global posledni_aktivita, displej_vzhuru, current_state
    log("[Task] Hlídač korunky spuštěn.")
    pmu_address = 0x34
    reg_irq_status = 0x49

    def direct_read_reg(reg):
        try:
            if i2c.try_lock():
                buffer = bytearray(1)
                i2c.writeto_then_readfrom(pmu_address, bytes([reg]), buffer)
                i2c.unlock()
                return buffer[0]
        except Exception:
            try:
                i2c.unlock()
            except Exception:
                pass
        return 0

    def direct_write_reg(reg, val):
        try:
            if i2c.try_lock():
                i2c.writeto(pmu_address, bytes([reg, val]))
                i2c.unlock()
        except Exception:
            try:
                i2c.unlock()
            except Exception:
                pass

    direct_write_reg(reg_irq_status, direct_read_reg(reg_irq_status))

    while True:
        try:
            irq_status = direct_read_reg(reg_irq_status)
            if irq_status > 0:
                direct_write_reg(reg_irq_status, irq_status)
                if irq_status in (2, 3):
                    log(f"[HARDWARE-OK] Korunka stisknuta! Status: {irq_status}")
                    posledni_aktivita = time.monotonic()
                    if not displej_vzhuru:
                        probud_displej()
                        try:
                            drv.play()
                        except Exception:
                            pass
                    else:
                        if current_state != STATE_WATCHFACE:
                            current_state = STATE_WATCHFACE
                            display.root_group = main_group
                            memory_cleanup("Návrat na Watchface")
                            log("[AKCE] Návrat na Ciferník")
                        else:
                            log("[AKCE] Uspávám displej...")
                            for jas in range(90, -1, -10):
                                nastav_jas(jas)
                                await asyncio.sleep(0.01)
                            displej_vzhuru = False
                    await asyncio.sleep(0.5)
        except Exception:
            pass

        await asyncio.sleep(0.05 if displej_vzhuru else 0.2)


async def sprava_napajeni_task():
    """Automatické zhasínání displeje při neaktivitě"""
    global posledni_aktivita, displej_vzhuru, wifi_sync_probha
    log("[Task] Správa napájení spuštěna.")
    while True:
        try:
            now = time.monotonic()
            rozdil = now - posledni_aktivita
            usb_pripojeno = supervisor.runtime.usb_connected

            if displej_vzhuru and not wifi_sync_probha and not usb_pripojeno:
                if rozdil > TIMEOUT_SPANKU_SEC:
                    log(f"[POWER] Timeout vypršel ({rozdil:.1f}s). Uspávám displej...")
                    for jas in range(90, -1, -10):
                        nastav_jas(jas)
                        await asyncio.sleep(0.02)
                    displej_vzhuru = False
        except Exception:
            pass
        await asyncio.sleep(0.5)


async def pocitadlo_kroku_task():
    """Krokoměr s udržením denní databáze"""
    global kroky_dnes, posledni_datum_str
    log("[Task] Počítadlo kroků spuštěno.")
    try:
        if rtc_hw:
            t = rtc_hw.datetime
            posledni_datum_str = f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}"
            db = nacti_databazi_kroku()
            kroky_dnes = db.get(posledni_datum_str, 0)
    except Exception:
        pass

    ulozeni_pocitadlo = 0
    while True:
        try:
            if rtc_hw:
                t = rtc_hw.datetime
                aktualni_datum_str = f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}"
                if aktualni_datum_str != posledni_datum_str:
                    log(f"[PŮLNOC] Archivuji kroky za den {posledni_datum_str}: {kroky_dnes}")
                    uloz_kroky_do_db(posledni_datum_str, kroky_dnes)
                    posledni_datum_str = aktualni_datum_str
                    kroky_dnes = 0

            bma423_merit_kroky()
            if displej_vzhuru:
                kroky_label.text = f"K: {kroky_dnes}"

            ulozeni_pocitadlo += 1
            if ulozeni_pocitadlo >= 1500:
                ulozeni_pocitadlo = 0
                if posledni_datum_str:
                    uloz_kroky_do_db(posledni_datum_str, kroky_dnes)
        except Exception as e:
            log(f"[KROKY-ERR] {e}")

        await asyncio.sleep(0.2)


async def graficka_smycka_hodin_task():
    """Obnovování textů ciferníku a statusů"""
    log("[Task] Grafická smyčka hodin spuštěna.")
    posledni_sekunda = -1

    while True:
        if displej_vzhuru and rtc_hw:
            try:
                t = rtc_hw.datetime
                if current_state == STATE_WATCHFACE:
                    if t.tm_sec != posledni_sekunda:
                        posledni_sekunda = t.tm_sec
                        cas_label.text = f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}"
                        datum_label.text = f"{t.tm_mday:02d}.{t.tm_mon:02d}."

                        if t.tm_sec % 5 == 0:
                            ram_label.text = f"R: {gc.mem_free() // 1024}k"

                        if t.tm_sec % 10 == 0:
                            try:
                                if pmu.is_battery_connected:
                                    bat_label.text = f"B:{pmu.battery_level}%"
                                    mv_label.text = f"{pmu.battery_voltage} mV"
                                else:
                                    bat_label.text = "B: USB"
                                    mv_label.text = "USB PWR"
                            except Exception:
                                pass

                elif current_state == STATE_HWTEST:
                    cas_sec = f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}"
                    volna_ram = gc.mem_free() // 1024
                    try:
                        if pmu.is_battery_connected:
                            b_str = f"{pmu.battery_level}%"
                            mv_str = f"{pmu.battery_voltage} mV"
                        else:
                            b_str = "USB Připojeno"
                            mv_str = "5000 mV"
                    except Exception:
                        b_str, mv_str = "Neznámo", "---- mV"

                    hwtest_app.update_data(b_str, mv_str, cas_sec, volna_ram)

            except Exception as e:
                log(f"[GUI-ERR] {e}")
            await asyncio.sleep(0.2)
        else:
            await asyncio.sleep(0.5)


async def dotyk_a_gui_task():
    """Obsluha dotykové vrstvy a přepínání obrazovek"""
    global current_state, posledni_aktivita, displej_vzhuru
    log("[Task] Dotyková obsluha spuštěna.")
    while True:
        try:
            ev = tc.get_event()
            if ev:
                if not displej_vzhuru:
                    probud_displej()

                posledni_aktivita = time.monotonic()
                ev_type, x, y = ev[0], ev[1], ev[2]

                if current_state == STATE_WATCHFACE:
                    if ev_type in ("TAP", "SWIPE_DOWN", "SWIPE_UP"):
                        log("[TOUCH] Otevírám MENU")
                        current_state = STATE_MENU
                        display.root_group = menu_app.group

                elif current_state == STATE_MENU:
                    if ev_type == "TAP":
                        akce = menu_app.handle_tap(x, y)
                        log(f"[MENU-TAP] Vybrána akce: {akce}")
                        if akce == "MOBLIN":
                            current_state = STATE_MOBLIN
                            display.root_group = moblin_app.group
                        elif akce == "NOTIF":
                            current_state = STATE_NOTIF
                            display.root_group = notif_app.group
                        elif akce == "HWTEST":
                            current_state = STATE_HWTEST
                            display.root_group = hwtest_app.group
                        elif akce == "BACK":
                            current_state = STATE_WATCHFACE
                            display.root_group = main_group
                            memory_cleanup("Zavření menu")

                elif current_state == STATE_NOTIF:
                    akce = notif_app.handle_event(ev_type, x, y)
                    if akce == "BACK":
                        current_state = STATE_MENU
                        display.root_group = menu_app.group
                    elif akce == "CLEARED":
                        try:
                            drv.sequence[0] = Effect(14)
                            drv.play()
                        except Exception:
                            pass

                elif current_state in (STATE_MOBLIN, STATE_HWTEST):
                    app = moblin_app if current_state == STATE_MOBLIN else hwtest_app
                    if ev_type == "TAP" and app.handle_tap(x, y) == "BACK":
                        current_state = STATE_MENU
                        display.root_group = menu_app.group
                        memory_cleanup("Zavření aplikací")

        except Exception as e:
            log(f"[TOUCH-ERR] {e}")

        await asyncio.sleep(0.04)

# =========================================================================
# HLAVNÍ SMYČKA A BEZPEČNÝ RUNTIME
# =========================================================================
async def main():
    log("Spouštím optimalizovaný CircuitPython OS pro T-Watch-S3...")
    await asyncio.gather(
        hlidac_korunky_task(),
        sprava_napajeni_task(),
        graficka_smycka_hodin_task(),
        wifi_cas_sync_task(),
        pocitadlo_kroku_task(),
        dotyk_a_gui_task(),
        ble_ancs_task()
    )

try:
    asyncio.run(main())

except KeyboardInterrupt:
    log("[REPL] Přerušeno uživatelem.")

except MemoryError:
    log("[CRITICAL] Došla paměť RAM! Provádím emergency reload...")
    memory_cleanup("Emergency MemoryError")
    time.sleep(1)
    supervisor.reload()

except Exception as e:
    log(f"[CRASH] Neošetřená chyba ({type(e).__name__}): {e}")
    time.sleep(1)
    supervisor.reload()

finally:
    log("[SYSTEM] Zahajuji bezpečný úklid...")

    try:
        if radio is not None:
            if hasattr(radio, 'advertising') and radio.advertising:
                radio.stop_advertising()
                log("[BLE] Advertising zastaven.")
            
            if radio.connected:
                for conn in list(radio.connections):
                    try:
                        conn.disconnect()
                        log("[BLE] Odpojen telefon.")
                    except Exception:
                        pass
                time.sleep(0.2)

            _bleio.adapter.enabled = False
            time.sleep(0.1)
            _bleio.adapter.enabled = True
            log("[BLE] BLE adaptér resetován.")
    except Exception as e:
        log(f"[BLE-CLEANUP-ERR] {e}")

    try:
        nastav_jas(100)
        display.root_group = displayio.CIRCUITPYTHON_TERMINAL
        try:
            i2c.unlock()
            log("[I2C] Sběrnice odemčena.")
        except Exception:
            pass
    except Exception as e:
        log(f"[HW-CLEANUP-ERR] {e}")

    memory_cleanup("Závěrečný úklid")
    log("[SYSTEM] Úklid dokončen.")
