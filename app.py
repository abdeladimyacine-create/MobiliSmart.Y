# =============================================================
# L'application MobiliSmart
# Projet Mobility+
# =============================================================
# 2 pages :
#   - Planifier mon trajet  (pour les usagers : accessibilité + affluence du trajet)
#   - Pilotage du réseau    (pour les équipes internes)
# + des réglages d'accessibilité (grands caractères, contraste renforcé)
# Les couleurs de base sont réglées dans le fichier .streamlit/config.toml
#
# Pour lancer l'application, tape dans le terminal :
#     streamlit run app.py
# =============================================================

import datetime
import sqlite3
import pandas as pd
import altair as alt                       # pour les graphiques (installé avec Streamlit)
import streamlit as st

from page_pilotage import afficher_pilotage   # l'espace de pilotage (protégé)

# Le moteur de l'étape 3 (il utilise lui-même le modèle d'IA de l'étape 2)
from etape3_recommandation import (RESEAU, REGLES, ICONES_TYPES, charger_donnees, evaluer_trajet,
                                   meilleur_horaire, stations_compatibles, occupation_etape,
                                   calculer_niveau)

st.set_page_config(page_title="MobiliSmart", page_icon="🚇", layout="centered")

# Déclarer la page en français (Streamlit la déclare en anglais par défaut).
# Utile pour les lecteurs d'écran (critère RGAA) et pour éviter la traduction automatique du navigateur.
st.iframe("""<script>
    window.parent.document.documentElement.lang = "fr";
    window.parent.document.documentElement.setAttribute("translate", "no");
</script>""", height=1)


# =============================================================
# 1. LE STYLE DE L'APPLICATION (CSS)
# =============================================================
# Le CSS décrit l'apparence : couleurs, arrondis, ombres, espacements.
# Toutes les couleurs de texte respectent un contraste d'au moins 4,5:1 (RGAA).
STYLE = """
<style>
[data-testid="stToolbar"] { display: none; }                 /* cache le bouton « Deploy » */
.block-container { padding-top: 2rem; max-width: 780px; }

/* Bandeau d'en-tête */
.ms-hero { background: linear-gradient(135deg, #0A2E6E 0%, #0B5CAD 100%); border-radius: 20px;
           padding: 26px 28px; margin-bottom: 18px; }
.ms-hero .ms-hero-titre { color: #FFFFFF; font-size: 1.8rem; font-weight: 800; margin: 0; }
.ms-hero .ms-hero-texte { color: #DCE8F7; margin: 6px 0 0 0; font-size: 1rem; }

/* Cartes blanches arrondies avec une ombre légère */
[data-testid="stForm"], [data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 18px !important; border: 1px solid #E4E9F0 !important;
    box-shadow: 0 6px 20px rgba(16, 24, 40, 0.06); background: #FFFFFF; }
.ms-carte { background: #FFFFFF; border: 1px solid #E4E9F0; border-radius: 18px;
            box-shadow: 0 6px 20px rgba(16, 24, 40, 0.06); padding: 22px 24px; margin: 16px 0; }
.ms-titre-trajet { font-size: 1.4rem; font-weight: 800; color: #1B1F24; }
.ms-sous-titre { color: #4A5260; font-size: 0.95rem; margin-top: 2px; }
.ms-phrase { color: #1B1F24; margin-top: 12px; }

/* Pastilles d'information */
.ms-pastilles { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.ms-pastille { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 999px;
               font-weight: 600; font-size: 0.92rem; border: 1px solid; }
.ms-vert   { background: #E8F5EC; color: #14532D; border-color: #B7E1C3; }
.ms-orange { background: #FFF4E5; color: #7A4100; border-color: #F6D3A1; }
.ms-rouge  { background: #FDECEC; color: #8A1C1C; border-color: #F5C2C2; }
.ms-bleu   { background: #EAF2FB; color: #0A2E6E; border-color: #C5DAF2; }

/* Feuille de route du trajet (ligne verticale colorée) */
.ms-arret { display: flex; gap: 14px; align-items: flex-start; }
.ms-point { width: 18px; height: 18px; border-radius: 50%; background: #FFFFFF; border: 4px solid #1B1F24;
            flex: none; margin-top: 2px; }
.ms-arret-nom { font-weight: 700; color: #1B1F24; }
.ms-arret-info { color: #4A5260; font-size: 0.88rem; }
.ms-troncon { display: flex; gap: 14px; margin: 4px 0; }
.ms-barre { width: 6px; border-radius: 3px; margin: 0 6px; min-height: 70px; flex: none; }
.ms-troncon-texte { padding: 10px 0; color: #1B1F24; }
.ms-badge { display: inline-block; min-width: 28px; text-align: center; padding: 2px 8px; border-radius: 7px;
            font-weight: 800; margin-right: 6px; }
.ms-valeur { font-size: 1.8rem !important; font-weight: 800; color: #1B1F24; margin: 0 0 6px 0; line-height: 1.2; }
.ms-section { font-size: 1.15rem; font-weight: 800; color: #1B1F24; margin: 22px 0 6px 0; }
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)


# =============================================================
# 2. FONCTIONS UTILES
# =============================================================

# Lire les données et le modèle d'IA une seule fois (gardés en mémoire)
@st.cache_resource
def lire_donnees():
    return charger_donnees()


@st.cache_data
def lire_table(nom_table):
    connexion = sqlite3.connect("data/mobility.db")
    tableau = pd.read_sql("SELECT * FROM " + nom_table, connexion)
    connexion.close()
    return tableau


# Premier jour prédit : juste après la fin de l'historique (janvier à juin 2026)
DEBUT_PREDICTIONS = datetime.date(2026, 7, 1)


# Transformer une date en "samedi 21 novembre 2026"
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]


def afficher_date(texte_date):
    date = pd.to_datetime(texte_date)
    return JOURS[date.dayofweek] + " " + str(date.day) + " " + MOIS[date.month - 1] + " " + str(date.year)


# Chaque niveau a une icône, un mot ET une couleur : l'information ne passe jamais par la couleur seule
ICONES = {"Calme": "🟢", "Chargé": "🟠", "Saturé": "🔴"}
CLASSES_NIVEAU = {"Calme": "ms-vert", "Chargé": "ms-orange", "Saturé": "ms-rouge"}
CONSEILS = {
    "Calme": "Vous devriez trouver de la place facilement.",
    "Chargé": "La rame sera bien remplie : vous voyagerez peut-être debout.",
    "Saturé": "La rame sera presque pleine : il sera difficile de monter, surtout en fauteuil ou avec une poussette.",
}
STATUTS = {"Compatible": "✅ Équipée pour votre besoin",
           "Incompatible": "❌ Non équipée pour votre besoin",
           "Indéterminé": "❔ Information manquante"}

# Couleur officielle de chaque ligne (référentiel des lignes) : (fond, texte)
COULEURS_LIGNES = {"Bleu": ("#1E63B5", "#FFFFFF"), "Vert": ("#1F7A4D", "#FFFFFF"),
                   "Orange": ("#F28C28", "#1B1F24")}


# Une pastille d'information
def pastille(texte, classe):
    return '<span class="ms-pastille ' + classe + '">' + texte + '</span>'


# Un tableau sous chaque graphique, pour les lecteurs d'écran (accessibilité)
def tableau_accessible(tableau):
    with st.expander("Voir les valeurs sous forme de tableau"):
        st.dataframe(tableau, hide_index=True)


# Graphique de l'affluence, avec l'heure choisie mise en évidence et les seuils 40 % et 80 %
def graphique_affluence(tableau, heure_choisie):
    tableau = tableau.copy()
    tableau["Repère"] = ["Votre heure de départ" if h == heure_choisie else "Autres heures"
                         for h in tableau["Heure"]]
    barres = alt.Chart(tableau).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("Heure:O", title="Heure de la journée", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Remplissage prévu (%):Q", title="Remplissage prévu (%)", scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("Repère:N", title=None, legend=alt.Legend(orient="top"),
                        scale=alt.Scale(domain=["Votre heure de départ", "Autres heures"],
                                        range=["#0B5CAD", "#B9CCE2"])),
        tooltip=["Heure", "Remplissage prévu (%)"],
    )
    reperes = pd.DataFrame({"seuil": [40, 80], "texte": ["40 % : chargé", "80 % : saturé"]})
    lignes = alt.Chart(reperes).mark_rule(strokeDash=[4, 4], color="#5A6270").encode(y="seuil:Q")
    textes = alt.Chart(reperes).mark_text(align="left", dx=4, dy=-6, color="#3A4048").encode(
        y="seuil:Q", x=alt.value(0), text="texte:N")
    st.altair_chart((barres + lignes + textes).configure_view(strokeWidth=0), width="stretch")


# La feuille de route du trajet, en HTML : arrêts + tronçons colorés aux couleurs des lignes
def feuille_de_route(resultat, donnees, lignes_reseau, date, heure):
    html = ""
    stations = resultat["stations"]
    for numero in range(len(stations)):
        station = stations.iloc[numero]
        # La couleur du point = la couleur de la ligne qui arrive ou qui part
        etape = resultat["trajet"][min(numero, len(resultat["trajet"]) - 1)]
        couleur = COULEURS_LIGNES[lignes_reseau[etape[0]]["couleur"]][0]
        html += ('<div class="ms-arret"><div class="ms-point" style="border-color:' + couleur + '"></div>'
                 + '<div><div class="ms-arret-nom">' + station["Station"]
                 + ' <span class="ms-arret-info">· ' + station["Rôle"].lower() + '</span></div>'
                 + '<div class="ms-arret-info">' + STATUTS[station["Statut"]] + ' · ' + station["Équipements"]
                 + '</div></div></div>')
        # Entre deux arrêts : le tronçon de ligne à prendre
        if numero < len(resultat["trajet"]):
            ligne, debut, fin = resultat["trajet"][numero]
            infos = lignes_reseau[ligne]
            fond, texte = COULEURS_LIGNES[infos["couleur"]]
            occupation = occupation_etape(donnees, resultat["trajet"][numero], date, heure)
            niveau = calculer_niveau(occupation)
            html += ('<div class="ms-troncon"><div class="ms-barre" style="background:' + fond + '"></div>'
                     + '<div class="ms-troncon-texte">'
                     + '<span class="ms-badge" style="background:' + fond + ';color:' + texte + '">'
                     + ligne[-1] + '</span>'
                     + ICONES_TYPES.get(infos["type"], "") + " " + infos["type"]
                     + ' · un passage toutes les ' + str(infos["frequence_passage_min"]) + ' min<br>'
                     + pastille(ICONES[niveau] + " " + niveau + " · " + str(round(occupation * 100)) + " %",
                                CLASSES_NIVEAU[niveau])
                     + '</div></div>')
    return '<div class="ms-carte">' + html + '</div>'


# =============================================================
# 3. BARRE LATÉRALE : MENU ET RÉGLAGES D'ACCESSIBILITÉ
# =============================================================

st.sidebar.markdown("## 🚇 MobiliSmart")
st.sidebar.caption("Mobility+ · le transport accessible à tous")
page = st.sidebar.radio("Menu", ["Planifier mon trajet", "Pilotage du réseau"])

st.sidebar.write("---")
st.sidebar.write("**Réglages d'affichage**")
grands_caracteres = st.sidebar.checkbox("Grands caractères")
contraste_renforce = st.sidebar.checkbox("Contraste renforcé")

style = ""
if grands_caracteres:
    style = style + "html { font-size: 125% !important; }"   # tout le texte grossit de 25 %
if contraste_renforce:
    style = style + """
        .stApp { background-color: #FFFFFF; }
        p, label, li, h1, h2, h3, .ms-arret-info, .ms-sous-titre { color: #000000 !important; }
        *:focus { outline: 3px solid #000000 !important; }
    """
if style != "":
    st.markdown("<style>" + style + "</style>", unsafe_allow_html=True)


# =============================================================
# 4. PAGE « PLANIFIER MON TRAJET »
# =============================================================
if page == "Planifier mon trajet":

    st.markdown('<div class="ms-hero"><p class="ms-hero-titre">Où allez-vous ?</p>'
                '<p class="ms-hero-texte">MobiliSmart vérifie que votre trajet est adapté à votre besoin '
                'et vous indique s\'il y aura du monde.</p></div>', unsafe_allow_html=True)

    donnees = lire_donnees()
    lignes_reseau = lire_table("lignes").set_index("nom_ligne").to_dict("index")

    # --- Le formulaire : rien n'est calculé tant que l'usager n'a pas cliqué sur le bouton ---
    toutes_les_stations = sorted(set(sum(RESEAU.values(), [])))
    with st.form("formulaire_trajet"):
        colonne1, colonne2 = st.columns(2)
        choix_depart = colonne1.selectbox("📍 Départ", toutes_les_stations)
        choix_arrivee = colonne2.selectbox("🏁 Arrivée", toutes_les_stations, index=1)
        choix_besoin = st.selectbox("♿ Votre besoin d'accessibilité", list(REGLES.keys()), index=3)
        colonne3, colonne4 = st.columns(2)
        # Les données s'arrêtent fin juin 2026 : les prédictions commencent le 1er juillet 2026
        choix_date = colonne3.date_input("📅 Jour", value=DEBUT_PREDICTIONS,
                                         min_value=DEBUT_PREDICTIONS, format="DD/MM/YYYY")
        choix_heure = colonne4.slider("🕗 Heure de départ", min_value=0, max_value=23, value=8, format="%d h")
        bouton = st.form_submit_button("Rechercher mon trajet", type="primary", width="stretch")

    # Au clic, on mémorise les choix : le résultat reste affiché
    # même si l'usager change ensuite un réglage d'affichage.
    if bouton:
        if choix_depart == choix_arrivee:
            st.error("La station de départ et la station d'arrivée doivent être différentes.")
            st.session_state.pop("calcul", None)
        else:
            st.session_state["calcul"] = (choix_depart, choix_arrivee, choix_besoin, choix_date, choix_heure)

    if "calcul" not in st.session_state:
        st.stop()      # on s'arrête ici : pas de résultat à afficher

    depart, arrivee, besoin, date, heure = st.session_state["calcul"]

    # --- On interroge le moteur ---
    resultat = evaluer_trajet(donnees, besoin, depart, arrivee, date, heure)
    conseil = meilleur_horaire(donnees, besoin, depart, arrivee, date, heure)
    niveau = resultat["niveau"]
    pourcentage = round(resultat["occupation_max"] * 100)

    # --- 1. La carte de résultat ---
    pastilles = ""
    if resultat["accessible"]:
        pastilles += pastille("✅ Trajet adapté à votre besoin", "ms-vert")
    else:
        pastilles += pastille("❌ Trajet non adapté à votre besoin", "ms-rouge")
    pastilles += pastille(ICONES[niveau] + " " + niveau + " · environ " + str(pourcentage) + " %",
                          CLASSES_NIVEAU[niveau])
    if conseil["heure"] != heure and conseil["niveau"] != niveau:
        pastilles += pastille("🕗 Meilleur départ : " + str(conseil["heure"]) + " h · "
                              + conseil["niveau"].lower(), "ms-bleu")
    if resultat["incident"]:
        pastilles += pastille("⚠️ Incident important en cours", "ms-orange")

    st.markdown('<div class="ms-carte">'
                + '<div class="ms-titre-trajet">' + depart + ' → ' + arrivee + '</div>'
                + '<div class="ms-sous-titre">' + afficher_date(date).capitalize() + ' · départ à '
                + str(heure) + ' h · ' + besoin + '</div>'
                + '<div class="ms-pastilles">' + pastilles + '</div>'
                + '<div class="ms-phrase">' + CONSEILS[niveau] + '</div>'
                + '</div>', unsafe_allow_html=True)

    # --- 2. Si le trajet n'est pas adapté : la station qui bloque et une solution ---
    if not resultat["accessible"]:
        stations_bloquantes = resultat["stations"][resultat["stations"]["Statut"] != "Compatible"]
        noms = ", ".join(stations_bloquantes["Station"])
        st.error("La station " + noms + " n'est pas équipée pour votre besoin.")
        compatibles = stations_compatibles(donnees, besoin)
        if len(compatibles) > 0:
            st.write("Stations du réseau adaptées à votre besoin : " + ", ".join(compatibles) + ".")
        st.info("📞 Contactez le service d'assistance de Mobility+ : un agent peut organiser "
                "un accompagnement ou un transport adapté pour ce trajet.")

    # --- 3. La feuille de route ---
    st.markdown('<div class="ms-section">Votre itinéraire</div>', unsafe_allow_html=True)
    st.markdown(feuille_de_route(resultat, donnees, lignes_reseau, date, heure), unsafe_allow_html=True)

    # --- 4. L'affluence sur toute la journée pour ce trajet ---
    st.markdown('<div class="ms-section">Affluence prévue sur la journée</div>', unsafe_allow_html=True)
    lignes_graphique = []
    for h in range(24):
        occupations = [occupation_etape(donnees, etape, date, h) for etape in resultat["trajet"]]
        lignes_graphique.append({"Heure": h, "Remplissage prévu (%)": round(max(occupations) * 100)})
    graphique = pd.DataFrame(lignes_graphique)
    graphique_affluence(graphique, heure)
    tableau_accessible(graphique)
    st.caption("Prévisions fondées sur les habitudes observées de janvier à juin 2026. "
               "Elles ne tiennent pas encore compte des vacances, des jours fériés ni des événements.")

    with st.expander("Comment MobiliSmart évalue-t-il votre trajet ?"):
        st.write("1. **Accessibilité** : chaque station du trajet (départ, correspondance, arrivée) "
                 "doit être équipée pour votre besoin. Une station n'est jamais considérée comme "
                 "accessible si une information manque.")
        st.write("2. **Affluence** : un modèle d'intelligence artificielle prévoit le remplissage "
                 "des rames à partir de l'historique de janvier à juin 2026.")
        st.write("3. **Évaluation du trajet** : MobiliSmart calcule une note interne qui combine "
                 "l'accessibilité de la station la moins équipée (50 %), la tranquillité de l'étape "
                 "la plus chargée (30 %) et l'absence d'incident important (20 %).")
        st.write("4. **Conseil d'horaire** : MobiliSmart compare votre heure de départ avec les "
                 "2 heures avant et après, et vous signale le créneau le moins chargé.")


# =============================================================
# 5. PAGE « PILOTAGE DU RÉSEAU » (équipes internes, protégée par mot de passe)
# =============================================================
# Le contenu de cette page est dans le fichier page_pilotage.py
elif page == "Pilotage du réseau":
    afficher_pilotage(lire_donnees())
