import paho.mqtt.client as mqtt
import time
# The callback for when the client receives a CONNACK response from the server.
import json

import random




THINGSBOARD_HOST = 'buildwise.digital'
ACCESS_TOKEN = 'CHRISTOPHE'

# Data capture and upload interval in seconds. Less interval will eventually hang the DHT22.
INTERVAL=1.0

sensor_data = {'temperature': 0, 'humidity': 0}

next_reading = time.time() 

client = mqtt.Client()

# Set access token
client.username_pw_set(ACCESS_TOKEN)

# Connect to ThingsBoard using default MQTT port and 60 seconds keepalive interval
client.connect(THINGSBOARD_HOST, 1884, 60)

client.loop_start()

try:
    while True:
        humidity = random.randrange(40,100)
        temperature = random.randrange(0,30)
        humidity = round(humidity, 2)
        temperature = round(temperature, 2)
        print(u"Temperature: {:g}\u00b0C, Humidity: {:g}%".format(temperature, humidity))
        sensor_data['temperature'] = temperature
        sensor_data['humidity'] = humidity

        # Sending humidity and temperature data to ThingsBoard
        client.publish('v1/devices/me/telemetry', json.dumps(sensor_data), 1)

        next_reading += INTERVAL
        sleep_time = next_reading-time.time()
        if sleep_time > 0:
            time.sleep(sleep_time)

except KeyboardInterrupt:
    pass

client.loop_stop()
client.disconnect()

