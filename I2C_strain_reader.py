import time
import board
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import adafruit_tca9548a
import logging

# Constantes
TCA_ADDRESSES = [0x70, 0x72]  # Il suffit d'ajouter l'adresse des TCAs supplémentaires
INTERVAL = 5  # Intervalle de capture en sec
LOG_FORMAT = "%(levelname)s:%(asctime)s:%(message)s"

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
                        "tca_address": address,  # Include TCA address
                        "channel": channel,      # Include channel
                        "device": my_ads,
                        "voltage_pair_1": AnalogIn(my_ads, ADS.P2, ADS.P3),
                        "voltage_pair_2": AnalogIn(my_ads, ADS.P0, ADS.P1),
                    })
            except Exception as e:
                logging.error(f"Erreur lors du balayage de TCA {hex(address)} Canal {channel} : {e}")
    return ads_devices

def read_strain_gauges(ads_devices):
    """Lit les valeurs de contrainte des capteurs."""
    strain_values = []
    for ads in ads_devices:
        try:
            ads["device"].gain = 16
            dv = ads["voltage_pair_1"].voltage
            ads["device"].gain = 1
            v = ads["voltage_pair_2"].voltage
            strain = dv / v * 1e6 * 4 / 2.1
            strain_values.append((dv, v, strain, ads["tca_address"], ads["channel"]))
        except Exception as e:
            logging.error(f"Erreur lors de la lecture du capteur : {e}")
            strain_values.append((None, None, None, ads["tca_address"], ads["channel"]))
    return strain_values


previous_strains = {}  # Dictionary to store previous strain values

def print_strain_values(strain_values):
    """Affiche les valeurs de contrainte avec des couleurs."""
    global previous_strains
    RED = "\033[31m"    # ANSI code pour rouge
    GREEN = "\033[32m"  # ANSI code pour vert
    RESET = "\033[0m"   # ANSI code pour reset

    for dv, v, strain, tca_address, channel in strain_values:
        color = RED if tca_address == TCA_ADDRESSES[0] else GREEN
        if dv is not None:
            previous_strain = previous_strains.get((tca_address, channel), (None, None, None))
            diff = strain - previous_strain[2] if previous_strain[2] is not None else 0
            message = f"TCA {hex(tca_address)} Channel {channel:1}: {dv:12.6f}\t{v:8.3f}\t{strain:10.3f}\tdiff: {diff:10.3f}"
            logging.info(color + message + RESET)
            previous_strains[(tca_address, channel)] = (dv, v, strain)
        else:
            logging.error(color + "Erreur de lecture du capteur" + RESET)




def main():
    initialize_logging()

    try:
        i2c = board.I2C()  # Initialisation de l'I2C
        tcas_with_addresses = initialize_tcas(i2c, TCA_ADDRESSES)
        ads_devices = initialize_ads_devices(tcas_with_addresses)

        while True:
            strain_values = read_strain_gauges(ads_devices) 
            print_strain_values(strain_values)
            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        logging.info("Programme terminé par l'utilisateur.")
    except Exception as e:
        logging.error(f"Erreur inattendue : {e}")


if __name__ == "__main__":
    main()