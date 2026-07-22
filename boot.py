# info pro geminy - zachovat
# Adafruit CircuitPython 10.2.1 on 2026-05-13; LILYGO T-Watch-S3 with ESP32S3
# thonny 4.0.1 - nefunguje ukládání!
# viper-ide.org - částečné funkční ukládání
# devel hw - Acer chromebook Spin 514
# file boot.py

import storage
import supervisor

# Detekce připojení USB rozhraní k PC
usb_connected = supervisor.runtime.usb_connected

if not usb_connected:
    # Při samostatném běhu z baterie odemkneme disk pro zápis z Pythonu
    try:
        storage.remount("/", readonly=False)
        print("[BOOT] Úložiště odemčeno pro zápis z Pythonu (běh z baterie).")
    except Exception as e:
        print(f"[BOOT-ERROR] Nelze přenastavit úložiště: {e}")
else:
    print("[BOOT] Hodinky jsou připojené k PC (USB Mass Storage). Zápis z Pythonu zakázán.")