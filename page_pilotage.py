# =============================================================
# L'espace « Pilotage du réseau » (équipes internes de Mobility+)
# Projet Mobility+ (MobiliSmart)
# =============================================================
# Cette page est protégée par un identifiant et un mot de passe.
# Elle contient :
#   - des filtres (période, lignes, stations) qui s'appliquent à toute la page
#   - 8 onglets : vue d'ensemble, affluence, incidents, accessibilité, usagers,
#     modèle d'IA, KPI du projet, données et export
# Elle est appelée par app.py.
# =============================================================

import hashlib
import sqlite3
import pandas as pd
import altair as alt
import streamlit as st

from etape3_recommandation import RESEAU, REGLES, CORRESPONDANCE, evaluer_trajet, lister_equipements

BLEU = "#0B5CAD"
# Couleurs officielles des lignes (référentiel : A bleu, B vert, C orange)
COULEURS_LIGNES = alt.Scale(domain=["Ligne A", "Ligne B", "Ligne C"], range=["#1E63B5", "#1F7A4D", "#F28C28"])
ORDRE_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
NOMS_MOIS = {1: "janv.", 2: "févr.", 3: "mars", 4: "avr.", 5: "mai", 6: "juin",
             7: "juil.", 8: "août", 9: "sept.", 10: "oct.", 11: "nov.", 12: "déc."}
ESSAIS_MAXIMUM = 5


# =============================================================
# 1. LECTURE DES DONNÉES
# =============================================================
@st.cache_data
def lire_table(nom_table):
    connexion = sqlite3.connect("data/mobility.db")
    tableau = pd.read_sql("SELECT * FROM " + nom_table, connexion)
    connexion.close()
    return tableau


@st.cache_data
def lire_donnees_pilotage():
    frequentation = lire_table("frequentation")
    frequentation["date"] = pd.to_datetime(frequentation["datetime"]).dt.date
    incidents = lire_table("incidents")
    incidents["date"] = pd.to_datetime(incidents["date"]).dt.date
    return frequentation, incidents, lire_table("usagers"), lire_table("accessibilite")


def lire_performance():
    try:
        return lire_table("performance_modele").iloc[0]
    except Exception:          # la table n'existe pas encore : étape 2 pas relancée
        return None


# =============================================================
# 2. PETITS OUTILS D'AFFICHAGE
# =============================================================
def carte(colonne, titre, valeur, phrase):
    with colonne.container(border=True):
        st.caption(titre)
        st.markdown('<div class="ms-valeur">' + valeur + '</div>', unsafe_allow_html=True)
        st.write(phrase)


def nombre(valeur, decimales=0):
    """Écrit un nombre à la française : 6 542,2 au lieu de 6542.2"""
    texte = f"{valeur:,.{decimales}f}"
    return texte.replace(",", " ").replace(".", ",")


def tableau_accessible(tableau):
    with st.expander("Voir les valeurs sous forme de tableau"):
        st.dataframe(tableau, hide_index=True, width="stretch")


def bouton_export(tableau, nom_fichier, libelle):
    # Le point-virgule et l'encodage utf-8-sig permettent une ouverture correcte dans Excel
    contenu = tableau.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("⬇️ " + libelle, contenu, file_name=nom_fichier, mime="text/csv")


# =============================================================
# 3. LA CONNEXION (identifiant + mot de passe)
# =============================================================
def verifier_connexion():
    """Renvoie True si l'utilisateur est connecté. Sinon, affiche le formulaire de connexion."""
    if st.session_state.get("connecte"):
        return True

    st.markdown('<div class="ms-hero"><p class="ms-hero-titre">🔒 Espace réservé</p>'
                '<p class="ms-hero-texte">Le pilotage du réseau est réservé aux équipes de Mobility+. '
                'Connectez-vous pour continuer.</p></div>', unsafe_allow_html=True)

    # Les identifiants sont rangés dans .streamlit/secrets.toml (jamais dans le code)
    # Si le fichier est absent ou mal rangé, on affiche un message clair au lieu de planter
    try:
        reglages = st.secrets["pilotage"]
    except Exception:
        st.error("Fichier des identifiants introuvable. Créez le fichier .streamlit/secrets.toml "
                 "(dans le dossier du projet) avec la section [pilotage].")
        return False

    essais = st.session_state.get("essais", 0)
    if essais >= ESSAIS_MAXIMUM:
        st.error("Trop de tentatives incorrectes. Fermez la page et réessayez plus tard.")
        return False

    with st.form("connexion"):
        identifiant = st.text_input("Identifiant")
        mot_de_passe = st.text_input("Mot de passe", type="password")
        valider = st.form_submit_button("Se connecter", type="primary", width="stretch")

    if valider:
        # On compare l'EMPREINTE du mot de passe saisi avec celle enregistrée :
        # le vrai mot de passe n'est jamais stocké.
        empreinte = hashlib.sha256(mot_de_passe.encode()).hexdigest()
        if (identifiant == reglages["identifiant"]
                and empreinte == reglages["mot_de_passe_sha256"]):
            st.session_state["connecte"] = True
            st.session_state["essais"] = 0
            st.rerun()
        else:
            st.session_state["essais"] = essais + 1
            reste = ESSAIS_MAXIMUM - st.session_state["essais"]
            st.error("Identifiant ou mot de passe incorrect. Tentatives restantes : " + str(reste) + ".")
    return False


# =============================================================
# 4. LA PAGE COMPLÈTE
# =============================================================
def afficher_pilotage(donnees_moteur):
    # donnees_moteur = les données et le modèle chargés par app.py (pour tester les trajets)
    if not verifier_connexion():
        return

    frequentation, incidents, usagers, accessibilite = lire_donnees_pilotage()

    # ---------- Les filtres (barre latérale) ----------
    st.sidebar.write("---")
    st.sidebar.write("**Filtres du pilotage**")
    date_min = min(frequentation["date"].min(), incidents["date"].min())
    date_max = max(frequentation["date"].max(), incidents["date"].max())
    periode = st.sidebar.date_input("Période", value=(date_min, date_max),
                                    min_value=date_min, max_value=date_max, format="DD/MM/YYYY")
    toutes_lignes = sorted(frequentation["ligne"].unique())
    lignes_choisies = st.sidebar.multiselect("Lignes", toutes_lignes, default=toutes_lignes)
    toutes_stations = sorted(frequentation["station"].unique())
    stations_choisies = st.sidebar.multiselect("Stations", toutes_stations, default=toutes_stations)
    if st.sidebar.button("Se déconnecter", width="stretch"):
        st.session_state["connecte"] = False
        st.rerun()

    # Tant que l'utilisateur n'a choisi qu'une date de la période, on attend la seconde
    if len(periode) != 2:
        st.info("Choisissez la date de fin de la période dans la barre latérale.")
        return
    debut, fin = periode

    # On applique les filtres
    freq = frequentation[(frequentation["date"] >= debut) & (frequentation["date"] <= fin)
                         & (frequentation["ligne"].isin(lignes_choisies))
                         & (frequentation["station"].isin(stations_choisies))]
    inc = incidents[(incidents["date"] >= debut) & (incidents["date"] <= fin)
                    & (incidents["ligne"].isin(lignes_choisies))
                    & (incidents["station_principale"].isin(stations_choisies))]

    st.markdown('<div class="ms-hero"><p class="ms-hero-titre">Pilotage du réseau</p>'
                '<p class="ms-hero-texte">Du ' + debut.strftime("%d/%m/%Y") + ' au ' + fin.strftime("%d/%m/%Y")
                + ' · ' + str(len(lignes_choisies)) + ' ligne(s) · ' + str(len(stations_choisies))
                + ' station(s)</p></div>', unsafe_allow_html=True)

    if len(freq) == 0 and len(inc) == 0:
        st.warning("Aucune donnée pour ces filtres.")
        return

    onglets = st.tabs(["Vue d'ensemble", "Affluence", "Incidents", "Accessibilité",
                       "Usagers", "Modèle d'IA", "KPI du projet", "Données et export"])

    # ---------------------------------------------------------
    # Onglet 1 : vue d'ensemble
    # ---------------------------------------------------------
    with onglets[0]:
        taux_moyen = freq["taux_occupation"].mean() * 100 if len(freq) > 0 else 0
        part_saturee = (freq["taux_occupation"] > 0.8).mean() * 100 if len(freq) > 0 else 0
        non_resolus = (inc["statut"] != "Résolu").sum()

        st.markdown("#### Fréquentation")
        c1, c2, c3 = st.columns(3)
        carte(c1, "Voyageurs comptés", nombre(freq["affluence"].sum()), "Sur la période filtrée.")
        carte(c2, "Remplissage moyen", nombre(taux_moyen, 1) + " %", "Moyenne de toutes les mesures.")
        carte(c3, "Mesures saturées", nombre(part_saturee, 1) + " %", "Rames remplies à plus de 80 %.")

        st.markdown("#### Incidents")
        c1, c2, c3 = st.columns(3)
        carte(c1, "Incidents", nombre(len(inc)), nombre(non_resolus) + " non résolus.")
        carte(c2, "Durée moyenne", nombre(inc["duree_minutes"].mean() if len(inc) else 0) + " min",
              "Par incident.")
        carte(c3, "Coût estimé", nombre(inc["cout_estimé_keur"].sum() / 1000, 2) + " M€", "Total de la période.")

        st.markdown("#### Usagers")
        c1, c2, c3 = st.columns(3)
        carte(c1, "Satisfaction moyenne", nombre(usagers["satisfaction"].mean(), 2) + " / 5", "Tous profils.")
        carte(c2, "Satisfaction PMR", nombre(usagers[usagers["profil"] == "PMR"]["satisfaction"].mean(), 2)
              + " / 5", "La plus basse des profils.")
        carte(c3, "Usagers avec un besoin d'accessibilité",
              nombre((usagers["besoin_accessibilite"] == "Oui").mean() * 100) + " %", "Part des usagers.")
        st.caption("Les indicateurs « Usagers » ne dépendent pas des filtres : la base des usagers n'est pas datée.")

    # ---------------------------------------------------------
    # Onglet 2 : affluence
    # ---------------------------------------------------------
    with onglets[1]:
        st.markdown("#### Carte de chaleur : remplissage moyen par jour et par heure")
        chaleur = freq.groupby(["jour_semaine", "heure"])["taux_occupation"].mean().reset_index()
        chaleur["Remplissage (%)"] = (chaleur["taux_occupation"] * 100).round()
        graphique = alt.Chart(chaleur).mark_rect().encode(
            x=alt.X("heure:O", title="Heure", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("jour_semaine:N", title=None, sort=ORDRE_JOURS),
            color=alt.Color("Remplissage (%):Q", scale=alt.Scale(scheme="blues"), title="Remplissage (%)"),
            tooltip=["jour_semaine", "heure", "Remplissage (%)"])
        st.altair_chart(graphique, width="stretch")
        st.caption("Plus la case est foncée, plus les rames sont remplies. Les pics de semaine "
                   "(6 h-9 h et 17 h-19 h) apparaissent nettement.")
        tableau_accessible(chaleur[["jour_semaine", "heure", "Remplissage (%)"]])

        st.markdown("#### Évolution mensuelle du remplissage par ligne")
        mensuel = freq.groupby(["mois", "ligne"])["taux_occupation"].mean().reset_index()
        mensuel["Remplissage (%)"] = (mensuel["taux_occupation"] * 100).round(1)
        mensuel["Mois"] = mensuel["mois"].map(NOMS_MOIS)
        graphique = alt.Chart(mensuel).mark_line(point=True).encode(
            x=alt.X("Mois:N", sort=list(NOMS_MOIS.values()), title=None),
            y=alt.Y("Remplissage (%):Q", scale=alt.Scale(zero=False)),
            color=alt.Color("ligne:N", title="Ligne", scale=COULEURS_LIGNES),
            tooltip=["Mois", "ligne", "Remplissage (%)"])
        st.altair_chart(graphique, width="stretch")
        tableau_accessible(mensuel[["Mois", "ligne", "Remplissage (%)"]])

        st.markdown("#### Stations et lignes les plus saturées")
        saturation = freq.groupby(["station", "ligne"]).agg(
            remplissage=("taux_occupation", "mean"),
            saturees=("taux_occupation", lambda x: (x > 0.8).mean())).reset_index()
        saturation["Remplissage moyen (%)"] = (saturation["remplissage"] * 100).round(1)
        saturation["Mesures saturées (%)"] = (saturation["saturees"] * 100).round(1)
        saturation = saturation.sort_values("Mesures saturées (%)", ascending=False)
        st.dataframe(saturation[["station", "ligne", "Remplissage moyen (%)", "Mesures saturées (%)"]],
                     hide_index=True, width="stretch")

    # ---------------------------------------------------------
    # Onglet 3 : incidents
    # ---------------------------------------------------------
    with onglets[2]:
        if len(inc) == 0:
            st.info("Aucun incident sur cette période.")
        else:
            st.markdown("#### Évolution mensuelle des incidents par type")
            inc_mois = inc.copy()
            inc_mois["Mois"] = pd.to_datetime(inc_mois["date"]).dt.strftime("%Y-%m")
            par_mois = inc_mois.groupby(["Mois", "type_incident"]).size().reset_index(name="Incidents")
            graphique = alt.Chart(par_mois).mark_bar().encode(
                x=alt.X("Mois:N", title=None), y="Incidents:Q",
                color=alt.Color("type_incident:N", title="Type"),
                tooltip=["Mois", "type_incident", "Incidents"])
            st.altair_chart(graphique, width="stretch")
            tableau_accessible(par_mois)

            st.markdown("#### Coût et durée par type d'incident")
            par_type = inc.groupby("type_incident").agg(
                Nombre=("id_incident", "count"),
                Durée_moyenne_min=("duree_minutes", "mean"),
                Coût_total_kEUR=("cout_estimé_keur", "sum")).round(1).reset_index()
            par_type = par_type.sort_values("Coût_total_kEUR", ascending=False)
            par_type.columns = ["Type d'incident", "Nombre", "Durée moyenne (min)", "Coût total (k€)"]
            st.dataframe(par_type, hide_index=True, width="stretch")

            st.markdown("#### Incidents à traiter (en cours ou planifiés)")
            gravite = st.multiselect("Gravité", ["Élevée", "Moyenne", "Faible"], default=["Élevée"])
            a_traiter = inc[(inc["statut"] != "Résolu") & (inc["gravite"].isin(gravite))]
            a_traiter = a_traiter.sort_values("date", ascending=False)
            colonnes = ["date", "ligne", "station_principale", "type_incident", "gravite",
                        "duree_minutes", "cout_estimé_keur", "statut"]
            st.dataframe(a_traiter[colonnes], hide_index=True, width="stretch")
            bouton_export(a_traiter[colonnes], "incidents_a_traiter.csv", "Exporter ces incidents (CSV)")

    # ---------------------------------------------------------
    # Onglet 4 : accessibilité et priorité des travaux
    # ---------------------------------------------------------
    with onglets[3]:
        st.markdown("#### Priorité des travaux d'accessibilité")
        st.write("Indice de priorité = affluence moyenne de la station × manque d'accessibilité "
                 "(100 − score). Une station de correspondance compte double, car elle bloque tous les trajets.")
        affluence_station = freq.groupby("station")["affluence"].mean()
        priorite = accessibilite[accessibilite["station"].isin(affluence_station.index)].copy()
        priorite["Affluence moyenne"] = priorite["station"].map(affluence_station).round()
        priorite["Correspondance"] = ["Oui" if s == CORRESPONDANCE else "Non" for s in priorite["station"]]
        priorite["Indice de priorité"] = (priorite["Affluence moyenne"] * (100 - priorite["score_normalise"]) / 100
                                          * [2 if c == "Oui" else 1 for c in priorite["Correspondance"]]).round()
        priorite = priorite.sort_values("Indice de priorité", ascending=False)
        priorite["Rang"] = range(1, len(priorite) + 1)
        priorite["Équipements"] = priorite.apply(lister_equipements, axis=1)
        st.dataframe(priorite[["Rang", "station", "score_normalise", "Affluence moyenne", "Correspondance",
                               "Indice de priorité", "Équipements"]].rename(
                         columns={"station": "Station", "score_normalise": "Score /100"}),
                     hide_index=True, width="stretch")

        st.markdown("#### Trajets possibles selon le besoin")
        stations_reseau = sorted(set(sum(RESEAU.values(), [])))
        lignes = []
        for besoin in REGLES:
            possibles = 0
            total = 0
            for depart in stations_reseau:
                for arrivee in stations_reseau:
                    if depart != arrivee:
                        total += 1
                        # l'heure et la date n'influencent pas l'accessibilité
                        if evaluer_trajet(donnees_moteur, besoin, depart, arrivee, "2026-12-01", 12)["accessible"]:
                            possibles += 1
            lignes.append({"Besoin": besoin, "Trajets possibles": str(possibles) + " sur " + str(total),
                           "Part (%)": round(possibles / total * 100)})
        st.dataframe(pd.DataFrame(lignes), hide_index=True, width="stretch")
        st.warning("Aucun trajet n'est possible en fauteuil roulant : la seule correspondance, "
                   "Gare Centrale, n'a ni ascenseur ni rampe. L'équiper rendrait possibles les trajets "
                   "entre Hôpital et Centre Ville.")

    # ---------------------------------------------------------
    # Onglet 5 : usagers
    # ---------------------------------------------------------
    with onglets[4]:
        st.markdown("#### Satisfaction moyenne par profil")
        par_profil = usagers.groupby("profil")["satisfaction"].agg(["mean", "count"]).reset_index()
        par_profil.columns = ["Profil", "Satisfaction (sur 5)", "Usagers"]
        par_profil["Satisfaction (sur 5)"] = par_profil["Satisfaction (sur 5)"].round(2)
        graphique = alt.Chart(par_profil).mark_bar(color=BLEU).encode(
            x=alt.X("Satisfaction (sur 5):Q", scale=alt.Scale(domain=[0, 5])),
            y=alt.Y("Profil:N", sort="x", title=None),
            tooltip=["Profil", "Satisfaction (sur 5)", "Usagers"])
        st.altair_chart(graphique, width="stretch")
        tableau_accessible(par_profil)

        st.markdown("#### Satisfaction selon la fréquence d'utilisation et l'abonnement")
        croise = usagers.pivot_table(index="frequence_utilisation", columns="abonnement",
                                     values="satisfaction", aggfunc="mean").round(2)
        st.dataframe(croise, width="stretch")

        st.markdown("#### Qualité des données usagers")
        nb_incoherents = (usagers["profil_incoherent"] == "Oui").sum()
        st.warning("⚠️ " + str(nb_incoherents) + " profils sur " + str(len(usagers))
                   + " sont incohérents avec l'âge déclaré. Les analyses par profil sont donc à interpréter "
                     "avec prudence.")
        incoherents = usagers[usagers["profil_incoherent"] == "Oui"]
        st.dataframe(pd.crosstab(incoherents["profil"], incoherents["tranche_age"]), width="stretch")

    # ---------------------------------------------------------
    # Onglet 6 : surveillance du modèle d'IA
    # ---------------------------------------------------------
    with onglets[5]:
        st.markdown("#### Performance du modèle de prédiction d'affluence")
        perf = lire_performance()
        if perf is None:
            st.info("Relancez etape2_modele.py pour enregistrer les performances du modèle.")
        else:
            st.caption("Dernier entraînement : " + str(perf["date_entrainement"]) + " · apprentissage sur "
                       + perf["periode_apprentissage"] + " · test sur " + perf["periode_test"])
            c1, c2, c3 = st.columns(3)
            carte(c1, "Erreur moyenne (MAE)", nombre(perf["erreur_modele_points"], 1) + " points",
                  "Référence (moyenne historique) : " + nombre(perf["erreur_baseline_points"], 1) + " points.")
            carte(c2, "Bons niveaux prédits", nombre(perf["exactitude_pourcent"], 1) + " %",
                  "Calme, chargé ou saturé. Cible : 80 %.")
            rappel = perf["saturations_detectees"] / perf["saturations_total"] * 100
            carte(c3, "Saturations détectées", nombre(rappel) + " %",
                  str(perf["saturations_detectees"]) + " sur " + str(perf["saturations_total"]) + " situations.")
            st.warning("Point de vigilance : le modèle détecte environ 6 saturations sur 10. Pistes : abaisser "
                       "le seuil d'alerte, ajouter des variables (incidents, vacances, météo), ré-entraîner "
                       "chaque semaine.")

    # ---------------------------------------------------------
    # Onglet 7 : les KPI du projet (cahier des charges)
    # ---------------------------------------------------------
    with onglets[6]:
        st.markdown("#### Suivi des indicateurs de réussite du cahier des charges")
        perf = lire_performance()
        exactitude = "—" if perf is None else nombre(perf["exactitude_pourcent"], 1) + " %"
        atteint_ia = perf is not None and perf["exactitude_pourcent"] >= 80
        stations_reseau = sorted(set(sum(RESEAU.values(), [])))
        couvertes = accessibilite["station"].isin(stations_reseau).sum()
        affluence_incidents = (incidents["type_incident"] == "Affluence excessive").sum()
        satisfaction_pmr = usagers[usagers["profil"] == "PMR"]["satisfaction"].mean()
        satisfaction_senior = usagers[usagers["profil"] == "Senior"]["satisfaction"].mean()
        kpi = pd.DataFrame([
            {"Indicateur": "Exactitude de la prédiction", "Cible": "≥ 80 %", "Valeur": exactitude,
             "Statut": "✅ Atteint" if atteint_ia else "⏳ À mesurer"},
            {"Indicateur": "Couverture de l'information d'accessibilité", "Cible": "100 % des stations",
             "Valeur": str(couvertes) + " / " + str(len(stations_reseau)) + " stations", "Statut": "✅ Atteint"},
            {"Indicateur": "Fiabilité de la recommandation", "Cible": "0 trajet inadapté présenté comme adapté",
             "Valeur": "0 (règle de sécurité du moteur)", "Statut": "✅ Atteint"},
            {"Indicateur": "Centralisation des données", "Cible": "4 sources dans l'espace de pilotage",
             "Valeur": "4 / 4 (affluence, incidents, accessibilité, satisfaction)", "Statut": "✅ Atteint"},
            {"Indicateur": "Conformité RGAA prioritaire", "Cible": "100 % des critères testés",
             "Valeur": "Plan de tests à exécuter", "Statut": "⏳ À mesurer"},
            {"Indicateur": "Formation des équipes", "Cible": "100 % avant mise en service",
             "Valeur": "Mise en service non démarrée", "Statut": "⏳ À mesurer"},
            {"Indicateur": "Réduction des incidents d'affluence", "Cible": "−10 % à 6 mois",
             "Valeur": "Référence : " + str(affluence_incidents) + " incidents", "Statut": "📍 Référence mesurée"},
            {"Indicateur": "Satisfaction des publics fragiles", "Cible": "+0,5 point à 12 mois",
             "Valeur": "Référence : PMR " + nombre(satisfaction_pmr, 2) + " · seniors " + nombre(satisfaction_senior, 2),
             "Statut": "📍 Référence mesurée"},
        ])
        kpi = kpi[["Statut", "Indicateur", "Cible", "Valeur"]]      # le statut en premier : lisible d'un coup d'œil
        st.dataframe(kpi, hide_index=True, width="stretch")
        st.caption("✅ atteint sur le prototype · ⏳ mesurable seulement après un déploiement réel · "
                   "📍 valeur de départ enregistrée pour mesurer les progrès.")
        bouton_export(kpi, "kpi_projet.csv", "Exporter les KPI du projet (CSV)")

    # ---------------------------------------------------------
    # Onglet 8 : KPI mensuels officiels et export des données
    # ---------------------------------------------------------
    with onglets[7]:
        st.markdown("#### KPI mensuels par ligne")
        st.write("Mêmes indicateurs que la feuille « Indicateurs_KPIs » fournie par Mobility+, "
                 "recalculés automatiquement à partir de la base et des filtres.")
        kpi_freq = freq.groupby(["mois", "ligne"]).agg(
            affluence_totale=("affluence", "sum"), affluence_moyenne=("affluence", "mean"),
            nb_mesures=("affluence", "count"), taux_occupation_moyen=("taux_occupation", "mean")).reset_index()
        inc_mois = inc.copy()
        inc_mois["mois_num"] = pd.to_datetime(inc_mois["date"]).dt.month
        kpi_inc = inc_mois.groupby(["mois_num", "ligne"]).agg(
            nb_incidents=("id_incident", "count"), duree_moyenne_min=("duree_minutes", "mean")).reset_index()
        kpi_inc = kpi_inc.rename(columns={"mois_num": "mois"})
        kpi_mensuels = kpi_freq.merge(kpi_inc, on=["mois", "ligne"], how="left").fillna(0)
        kpi_mensuels["Mois"] = kpi_mensuels["mois"].map(NOMS_MOIS)
        kpi_mensuels = kpi_mensuels.round({"affluence_moyenne": 1, "taux_occupation_moyen": 3,
                                           "duree_moyenne_min": 1})
        kpi_mensuels = kpi_mensuels[["Mois", "ligne", "affluence_totale", "affluence_moyenne", "nb_mesures",
                                     "taux_occupation_moyen", "nb_incidents", "duree_moyenne_min"]]
        st.dataframe(kpi_mensuels, hide_index=True, width="stretch")
        bouton_export(kpi_mensuels, "kpi_mensuels.csv", "Exporter les KPI mensuels (CSV)")

        st.markdown("#### Données brutes filtrées")
        c1, c2 = st.columns(2)
        with c1:
            bouton_export(freq.drop(columns=["date"]), "frequentation_filtree.csv", "Fréquentation (CSV)")
        with c2:
            bouton_export(inc, "incidents_filtres.csv", "Incidents (CSV)")
