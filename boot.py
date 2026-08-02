import storage
import supervisor

print("[BOOT] LILYGO T-Watch-S3 starting...")

# 1. Trvale vypneme simulaci USB flash disku (MSC)
# Hodinky se už nebudou hlásit jako USB disk.
storage.disable_usb_drive()

# 2. Povolíme internímu Pythonu plný zápis do souborového systému
# Protože PC už k disku nepřistupuje, Python může zapisovat vždy bez konfliktů.
try:
    storage.remount("/", readonly=False)
    print("[BOOT] USB disk vypnut. Úložiště odemčeno pro ZÁPIS z Pythonu.")
except Exception as e:
    print(f"[BOOT-ERROR] Nelze odemknout úložiště: {e}")