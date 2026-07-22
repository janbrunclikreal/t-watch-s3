import board, time
import adafruit_focaltouch

try:
    # Otevřeme oficiální dotykovou sběrnici
    touch_i2c = board.TOUCH_I2C()
    ft = adafruit_focaltouch.Adafruit_FocalTouch(touch_i2c, address=0x38)
    print("✅ Dotykový displej (FT6336U) úspěšně inicializován!")
    print("👉 Sáhni na displej a přejeď po něm prstem...")

    for _ in range(50):
        if ft.touched:
            touches = ft.touches
            for point in touches:
                print(f"📍 Dotyk X: {point['x']} | Y: {point['y']}")
        time.sleep(0.1)

except Exception as e:
    print(f"❌ Chyba: {e}")