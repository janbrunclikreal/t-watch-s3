import os
import time

import _bleio
import adafruit_ntp
import board
import microcontroller
import socketpool
import wifi
from adafruit_drv2605 import DRV2605, Effect
from adafruit_pcf8563.pcf8563 import PCF8563
from axp2101 import AXP2101
import bma423


class WatchHardware:
    DB_FILE = "/kroky_db.json"
    PMU_ADDRESS = 0x34

    def __init__(self):
        self.radio = None
        self.ble_available = False
        self.SolicitServicesAdvertisement = None
        self.ancs = None
        self._initialize_ble()

        self.i2c = board.I2C()
        self.pmu = self._initialize_pmu()
        time.sleep(0.05)
        self.rtc = self._initialize_rtc()
        self.wifi_ssid = os.getenv("CIRCUITPYTHON_WIFI_SSID")
        self.wifi_pass = os.getenv("CIRCUITPYTHON_WIFI_PASSWORD")
        self.timezone_offset = int(os.getenv("TIMEZONE_OFFSET", "2"))
        self.force_ntp_sync = self._parse_bool_env("FORCE_NTP_SYNC", False)
        self.drv = self._initialize_haptics()
        self.display = board.DISPLAY
        self.bma_sensor = self._initialize_bma423()

    def _parse_bool_env(self, key, default=False):
        value = os.getenv(key)
        if value is None:
            return default
        value = value.strip().lower()
        return value in ("1", "true", "yes", "on")

    def _initialize_ble(self):
        try:
            import adafruit_ble
            from adafruit_ble.advertising.standard import SolicitServicesAdvertisement
            import adafruit_ble_apple_notification_center as ancs

            self.radio = adafruit_ble.BLERadio()
            
            # ZKRÁCENÝ NÁZEV: Vejde se do 31bajtového limitu vedle 128bitového ANCS UUID
            self.radio.name = "TW-S3"
            
            self.SolicitServicesAdvertisement = SolicitServicesAdvertisement
            self.ancs = ancs
            self.ble_available = True
            self.log("[BLE] BLE adaptér připraven (Solicit ANCS).")
        except Exception as err:
            self.log(f"[BLE-INIT-ERR] {err}")
            self.ble_available = False

    def _initialize_pmu(self):
        try:
            pmu = AXP2101(self.i2c)
            for method_name in (
                "enable_aldo1",
                "enable_aldo2",
                "enable_aldo3",
                "enable_aldo4",
                "enable_dldo1",
            ):
                if hasattr(pmu, method_name):
                    try:
                        getattr(pmu, method_name)()
                    except Exception:
                        pass
            return pmu
        except Exception as err:
            print(f"[PMU-INIT-ERR] {err}")
            return None

    def _initialize_rtc(self):
        try:
            return PCF8563(self.i2c)
        except Exception as err:
            print(f"[RTC-INIT-ERR] {err}")
            return None

    def _initialize_haptics(self):
        try:
            drv = DRV2605(self.i2c)
            drv.sequence[0] = Effect(1)
            drv.play()
            return drv
        except Exception as err:
            self.log(f"[DRV-ERR] Nelze inicializovat haptiku: {err}")
            return None

    def _initialize_bma423(self):
        try:
            sensor = bma423.BMA423(self.i2c)
            self.log("[BMA423] Akcelerometr v režimu G-Force inicializován.")
            return sensor
        except Exception as err:
            self.log(f"[BMA423-ERR] {err}")
            return None

    def log(self, message):
        try:
            rtc_time = self.rtc.datetime
            ms = int((time.monotonic() % 1) * 1000)
            time_str = f"{rtc_time.tm_hour:02d}:{rtc_time.tm_min:02d}:{rtc_time.tm_sec:02d}.{ms:03d}"
        except Exception:
            monotonic_time = time.monotonic()
            seconds = int(monotonic_time)
            ms = int((monotonic_time % 1) * 1000)
            time_str = f"{seconds}s.{ms:03d}"
        print(f"[{time_str}] {message}")

    def set_cpu_frequency(self, freq_hz):
        try:
            if microcontroller.cpu.frequency != freq_hz:
                microcontroller.cpu.frequency = freq_hz
                self.log(f"[POWER] CPU nastaveno na {freq_hz // 1000000} MHz.")
        except Exception as err:
            self.log(f"[POWER-ERR] Nelze změnit frekvenci CPU: {err}")

    def set_brightness(self, percent):
        self.display.brightness = percent / 100

    def play_effect(self, effect_id=14):
        """Přehrání haptického efektu bez blokování smyčky."""
        try:
            if self.drv is not None:
                self.drv.sequence[0] = Effect(effect_id)
                self.drv.play()
        except Exception:
            pass

    def has_valid_rtc_time(self):
        try:
            return self.rtc is not None and self.rtc.datetime.tm_year >= 2026
        except Exception:
            return False

    def sync_time(self):
        if not self.wifi_ssid or not self.wifi_pass:
            raise ValueError("Chybí CIRCUITPYTHON_WIFI_SSID nebo CIRCUITPYTHON_WIFI_PASSWORD")
        wifi.radio.enabled = True
        wifi.radio.connect(self.wifi_ssid, self.wifi_pass)
        pool = socketpool.SocketPool(wifi.radio)
        ntp = adafruit_ntp.NTP(pool, server="europe.pool.ntp.org", tz_offset=0)
        ntp_time_utc = ntp.datetime
        seconds_utc = time.mktime(ntp_time_utc)
        local_time = time.localtime(seconds_utc + (self.timezone_offset * 3600))
        if self.rtc is not None:
            self.rtc.datetime = local_time
        return local_time

    def disable_wifi(self):
        try:
            wifi.radio.enabled = False
        except Exception:
            pass

    def is_usb_powered(self):
        """Přímé zjištění 5V napájení z AXP2101 PMU."""
        try:
            if self.pmu is not None:
                if hasattr(self.pmu, "is_vbus_in"):
                    return self.pmu.is_vbus_in()
                status = self.read_register(self.PMU_ADDRESS, 0x00)
                return (status & 0x20) != 0
        except Exception:
            pass
        return False

    def read_battery_strings(self):
        try:
            if self.pmu is not None:
                if self.is_usb_powered():
                    return " USB", "USB PWR"
                if hasattr(self.pmu, "battery_level"):
                    return f"{self.pmu.battery_level}%", f"{self.pmu.battery_voltage} mV"
            return "--%", "---- mV"
        except Exception:
            return "--%", "---- mV"

    def read_battery_info(self):
        """Vrací přesná čísla (procenta, napětí v mV) pro spravu_napajeni_task."""
        try:
            if self.pmu is not None:
                level = getattr(self.pmu, "battery_level", 50)
                voltage = getattr(self.pmu, "battery_voltage", 3700)
                return level, voltage
        except Exception:
            pass
        return 50, 3700

    def measure_steps(self, state):
        """Optimalizovaná detekce kroků bez použití těžké operace math.sqrt()."""
        if self.bma_sensor is None:
            return state.steps_today

        try:
            x_val, y_val, z_val = self.bma_sensor.acceleration
            acc_sum = (x_val * x_val) + (y_val * y_val) + (z_val * z_val)
            now = time.monotonic()

            if acc_sum > 1.3924 and getattr(state, "last_acc_sum", 0) <= 1.3924:
                if (now - state.last_step_time) > 0.33:
                    state.steps_today += 1
                    state.last_step_time = now

                    current_thousand = state.steps_today // 1000
                    if current_thousand > state.last_step_milestone:
                        state.last_step_milestone = current_thousand
                        self.play_effect(14)

            state.last_acc_sum = acc_sum
        except Exception:
            pass

        return state.steps_today

    def read_register(self, address, register):
        """Bezpečné čtení I2C s ošetřením výjimek."""
        try:
            deadline = time.monotonic() + 0.05
            while not self.i2c.try_lock():
                if time.monotonic() > deadline:
                    return 0
                time.sleep(0.001)
            try:
                buffer = bytearray(1)
                self.i2c.writeto_then_readfrom(address, bytes([register]), buffer)
                return buffer[0]
            finally:
                self.i2c.unlock()
        except Exception:
            pass
        return 0

    def write_register(self, address, register, value):
        """Bezpečný zápis na I2C s ošetřením výjimek."""
        try:
            deadline = time.monotonic() + 0.05
            while not self.i2c.try_lock():
                if time.monotonic() > deadline:
                    return
                time.sleep(0.001)
            try:
                self.i2c.writeto(address, bytes([register, value]))
            finally:
                self.i2c.unlock()
        except Exception:
            pass

    def create_ancs_advertisement(self):
        if not self.ble_available or self.SolicitServicesAdvertisement is None or self.ancs is None:
            return None

        try:
            # Ponecháme čistý SolicitServicesAdvertisement
            advertisement = self.SolicitServicesAdvertisement()
            advertisement.solicited_services.append(self.ancs.AppleNotificationCenterService)
            return advertisement
        except Exception as err:
            self.log(f"[BLE-ADV-ERR] Selhalo vytvoření inzerce: {err}")
            return None

    def cleanup_ble(self):
        try:
            if self.radio is not None:
                if hasattr(self.radio, "advertising") and self.radio.advertising:
                    self.radio.stop_advertising()
                if self.radio.connected:
                    for connection in list(self.radio.connections):
                        try:
                            connection.disconnect()
                        except Exception:
                            pass
                _bleio.adapter.enabled = False
                time.sleep(0.1)
                _bleio.adapter.enabled = True
                self.log("[BLE] BLE adaptér resetován.")
        except Exception as err:
            self.log(f"[BLE-CLEANUP] {err}")

    def unlock_i2c(self):
        try:
            self.i2c.unlock()
            self.log("[I2C] Sběrnice odemčena.")
        except Exception:
            pass