import board
import asyncio
i2c = board.I2C()

while True:

  if i2c.try_lock():
      buf = bytearray(6)
      # Vyčtení os X, Y, Z (registry 0x12 až 0x17)
      i2c.writeto_then_readfrom(0x19, bytes([0x12]), buf)
      i2c.unlock()
      print("Surová data z BMA423:", list(buf))
