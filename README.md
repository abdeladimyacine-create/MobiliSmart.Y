# 🚇 MobiliSmart – Mobility+

**MobiliSmart** est le prototype d'un service numérique qui rend le transport public de Mobility+ plus accessible, grâce à la donnée et à l'intelligence artificielle.

Projet réalisé dans le cadre du **Mastère Transformation Digitale, Data et IA (ISCOD)**, à partir du cas fictif Mobility+.

---

## Fonctionnalités

### Pour les usagers : « Planifier mon trajet »
- Saisie du départ, de l'arrivée, du besoin d'accessibilité, du jour et de l'heure.
- **Vérification de l'accessibilité** de chaque station du trajet (départ, correspondance, arrivée).
- **Prévision de l'affluence** (calme, chargé, saturé) par un modèle d'intelligence artificielle.
- **Conseil du meilleur horaire**, 2 heures avant ou après l'heure choisie.
- Signalement des **incidents importants**.
- Réglages d'accessibilité : grands caractères et contraste renforcé.

### Pour les équipes internes : « Pilotage du réseau » (accès protégé)
- Filtres par période, ligne et station.
- Vue d'ensemble, affluence (carte de chaleur), incidents, priorité des travaux d'accessibilité, usagers.
- Surveillance des performances du modèle d'IA.
- Suivi des indicateurs de réussite (KPI) du projet.
- Export des données en CSV.

---

## Les deux briques d'intelligence artificielle

| Brique | Méthode | Résultat |
|---|---|---|
| Prédiction de l'affluence | Random Forest (scikit-learn), entraîné sur janvier à mai 2026, testé sur juin 2026 | Erreur moyenne de 2,7 points ; 91 % de niveaux correctement prédits |
| Recommandation de trajet accessible | Règles d'accessibilité par station + prédictions d'affluence + incidents | Aucun trajet inadapté présenté comme adapté |

---

## Organisation du projet

```
mobility-plus-acces/
├── .streamlit/
│   ├── config.toml            # couleurs de l'application (contrastes accessibles)
│   └── secrets.toml           # identifiants du pilotage (NON publié)
├── data/
│   ├── mobility_plus_datasets.xlsx   # données sources (fictives)
│   ├── mobility.db                   # base SQLite nettoyée
│   └── modele_affluence.joblib       # modèle d'IA entraîné
├── etape1_nettoyage.py        # nettoyage des données et création de la base
├── etape2_modele.py           # entraînement et évaluation du modèle
├── etape3_recommandation.py   # moteur de trajet accessible
├── app.py                     # application Streamlit
├── page_pilotage.py           # espace de pilotage (protégé)
└── requirements.txt           # bibliothèques Python nécessaires
```

---

## Installation et lancement en local

1. Installer Python 3.12 ou plus récent.
2. Installer les bibliothèques :
   ```
   pip install -r requirements.txt
   ```
3. Préparer les données et le modèle :
   ```
   python etape1_nettoyage.py
   python etape2_modele.py
   ```
4. Créer le fichier `.streamlit/secrets.toml` avec les identifiants du pilotage (voir l'administrateur du projet).
5. Lancer l'application :
   ```
   streamlit run app.py
   ```

---

## Accessibilité

- L'information n'est jamais transmise par la couleur seule (icône + mot).
- Contrastes de texte d'au moins 4,5:1 (RGAA / WCAG niveau AA).
- Chaque graphique est accompagné d'un tableau lisible par un lecteur d'écran.
- Page déclarée en français pour les lecteurs d'écran.
- Réglages « Grands caractères » et « Contraste renforcé ».

---

## Limites connues

- Données fictives et figées (janvier à juin 2026), sans flux en temps réel.
- Le modèle ne connaît ni les vacances, ni les jours fériés, ni les événements.
- Hypothèse : la ligne C relie l'Aéroport à Gare Centrale.
- Streamlit limite certains réglages d'accessibilité (taille du texte dans les graphiques).

---

## Auteur

Yacine ABDELADIM – Mastère Transformation Digitale, Data et IA, ISCOD – 2026
