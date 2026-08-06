import asyncio
import gc
import time

import displayio
import supervisor

from app_hwtest import AppHwTest
from app_menu import AppMenu
from app_moblin import AppMoblin
from app_notifications import AppNotifications
from touch import TouchController
from watch_hardware import WatchHardware
from watch_state import WatchState
from watch_storage import StepDatabase
from watch_ui import WatchFaceUI


class WatchRuntime:
    PMU_ADDRESS = 0x34
    REG_IRQ_STATUS = 0x49

    def __init__(self):
        self.state = WatchState()
        self.hardware = WatchHardware()
        self.watchface = WatchFaceUI()
        self.touch = TouchController()
        self.menu_app = AppMenu()
        self.moblin_app = AppMoblin()
        self.hwtest_app = AppHwTest()
        self.notif_app = AppNotifications()
        self.step_db = StepDatabase(self.hardware.DB_FILE, self.hardware.log)
        self.cpu_usage_cache = 0
        self.watchface.show_on(self.hardware.display)
        
        # Nastavení stabilní úsporné frekvence CPU (80 MHz)
        self.hardware.set_cpu_frequency(80000000)

    def memory_cleanup(self, reason=""):
        gc.collect()
        if reason:
            self.hardware.log(f"[MEM] ({reason}) Uvolněno | Volno: {gc.mem_free() // 1024} kB")
        else:
            self.hardware.log(f"[MEM] Uvolněno | Volno: {gc.mem_free() // 1024} kB")

    async def wake_display_async(self):
        """Neblokující rozsvícení displeje (připraveno pro 80 % jasu)."""
        self.state.register_activity()
        if not self.state.display_awake:
            self.state.display_awake = True
            for brightness in range(0, 81, 20):
                self.hardware.set_brightness(brightness)
                await asyncio.sleep(0.01)

    async def sleep_display_async(self):
        """Neblokující zhasnutí displeje."""
        if self.state.display_awake:
            for brightness in range(80, -1, -10):
                self.hardware.set_brightness(brightness)
                await asyncio.sleep(0.01)
            self.state.display_awake = False

    def wake_display(self):
        self.state.register_activity()
        if not self.state.display_awake:
            self.hardware.set_brightness(80)
            self.state.display_awake = True

    def show_watchface(self, cleanup_reason=None):
        self.state.set_state(self.state.STATE_WATCHFACE)
        self.watchface.show_on(self.hardware.display)
        if cleanup_reason:
            self.memory_cleanup(cleanup_reason)

    def show_menu(self, cleanup_reason=None):
        self.state.set_state(self.state.STATE_MENU)
        self.hardware.display.root_group = self.menu_app.group
        if cleanup_reason:
            self.memory_cleanup(cleanup_reason)

    def show_moblin(self):
        self.state.set_state(self.state.STATE_MOBLIN)
        self.hardware.display.root_group = self.moblin_app.group

    def show_notifications(self):
        self.state.set_state(self.state.STATE_NOTIF)
        self.hardware.display.root_group = self.notif_app.group

    def show_hwtest(self):
        self.state.set_state(self.state.STATE_HWTEST)
        self.hardware.display.root_group = self.hwtest_app.group

    async def wifi_cas_sync_task(self):
        try:
            if self.hardware.has_valid_rtc_time():
                rtc_time = self.hardware.rtc.datetime
                self.hardware.log(
                    f"[RTC-OK] Čas z RTC je platný ({rtc_time.tm_mday:02d}.{rtc_time.tm_mon:02d}.{rtc_time.tm_year} {rtc_time.tm_hour:02d}:{rtc_time.tm_min:02d}). Wi-Fi přeskočena!"
                )
                self.watchface.update_ntp("N: RTC", 0x03F830)
                self.state.time_synchronized = True
                return
        except Exception as err:
            self.hardware.log(f"[RTC-WARN] {err}")

        await asyncio.sleep(1)
        self.state.wifi_sync_in_progress = True
        self.watchface.update_status("W:SYNC B:off")
        self.hardware.log("[NTP-Sync] Připojuji se k Wi-Fi...")
        try:
            self.hardware.sync_time()
            self.watchface.update_status("W:WIFI B:off")
            self.state.time_synchronized = True
            self.watchface.update_ntp("N: OK", 0x03F830)
            if self.hardware.rtc is not None:
                rtc_time = self.hardware.rtc.datetime
                self.hardware.log(
                    f"[NTP-Sync] RTC aktualizováno: {rtc_time.tm_hour:02d}:{rtc_time.tm_min:02d}"
                )
        except (ValueError, OSError) as err:
            self.hardware.log(f"[NTP-Sync-WARN] Neúplný NTP paket: {err}")
            self.watchface.update_ntp("N: Err", 0xFF0000)
        except Exception as err:
            self.hardware.log(f"[NTP-Sync-ERR] {err}")
            self.watchface.update_ntp("N: Err", 0xFF0000)

        self.hardware.disable_wifi()
        self.watchface.update_status("W:off B:off")
        self.state.wifi_sync_in_progress = False
        self.memory_cleanup("Po Wi-Fi sync")

    async def ble_ancs_task(self):
        if not self.hardware.ble_available or self.hardware.radio is None or self.hardware.ancs is None:
            self.hardware.log("[BLE-WARN] Knihovny adafruit_ble nebo ANCS chybí!")
            return

        self.hardware.log("[Task] Nativní BLE ANCS Notifikační task spuštěn.")
        advertisement = self.hardware.create_ancs_advertisement()
        known_notifications = set()

        while True:
            try:
                radio = self.hardware.radio
                
                if advertisement is None:
                    advertisement = self.hardware.create_ancs_advertisement()

                # Pokud je inzerce v pauze, šetříme CPU
                if self.state.ble_pause_advertising and not radio.connected:
                    self.watchface.update_status("W:off B:sleep")
                    await asyncio.sleep(2.0)
                    continue

                if not radio.connected and not radio.advertising and advertisement is not None:
                    self.hardware.log("[BLE] Spouštím inzerci pro ANCS...")
                    self.watchface.update_status("W:off B:adv-iOS")
                    radio.start_advertising(advertisement)
                    self.state.ble_adv_start_time = time.monotonic()

                while not radio.connected and radio.advertising:
                    # Timeout zkrácen na 10 sekund
                    if (time.monotonic() - self.state.ble_adv_start_time) > 10:
                        self.hardware.log("[BLE-POWER] Timeout inzerce (10 s) vypršel! Vypínám BLE rádio...")
                        radio.stop_advertising()
                        self.state.ble_pause_advertising = True
                        self.watchface.update_status("W:off B:sleep")
                        break
                    await asyncio.sleep(0.5)

                if radio.connected:
                    self.hardware.log("[BLE] Telefon připojen!")
                    self.watchface.update_status("W:off B:iOS-OK")
                    if radio.advertising:
                        radio.stop_advertising()

                    # OŠETŘENÍ CHYBY NoneType isn't iterable:
                    connections = radio.connections
                    if connections is not None:
                        for connection in list(connections):
                            if self.hardware.ancs.AppleNotificationCenterService not in connection:
                                continue

                            try:
                                if not connection.paired:
                                    self.hardware.log("[BLE] Dojednávám šifrování relace...")
                                    connection.pair()
                                    self.hardware.log("[BLE] Spárováno!")
                            except Exception as err:
                                self.hardware.log(f"[BLE-PAIR-WARN] {err}")

                            while connection.connected:
                                try:
                                    ancs_service = connection[self.hardware.ancs.AppleNotificationCenterService]
                                    active_notifications = ancs_service.active_notifications
                                    if active_notifications:
                                        for notif_id in list(active_notifications.keys()):
                                            if notif_id in known_notifications:
                                                continue

                                            known_notifications.add(notif_id)
                                            if len(known_notifications) > 30:
                                                known_notifications.clear()
                                                known_notifications.add(notif_id)

                                            notification = active_notifications[notif_id]
                                            app_id = getattr(notification, "app_id", "Aplikace") or "Aplikace"
                                            title = getattr(notification, "title", "") or ""
                                            message = getattr(notification, "message", "") or ""
                                            
                                            self.hardware.log(f"[ANCS-NOTIF] {app_id} | {title}: {message}")
                                            self.hardware.play_effect(14)
                                            await self.wake_display_async()
                                            
                                            try:
                                                self.notif_app.add_notification(app_id, f"{title}: {message}")
                                            except Exception:
                                                pass
                                except Exception as err:
                                    self.hardware.log(f"[ANCS-ERR] {err}")
                                    await asyncio.sleep(1.0)
                                
                                await asyncio.sleep(0.5)

                    self.hardware.log("[BLE] Spojení ztraceno. Obnovuji inzerci...")
                    self.watchface.update_status("W:off B:off")
                    known_notifications.clear()
                    self.memory_cleanup("Po odpojení BLE")
                    self.state.refresh_ble_advertising()
                    await asyncio.sleep(1)

            except Exception as err:
                self.hardware.log(f"[BLE-GLOBAL-ERR] {err}")
                await asyncio.sleep(2)

    async def hlidac_korunky_task(self):
        self.hardware.log("[Task] Hlídač korunky spuštěn.")
        self.hardware.write_register(
            self.PMU_ADDRESS,
            self.REG_IRQ_STATUS,
            self.hardware.read_register(self.PMU_ADDRESS, self.REG_IRQ_STATUS),
        )

        while True:
            try:
                irq_status = self.hardware.read_register(self.PMU_ADDRESS, self.REG_IRQ_STATUS)
                if irq_status > 0:
                    self.hardware.write_register(self.PMU_ADDRESS, self.REG_IRQ_STATUS, irq_status)
                    if irq_status in (2, 3):
                        self.hardware.log(f"[HARDWARE-OK] Korunka stisknuta! Status: {irq_status}")
                        self.state.register_activity()
                        
                        # STISK KORUNKY OPĚT OBNOVÍ HLEDÁNÍ TELEFONU (10 S)
                        self.state.ble_pause_advertising = False
                        
                        if not self.state.display_awake:
                            await self.wake_display_async()
                            self.hardware.play_effect(1)
                        else:
                            if self.state.current_state != self.state.STATE_WATCHFACE:
                                self.show_watchface("Návrat na Watchface")
                                self.hardware.log("[AKCE] Návrat na Ciferník")
                            else:
                                self.hardware.log("[AKCE] Uspávám displej...")
                                await self.sleep_display_async()
                        await asyncio.sleep(0.4)
            except Exception as err:
                self.hardware.log(f"[CROWN-ERR] {err}")
            
            await asyncio.sleep(0.05 if self.state.display_awake else 0.3)

    async def sprava_napajeni_task(self):
        self.hardware.log("[Task] Správa napájení spuštěna.")
        while True:
            try:
                now = time.monotonic()
                inactivity = now - self.state.last_activity
                usb_connected = supervisor.runtime.usb_connected
                if self.state.display_awake and not self.state.wifi_sync_in_progress and not usb_connected:
                    if inactivity > self.state.sleep_timeout_sec:
                        self.hardware.log(f"[POWER] Timeout vypršel ({inactivity:.1f}s). Uspávám displej...")
                        await self.sleep_display_async()
            except Exception as err:
                self.hardware.log(f"[POWER-TASK-ERR] {err}")
            await asyncio.sleep(0.5)

    async def pocitadlo_kroku_task(self):
        self.hardware.log("[Task] Počítadlo kroků spuštěno.")
        try:
            if self.hardware.rtc is not None:
                rtc_time = self.hardware.rtc.datetime
                self.state.last_date_str = f"{rtc_time.tm_year:04d}-{rtc_time.tm_mon:02d}-{rtc_time.tm_mday:02d}"
                db_data = self.step_db.load()
                self.state.steps_today = db_data.get(self.state.last_date_str, 0)
                self.state.last_step_milestone = self.state.steps_today // 1000
        except Exception:
            pass

        save_counter = 0
        while True:
            try:
                if self.hardware.rtc is not None:
                    rtc_time = self.hardware.rtc.datetime
                    current_date_str = f"{rtc_time.tm_year:04d}-{rtc_time.tm_mon:02d}-{rtc_time.tm_mday:02d}"
                    if current_date_str != self.state.last_date_str:
                        self.hardware.log(
                            f"[PŮLNOC] Archivuji kroky za den {self.state.last_date_str}: {self.state.steps_today}"
                        )
                        self.step_db.save_day(self.state.last_date_str, self.state.steps_today)
                        self.state.last_date_str = current_date_str
                        self.state.steps_today = 0
                        self.state.last_step_milestone = 0

                self.hardware.measure_steps(self.state)
                if self.state.display_awake:
                    self.watchface.update_steps(self.state.steps_today)

                save_counter += 1
                if save_counter >= 1500:
                    save_counter = 0
                    if self.state.last_date_str:
                        self.step_db.save_day(self.state.last_date_str, self.state.steps_today)
            except Exception as err:
                self.hardware.log(f"[KROKY-ERR] {err}")
            
            await asyncio.sleep(0.2 if self.state.display_awake else 0.4)

    async def graficka_smycka_hodin_task(self):
        self.hardware.log("[Task] Grafická smyčka hodin spuštěna.")
        last_second = -1

        while True:
            loop_start = time.monotonic()
            if self.state.display_awake and self.hardware.rtc is not None:
                try:
                    rtc_time = self.hardware.rtc.datetime
                    if self.state.current_state == self.state.STATE_WATCHFACE:
                        if rtc_time.tm_sec != last_second:
                            last_second = rtc_time.tm_sec
                            loop_duration = time.monotonic() - loop_start
                            if loop_duration > 0:
                                self.cpu_usage_cache = min(99, int((loop_duration / 0.2) * 100))
                            else:
                                self.cpu_usage_cache = 0
                            self.watchface.update_clock(rtc_time, self.cpu_usage_cache)

                        if rtc_time.tm_sec % 5 == 0:
                            self.watchface.update_memory(gc.mem_free() // 1024)

                        if rtc_time.tm_sec % 10 == 0:
                            battery_text, voltage_text = self.hardware.read_battery_strings()
                            self.watchface.update_battery(battery_text, voltage_text)

                    elif self.state.current_state == self.state.STATE_HWTEST:
                        battery_text, voltage_text = self.hardware.read_battery_strings()
                        if battery_text == " USB":
                            battery_text = "USB Připojeno"
                            voltage_text = "5000 mV"
                        self.hwtest_app.update_data(
                            battery_text,
                            voltage_text,
                            f"{rtc_time.tm_hour:02d}:{rtc_time.tm_min:02d}:{rtc_time.tm_sec:02d}",
                            gc.mem_free() // 1024,
                            self.cpu_usage_cache,
                        )
                except Exception as err:
                    self.hardware.log(f"[GUI-ERR] {err}")
                await asyncio.sleep(0.2)
            else:
                await asyncio.sleep(1.0)

    async def dotyk_a_gui_task(self):
        self.hardware.log("[Task] Dotyková obsluha spuštěna.")
        while True:
            try:
                event = self.touch.get_event()
                if event:
                    if not self.state.display_awake:
                        await self.wake_display_async()
                    self.state.register_activity()
                    event_type, x_pos, y_pos = event[0], event[1], event[2]

                    if self.state.current_state == self.state.STATE_WATCHFACE:
                        if event_type in ("TAP", "SWIPE_DOWN", "SWIPE_UP"):
                            self.hardware.log("[TOUCH] Otevírám MENU")
                            self.show_menu()

                    elif self.state.current_state == self.state.STATE_MENU:
                        if event_type == "TAP":
                            action = self.menu_app.handle_tap(x_pos, y_pos)
                            self.hardware.log(f"[MENU-TAP] Vybrána akce: {action}")
                            if action == "MOBLIN":
                                self.show_moblin()
                            elif action == "NOTIF":
                                self.show_notifications()
                            elif action == "HWTEST":
                                self.show_hwtest()
                            elif action == "BACK":
                                self.show_watchface("Zavření menu")

                    elif self.state.current_state == self.state.STATE_NOTIF:
                        action = self.notif_app.handle_event(event_type, x_pos, y_pos)
                        if action == "BACK":
                            self.show_menu()
                        elif action == "CLEARED":
                            self.hardware.play_effect(14)

                    elif self.state.current_state in (self.state.STATE_MOBLIN, self.state.STATE_HWTEST):
                        app = self.moblin_app if self.state.current_state == self.state.STATE_MOBLIN else self.hwtest_app
                        if event_type == "TAP" and app.handle_tap(x_pos, y_pos) == "BACK":
                            self.show_menu("Zavření aplikací")
            except Exception as err:
                self.hardware.log(f"[TOUCH-ERR] {err}")
            
            await asyncio.sleep(0.04 if self.state.display_awake else 0.2)

    async def main(self):
        self.hardware.log("Spouštím optimalizovaný CircuitPython OS pro T-Watch-S3...")
        await asyncio.gather(
            self.hlidac_korunky_task(),
            self.sprava_napajeni_task(),
            self.graficka_smycka_hodin_task(),
            self.wifi_cas_sync_task(),
            self.pocitadlo_kroku_task(),
            self.dotyk_a_gui_task(),
            self.ble_ancs_task(),
        )

    def cleanup(self):
        self.hardware.log("[SYSTEM] Zahajuji bezpečný úklid...")
        self.hardware.cleanup_ble()

        try:
            self.hardware.set_brightness(100)
            self.hardware.display.root_group = displayio.CIRCUITPYTHON_TERMINAL
            self.memory_cleanup("Závěrečný úklid")
        except Exception:
            pass

        self.hardware.unlock_i2c()
        self.hardware.log("[SYSTEM] Úklid dokončen.")


def run():
    runtime = WatchRuntime()
    should_reload = False
    
    try:
        asyncio.run(runtime.main())
    except KeyboardInterrupt:
        print("\n[REPL] Přerušeno uživatelem (Ctrl+C). Provádím bezpečné odpojení...")
        try:
            runtime.cleanup()
        except Exception as e:
            print(f"[CLEANUP-ERR] {e}")

    except MemoryError:
        print("[CRITICAL] Došla paměť RAM! Provádím hardwarový reset...")
        time.sleep(0.1)
        import microcontroller
        microcontroller.reset()

    except Exception as err:
        print(f"[CRASH] Neošetřená chyba: {type(err).__name__}: {err}")
        should_reload = True

    finally:
        if should_reload:
            time.sleep(1)
            supervisor.reload()