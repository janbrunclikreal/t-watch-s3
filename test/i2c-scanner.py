import board

i2c = board.I2C()

while not i2c.try_lock():
    pass

try:
    adresy = i2c.scan()
    print("Nalezené I2C adresy (v hexadecimálním tvaru):")
    print([hex(a) for a in adresy])
finally:
    i2c.unlock()