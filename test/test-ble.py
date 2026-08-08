import gc
import time

try:
    import adafruit_ble
except ImportError as exc:  # pragma: no cover - runtime only
    print("[BLE-ERR] Nelze importovat adafruit_ble:", exc)
    raise

try:
    import _bleio
except ImportError:  # pragma: no cover - runtime only
    _bleio = None


class BLEDiagnostic:
    def __init__(self):
        self.radio = None
        self.last_scan = []

    def initialize(self):
        print("=========================================")
        print("       DIAGNOSTIKA BLE RÁDIA            ")
        print("=========================================")
        gc.collect()

        print("\n[1/4] Inicializuji BLE rádio...")
        try:
            self.radio = adafruit_ble.BLERadio()
            self.radio.name = "TW-S3-DIAG"
            print("[OK] BLE rádio inicializováno.")
            return True
        except Exception as err:
            print("[ERR] Inicializace selhala:", err)
            return False

    def scan_surroundings(self, timeout=2):
        print(f"\n[2/4] Skenuji okolí BLE po {timeout} s...")
        if self.radio is None:
            print("[WARN] BLE rádio není dostupné, skenování přeskočeno.")
            return []

        results = []
        try:
            if hasattr(self.radio, "start_scan"):
                try:
                    entries = self.radio.start_scan(timeout=timeout)
                except TypeError:
                    self.radio.start_scan(timeout=timeout)
                    entries = []

                if entries is not None:
                    for entry in entries:
                        try:
                            results.append(
                                {
                                    "address": str(getattr(entry, "address", "")),
                                    "name": getattr(entry, "complete_name", None)
                                    or getattr(entry, "name", None),
                                    "rssi": getattr(entry, "rssi", None),
                                    "connectable": getattr(entry, "connectable", None),
                                }
                            )
                        except Exception:
                            pass
                else:
                    time.sleep(timeout)
            else:
                print("[WARN] start_scan není dostupné v této verzi knihovny.")

            if hasattr(self.radio, "stop_scan"):
                self.radio.stop_scan()
        except Exception as err:
            print("[ERR] Skenování selhalo:", err)

        self.last_scan = results
        if results:
            for item in results:
                print(
                    "  -> {address} | {name} | RSSI {rssi} | connectable={connectable}".format(
                        address=item.get("address") or "?",
                        name=item.get("name") or "<bez názvu>",
                        rssi=item.get("rssi"),
                        connectable=item.get("connectable"),
                    )
                )
        else:
            print("[INFO] Nebyla nalezena žádná BLE zařízení.")

        gc.collect()
        return results

    def sleep_radio(self):
        print("\n[3/4] Testuji uspání a probuzení BLE rádia...")
        if self.radio is None:
            print("[WARN] BLE rádio není dostupné, krok přeskočen.")
            return False

        try:
            if hasattr(self.radio, "enabled"):
                self.radio.enabled = False
            time.sleep(0.1)
            if hasattr(self.radio, "enabled"):
                self.radio.enabled = True
            print("[OK] BLE rádio bylo uspáno a opět aktivováno.")
            gc.collect()
            return True
        except Exception as err:
            print("[ERR] Uspání selhalo:", err)
            return False

    def cleanup(self):
        print("\n[4/4] Bezpečně ukončuji BLE rádio a uvolňuji prostředky...")
        try:
            if self.radio is not None:
                if hasattr(self.radio, "stop_scan"):
                    self.radio.stop_scan()
                if hasattr(self.radio, "stop_advertising"):
                    self.radio.stop_advertising()

                connections = getattr(self.radio, "connections", None)
                if connections is not None:
                    for connection in list(connections):
                        try:
                            connection.disconnect()
                        except Exception:
                            pass

                if hasattr(self.radio, "enabled"):
                    self.radio.enabled = False

                self.radio = None
        except Exception as err:
            print("[ERR] Cleanup selhalo:", err)

        if _bleio is not None:
            try:
                if hasattr(_bleio, "adapter") and hasattr(_bleio.adapter, "enabled"):
                    _bleio.adapter.enabled = False
                    time.sleep(0.05)
                    _bleio.adapter.enabled = True
            except Exception as err:
                print("[WARN] Reset adapteru selhal:", err)

        gc.collect()
        print("[OK] BLE rádio bylo bezpečně uvolněno.")


def main():
    diagnostic = BLEDiagnostic()
    try:
        if not diagnostic.initialize():
            return
        diagnostic.scan_surroundings(timeout=2)
        diagnostic.sleep_radio()
    finally:
        diagnostic.cleanup()


if __name__ == "__main__":
    main()
