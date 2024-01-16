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
            strain_values.append((dv, v, strain))
        except Exception as e:
            logging.error(f"Erreur lors de la lecture du capteur : {e}")
            strain_values.append((None, None, None))
    return strain_values

def print_strain_values(strain_values):
    """Affiche les valeurs de contrainte."""
    for dv, v, strain in strain_values:
        if dv is not None:
            logging.info(f"{dv:>5}\t{v:>5.3f}\t{strain:>5.3f}")
        else:
            logging.error("Erreur de lecture du capteur")

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
