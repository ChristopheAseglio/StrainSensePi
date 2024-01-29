import time
import board
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import adafruit_tca9548a
import logging

import paho.mqtt.client as mqtt
import json
import sqlite3

# Constantes
TCA_ADDRESSES = [0x70,0x71,0x72]  # Il suffit d'ajouter l'adresse des TCAs supplémentaires
INTERVAL = 5  # Intervalle de capture en sec
LOG_FORMAT = "%(levelname)s:%(asctime)s:%(message)s"
NUM_READINGS = 50 #Nombre de readings pour faire une moyenne (bruit)

# Constantes MQTT
THINGSBOARD_HOST = ''
ACCESS_TOKEN = ''

def initialize_mqtt_client():
    """Initialise et configure le client MQTT."""
    client = mqtt.Client()
    client.username_pw_set(ACCESS_TOKEN)
    client.connect(THINGSBOARD_HOST, 1883, 60)
    return client

def publish_to_cloud(client, sensor_data, db_path):
    """Publie les données de capteur sur ThingsBoard et sauvegarde dans SQLite en cas d'échec."""
    try:
        result = client.publish('v1/devices/me/telemetry', json.dumps(sensor_data), 1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise Exception(f"Échec de la publication MQTT avec le code d'erreur {result.rc}")
        logging.info("Données publiées avec succès.")
    except Exception as e:
        logging.error(f"Erreur lors de la publication des données: {e}")
        save_to_sqlite(db_path, sensor_data)

def save_to_sqlite(db_path, sensor_data):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for key, data in sensor_data.items():
            cursor.execute("INSERT INTO donnees_capteur (tca_address, channel, average_dv, average_v, average_strain) VALUES (?, ?, ?, ?, ?)", 
                           (key.split('_')[0], int(key.split('_')[1][2]), data['Average DV'], data['Average V'], data['Average Strain']))
        conn.commit()
    except Exception as e:
        logging.error(f"Erreur lors de l'enregistrement dans SQLite : {e}")
    finally:
        conn.close()

def initialize_logging():
    """Initialise le framework de logs."""
    logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

def initialize_tcas(i2c, addresses):
    """Initialise les dispositifs TCA et les retourne avec leurs adresses."""
    tcas = []
    for address in addresses:
        try:
            tca = adafruit_tca9548a.TCA9548A(i2c, address=address)
            tcas.append((tca, address))
            logging.info(f"Initialisation de TCA à l'adresse : {hex(address)}")
        except Exception as e:
            logging.error(f"Erreur lors de l'initialisation de TCA à l'adresse {hex(address)} : {e}")
    return tcas

def initialize_ads_devices(tcas_with_addresses):
    """Initialise les dispositifs ADS pour chaque canal TCA."""
    ads_devices = []
    for tca, address in tcas_with_addresses:
        for channel in range(4):
            try:
                if tca[channel].try_lock():
                    logging.info(f"Balayage de l'adresse TCA {hex(address)} Canal {channel}")
                    addresses = tca[channel].scan()
                    logging.info(f"Appareils trouvés : {[hex(addr) for addr in addresses if addr != address]}")
                    tca[channel].unlock()

                    my_ads = ADS.ADS1115(tca[channel])
                    ads_devices.append({
                        "tca_address": address,  
                        "channel": channel,     
                        "device": my_ads,
                        "voltage_pair_1": AnalogIn(my_ads, ADS.P2, ADS.P3),
                        "voltage_pair_2": AnalogIn(my_ads, ADS.P0, ADS.P1),
                    })
            except Exception as e:
                logging.error(f"Erreur lors du balayage de TCA {hex(address)} Canal {channel} : {e}")
    return ads_devices

def read_strain(ads_device):
    """Lit et calcule la déformation à partir d’un ADS."""
    try:
        ads_device["device"].gain = 16
        dv = ads_device["voltage_pair_1"].voltage
        ads_device["device"].gain = 1
        v = ads_device["voltage_pair_2"].voltage
        strain = dv / v * 1e6 * 4 / 2.1
        return dv, v, strain
    except Exception as e:
        logging.error(f"Erreur lors de la lecture du capteur: {e}")
        return None, None, None

def read_strain_gauges(ads_devices):
    """Lit les valeurs de contrainte des capteurs"""
    strain_values = []
    for ads in ads_devices:
        dv, v, strain = read_strain(ads)
        strain_values.append((dv, v, strain, ads["tca_address"], ads["channel"]) if dv is not None else (None, None, None, ads["tca_address"], ads["channel"]))
    return strain_values

def get_color_code(tca_address):
    """Renvoie le code couleur ANSI basé sur l'adresse TCA"""
    RED = "\033[31m"
    BLUE = "\033[34m"
    GREEN = "\033[32m"
    return RED if tca_address == TCA_ADDRESSES[0] else BLUE if tca_address == TCA_ADDRESSES[1] else GREEN

def print_strain_values(average_values, tca_address, channel, previous_strains):
    """Print les valeurs de déformation moyennes avec un code couleur et la différence avec la valeur précédente."""
    RESET = "\033[0m"
    color = get_color_code(tca_address)
    average_dv, average_v, average_strain = average_values

    # Calcule la différence avec la valeur précédente
    previous_strain = previous_strains.get((tca_address, channel), (None, None, None))
    diff = average_strain - previous_strain[2] if previous_strain[2] is not None else 0
    previous_strains[(tca_address, channel)] = average_values

    message = f"TCA {hex(tca_address)} Channel {channel}: Average DV: {average_dv:.6f}, V: {average_v:.3f}, Strain: {average_strain:.3f} diff : {diff:.3f}"
    logging.info(color + message + RESET)

def collect_readings(ads_device):
    """Collecte plusieurs lectures à partir d’un ADS"""
    readings = []
    for _ in range(NUM_READINGS):
        dv, v, strain = read_strain(ads_device)
        if dv is not None:
            readings.append((dv, v, strain))
    return readings

def calculate_average(readings):
    """Calcule la moyenne des lectures"""
    average_dv = sum(dv for dv, _, _ in readings) / len(readings)
    average_v = sum(v for _, v, _ in readings) / len(readings)
    average_strain = sum(strain for _, _, strain in readings) / len(readings)
    return average_dv, average_v, average_strain

def main():
    initialize_logging()
    previous_strains = {}
    mqtt_client = initialize_mqtt_client()
    db_path = "MaBaseDeDonnees.db"  # Chemin vers la base de données SQLite

    try:
        i2c = board.I2C()
        tcas_with_addresses = initialize_tcas(i2c, TCA_ADDRESSES)
        ads_devices = initialize_ads_devices(tcas_with_addresses)

        while True:
            sensor_data = {}
            for ads in ads_devices:
                readings = collect_readings(ads)
                average_values = calculate_average(readings)
                print_strain_values(average_values, ads["tca_address"], ads["channel"], previous_strains)
                
                # Préparation des données pour l'envoi
                sensor_data[f"TCA{ads['tca_address']}_CH{ads['channel']}"] = {
                    'Average DV': average_values[0],
                    'Average V': average_values[1],
                    'Average Strain': average_values[2]
                }

            publish_to_cloud(mqtt_client, sensor_data, db_path)
            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        logging.info("Programme terminé par l'utilisateur.")
    except Exception as e:
        logging.error(f"Erreur inattendue: {e}")
