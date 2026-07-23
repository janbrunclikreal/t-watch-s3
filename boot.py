# info pro geminy - zachovat
# Adafruit CircuitPython 10.2.1 on 2026-05-13; LILYGO T-Watch-S3 with ESP32S3
# thonny 4.0.1 - nefunguje ukládání!
# viper-ide.org - částečné funkční ukládání
# devel hw - Acer chromebook Spin 514

# boot.py - aktualizováno
import storage
import supervisor

print("[BOOT] LILYGO T-Watch-S3 starting...")

usb_connected = supervisor.runtime.usb_connected

if not usb_connected:
    # Samostatný běh z baterie
    try:
        storage.remount("/", readonly=False)
        print("[BOOT] Úložiště odemčeno pro zápis z Pythonu.")
    except Exception as e:
        print(f"[BOOT-ERROR] Nelze odemknout úložiště: {e}")
else:
    print("[BOOT] Připojeno k PC (USB). Zápis z Pythonu zakázán.")
    # Zabraň automatickému spuštění code.py při vývoji (lze odkomentovat)
    # supervisor.set_next_code_file(None)