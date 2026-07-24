# T-Watch S3 – Optimalizovaný CircuitPython OS

`code.py` je firmware / operační systém pro chytré hodinky **LILYGO T-Watch S3**
běžící na **CircuitPythonu**. Jde o asynchronní runtime (vlastní `asyncio` tasky),
který obsluhuje ciferník, dotykové menu, krokoměr, BLE notifikace z iOS (ANCS),
NTP synchronizaci, haptickou odezvu a chytrou správu napájení.

> Cílový hardware: T-Watch-S3 (ESP32-S3) s **displejem**, **dotykovou vrstvou**,
> **AXP2101** (PMU), **PCF8563** (RTC), **BMA423** (akcelerometr),
> **DRV2605** (haptika) a **Wi-Fi / BLE** modulem.

---

## 🧭 Hlavní funkce

| Oblast | Co dělá |
|---|---|
| ⌚ **Watchface** | Ciferník s časem, datem, Wi-Fi/BLE stavem, baterií, CPU loadem, RAM a napětím |
| 📱 **Bluetooth ANCS** | Příjem notifikací z iPhonu (Apple Notification Center Service) přes BLE |
| 🚶 **Krokoměr** | Počítání kroků z akcelerometru BMA423 s denním přepisem a historií 90 dní |
| ⏰ **RTC (PCF8563)** | Hardwarové hodiny s možností zálohy bez Wi-Fi; NTP sync přes evrop.pool.ntp.org |
| 📡 **Wi-Fi NTP sync** | Jednorázová synchronizace času z NTP při startu (pokud RTC nemá platný čas) |
| 🎛 **Menu & Aplikace** | `Moblin`, `HwTest`, `Notifications` – vlastní `Group`-y s dotykovou obsluhou |
| 🔋 **Správa napájení** | Dynamická frekvence CPU (80 / 160 / 240 MHz), sleep displeje, vypínání Wi-Fi/BLE |
| 🔘 **Hardwarová korunka** | Krátký stisk = návrat na ciferník / uspání displeje (přes IRQ registr AXP2101) |
| 📳 **Haptika DRV2605** | Krátká vibrace na notifikaci, na milník 1 000 kroků a na vyčištění notifikací |
| 📊 **Diagnostika** | Výpis do REPLu s milisekundovým časovým razítkem `[HH:MM:SS.mmm]` |

---

## 🗂 Architektura

Kód je rozdělený na nezávislé `asyncio` korutiny spouštěné v `main()`:

```
asyncio.gather(
    hlidac_korunky_task(),          # IRQ z AXP2101 – korunka / tlačítko
    sprava_napajeni_task(),         # Auto-sleep displeje (10 s neaktivity)
    graficka_smycka_hodin_task(),   # Update textů ciferníku, CPU load
    wifi_cas_sync_task(),           # Jednorázový NTP sync
    pocitadlo_kroku_task(),         # BMA423 krokoměr + zápis do /kroky_db.json
    dotyk_a_gui_task(),             # TouchController + přepínání stavů
    ble_ancs_task(),                # iOS notifikace přes ANCS
)
```

Stavový automat (top-level `current_state`):

```
WATCHFACE ⇄ MENU ⇄ MOBLIN
            ⇄ HWTEST
            ⇄ NOTIF
```

Korunka vždycky skočí zpět na `WATCHFACE`. Pokud už na něm jste, displej se
plynule uspí přes `display.brightness`.

---

## 📁 Požadované soubory na zařízení (`CIRCUITPY`)

```
/code.py                      # tento firmware
/modules/touch.py             # TouchController (I2C dotykový driver)
/modules/app_menu.py          # AppMenu
/modules/app_moblin.py        # AppMoblin
/modules/app_hwtest.py        # AppHwTest
/modules/app_notifications.py # AppNotifications
/modules/bma423.py            # driver BMA423
/modules/axp2101.py           # driver AXP2101 PMU
/modules/adafruit_pcf8563/    # RTC
/modules/adafruit_drv2605.mpy
/modules/adafruit_display_text/
/modules/adafruit_ble/        # + adafruit_ble_apple_notification_center
/kroky_db.json                # vytvoří se automaticky
```

> Moduly v `/modules` musí odpovídat verzi vašeho CircuitPythonu
> (doporučeno **9.x** pro ESP32-S3).

---

## 🔧 Konfigurace (env proměnné)

Nastavuje se přes `settings.toml` v `CIRCUITPY`, nebo přes `os.getenv()`:

```toml
# settings.toml
CIRCUITPYTHON_WIFI_SSID = "vas-wifi"
CIRCUITPYTHON_WIFI_PASSWORD = "vas-heslo"
TIMEZONE_OFFSET = 2            # SELČ / letní čas ČR
```

| Proměnná | Význam |
|---|---|
| `CIRCUITPYTHON_WIFI_SSID` | SSID Wi-Fi sítě (pro NTP) |
| `CIRCUITPYTHON_WIFI_PASSWORD` | Heslo k Wi-Fi |
| `TIMEZONE_OFFSET` | Offset vůči UTC v hodinách (např. `2` pro ČR) |

Pokud RTC již obsahuje platný čas (`year >= 2026`), **Wi-Fi sync se přeskočí**
a modul běží zcela offline.

---

## 🚀 Instalace

1. **Připravte T-Watch S3**
   * Stáhněte [CircuitPython UF2 pro ESP32-S3](https://circuitpython.org/board/lilygo_twatch_s3/)
     a flashněte jej přes bootloader (dvakrát rychle `RST`).
2. **Nahrajte knihovny**
   * Rozbalte `adafruit-circuitpython-bundle` a zkopírujte potřebné `.mpy`
     do `/lib` na disku `CIRCUITPY`.
3. **Přidejte vlastní moduly** (viz výše) do `/modules`.
4. **Vložte `code.py`**
   * Obsah tohoto repozitáře nahrajte jako `code.py` na `CIRCUITPY`.
5. **Nastavte `settings.toml`** (volitelně – pokud chcete Wi-Fi sync).
6. **Restartujte hodinky** – měl by naskočit ciferník.

---

## 🛠 Hardwarové IO mapa (I²C)

| Adresa | Zařízení | Poznámka |
|---|---|---|
| `0x34` | AXP2101 | PMU (power management) |
| `0x51` | PCF8563 | RTC hodiny reálného času |
| `0x5A` | DRV2605 | Haptický driver (LRA motor) |
| `0x19` | BMA423 | Akcelerometr + krokoměr |

`board.I2C()` je sdílená sběrnice; driver AXP2101 navíc vyžaduje
**přímé čtení IRQ registru** (`0x49`) přes `try_lock()` – v kódu je to
řešeno bezpečným `try/finally` patternem.

---

## 🔋 Profil spotřeby (orientačně)

| Režim | CPU | Displej | BLE | Wi-Fi |
|---|---|---|---|---|
| Ciferník | 80 MHz | 90 % | reklama (iOS) | off |
| Menu | 160 MHz | 90 % | reklama (iOS) | off |
| Moblin | 240 MHz | 90 % | reklama (iOS) | off |
| HwTest | 80 MHz | 90 % | reklama (iOS) | off |
| Sleep | 80 MHz | 0 % | pause 30 s | off |

Displej se automaticky uspí po **10 s** neaktivity, pokud není připojeno USB
a neprobíhá Wi-Fi sync.

---

## 🧠 Krokoměr – detaily

* Prahová hodnota: `magnitude > 1.18` (m/s²), s debounce **330 ms**.
* Milník vibrace: každých **1 000 kroků** (`Effect(14)`).
* Denní reset v `00:00` (přes RTC); předchozí den se uloží do
  `/kroky_db.json` (max. **90 dní** historie, FIFO).
* Zápis na flash probíhá každých **1500 smyček** (= ~5 min) a při přechodu
  dne. Pokud je zařízení připojeno k PC (read-only mount), zápis se taktéž
  přeskočí – počítadlo se nevytratí, jen se neuloží.

---

## 📡 BLE ANCS (iOS notifikace)

* Inzerce přes `SolicitServicesAdvertisement` – vyžaduje **spárování** v iOS
  (Systém → Bluetooth → spárovat ručně).
* Set aktivních notifikací je omezen na **50 ID** – pak se vyčistí, aby
  nedošlo k memory leaku.
* Pokud telefon není připojen **do 30 s**, reklama se vypne (úspora
  energie) a obnoví se při další aktivitě.
* Na příchozí notifikaci: krátká vibrace + probuzení displeje + uložení
  do `AppNotifications` (přepne stav do `NOTIF`).

> Android nativně ANCS nepodporuje. Pro Android by bylo nutné přidat
> vlastní GATT službu (mimo rozsah tohoto firmware).

---

## 🧪 Ladění a logy

Připojte se přes **REPL** (Mu editor, `screen`, nebo `mpremote`). Výstup
vypadá takto:

```
[12:34:56.421] [POWER] CPU nastaveno na 80 MHz.
[12:34:57.103] [NTP-Sync] Připojuji se k Wi-Fi...
[12:34:59.842] [NTP-Sync] RTC aktualizováno: 12:34
[12:35:00.117] [BLE] Spouštím inzerci pro ANCS...
[12:35:30.512] [BLE-POWER] Timeout inzerce (30 s) vypršel! Vypínám BLE rádio...
[12:36:01.004] [TOUCH] Otevírám MENU
[12:36:05.880] [MENU-TAP] Vybrána akce: MOBLIN
```

Každá zpráva má prefix `[MM:SS.mmm]` z `time.monotonic()`, dokud není
dostupné RTC – pak se používá skutečný čas.

---

## ❗ Řešení problémů

| Problém | Řešení |
|---|---|
| Hodinky stále resetují | Zkontrolujte, zda je PMU AXP2101 inicializovaná (`PMU-INIT-ERR`). |
| Displej je bílý / nic | `display.brightness` je 0 – stiskněte korunku. |
| ANCS nefunguje | Na iPhonu zrušte párování a spárujte znovu přes Bluetooth nastavení. |
| Notifikace nezobrazuje | Aplikace musí v iOS povolit „Oznámení“ pro Notification Center. |
| `MemoryError` | Snížení `len(posledni_zname_notifikace)` limitu nebo vypnutí Moblin. |
| Čas se nedaří synchronizovat | Wi-Fi přihlašovací údaje špatné, nebo blokován port 123 (NTP). |

---

## 🧾 Licence

Tento firmware je interní projekt autora. Knihovny třetích stran
(Adafruit, LILYGO, BMA423, aj.) se řídí jejich vlastními licencemi.

---

## ✅ TODO / Nápady

- [ ] Vlastní ciferníky (bitmapa + analogové ručičky)
- [ ] Počasí přes OpenWeatherMap (jen přes Wi-Fi)
- [ ] Stopky / budík v menu
- [ ] Aplikace „Music control" přes BLE GATT
- [ ] OTA update přes Wi-Fi (`.uf2` z GitHubu)
