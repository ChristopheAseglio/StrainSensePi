import time
import board
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import adafruit_tca9548a
import logging
import paho.mqtt.client as mqtt
import json
import os
from dotenv import load_dotenv


load_dotenv()  # charge les credentials à partir du .env

logger = logging.getLogger("thingsboard")
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Constantes
TCA_ADDRESSES = [0x70]#,0x71,0x72]  # Il suffit d'ajouter ou supprimer l'adresse des TCAs branchés
INTERVAL = 5  # Intervalle de capture en sec
LOG_FORMAT = "%(levelname)s:%(asctime)s:%(message)s"
NUM_READINGS = 100 #Nombre de readings pour faire une moyenne (bruit)
MAX_DIFF_THRESHOLD = 500  # Différence max autorisée dans les strains sur 2 lectures consécutives (On élimine les valeurs out-of-range)

# Constantes MQTT
THINGSBOARD_HOST = os.getenv("THINGSBOARD_HOST")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

baseline_strains = {} # Pour stocker les mesures zéro

# Capture des mesures initiales pour mesure zéro
def capture_baseline(ads_devices):
    global baseline_strains
    print("Press space + enter to capture baseline measurements...")
    input()
    baseline_readings = {}
    for ads in ads_devices:
        readings = collect_readings(ads)
        average_values = calculate_average(readings)  
        key = f"TCA{hex(ads['tca_address'])}_CH{ads['channel']}"
        #logger.debug(f"Clé pour baseline_readings : {key}, Valeur de Strain : {average_values[2]}") 
        #logger.debug(f"Valeur directe de tca_address : {ads['tca_address']}")
        baseline_readings[key] = average_values[2]  
    return baseline_readings

# Ajuste la mesure en fonction des valeurs de base
def adjust_for_baseline(strain, baseline, tca_address, channel):
    key = f"TCA{tca_address}_CH{channel}"
    if key in baseline:
        return strain - baseline[key]  
    else:
        return strain  

# Config du client MQTT
def initialize_mqtt_client():
    client = mqtt.Client()
    client.username_pw_set(ACCESS_TOKEN)
    client.connect(THINGSBOARD_HOST, 1884, 60)
    client.loop_start()
    return client

# Publie les datas sur l'interface IoT
def publish_to_cloud(client, sensor_data):
    try:
        formatted_data = {}
        for tca_channel, values in sensor_data.items():
            formatted_data.update({
                f"{tca_channel}-{measure}": value 
                for measure, value in values.items()
            })

        jdumps = json.dumps(formatted_data)
        print(jdumps)

         
        logger.debug(f"Données formatées pour publication : {jdumps}")
        result = client.publish('v1/devices/me/telemetry', jdumps, 1)
        print(result)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise Exception(f"Échec de la publication MQTT avec le code d'erreur {result.rc}")
        logger.info("Données publiées avec succès.")
    except Exception as e:
        logger.error(f"Erreur lors de la publication des données: {e}")

# Initialise les TCA et retourne leurs instances
def initialize_tcas(i2c, addresses):
    tcas = []
    for address in addresses:
        #logger.debug(f"Début de l'initialisation de TCA avec l'adresse : {hex(address)}") 
        try:
            tca = adafruit_tca9548a.TCA9548A(i2c, address=address)
            tcas.append((tca, address))
            logger.info(f"Initialisation de TCA à l'adresse : {hex(address)}")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de TCA à l'adresse {hex(address)} : {e}")
    return tcas

# Initialise les ADS pour chaque canal TCA
def initialize_ads_devices(tcas_with_addresses):
    ads_devices = []
    for tca, address in tcas_with_addresses:
        for channel in range(4):
            try:
                #logger.debug(f"Création d'un ADS pour TCA à l'adresse : {hex(address)} sur le canal {channel}")
                if tca[channel].try_lock():
                    logger.info(f"Balayage de l'adresse TCA {hex(address)} Canal {channel}")
                    addresses = tca[channel].scan()
                    logger.info(f"Appareils trouvés : {[hex(addr) for addr in addresses if addr != address]}")
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
                logger.error(f"Erreur lors du balayage de TCA {hex(address)} Canal {channel} : {e}")
    return ads_devices

# lit les strains et crée une nouvelle tentative (max 5 fois) de lecure en fonction du seuil MAX_DIFF_THRESHOLD
def read_strain_with_retry(ads_device, previous_strains, max_retries=5, threshold=MAX_DIFF_THRESHOLD):
    current_try = 0
    backoff_time = 1  # Initial backoff en sec
    tca_address, channel = ads_device["tca_address"], ads_device["channel"]
    previous_strain = previous_strains.get((tca_address, channel), None)

    while current_try < max_retries:
        try:
            ads_device["device"].gain = 16
            dv = ads_device["voltage_pair_1"].voltage
            ads_device["device"].gain = 1
            v = ads_device["voltage_pair_2"].voltage
            strain = dv / v * 1e6 * 4 / 2.1

            if previous_strain is not None:
                diff = abs(strain - previous_strain[2])
                if diff <= threshold:
                    previous_strains[(tca_address, channel)] = (dv, v, strain)
                    return dv, v, strain
                else:
                    logger.info(f"Strain difference exceeded threshold ({diff:.3f} > {threshold}), retrying...")
            else:
                previous_strains[(tca_address, channel)] = (dv, v, strain)
                return dv, v, strain

        except Exception as e:
            logger.error(f"Error reading sensor on {tca_address} channel {channel}, attempt {current_try + 1}: {e}")
            if "Remote I/O error" in str(e):
                # Ici possibilité de réinitialiser la connection 
                # Par exemple: reinitialize_i2c_connection()
                pass

        current_try += 1
        time.sleep(backoff_time)
        backoff_time *= 2  # Exponential backoff

    # Après le nombre maximal de tentatives, renvoie la dernière bonne valeur connue ou gère l'erreur
    logger.error(f"Failed to read valid strain from {tca_address} channel {channel} after {max_retries} attempts.")
    return previous_strain if previous_strain else (None, None, None)


# # lit les strains et crée une nouvelle tentative (max 5 fois) de lecure en fonction du seuil MAX_DIFF_THRESHOLD
# def read_strain_with_retry(ads_device, previous_strains, max_retries=5, threshold=MAX_DIFF_THRESHOLD):
#     current_try = 0
#     tca_address, channel = ads_device["tca_address"], ads_device["channel"]
#     previous_strain = previous_strains.get((tca_address, channel), None)

#     while current_try < max_retries:
#         try:
#             ads_device["device"].gain = 16
#             dv = ads_device["voltage_pair_1"].voltage
#             ads_device["device"].gain = 1
#             v = ads_device["voltage_pair_2"].voltage
#             strain = dv / v * 1e6 * 4 / 2.1

#             if previous_strain is not None:
#                 diff = abs(strain - previous_strain[2])
#                 if diff <= threshold:
#                     previous_strains[(tca_address, channel)] = (dv, v, strain)
#                     return dv, v, strain
#                 else:
#                     logger.info(f"Strain difference exceeded threshold ({diff:.3f} > {threshold}), retrying...")
#             else:
#                 previous_strains[(tca_address, channel)] = (dv, v, strain)
#                 return dv, v, strain

#         except Exception as e:
#             logger.error(f"Error reading sensor, attempt {current_try + 1}: {e}")
#             if "Remote I/O error" in str(e):
#                 # Handle specific I/O error logic here if needed
#                 pass

#         current_try += 1
#         time.sleep(1)  # Temps en sec avant la nouvelle tentative

#     # Après le nombre maximal de tentatives, renvoie la dernière bonne valeur connue ou gère l'erreur
#     logger.error(f"Failed to read valid strain after {max_retries} attempts.")
#     return previous_strain if previous_strain else (None, None, None)

#Lit et calcule la déformation à partir d’un ADS.
def read_strain(ads_device):
    try:
        ads_device["device"].gain = 16
        dv = ads_device["voltage_pair_1"].voltage
        ads_device["device"].gain = 1
        v = ads_device["voltage_pair_2"].voltage
        strain = dv / v * 1e6 * 4 / 2.1
        return dv, v, strain
    except Exception as e:
        logger.error(f"Erreur lors de la lecture du capteur: {e}")
        return None, None, None

# Lecture des strains
def read_strain_gauges(ads_devices, previous_strains):
    strain_values = []
    for ads in ads_devices:
        #logger.debug(f"Lecture de déformation pour TCA à l'adresse : {hex(ads['tca_address'])}, Canal : {ads['channel']}")
        dv, v, strain = read_strain_with_retry(ads, previous_strains)
        strain_values.append((dv, v, strain, ads["tca_address"], ads["channel"]) if dv is not None else (None, None, None, ads["tca_address"], ads["channel"]))
    return strain_values

# code couleur
def get_color_code(tca_address):
    RED = "\033[31m"
    BLUE = "\033[34m"
    GREEN = "\033[32m"
    return RED if tca_address == TCA_ADDRESSES[0] else BLUE if tca_address == TCA_ADDRESSES[1] else GREEN

# moyennes de déformation avec couleur
def print_strain_values(average_values, tca_address, channel, previous_strains):
    RESET = "\033[0m"
    color = get_color_code(tca_address)
    average_dv, average_v, average_strain = average_values
 
    # Calcule la différence avec la valeur précédente
    previous_strain = previous_strains.get((tca_address, channel), (None, None, None))
    diff = average_strain - previous_strain[2] if previous_strain[2] is not None else 0
    previous_strains[(tca_address, channel)] = average_values

    message = f"TCA {hex(tca_address)} Channel {channel}: Average DV: {average_dv:.6f}, V: {average_v:.3f}, Strain: {average_strain:.3f} diff : {diff:.3f}"
    logger.info(color + message + RESET)

# Collecte plusieurs readings à partir d’un ADS
def collect_readings(ads_device):
    readings = []
    for _ in range(NUM_READINGS):
        dv, v, strain = read_strain(ads_device)
        if dv is not None:
            readings.append((dv, v, strain))
    return readings

# Calcule la moyenne des readings
def calculate_average(readings):
    average_dv = sum(dv for dv, _, _ in readings) / len(readings)
    average_v = sum(v for _, v, _ in readings) / len(readings)
    average_strain = sum(strain for _, _, strain in readings) / len(readings)
    return average_dv, average_v, average_strain

def main():
    logger.info('Initialisation terminée')
    previous_strains = {}
    mqtt_client = initialize_mqtt_client()

    try:
        i2c = board.I2C()
        tcas_with_addresses = initialize_tcas(i2c, TCA_ADDRESSES)
        ads_devices = initialize_ads_devices(tcas_with_addresses)
        
        # Capture des mesures zéro
        baseline_strains = capture_baseline(ads_devices)    

        while True:
            sensor_data = {}
            # appel de la nouvelle tentative si valeur au dela du seuil (MAX_DIFF_THRESHOLD)
            strain_values = read_strain_gauges(ads_devices, previous_strains)
            for value in strain_values:
                dv, v, strain, tca_address, channel = value
                # Check si dv n'est pas None, indiquant une lecture réussie
                if dv is not None:
                    # appel de la mise à zéro
                    adjusted_strain = adjust_for_baseline(strain, baseline_strains, tca_address, channel)
                    # prépare les données pour l'envoi
                    sensor_key = f"TCA{hex(tca_address)}_CH{channel}"
                    sensor_data[sensor_key] = {
                        'Average DV': dv,
                        'Average V': v,
                        'Average Strain': adjusted_strain  
                    }
                    # Log les valeurs ajustées
                    print_strain_values((dv, v, adjusted_strain), tca_address, channel, previous_strains)
                else:
                    # Gére le cas ou strain n'a pas pu être lu après les nouvelles tentatives
                    logger.error(f"Failed to read strain for TCA{hex(tca_address)} Channel {channel} after retries.")

            publish_to_cloud(mqtt_client, sensor_data)
            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        logger.error("Programme terminé par l'utilisateur.")
    except Exception as e:
        logger.error(f"Erreur inattendue : {e}")

if __name__ == "__main__":
    main()
