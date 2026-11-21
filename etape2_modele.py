# =============================================================
# ÉTAPE 2 : Entraîner le modèle d'IA qui prédit l'affluence
# Projet Mobility+ Accès
# =============================================================
# Ce script :
#   1. lit les données propres dans la base (créée à l'étape 1)
#   2. entraîne un Random Forest sur janvier -> mai
#   3. le teste sur juin et le compare à une simple moyenne
#   4. sauvegarde le modèle et les prédictions des 7 prochains jours
# =============================================================

import pandas as pd
import sqlite3
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

FICHIER_BASE = "data/mobility.db"
FICHIER_MODELE = "data/modele_affluence.joblib"


# ---------- Fonction utile : transformer un taux en niveau ----------
def calculer_niveau(taux):
    if taux < 0.40:
        return "Calme"
    elif taux <= 0.80:
        return "Chargé"
    else:
        return "Saturé"


# ---------- Fonction utile : préparer les colonnes pour le modèle ----------
# Le modèle ne comprend que des nombres. On transforme donc le texte
# "Gare Centrale" en colonnes 0 / 1 (c'est ce que fait get_dummies).
def preparer_X(tableau):
    X = pd.get_dummies(tableau[["station", "ligne"]], dtype=int)
    X["heure"] = tableau["heure"]
    X["num_jour"] = tableau["num_jour"]
    return X


# ---------- 1. Lire les données ----------
connexion = sqlite3.connect(FICHIER_BASE)
donnees = pd.read_sql("SELECT * FROM frequentation", connexion)
print("Données chargées :", len(donnees), "lignes")

# ---------- 2. Séparer apprentissage (janv. -> mai) et test (juin) ----------
apprentissage = donnees[donnees["mois"] <= 5]
test = donnees[donnees["mois"] == 6]

X_app = preparer_X(apprentissage)
y_app = apprentissage["taux_occupation"]          # ce qu'on veut prédire
X_test = preparer_X(test)
y_test = test["taux_occupation"]

# ---------- 3. Entraîner le Random Forest ----------
print("Entraînement du modèle (quelques secondes)...")
modele = RandomForestRegressor(n_estimators=100, max_depth=12, random_state=0)
modele.fit(X_app, y_app)

# ---------- 4. Tester le modèle sur juin ----------
predictions = modele.predict(X_test)
erreur_ia = mean_absolute_error(y_test, predictions)

# La "baseline" : la moyenne historique (même station, ligne, heure, jour)
moyennes = apprentissage.groupby(["station", "ligne", "heure", "num_jour"])["taux_occupation"].mean()
moyennes = moyennes.rename("prediction_moyenne").reset_index()
test_avec_moyenne = test.merge(moyennes, on=["station", "ligne", "heure", "num_jour"], how="left")
erreur_moyenne = mean_absolute_error(test_avec_moyenne["taux_occupation"],
                                     test_avec_moyenne["prediction_moyenne"])

# Exactitude sur les niveaux Calme / Chargé / Saturé
niveaux_reels = [calculer_niveau(t) for t in y_test]
niveaux_predits = [calculer_niveau(p) for p in predictions]
bonnes_reponses = 0
for reel, predit in zip(niveaux_reels, niveaux_predits):
    if reel == predit:
        bonnes_reponses = bonnes_reponses + 1
exactitude = bonnes_reponses / len(niveaux_reels)

# Détection des saturations : parmi les vraies saturations, combien trouvées ?
saturees = 0
saturees_trouvees = 0
for reel, predit in zip(niveaux_reels, niveaux_predits):
    if reel == "Saturé":
        saturees = saturees + 1
        if predit == "Saturé":
            saturees_trouvees = saturees_trouvees + 1

print()
print("===== RÉSULTATS DU TEST SUR JUIN =====")
print("Erreur moyenne du Random Forest   :", round(erreur_ia * 100, 1), "points")
print("Erreur moyenne de la baseline     :", round(erreur_moyenne * 100, 1), "points")
print("Bons niveaux (calme/chargé/saturé):", round(exactitude * 100), "%")
print("Saturations détectées             :", saturees_trouvees, "sur", saturees)
print()

# On enregistre ces résultats dans la base, pour les suivre dans l'espace de pilotage
performance = pd.DataFrame([{
    "date_entrainement": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
    "periode_apprentissage": "janvier à mai 2026",
    "periode_test": "juin 2026",
    "erreur_modele_points": round(erreur_ia * 100, 1),
    "erreur_baseline_points": round(erreur_moyenne * 100, 1),
    "exactitude_pourcent": round(exactitude * 100, 1),
    "saturations_detectees": saturees_trouvees,
    "saturations_total": saturees,
}])
performance.to_sql("performance_modele", connexion, if_exists="replace", index=False)

# ---------- 5. Ré-entraîner sur TOUTES les données et sauvegarder ----------
# Maintenant qu'on sait que le modèle fonctionne, on lui donne tout l'historique.
X_tout = preparer_X(donnees)
modele.fit(X_tout, donnees["taux_occupation"])
joblib.dump({"modele": modele, "colonnes": list(X_tout.columns)}, FICHIER_MODELE)
print("Modèle sauvegardé :", FICHIER_MODELE)

# ---------- 6. Prédire les 7 prochains jours (1er au 7 juillet 2026) ----------
combinaisons = donnees[["station", "ligne"]].drop_duplicates()
lignes_futur = []
for jour in pd.date_range("2026-07-01", "2026-07-07"):
    for heure in range(24):
        for _, combo in combinaisons.iterrows():
            lignes_futur.append({
                "date": jour.strftime("%Y-%m-%d"),
                "heure": heure,
                "num_jour": jour.dayofweek,
                "station": combo["station"],
                "ligne": combo["ligne"],
            })
futur = pd.DataFrame(lignes_futur)

X_futur = preparer_X(futur)
X_futur = X_futur.reindex(columns=X_tout.columns, fill_value=0)   # mêmes colonnes qu'à l'entraînement
futur["occupation_prevue"] = modele.predict(X_futur).round(3)
futur["niveau"] = futur["occupation_prevue"].apply(calculer_niveau)

futur.to_sql("predictions", connexion, if_exists="replace", index=False)
connexion.close()
print("Prédictions enregistrées :", len(futur), "lignes (table 'predictions')")
