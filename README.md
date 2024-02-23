# StrainSensePi

## Description du projet
StrainSensePi est un projet d'innovation technologique conçu pour la surveillance du retrait du béton, en intégrant un Raspberry Pi avec des PCBs et des modules Adafruit pour mesurer les jauges de contrainte. Ce système permet la collecte, l'envoi et l'analyse des données en temps réel sur le cloud, visant à améliorer la précision des essais de retrait du béton et faciliter la consultation des données pour les professionnels du bâtiment et de la construction.

## Fonctionnalités
- Mesure précise des déformations (strains) à l'aide de jauges de contrainte connectées à un Raspberry Pi.
- Filtrage et analyse des données pour éliminer les valeurs aberrantes et calculer les moyennes.
- Publication des données mesurées en temps réel sur une plateforme IoT cloud (ThingsBoard).
- Configuration et gestion des appareils via MQTT pour une intégration facile avec d'autres systèmes IoT.

## Matériel requis
- Raspberry Pi (modèle recommandé : Raspberry Pi 3 ou supérieur)
- Modules Adafruit ADS1x15 pour la lecture des jauges de contrainte
- Adafruit TCA9548A TCA pour la multiplexation des signaux I2C
- Jauges de contrainte
- Connexion Internet pour la publication des données sur le cloud

## Configuration et installation
1. **Préparation du Raspberry Pi** : Installez le système d'exploitation Raspbian et assurez-vous que votre Pi est à jour.
2. **Installation des dépendances** :
   - Exécutez `pip install -r requirements.txt` pour installer les bibliothèques Python nécessaires.
3. **Configuration du .env** : Créez un fichier `.env` à la racine du projet pour stocker les variables d'environnement `THINGSBOARD_HOST` et `ACCESS_TOKEN`.
4. **Branchement des composants** : Connectez les modules Adafruit ADS1x15 et TCA9548A au Raspberry Pi.

## Utilisation

### Démarrage rapide
Pour démarrer le système de mesure `I2C_strain_reader_platform.py` et commencer la collecte des données, suivez ces étapes :

1. **Lancement du programme** : Ouvrez un terminal sur le Raspberry Pi et naviguez jusqu'au dossier contenant le projet. Lancez le script en exécutant :
   ```bash
   `python3 I2C_strain_reader_platform.py
Initialisation des mesures zéro : Lorsque le programme démarre, il vous sera demandé d'appuyer sur la touche Espace suivi de Entrée pour commencer les mesures de référence (mesure zéro). Cette étape est cruciale pour calibrer le système avant de procéder à la collecte des données réelles.


**Appuyer sur espace + enter pour commencer la mesure zéro**
Veillez à ne pas appliquer de contrainte sur les capteurs pendant cette étape d'initialisation pour garantir une mesure de référence précise.

Collecte et publication des données : Après l'étape d'initialisation, le système commence automatiquement à mesurer les déformations, à filtrer les données, et à publier les résultats sur la plateforme IoT cloud configurée. Vous pouvez visualiser ces données en temps réel via l'interface de la plateforme IoT.

Arrêt du programme
Pour arrêter la collecte des données et le programme, appuyez sur CTRL + C dans le terminal. Ceci interrompt proprement l'exécution du script et assure la fermeture de toutes les connexions réseau et capteurs de manière sécurisée.

