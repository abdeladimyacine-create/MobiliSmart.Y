# =============================================================
# ÉTAPE 1 : Nettoyer les données et les ranger dans une base
# Projet Mobility+ Accès
# =============================================================
# Ce script :
#   1. lit le fichier Excel fourni par l'école
#   2. corrige les anomalies trouvées pendant l'audit
#   3. enregistre les tables propres dans une base SQLite (mobility.db)
# =============================================================

import pandas as pd   # pour manipuler les tableaux de données
import sqlite3        # pour la base de données (déjà inclus dans Python)

FICHIER_EXCEL = "data/mobility_plus_datasets.xlsx"
FICHIER_BASE = "data/mobility.db"

print("Lecture du fichier Excel...")

# ---------- 1. Lire chaque onglet du fichier Excel ----------
frequentation = pd.read_excel(FICHIER_EXCEL, sheet_name="Frequentation_2026")
incidents = pd.read_excel(FICHIER_EXCEL, sheet_name="Incidents_2026")
usagers = pd.read_excel(FICHIER_EXCEL, sheet_name="Usagers")
accessibilite = pd.read_excel(FICHIER_EXCEL, sheet_name="Accessibilite")
stations = pd.read_excel(FICHIER_EXCEL, sheet_name="Referentiel_Stations")
lignes = pd.read_excel(FICHIER_EXCEL, sheet_name="Referentiel_Lignes")


# ---------- 2. Nettoyer la fréquentation ----------
# On supprime les lignes en double (s'il y en a)
avant = len(frequentation)
frequentation = frequentation.drop_duplicates()
print("Fréquentation : doublons supprimés =", avant - len(frequentation))

# On ajoute une colonne "heure" (0 à 23), utile pour le modèle d'IA
frequentation["heure"] = frequentation["datetime"].dt.hour

# On ajoute le numéro du jour (0 = lundi ... 6 = dimanche)
frequentation["num_jour"] = frequentation["datetime"].dt.dayofweek


# ---------- 3. Nettoyer l'accessibilité ----------
# Le nom de colonne "bande_pod tactile" contient une faute et un espace
accessibilite = accessibilite.rename(columns={"bande_pod tactile": "bande_podotactile"})


# Le niveau ("Bon", "Moyen"...) ne correspond pas au score.
# On le recalcule à partir du score, avec une règle claire :
def calculer_niveau(score):
    if score >= 80:
        return "Excellent"
    elif score >= 60:
        return "Bon"
    elif score >= 40:
        return "Moyen"
    else:
        return "Faible"


accessibilite["niveau_accessibilite"] = accessibilite["score_normalise"].apply(calculer_niveau)
print("Accessibilité : niveaux recalculés à partir du score")


# ---------- 4. Signaler les usagers incohérents ----------
# Exemple : un "Senior" de 18 ans, ou un "Étudiant" de 71 ans.
# On ne supprime pas ces usagers : on les SIGNALE dans une nouvelle colonne.
def profil_incoherent(ligne):
    if ligne["profil"] == "Senior" and ligne["age"] < 60:
        return "Oui"
    if ligne["profil"] == "Étudiant" and ligne["age"] > 30:
        return "Oui"
    return "Non"


usagers["profil_incoherent"] = usagers.apply(profil_incoherent, axis=1)
nb_incoherents = (usagers["profil_incoherent"] == "Oui").sum()
print("Usagers : profils incohérents signalés =", nb_incoherents, "sur", len(usagers))


# ---------- 5. Enregistrer les tables propres dans la base SQLite ----------
connexion = sqlite3.connect(FICHIER_BASE)

frequentation.to_sql("frequentation", connexion, if_exists="replace", index=False)
incidents.to_sql("incidents", connexion, if_exists="replace", index=False)
usagers.to_sql("usagers", connexion, if_exists="replace", index=False)
accessibilite.to_sql("accessibilite", connexion, if_exists="replace", index=False)
stations.to_sql("stations", connexion, if_exists="replace", index=False)
lignes.to_sql("lignes", connexion, if_exists="replace", index=False)

connexion.close()

print("Terminé ! Base créée :", FICHIER_BASE)
