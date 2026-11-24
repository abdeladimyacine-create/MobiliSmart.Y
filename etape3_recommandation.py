# =============================================================
# ÉTAPE 3 : Le moteur de trajet accessible
# Projet Mobility+ (MobiliSmart) - seconde brique d'IA
# =============================================================
# L'usager donne : sa station de départ, sa station d'arrivée,
# son besoin d'accessibilité, le jour (n'importe quelle date) et l'heure.
# Le moteur :
#   1. trouve le trajet (direct ou avec une correspondance)
#   2. vérifie que CHAQUE station du trajet est compatible avec le besoin
#   3. demande au modèle d'IA (étape 2) l'affluence prévue
#   4. calcule une note sur 100 du trajet (non affichée à l'usager)
#   5. cherche le meilleur horaire, 2 h avant ou après l'heure choisie
# Il est utilisé par l'application (app.py).
# =============================================================

import sqlite3
import joblib
import pandas as pd

FICHIER_BASE = "data/mobility.db"
FICHIER_MODELE = "data/modele_affluence.joblib"

# ---------- 1. Le plan du réseau ----------
# Les stations desservies par chaque ligne (d'après le référentiel des stations).
# HYPOTHÈSE : la ligne C (bus express) relie l'Aéroport à Gare Centrale.
# Les données ne donnent que l'Aéroport sur cette ligne : sans cette hypothèse,
# l'Aéroport ne serait relié à aucune autre station.
RESEAU = {
    "Ligne A": ["Gare Centrale", "Hôpital", "Université"],
    "Ligne B": ["Gare Centrale", "Centre Ville"],
    "Ligne C": ["Gare Centrale", "Aéroport"],
}
CORRESPONDANCE = "Gare Centrale"   # la seule station commune aux 3 lignes

# Une icône par type de ligne (le type vient du référentiel des lignes)
ICONES_TYPES = {"Métro": "🚇", "Tramway": "🚊", "Bus express": "🚌"}

# ---------- 2. Les règles d'accessibilité ----------
# Pour chaque besoin : les équipements qui rendent une station utilisable (un seul suffit).
# Une liste vide = pas d'équipement obligatoire.
REGLES = {
    "Fauteuil roulant": ["ascenseur", "rampe_acces"],
    "Malvoyant ou aveugle": ["bande_podotactile", "audio_description"],
    "Mobilité réduite légère (canne, poussette, senior)": [],
    "Aucun besoin particulier": [],
}

# Poids de la note sur 100 (leur total fait 1)
POIDS_ACCESSIBILITE = 0.5
POIDS_TRANQUILLITE = 0.3
POIDS_INCIDENT = 0.2

NOMS_EQUIPEMENTS = {
    "ascenseur": "ascenseur",
    "rampe_acces": "rampe d'accès",
    "signaletique_adaptee": "signalétique adaptée",
    "bande_podotactile": "bande podotactile",
    "audio_description": "annonces audio",
}


# ---------- 3. Charger les données et le modèle d'IA ----------
# On range tout dans un dictionnaire : donnees["accessibilite"], donnees["modele"], etc.
def charger_donnees():
    connexion = sqlite3.connect(FICHIER_BASE)
    accessibilite = pd.read_sql("SELECT * FROM accessibilite", connexion)
    incidents = pd.read_sql("SELECT * FROM incidents", connexion)
    lignes = pd.read_sql("SELECT * FROM lignes", connexion)
    # Les couples (station, ligne) mesurés dans l'historique
    couples = pd.read_sql("SELECT DISTINCT station, ligne FROM frequentation", connexion)
    connexion.close()

    sauvegarde = joblib.load(FICHIER_MODELE)       # le modèle entraîné à l'étape 2

    # Le type de chaque ligne : {"Ligne A": "Métro", "Ligne B": "Tramway", ...}
    types = {}
    for _, ligne in lignes.iterrows():
        types[ligne["nom_ligne"]] = ligne["type"]

    return {
        "accessibilite": accessibilite,
        "incidents": incidents,
        "types": types,
        "couples": list(zip(couples["station"], couples["ligne"])),
        "modele": sauvegarde["modele"],
        "colonnes": sauvegarde["colonnes"],
    }


# ---------- 4. Demander au modèle l'affluence d'une journée ----------
# Le modèle ne regarde que : la station, la ligne, l'heure et le jour de la semaine.
# Il peut donc prédire n'importe quelle date.
MEMOIRE = {}   # on garde les réponses déjà calculées pour ne pas les refaire


def predire_journee(donnees, station, ligne, num_jour):
    cle = (station, ligne, num_jour)
    if cle in MEMOIRE:
        return MEMOIRE[cle]

    # On prépare 24 lignes (une par heure), avec les mêmes colonnes qu'à l'entraînement
    lignes_x = []
    for heure in range(24):
        ligne_x = {}
        for colonne in donnees["colonnes"]:
            ligne_x[colonne] = 0
        ligne_x["station_" + station] = 1
        ligne_x["ligne_" + ligne] = 1
        ligne_x["heure"] = heure
        ligne_x["num_jour"] = num_jour
        lignes_x.append(ligne_x)
    x = pd.DataFrame(lignes_x, columns=donnees["colonnes"])

    MEMOIRE[cle] = list(donnees["modele"].predict(x))
    return MEMOIRE[cle]


# L'affluence prévue sur une étape du trajet.
# On prend la station de début si elle a été mesurée sur cette ligne,
# sinon la station de fin (Gare Centrale n'a pas de mesure sur la ligne C).
def occupation_etape(donnees, etape, date, heure):
    ligne, debut, fin = etape
    num_jour = pd.to_datetime(date).dayofweek       # 0 = lundi ... 6 = dimanche
    for station in [debut, fin]:
        if (station, ligne) in donnees["couples"]:
            return predire_journee(donnees, station, ligne, num_jour)[heure]
    return None


def calculer_niveau(taux):
    if taux < 0.40:
        return "Calme"
    elif taux <= 0.80:
        return "Chargé"
    else:
        return "Saturé"


# ---------- 5. Trouver le trajet ----------
# Renvoie une liste d'étapes. Chaque étape = (ligne, station de début, station de fin).
def trouver_trajet(depart, arrivee):
    # Cas 1 : une ligne passe par les deux stations -> trajet direct
    for ligne in RESEAU:
        if depart in RESEAU[ligne] and arrivee in RESEAU[ligne]:
            return [(ligne, depart, arrivee)]

    # Cas 2 : sinon, on change de ligne à Gare Centrale
    for ligne in RESEAU:
        if depart in RESEAU[ligne]:
            ligne_depart = ligne
        if arrivee in RESEAU[ligne]:
            ligne_arrivee = ligne
    return [(ligne_depart, depart, CORRESPONDANCE), (ligne_arrivee, CORRESPONDANCE, arrivee)]


# Le nom d'une ligne avec son type : "🚇 Ligne A (métro)"
def nommer_ligne(donnees, ligne):
    type_ligne = donnees["types"][ligne]
    return ICONES_TYPES.get(type_ligne, "") + " " + ligne + " (" + type_ligne.lower() + ")"


# Décrire le trajet en une phrase
def decrire_trajet(donnees, trajet):
    if len(trajet) == 1:
        return nommer_ligne(donnees, trajet[0][0]) + " en direct"
    return (nommer_ligne(donnees, trajet[0][0]) + " jusqu'à " + CORRESPONDANCE
            + ", puis " + nommer_ligne(donnees, trajet[1][0]))


# ---------- 6. La station est-elle compatible avec le besoin ? ----------
# "Compatible", "Incompatible", ou "Indéterminé" si une information manque.
# On ne présume JAMAIS qu'une station est accessible.
def statut_station(equipements, besoin):
    requis = REGLES[besoin]
    if len(requis) == 0:
        return "Compatible"
    for colonne in requis:
        if pd.isna(equipements[colonne]):
            return "Indéterminé"
    for colonne in requis:
        if equipements[colonne] == 1:
            return "Compatible"
    return "Incompatible"


# Les équipements présents, en mots
def lister_equipements(equipements):
    presents = []
    for colonne in NOMS_EQUIPEMENTS:
        if equipements[colonne] == 1:
            presents.append(NOMS_EQUIPEMENTS[colonne])
    if len(presents) == 0:
        return "aucun équipement d'accessibilité"
    return ", ".join(presents)


# Les stations du réseau compatibles avec un besoin (pour proposer des solutions)
def stations_compatibles(donnees, besoin):
    accessibilite = donnees["accessibilite"]
    liste = []
    for station in sorted(set(sum(RESEAU.values(), []))):
        equipements = accessibilite[accessibilite["station"] == station].iloc[0]
        if statut_station(equipements, besoin) == "Compatible":
            liste.append(station)
    return liste


# ---------- 7. Incident important = "En cours" ET gravité "Élevée" (alerte, ne rend pas le trajet non adapté) ----------
def incident_important(incidents, station):
    importants = incidents[
        (incidents["station_principale"] == station)
        & (incidents["statut"] == "En cours")
        & (incidents["gravite"] == "Élevée")
    ]
    return len(importants) > 0


# ---------- 8. La note sur 100 du trajet ----------
# Un trajet vaut ce que vaut son point le plus faible :
# on prend la station la MOINS accessible et l'étape la PLUS chargée.
def calculer_score(score_accessibilite, occupation, incident):
    tranquillite = 100 - occupation * 100
    if incident:
        absence_incident = 0
    else:
        absence_incident = 100
    score = (POIDS_ACCESSIBILITE * score_accessibilite
             + POIDS_TRANQUILLITE * tranquillite
             + POIDS_INCIDENT * absence_incident)
    return round(score)


# ---------- 9. Évaluer un trajet à une date et une heure données ----------
def evaluer_trajet(donnees, besoin, depart, arrivee, date, heure):
    accessibilite = donnees["accessibilite"]
    trajet = trouver_trajet(depart, arrivee)

    # Les stations du trajet et leur rôle
    if len(trajet) == 1:
        stations = [(depart, "Départ"), (arrivee, "Arrivée")]
    else:
        stations = [(depart, "Départ"), (CORRESPONDANCE, "Correspondance"), (arrivee, "Arrivée")]

    # Vérifier chaque station
    lignes_stations = []
    scores_accessibilite = []
    un_incident = False
    for station, role in stations:
        equipements = accessibilite[accessibilite["station"] == station].iloc[0]
        incident = incident_important(donnees["incidents"], station)
        if incident:
            un_incident = True
        scores_accessibilite.append(equipements["score_normalise"])
        lignes_stations.append({
            "Rôle": role,
            "Station": station,
            "Statut": statut_station(equipements, besoin),
            "Équipements": lister_equipements(equipements),
            "Incident important": "Oui" if incident else "Non",
        })
    tableau_stations = pd.DataFrame(lignes_stations)

    # L'affluence prévue sur chaque étape
    lignes_etapes = []
    occupations = []
    for etape in trajet:
        occupation = occupation_etape(donnees, etape, date, heure)
        occupations.append(occupation)
        lignes_etapes.append({
            "Ligne": nommer_ligne(donnees, etape[0]),
            "De": etape[1],
            "À": etape[2],
            "Affluence prévue": calculer_niveau(occupation) + " (" + str(round(occupation * 100)) + " %)",
        })
    tableau_etapes = pd.DataFrame(lignes_etapes)

    # Le trajet est adapté seulement si TOUTES ses stations sont compatibles
    accessible = (tableau_stations["Statut"] == "Compatible").all()
    # Un trajet est aussi chargé que son étape la plus chargée
    occupation_max = max(occupations)
    if accessible:
        accessibilite_trajet = min(scores_accessibilite)     # la station la moins accessible
        # Sans besoin particulier, l'équipement des stations ne gêne pas l'usager :
        # ce critère ne doit pas faire baisser sa note.
        if besoin == "Aucun besoin particulier":
            accessibilite_trajet = 100
        note = calculer_score(accessibilite_trajet, occupation_max, un_incident)
    else:
        note = None

    return {
        "trajet": trajet,
        "description": decrire_trajet(donnees, trajet),
        "stations": tableau_stations,
        "etapes": tableau_etapes,
        "accessible": accessible,
        "note": note,
        "occupation_max": occupation_max,
        "niveau": calculer_niveau(occupation_max),
        "incident": un_incident,
    }


# ---------- 10. Chercher le meilleur horaire (2 h avant ou après) ----------
def meilleur_horaire(donnees, besoin, depart, arrivee, date, heure):
    lignes = []
    for h in range(heure - 2, heure + 3):
        if 0 <= h <= 23:
            evaluation = evaluer_trajet(donnees, besoin, depart, arrivee, date, h)
            lignes.append({"heure": h, "occupation": evaluation["occupation_max"],
                           "niveau": evaluation["niveau"], "note": evaluation["note"]})
    horaires = pd.DataFrame(lignes)
    # Le meilleur horaire = le trajet le moins chargé
    return horaires.sort_values("occupation").iloc[0]


# ---------- 11. Démonstration (quand on lance ce fichier directement) ----------
if __name__ == "__main__":
    pd.set_option("display.width", 200)
    donnees = charger_donnees()

    exemples = [
        ("Fauteuil roulant", "Gare Centrale", "Hôpital", "2026-12-01"),
        ("Malvoyant ou aveugle", "Hôpital", "Université", "2026-12-01"),
        ("Aucun besoin particulier", "Aéroport", "Centre Ville", "2026-12-05"),
    ]
    for besoin, depart, arrivee, date in exemples:
        print()
        print("=====", besoin, ":", depart, "->", arrivee, "-", date, "à 8 h =====")
        resultat = evaluer_trajet(donnees, besoin, depart, arrivee, date, 8)
        print("Trajet :", resultat["description"])
        print(resultat["stations"].to_string(index=False))
        print(resultat["etapes"].to_string(index=False))
        if resultat["accessible"]:
            print("-> Trajet ADAPTÉ, note :", resultat["note"], "sur 100")
            conseil = meilleur_horaire(donnees, besoin, depart, arrivee, date, 8)
            print("-> Meilleur horaire :", conseil["heure"], "h (" + conseil["niveau"] + ")")
        else:
            print("-> Trajet NON ADAPTÉ pour ce besoin")
            print("   Stations compatibles du réseau :", stations_compatibles(donnees, besoin))
