# T-Watch S3 pro CircuitPython

Firmware pro LILYGO T-Watch S3 postavený nad CircuitPythonem. Projekt spouští jednoduchý asynchronní runtime pro ciferník, menu, diagnostiku hardware, krokoměr a BLE notifikace z iPhonu přes ANCS.

Repozitář dnes odpovídá stavu funkčního základu systému s několika jednoduchými aplikacemi. Ne všechny obrazovky jsou plnohodnotné aplikace; `Moblin` je zatím jen statická obrazovka bez aktivní integrace.

## Co projekt aktuálně umí

- Zobrazit watchface s časem, datem, stavem Wi‑Fi/BLE, baterií, RAM, napětím a odhadovaným vytížením hlavní smyčky.
- Po startu synchronizovat čas přes Wi‑Fi a NTP, pokud RTC nemá platný čas nebo je zapnuté `FORCE_NTP_SYNC`.
- Číst čas z RTC PCF8563 a běžet i offline, pokud už je RTC platné.
- Měřit kroky z akcelerometru BMA423 a ukládat denní historii do `/kroky_db.json`.
- Přijímat iOS notifikace přes BLE ANCS, zobrazit je na displeji a upozornit vibrací.
- Uspat displej po neaktivitě a probudit ho dotykem nebo korunkou.
- Nabídnout jednoduché aplikace `Notifications`, `HW Test` a `Moblin`.

## Co je dobré vědět

- `Moblin` není napojený na žádnou službu; jde jen o placeholder obrazovku.
- BLE notifikace jsou určené pro iPhone a ANCS. Android není podporovaný.
- `boot.py` vypíná USB mass storage, takže po nasazení není disk `CIRCUITPY` běžně dostupný přes USB.

## Architektura

Entrypoint je velmi tenký:

```py
import sys

sys.path.append("/modules")

from watch_runtime import run

run()
```

Hlavní logika je v `WatchRuntime`, který spouští tyto tasky:

```py
asyncio.gather(
    hlidac_korunky_task(),
    sprava_napajeni_task(),
    graficka_smycka_hodin_task(),
    wifi_cas_sync_task(),
    pocitadlo_kroku_task(),
    dotyk_a_gui_task(),
    ble_ancs_task(),
)
```

Stavy UI:

```text
WATCHFACE <-> MENU <-> MOBLIN
                  <-> HWTEST
                  <-> NOTIF
```

Korunka vždy vrací uživatele na watchface. Pokud už je watchface aktivní, další stisk displej uspí.

## Ovládání

- Na watchface otevře menu klepnutí i vertikální swipe.
- V `Notifications` swipe dolů smaže všechny notifikace.
- V `Notifications` swipe nahoru vrací zpět do menu.
- V `Notifications` spodní tlačítka listují mezi staršími a novějšími zprávami.
- V `HW Test` a `Moblin` spodní část displeje vrací zpět do menu.

## Aktuální chování systému

- CPU je při startu nastavené na fixních `80 MHz`.
- Jas displeje se běžně používá na `80 %` a při uspání plynule klesá na `0 %`.
- Displej se uspí po `10 s` neaktivity, pokud neběží Wi‑Fi sync a není připojené USB.
- V režimu spánku runtime preferuje nízkou spotřebu: CPU se sníží na `40 MHz`, dotyk se aktivně nepolluje a primární probuzení je korunkou.
- Notifikace přijaté přes BLE ve spánku se ukládají do fronty a zobrazí se po probuzení korunkou.
- BLE reklama pro ANCS se po `10 s` bez připojení pozastaví a obnoví se další aktivitou uživatele.
- Historie notifikací v UI drží maximálně `15` položek.
- Runtime si kvůli paměti drží omezenou množinu již zpracovaných ANCS ID.

## Struktura projektu

```text
boot.py
code.py
kroky_db.json
settings.toml
modules/
  app_hwtest.py
  app_menu.py
  app_moblin.py
  app_notifications.py
  watch_hardware.py
  watch_runtime.py
  watch_state.py
  watch_storage.py
  watch_ui.py
lib/
  touch.py
test/
  i2c-scanner.py
  start-boot.py
  test-bma423.py
  test-dotik.py
  test-wifi.py
```

Poznámka k dotyku: runtime importuje `TouchController` z `touch`, což v tomto repozitáři znamená `lib/touch.py`, ne soubor v `modules/`.

## Hardware a I2C

Projekt počítá s hardwarem LILYGO T-Watch S3 a s těmito periferiemi:

- displej přes `board.DISPLAY`
- dotykový kontroler přes `board.TOUCH_I2C()`
- PMU `AXP2101`
- RTC `PCF8563`
- haptika `DRV2605`
- akcelerometr `BMA423`
- Wi‑Fi a BLE na ESP32-S3

Použité I2C adresy:

| Adresa | Zařízení |
|---|---|
| `0x34` | AXP2101 |
| `0x51` | PCF8563 |
| `0x5A` | DRV2605 |
| `0x19` | BMA423 |
| `0x38` | FocalTouch |

## Závislosti

V `lib/` jsou jen některé knihovny. Aktuální kód očekává zejména tyto závislosti:

- `adafruit_ntp`
- `adafruit_drv2605`
- `adafruit_pcf8563`
- `adafruit_ble`
- `adafruit_ble_apple_notification_center`
- `adafruit_display_text`
- `adafruit_focaltouch`
- `axp2101`
- `bma423`
- `asyncio` pro CircuitPython

Pokud některá z nich chybí, runtime často poběží dál v omezeném režimu a zapíše chybu do logu.

## Konfigurace

Konfigurace se čte ze `settings.toml` přes `os.getenv()`:

```toml
CIRCUITPYTHON_WIFI_SSID = "TVOJE_WIFI"
CIRCUITPYTHON_WIFI_PASSWORD = "TVOJE_HESLO"
TIMEZONE_OFFSET = "2"
FORCE_NTP_SYNC = "true"
```

| Proměnná | Význam |
|---|---|
| `CIRCUITPYTHON_WIFI_SSID` | Wi‑Fi síť pro NTP synchronizaci |
| `CIRCUITPYTHON_WIFI_PASSWORD` | Heslo k Wi‑Fi |
| `TIMEZONE_OFFSET` | Posun vůči UTC v hodinách |
| `FORCE_NTP_SYNC` | Vynutí NTP sync i při platném RTC |

RTC je považované za platné, pokud je `tm_year >= 2026`.

## Nasazení do hodinek

1. Nahrajte kompatibilní CircuitPython pro LILYGO T-Watch S3.
2. Zkopírujte `code.py`, adresář `modules/` a potřebné knihovny do `CIRCUITPY`.
3. Doplňte `settings.toml`.
4. Pokud chcete zachovat možnost přímého přístupu k disku `CIRCUITPY`, upravte nebo dočasně vynechte `boot.py`.
5. Restartujte zařízení.

`boot.py` aktuálně:

- vypne USB mass storage přes `storage.disable_usb_drive()`
- remountne interní filesystem pro zápis z Pythonu

To je vhodné pro průběžné ukládání kroků, ale komplikuje další kopírování souborů přes USB.

### Automatický deploy skript (Chromebook + CIRCUITPY)

V repozitáři je připravený skript `scripts/deploy_circuitpy.sh`, který:

- před synchronizací pošle do serial portu `Ctrl+C` (zastavení běžícího interpretu),
- ověří, že je mount `CIRCUITPY` zapisovatelný (včetně write testu),
- nasadí změny přes `rsync`,
- vynechá `settings.toml`, `kroky_db.json` a `boot_out.txt`.

Spuštění z konzole v rootu repozitáře:

```sh
./scripts/deploy_circuitpy.sh
```

Volitelně lze explicitně nastavit mount a serial port:

```sh
CIRCUITPY_MOUNT=/mnt/chromeos/removable/CIRCUITPY SERIAL_PORT=/dev/ttyACM0 ./scripts/deploy_circuitpy.sh
```

Nejdřív je možné spustit bezpečný náhled změn bez zápisu:

```sh
DRY_RUN=1 ./scripts/deploy_circuitpy.sh
```

Vynucení přítomnosti serial portu (strict režim):

```sh
REQUIRE_SERIAL=1 SERIAL_PORT=/dev/ttyACM0 ./scripts/deploy_circuitpy.sh
```

WebSerial režim (Chromebook, bez Linux serial portu):

```sh
WEBSERIAL_BREAK=1 ./scripts/deploy_circuitpy.sh
```

Skript v tomto režimu počká na potvrzení. Nejprve v otevřené WebSerial konzoli pošli `Ctrl+C` a po návratu do REPL potvrď pokračování Enterem v terminálu.

Poznámka: pokud je filesystém hodinek v read-only režimu, skript skončí chybou a vypíše doporučení, jak postupovat (odpojit/připojit zařízení, zkontrolovat `boot.py`, restartovat hodinky).

Troubleshooting pro Chromebook/Crostini:

- Skript používá `rsync` bez změn owner/group/perms, aby nepadal na USB/CIRCUITPY mountu.
- Systémové položky jako `.Trashes` nebo `.fseventsd` jsou při `--delete` chráněné a nemažou se.
- Na Chromebooku se USB zařízení často přepíná mezi Chrome a Linuxem. Když je dostupný disk `CIRCUITPY`, serial port v Linuxu nemusí být vidět. V tom případě skript běží bez `Ctrl+C` (informativní hláška, ne chyba).
- Pokud používáš WebSerial, doporučený postup je `WEBSERIAL_BREAK=1`, ručně poslat `Ctrl+C` do WebSerial relace a pak potvrdit deploy v terminálu.

## Ukládání kroků

- Databáze kroků je v souboru `/kroky_db.json`.
- Při startu se načte hodnota pro aktuální den z RTC.
- Při změně dne se starý den uloží a počítadlo se vynuluje.
- Databáze si drží maximálně posledních `90` dní.
- Průběžné uložení probíhá po `1500` iteracích smyčky.
- Pokud zápis selže kvůli read-only mountu, chyba se zaloguje a běh pokračuje.

Detekce kroku v aktuálním kódu:

- práh je `acc_sum > 1.3924`
- debounce mezi kroky je `0.33 s`
- při každých `1000` krocích se spustí haptický efekt `14`

## BLE notifikace

- Používá se `SolicitServicesAdvertisement` pro Apple Notification Center Service.
- Po připojení se runtime pokusí zařízení spárovat, pokud relace ještě není párovaná.
- Příchozí notifikace vyvolá vibraci, probuzení displeje a otevření obrazovky notifikací.
- Text se při zobrazení čistí od české diakritiky a zalamuje na více řádků.

## Logování a ladění

Projekt loguje do REPLu. Když RTC ještě není dostupné, používá prefix podle `time.monotonic()`. Jakmile je RTC inicializované, logy přepnou na skutečný čas.

Pomocné skripty v `test/`:

- `test/i2c-scanner.py`
- `test/test-wifi.py`
- `test/test-bma423.py`
- `test/test-dotik.py`
- `test/start-boot.py`

## Známé limity

- `Moblin` zatím nesdílí žádná data s runtime.
- Externí drivery `axp2101` a `bma423` nejsou v repozitáři, je potřeba je dodat zvlášť.
- Projekt nemá v repozitáři automatizované testy spustitelné na desktopu; ověření probíhá hlavně na zařízení.

## Licence

Projekt je licencovaný pod MIT, viz soubor `LICENSE`.
