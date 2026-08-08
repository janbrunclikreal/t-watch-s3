import storage
import supervisor

print("[BOOT] Spoustim LILYGO T-Watch-S3...")

supervisor.runtime.autoreload = False
print("[BOOT] Auto-reload: vypnut.")

# Hodinky se uz nebudou hlasit jako USB flash disk.
storage.disable_usb_drive()
print("[BOOT] USB disk (MSC): vypnut.")

# CircuitPython muze zapisovat, protoze USB disk uz nema pristup ke stejnemu ulozisti.
try:
    storage.remount("/", readonly=False)
    print("[BOOT] Uloziste: zapis povolen pro CircuitPython.")
except Exception as error:
    print(f"[BOOT-ERROR] Nelze povolit zapis do uloziste: {error}")