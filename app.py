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
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    .cat-header {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 8px;
        margin-top: 20px;
        margin-bottom: 10px;
        font-weight: bold;
        border-left: 5px solid #ff4b4b;
    }
    .stCheckbox, .stToggleButton, .stSelectbox { margin-bottom: 15px; }
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
        st.session_state.df_mod = fetch_data("modeles")
        st.session_state.df_projets = fetch_data("projets")
        st.session_state.data_loaded = True

# ==========================================
# --- 3. SÉCURITÉ (SIDEBAR) ---
# ==========================================
with st.sidebar:
    st.title("🛡️ Accès")
    pin = st.text_input("Code PIN Admin", type="password")
    is_admin = (pin == "1234") # Change ton code ici
    
    if is_admin: st.success("✅ Mode ADMIN")
    else: st.info("👀 Mode TERRAIN")

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

    actifs = df_ev[df_ev['statut'] != "Terminé"].copy()
    if actifs.empty:
        st.info("Aucun événement actif.")
        return

    actifs['label'] = actifs['couleur'] + " : " + actifs['nom']
    ev_sel = st.selectbox("Événement :", actifs['label'].tolist())
    ev_row = actifs[actifs['label'] == ev_sel].iloc[0]
    
    phase = st.radio("Phase de travail :", ["🚚 Départ", "🏁 Fin", "📦 Retour"], horizontal=True)
    col_target = {"🚚 Départ": "qte_depart", "🏁 Fin": "qte_fin", "📦 Retour": "qte_depot"}[phase]

    # Jointure sécurisée
    kit = df_transit[df_transit['evenement_id'] == ev_row['id']].copy()
    df_mat_tmp = df_mat[['id', 'nom', 'categorie']].copy()
    
    ptg = pd.merge(kit, df_mat_tmp, left_on='materiel_id', right_on='id', how='left')
    # CRUCIAL : Renommer id_x (du kit transit) en id pour éviter le plantage
    ptg = ptg.rename(columns={'id_x': 'id'})
    
    ptg['nom'] = ptg['nom'].fillna(ptg['nom_custom'])
    ptg['categorie'] = ptg['categorie'].fillna("DIVERS")
    
    # Barre de progression
    ptg['is_ok'] = ptg[col_target] == ptg['qte_necessaire']
    nb_ok = len(ptg[ptg['is_ok']])
    st.progress(nb_ok/len(ptg) if len(ptg)>0 else 0, text=f"📊 Progression : {nb_ok}/{len(ptg)}")

    # Export hors-ligne
    csv_data = ptg[['categorie', 'nom', 'qte_necessaire', col_target]].to_csv(index=False).encode('utf-8')
    st.download_button("📥 Export Offline (CSV)", csv_data, f"check_{ev_row['nom']}.csv", use_container_width=True)

    st.divider()
    st.info("💡 **Astuce :** Clique n'importe où sur le texte pour valider l'article entier !")

    # --- LISTE FIGÉE (SANS SCROLL INTERNE) ---
    for cat in sorted(ptg['categorie'].unique()):
        st.markdown(f'<div class="cat-header">📦 {cat.upper()}</div>', unsafe_allow_html=True)
        
        df_cat = ptg[ptg['categorie'] == cat]
        
        with st.form(key=f"form_{cat}_{phase}"):
            toggles = {}
            reels = {}
            
            for _, row in df_cat.iterrows():
                c1, c2 = st.columns([3, 1], vertical_alignment="center")
                
                with c1:
                    label = f"**{row['nom']}** ({row['qte_necessaire']} prévus)"
                    toggles[row['id']] = st.toggle(label, value=bool(row['is_ok']), key=f"tgl_{row['id']}_{phase}")
                
                with c2:
                    # Sécurisation du chiffre pour éviter les bugs si la case est vide
                    val_reel = pd.to_numeric(row[col_target], errors='coerce')
                    if pd.isna(val_reel): val_reel = 0
                    reels[row['id']] = st.number_input("Réel", value=int(val_reel), min_value=0, step=1, label_visibility="collapsed", key=f"num_{row['id']}_{phase}")

            # Bouton de sauvegarde sécurisé (à l'intérieur du formulaire)
            if st.form_submit_button(f"💾 ENREGISTRER {cat.upper()}", type="primary"):
                for _, row in df_cat.iterrows():
                    item_id = row['id']
                    val_finale = row['qte_necessaire'] if toggles[item_id] else reels[item_id]
                    st.session_state.df_transit.loc[st.session_state.df_transit['id'] == item_id, col_target] = val_finale
                
                conn.update(worksheet="transit", data=st.session_state.df_transit)
                st.success(f"✅ {cat} sauvegardé !")
                st.rerun()

# ==========================================
# --- 5. INTERFACE ET ONGLETS ---
# ==========================================
if is_admin:
    t_terrain, t_stock, t_ev, t_courses, t_proj = st.tabs(["🚚 Terrain", "📊 Stock", "📅 Évents", "🛒 Courses", "🚀 Projets"])
else:
    t_terrain, t_ev, t_courses = st.tabs(["🚚 Terrain", "📅 Évents", "🛒 Courses"])
    t_stock = t_proj = None

with t_terrain:
    render_terrain()

if is_admin and t_stock:
    with t_stock:
        st.subheader("📊 Gestion du Stock")
        edited_stock = st.data_editor(st.session_state.df_mat, hide_index=True, use_container_width=True, disabled=['id', 'nom', 'categorie', 'type'])
        if st.button("💾 Sauvegarder l'inventaire"):
            conn.update(worksheet="materiel", data=edited_stock)
            st.session_state.df_mat = edited_stock
            st.success("Stock mis à jour !")

with t_ev:
    st.subheader("📅 Événements")
    if is_admin:
        with st.expander("➕ Nouvel Événement"):
            with st.form("add_ev"):
                n_name = st.text_input("Nom de l'évent")
                EVENT_TYPES = ["🔵 BCF", "🔴 BBFL", "🇫🇷 Tour", "🩷 Giro", "🟣 8h", "⚫ BXL Crit", "🟠 UTWB", "🟡 CL", "🚴 Repérages"]
                n_type = st.selectbox("Type", EVENT_TYPES)
                d1, d2 = st.columns(2)
                start = d1.date_input("Début")
                end = d2.date_input("Fin")
                
                if st.form_submit_button("Créer l'événement"):
                    if n_name:
                        df_ev = st.session_state.df_ev
                        df_transit = st.session_state.df_transit
                        df_mod = st.session_state.df_mod
                        
                        new_id = int(pd.to_numeric(df_ev['id']).max()) + 1 if not df_ev.empty and pd.notna(df_ev['id'].max()) else 1
                        new_ev = pd.DataFrame([{"id": new_id, "nom": n_name, "couleur": n_type, "date_debut": str(start), "date_fin": str(end), "statut": "En préparation"}])

                        items_kit = []
                        if not df_mod.empty:
                            kit_mod = df_mod[df_mod['type_event'] == n_type]
                            start_t_id = int(pd.to_numeric(df_transit['id']).max()) if not df_transit.empty and pd.notna(df_transit['id'].max()) else 0
                            for i, row in enumerate(kit_mod.itertuples()):
                                items_kit.append({"id": start_t_id + i + 1, "evenement_id": new_id, "materiel_id": row.materiel_id, "nom_custom": row.materiel_nom, "qte_necessaire": row.qte_defaut, "qte_depart": 0, "qte_fin": 0, "qte_depot": 0})

                        st.session_state.df_ev = pd.concat([df_ev, new_ev], ignore_index=True)
                        conn.update(worksheet="evenements", data=st.session_state.df_ev)
                        
                        if items_kit:
                            st.session_state.df_transit = pd.concat([df_transit, pd.DataFrame(items_kit)], ignore_index=True)
                            conn.update(worksheet="transit", data=st.session_state.df_transit)

                        st.success(f"✅ Événement créé !")
                        st.rerun()

    st.dataframe(st.session_state.df_ev, hide_index=True, use_container_width=True)

with t_courses:
    st.subheader("🛒 Shopping List")
    df_m = st.session_state.df_mat
    df_m['stock_total'] = pd.to_numeric(df_m['stock_total'], errors='coerce').fillna(0)
    df_m['seuil_alerte'] = pd.to_numeric(df_m['seuil_alerte'], errors='coerce').fillna(0)
    alertes = df_m[(df_m['stock_total'] < df_m['seuil_alerte']) & (df_m['seuil_alerte'] > 0)].copy()
    if not alertes.empty:
        alertes['🛒 Manquant'] = alertes['seuil_alerte'] - alertes['stock_total']
        st.warning(f"Rupture sur {len(alertes)} articles")
        st.table(alertes[['nom', 'stock_total', 'seuil_alerte', '🛒 Manquant']])
    else:
        st.success("Tout est OK !")

if is_admin and t_proj:
    with t_proj:
        st.subheader("🚀 Projets")
        res_p = st.data_editor(st.session_state.df_projets, hide_index=True, use_container_width=True)
        if st.button("💾 Sauvegarder Projets"):
            conn.update(worksheet="projets", data=res_p)
            st.session_state.df_projets = res_p
            st.success("Projets enregistrés")
