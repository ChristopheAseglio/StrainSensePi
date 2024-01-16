import Adafruit_ADS1x15
import time

# Crée une instance ADS1115
adc = Adafruit_ADS1x15.ADS1115(busnum=1)

# Choisi un gain approprié
GAIN = 2/3

def read_differential_strain_gauge():
    # Lit la tension entre le canal 0 et 1
    value = adc.read_adc_difference(0, gain=GAIN)
    # Converti la valeur en tension
    voltage = value * (4.096 / 32767) * GAIN
    return voltage

def get_average_voltage(num_samples=10):
    total_voltage = 0
    for _ in range(num_samples):
        total_voltage += read_differential_strain_gauge()
        time.sleep(0.1)
    return total_voltage / num_samples

if __name__ == '__main__':
    initial_voltage = get_average_voltage()
    print(f"Tension initiale de la jauge de contrainte : {initial_voltage}")
    try:
        while True:
            current_voltage = get_average_voltage()
            voltage_change = current_voltage - initial_voltage
            print(f"Tension actuelle : {current_voltage}, Changement par rapport à l'initial : {voltage_change}")
            time.sleep(1)  # Mise à jour toutes les secondes
    except KeyboardInterrupt:
        print("Programme arrêté par l'utilisateur.")