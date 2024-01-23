
# import time
# import board
# import digitalio
# import adafruit_max31855

# # Initialize SPI
# spi = board.SPI()

# # Chip select (CS) pin setup
# cs = digitalio.DigitalInOut(board.D5)

# #Initialize MAX31855 sensor
# sensor = adafruit_max31855.MAX31855(spi, cs)

# while True:
#     temp = sensor.temperature
#     internal = sensor.reference_temperature

#     print('Thermocouple Temperature: {:.3f}°C'.format(temp))
#     print('Internal Temperature: {:.3f}°C'.format(internal))
#     time.sleep(1.0)

########################################################

import time
import board
import digitalio
import adafruit_max31855

spi = board.SPI()
cs = digitalio.DigitalInOut(board.D5)

max31855 = adafruit_max31855.MAX31855(spi, cs)
while True:
    tempC = max31855.temperature
    tempF = tempC * 9 / 5 + 32
    print("Temperature: {} C {} F ".format(tempC, tempF))
    time.sleep(2.0)
