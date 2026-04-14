import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# ==========================================
# --- 1. CONFIGURATION & STYLE MOBILE ---
# ==========================================
st.set_page_config(page_title="BS Manager Pro", page_icon="📦", layout="wide")

# Injection CSS pour transformer Streamlit en vraie App Mobile
st.markdown("""
<style>
    /* Agrandit les lignes pour les doigts */
    [data-testid="stDataFrame"] div[role="row"] { height: 48px !important; }
    /* Cache les index inutiles à gauche */
    [data-testid="stDataFrame"] div[role="rowheader"] { display: none; }
    /* Optimise les boutons pour le tactile */
    .stButton > button {
        min-height: 50px;
        border-radius: 12px;
        font-weight: bold;
    }
    /* Resserre les espaces sur mobile */
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)


# Connexion avec cache
@st.cache_resource
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)


conn = get_connection()

# --- STRUCTURES ---
COLS_MAT = ['id', 'nom', 'stockage', 'stock_total', 'categorie', 'type', 'seuil_alerte']
COLS_EV = ['id', 'nom', 'couleur', 'date_debut', 'date_fin', 'statut']
COLS_TRANSIT = ['id', 'evenement_id', 'materiel_id', 'nom_custom', 'qte_necessaire', 'qte_depart', 'qte_fin',
                'qte_depot']
EVENT_TYPES = ["🔵 BCF", "🔴 BBFL", "🇫🇷 Tour", "🩷 Giro", "🟣 8h", "⚫ BXL Crit", "🟠 UTWB", "🟡 CL", "🚴 Repérages"]


# ==========================================
# --- 2. GESTION DES DONNÉES & CACHE ---
# ==========================================
def fetch_data(sheet, cols):
    try:
        df = conn.read(worksheet=sheet, ttl=0)
        if df is None or df.empty: return pd.DataFrame(columns=cols)
        for c in cols:
            if c not in df.columns: df[c] = None
        return df
    except:
        return pd.DataFrame(columns=cols)


if "data_loaded" not in st.session_state:
    with st.spinner("🚀 Chargement BS Logistics..."):
        st.session_state.df_mat = fetch_data("materiel", COLS_MAT)
        st.session_state.df_ev = fetch_data("evenements", COLS_EV)
        st.session_state.df_transit = fetch_data("transit", COLS_TRANSIT)
        st.session_state.df_mod = fetch_data("modeles", ['type_event', 'materiel_id', 'materiel_nom', 'qte_defaut'])
        st.session_state.df_projets = fetch_data("projets",
                                                 ['id', 'date', 'titre', 'description', 'priorite', 'statut'])
        st.session_state.data_loaded = True

# ==========================================
# --- 3. BARRE LATÉRALE (SÉCURITÉ) ---
# ==========================================
with st.sidebar:
    st.title("🛡️ Accès")
    pin = st.text_input("Code PIN Admin", type="password")
    is_admin = (pin == "1234")  # TON CODE ICI

    if is_admin:
        st.success("Mode ADMIN")
    else:
        st.info("Mode GUEST")

    if st.button("🔄 Rafraîchir tout", use_container_width=True):
        st.session_state.clear()
        st.rerun()


# ==========================================
# --- 4. FRAGMENT : ONGLET TERRAIN ---
# ==========================================
@st.fragment
def render_terrain_tab():
    st.subheader("🚚 Pointage Terrain")
    df_ev = st.session_state.df_ev
    df_transit = st.session_state.df_transit
    df_mat = st.session_state.df_mat

    actifs = df_ev[df_ev['statut'] != "Terminé"].copy()
    if actifs.empty:
        st.info("Aucun événement actif.")
        return

    actifs['label'] = actifs['couleur'] + " : " + actifs['nom']
    ev_sel = st.selectbox("Événement :", actifs['label'].tolist())
    ev_row = actifs[actifs['label'] == ev_sel].iloc[0]

    phase = st.radio("Phase :", ["🚚 Départ", "🏁 Fin", "📦 Retour"], horizontal=True)
    col_target = {"🚚 Départ": "qte_depart", "🏁 Fin": "qte_fin", "📦 Retour": "qte_depot"}[phase]

    # Préparation du kit
    kit = df_transit[df_transit['evenement_id'] == ev_row['id']].copy()
    df_mat_tmp = df_mat[['id', 'nom', 'categorie']].copy()
    df_mat_tmp['id'] = pd.to_numeric(df_mat_tmp['id'], errors='coerce')
    kit['materiel_id'] = pd.to_numeric(kit['materiel_id'], errors='coerce')

    ptg = pd.merge(kit, df_mat_tmp, left_on='materiel_id', right_on='id', how='left')
    ptg['nom'] = ptg['nom'].fillna(ptg['nom_custom'])
    ptg['categorie'] = ptg['categorie'].fillna("⚠️ Divers")

    # UI Mobile : Fusion Nom + Prévu
    ptg['display_name'] = ptg['nom'] + " (" + ptg['qte_necessaire'].astype(str) + ")"
    ptg['is_ok'] = ptg[col_target] == ptg['qte_necessaire']

    # Progression
    nb_ok = len(ptg[ptg['is_ok']])
    st.progress(nb_ok / len(ptg) if len(ptg) > 0 else 0, text=f"Progression : {nb_ok}/{len(ptg)}")

    # Export CSV
    csv_data = ptg[['categorie', 'nom', 'qte_necessaire', col_target]].to_csv(index=False).encode('utf-8')
    st.download_button("📥 Export Offline (CSV)", csv_data, f"check_{ev_row['nom']}.csv", use_container_width=True)

    # Affichage par catégorie (Expander pour mobile)
    for cat in sorted(ptg['categorie'].unique()):
        df_cat = ptg[ptg['categorie'] == cat]
        with st.expander(f"📦 {cat.upper()} ({len(df_cat)})", expanded=False):
            with st.form(f"form_{cat}_{phase}"):
                res = st.data_editor(
                    df_cat[['id_x', 'display_name', 'is_ok', col_target]].rename(columns={'id_x': 'id'}),
                    hide_index=True, use_container_width=True, key=f"edit_{cat}_{phase}",
                    disabled=['id', 'display_name'],
                    column_config={
                        "id": None, "display_name": "Article (Prévu)",
                        "is_ok": st.column_config.CheckboxColumn("✅"),
                        col_target: st.column_config.NumberColumn("🔢")
                    }
                )
                if st.form_submit_button(f"Enregistrer {cat}", use_container_width=True):
                    # Validation auto si coché
                    mask = res['is_ok'] == True
                    res.loc[mask, col_target] = df_cat.loc[mask, 'qte_necessaire'].values

                    for _, r in res.iterrows():
                        st.session_state.df_transit.loc[st.session_state.df_transit['id'] == r['id'], col_target] = r[
                            col_target]

                    conn.update(worksheet="transit", data=st.session_state.df_transit)
                    st.success("C'est bon !")
                    st.rerun()


# ==========================================
# --- 5. FRAGMENT : ONGLET STOCK ---
# ==========================================
@st.fragment
def render_stock_tab():
    st.subheader("📊 État des Stocks")
    df = st.session_state.df_mat.copy()
    df['stock_total'] = pd.to_numeric(df['stock_total'], errors='coerce').fillna(0)
    df['seuil_alerte'] = pd.to_numeric(df['seuil_alerte'], errors='coerce').fillna(0)

    # Dashboard
    c1, c2 = st.columns(2)
    c1.metric("Total Articles", len(df))
    alerte_count = len(df[(df['stock_total'] < df['seuil_alerte']) & (df['seuil_alerte'] > 0)])
    c2.metric("En Alerte", alerte_count, delta=-alerte_count, delta_color="inverse")

    recherche = st.text_input("🔍 Rechercher un article...", key="search_stock")
    df_show = df[df['nom'].str.contains(recherche, case=False, na=False)] if recherche else df

    with st.form("stock_form"):
        updates = []
        for cat in sorted(df_show['categorie'].fillna("DIVERS").unique()):
            df_cat = df_show[df_show['categorie'] == cat]
            with st.expander(f"📂 {cat.upper()} ({len(df_cat)})"):
                edit = st.data_editor(
                    df_cat, hide_index=True, use_container_width=True, key=f"stock_{cat}",
                    disabled=['id', 'nom', 'categorie', 'type'],
                    column_config={"id": None, "stockage": st.column_config.SelectboxColumn("Lieu",
                                                                                            options=["Stock", "Bureau",
                                                                                                     "Club house"])}
                )
                updates.append(edit)

        if st.form_submit_button("💾 Sauvegarder l'inventaire", use_container_width=True, type="primary"):
            df_final = pd.concat(updates)
            df.set_index('id', inplace=True)
            df_final.set_index('id', inplace=True)
            df.update(df_final)
            st.session_state.df_mat = df.reset_index()
            conn.update(worksheet="materiel", data=st.session_state.df_mat)
            st.success("Stock mis à jour !")
            st.rerun()


# ==========================================
# --- 6. INTERFACE ET ONGLETS ---
# ==========================================
if is_admin:
    t_terrain, t_stock, t_ev, t_courses, t_proj = st.tabs(
        ["🚚 Terrain", "📊 Stock", "📅 Évents", "🛒 Courses", "🚀 Projets"])
else:
    t_terrain, t_ev, t_courses = st.tabs(["🚚 Terrain", "📅 Évents", "🛒 Courses"])
    t_stock = t_proj = None

with t_terrain:
    render_terrain_tab()

if is_admin and t_stock:
    with t_stock:
        render_stock_tab()

with t_ev:
    st.subheader("📅 Liste des Événements")
    if is_admin:
        with st.expander("➕ Nouvel Événement"):
            with st.form("add_ev"):
                n = st.text_input("Nom")
                t = st.selectbox("Type", EVENT_TYPES)
                d1, d2 = st.columns(2)
                start = d1.date_input("Début")
                end = d2.date_input("Fin")
                if st.form_submit_button("Créer"):
                    # Logique de création (simplifiée ici pour gain de place)
                    new_id = int(st.session_state.df_ev['id'].max() + 1)
                    new_row = pd.DataFrame(
                        [{"id": new_id, "nom": n, "couleur": t, "date_debut": str(start), "date_fin": str(end),
                          "statut": "En préparation"}])
                    st.session_state.df_ev = pd.concat([st.session_state.df_ev, new_row], ignore_index=True)
                    conn.update(worksheet="evenements", data=st.session_state.df_ev)
                    st.success("Événement créé !")
                    st.rerun()

    st.data_editor(st.session_state.df_ev, hide_index=True, use_container_width=True,
                   disabled=['id', 'nom', 'couleur', 'date_debut', 'date_fin'])

with t_courses:
    st.subheader("🛒 Shopping List")
    df_m = st.session_state.df_mat
    df_m['stock_total'] = pd.to_numeric(df_m['stock_total'], errors='coerce').fillna(0)
    df_m['seuil_alerte'] = pd.to_numeric(df_m['seuil_alerte'], errors='coerce').fillna(0)
    needed = df_m[(df_m['stock_total'] < df_m['seuil_alerte']) & (df_m['seuil_alerte'] > 0)].copy()
    if not needed.empty:
        needed['🛒 Manquant'] = needed['seuil_alerte'] - needed['stock_total']
        st.table(needed[['nom', 'stock_total', 'seuil_alerte', '🛒 Manquant']])
    else:
        st.success("Rien à acheter !")

if is_admin and t_proj:
    with t_proj:
        st.subheader("🚀 Projets & Idées")
        res_p = st.data_editor(st.session_state.df_projets, hide_index=True, use_container_width=True)
        if st.button("💾 Sauvegarder Projets"):
            conn.update(worksheet="projets", data=res_p)
            st.session_state.df_projets = res_p
            st.success("Projets enregistrés")
