import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# ==========================================
# --- 1. CONFIGURATION & STYLE NATIVE APP ---
# ==========================================
st.set_page_config(page_title="BS Manager Pro", page_icon="📦", layout="wide")

# CSS pour supprimer les bordures inutiles et agrandir les zones tactiles
st.markdown("""
<style>
    /* Supprime les marges excessives sur mobile */
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }

    /* Style pour les titres de catégories */
    .cat-header {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 8px;
        margin-top: 20px;
        margin-bottom: 10px;
        font-weight: bold;
        border-left: 5px solid #ff4b4b;
    }

    /* Agrandit la taille des interrupteurs pour les doigts */
    .stCheckbox, .stToggleButton, .stSelectbox {
        margin-bottom: 15px;
    }

    /* Bouton de sauvegarde flottant ou large */
    .stButton > button {
        width: 100%;
        min-height: 55px;
        border-radius: 12px;
        font-size: 18px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)


conn = get_connection()


# ==========================================
# --- 2. GESTION DES DONNÉES ---
# ==========================================
def fetch_data(sheet):
    return conn.read(worksheet=sheet, ttl=0)


if "data_loaded" not in st.session_state:
    with st.spinner("🚀 Initialisation..."):
        st.session_state.df_mat = fetch_data("materiel")
        st.session_state.df_ev = fetch_data("evenements")
        st.session_state.df_transit = fetch_data("transit")
        st.session_state.data_loaded = True

# ==========================================
# --- 3. SÉCURITÉ (SIDEBAR) ---
# ==========================================
with st.sidebar:
    st.title("🛡️ Accès")
    pin = st.text_input("Code PIN Admin", type="password")
    is_admin = (pin == "1234")  # Change ton code ici

    if is_admin:
        st.success("Mode ADMIN")
    else:
        st.info("Mode TERRAIN")

    if st.button("🔄 Rafraîchir les données"):
        st.session_state.clear()
        st.rerun()


# ==========================================
# --- 4. FRAGMENT : POINTAGE TERRAIN ---
# ==========================================
@st.fragment
def render_terrain():
    st.subheader("🚚 Pointage Terrain")
    df_ev = st.session_state.df_ev
    df_transit = st.session_state.df_transit
    df_mat = st.session_state.df_mat

    # Filtre événements actifs
    actifs = df_ev[df_ev['statut'] != "Terminé"].copy()
    if actifs.empty:
        st.info("Aucun événement actif.")
        return

    # Sélecteur d'évent et Phase
    actifs['label'] = actifs['couleur'] + " : " + actifs['nom']
    ev_sel = st.selectbox("Événement :", actifs['label'].tolist())
    ev_row = actifs[actifs['label'] == ev_sel].iloc[0]

    phase = st.radio("Phase de travail :", ["🚚 Départ", "🏁 Fin", "📦 Retour"], horizontal=True)
    col_target = {"🚚 Départ": "qte_depart", "🏁 Fin": "qte_fin", "📦 Retour": "qte_depot"}[phase]

    # Jointure pour avoir les noms et catégories
    kit = df_transit[df_transit['evenement_id'] == ev_row['id']].copy()
    ptg = pd.merge(kit, df_mat[['id', 'nom', 'categorie']], left_on='materiel_id', right_on='id', how='left')
    ptg['nom'] = ptg['nom'].fillna(ptg['nom_custom'])
    ptg['categorie'] = ptg['categorie'].fillna("DIVERS")

    # Barre de progression
    ptg['is_ok'] = ptg[col_target] == ptg['qte_necessaire']
    nb_ok = len(ptg[ptg['is_ok']])
    st.progress(nb_ok / len(ptg) if len(ptg) > 0 else 0, text=f"Progression : {nb_ok}/{len(ptg)}")

    st.divider()

    # --- LISTE FIGÉE (SANS SCROLL INTERNE) ---
    for cat in sorted(ptg['categorie'].unique()):
        st.markdown(f'<div class="cat-header">📦 {cat.upper()}</div>', unsafe_allow_html=True)

        df_cat = ptg[ptg['categorie'] == cat]

        # Un formulaire par catégorie pour valider par bloc
        with st.form(key=f"form_{cat}_{phase}"):
            toggles = {}
            reels = {}

            for _, row in df_cat.iterrows():
                # On crée une ligne avec colonnes pour le nom et la quantité
                c1, c2 = st.columns([3, 1])

                with c1:
                    # L'interrupteur : toute la zone du texte est cliquable !
                    label = f"**{row['nom']}** ({row['qte_necessaire']} prévus)"
                    toggles[row['id']] = st.toggle(label, value=bool(row['is_ok']), key=f"tgl_{row['id']}_{phase}")

                with c2:
                    # Champ numérique si besoin d'ajuster précisément
                    reels[row['id']] = st.number_input("Réel", value=int(row[col_target]), min_value=0, step=1,
                                                       label_visibility="collapsed", key=f"num_{row['id']}_{phase}")

            # Bouton de sauvegarde local à la catégorie
            if st.form_submit_button(f"💾 ENREGISTRER {cat.upper()}", type="primary"):
                for _, row in df_cat.iterrows():
                    item_id = row['id']
                    # Si toggle coché -> quantité max, sinon quantité saisie
                    val_finale = row['qte_necessaire'] if toggles[item_id] else reels[item_id]

                    # Mise à jour session state
                    st.session_state.df_transit.loc[
                        st.session_state.df_transit['id'] == item_id, col_target] = val_finale

                # Mise à jour Google Sheets
                conn.update(worksheet="transit", data=st.session_state.df_transit)
                st.success(f"{cat} sauvegardé !")
                st.rerun()


# ==========================================
# --- 5. INTERFACE ET ONGLETS ---
# ==========================================
if is_admin:
    t_terrain, t_stock, t_ev, t_courses, t_proj = st.tabs(
        ["🚚 Terrain", "📊 Stock", "📅 Évents", "🛒 Courses", "🚀 Projets"])
else:
    t_terrain, t_ev, t_courses = st.tabs(["🚚 Terrain", "📅 Évents", "🛒 Courses"])
    t_stock = t_proj = None

with t_terrain:
    render_terrain()

if is_admin and t_stock:
    with t_stock:
        st.subheader("📊 Gestion du Stock")
        # On garde le data_editor pour le stock car c'est une vue "Admin" plus complexe
        edited_stock = st.data_editor(st.session_state.df_mat, hide_index=True, use_container_width=True,
                                      disabled=['id', 'nom', 'categorie'])
        if st.button("💾 Sauvegarder l'inventaire"):
            conn.update(worksheet="materiel", data=edited_stock)
            st.session_state.df_mat = edited_stock
            st.success("Stock mis à jour !")

with t_ev:
    st.subheader("📅 Événements")
    if is_admin:
        with st.expander("➕ Nouvel Événement"):
            with st.form("add_ev"):
                n = st.text_input("Nom de l'évent")
                if st.form_submit_button("Créer"):
                    st.info("Logique de création active")
    st.dataframe(st.session_state.df_ev, hide_index=True, use_container_width=True)

with t_courses:
    st.subheader("🛒 Shopping List")
    # Calcul simple des alertes
    df_m = st.session_state.df_mat
    alertes = df_m[pd.to_numeric(df_m['stock_total']) < pd.to_numeric(df_m['seuil_alerte'])]
    if not alertes.empty:
        st.warning(f"Rupture sur {len(alertes)} articles")
        st.table(alertes[['nom', 'stock_total', 'seuil_alerte']])
    else:
        st.success("Tout est OK !")

if is_admin and t_proj:
    with t_proj:
        st.subheader("🚀 Projets")
        res_p = st.data_editor(st.session_state.df_projets, hide_index=True, use_container_width=True)
        if st.button("💾 Sauvegarder Projets"):
            conn.update(worksheet="projets", data=res_p)
            st.success("Projets enregistrés")
