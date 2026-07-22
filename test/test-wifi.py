import time
import wifi
import os
import gc

print("=========================================")
print("     SPUŠTĚNÍ DIAGNOSTIKY WI-FI          ")
print("=========================================")

# 1. ČIŠTĚNÍ PAMĚTI
gc.collect()

# 2. SKENOVÁNÍ OKOLNÍCH SÍTÍ
print("\n[1/2] Skenuji okolní Wi-Fi sítě...")
try:
    # CircuitPython skenuje sítě a vrací iterátor
    networks = list(wifi.radio.start_scanning_networks())
    wifi.radio.stop_scanning_networks()
    
    print(f"Nalezeno {len(networks)} sítí:")
    print("-" * 50)
    print(f"{'SSID (Název sítě)':<25} | {'Signál (RSSI)':<12} | {'Kanál':<5}")
    print("-" * 50)
    
    for net in networks:
        # Převedeme SSID na čitelný řetězec (ignorujeme případné dekódovací chyby)
        try:
            ssid = net.ssid
        except Exception:
            ssid = "<Neznámé SSID>"
            
        print(f"{ssid:<25} | {net.rssi:<12} dBm | {net.channel:<5}")
    print("-" * 50)

except Exception as e:
    print("CHYBA při skenování sítí:", e)

# 3. TEST PŘIPOJENÍ POMOCÍ settings.toml
print("\n[2/2] Testuji připojení přes settings.toml...")

# Zkusíme vytáhnout přihlašovací údaje ze settings.toml
ssid_toml = os.getenv("CIRCUITPYTHON_WIFI_SSID")
pass_toml = os.getenv("CIRCUITPYTHON_WIFI_PASSWORD")

if not ssid_toml or not pass_toml:
    print("[CHYBA] V settings.toml chybí proměnné SSID nebo PASSWORD!")
    print("Ujisti se, že soubor obsahuje:")
    print('CIRCUITPYTHON_WIFI_SSID = "tvuj_nazev"')
    print('CIRCUITPYTHON_WIFI_PASSWORD = "tvoje_heslo"')
else:
    print(f"Nalezeny údaje v settings.toml:")
    print(f" -> SSID: '{ssid_toml}'")
    print(f" -> Heslo: {'*' * len(pass_toml)} (délka {len(pass_toml)} znaků)")
    
    try:
        print(f"\nPokouším se připojit k '{ssid_toml}'...")
        wifi.radio.connect(ssid_toml, pass_toml)
        
        # Pokud se připojení podaří
        print("[OK] ÚSPĚCH! Deska se úspěšně připojila k Wi-Fi!")
        print(f"Přidělená IP adresa: {wifi.radio.ipv4_address}")
        
    except Exception as e:
        print("[SELHÁNÍ] Připojení selhalo!")
        print("Detaily chyby:", e)

print("\n=========================================")
print("      DIAGNOSTIKA DOKONČENA              ")
print("=========================================")
