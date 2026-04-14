import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# ==========================================
# --- CONFIGURATION INITIALE ---
# ==========================================
st.set_page_config(page_title="BS Manager Pro", page_icon="📦", layout="wide")


# Utilisation de cache pour la connexion
@st.cache_resource
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)


conn = get_connection()

# --- STRUCTURE DES DONNÉES ---
COLS_MAT = ['id', 'nom', 'stockage', 'stock_total', 'categorie', 'type', 'seuil_alerte']
COLS_EV = ['id', 'nom', 'couleur', 'date_debut', 'date_fin', 'statut']
COLS_TRANSIT = ['id', 'evenement_id', 'materiel_id', 'nom_custom', 'qte_necessaire', 'qte_depart', 'qte_fin',
                'qte_depot']
COLS_MOD = ['type_event', 'materiel_id', 'materiel_nom', 'qte_defaut', 'Commentaire']
COLS_PROJETS = ['id', 'date', 'titre', 'description', 'priorite', 'statut']

EVENT_TYPES = ["🔵 BCF", "🔴 BBFL", "🇫🇷 Tour", "🩷 Giro", "🟣 8h", "⚫ BXL Crit", "🟠 UTWB", "🟡 CL", "🚴 Repérages"]


def fetch_data(sheet, cols):
    try:
        df = conn.read(worksheet=sheet, ttl=0)
        if df is None or df.empty: return pd.DataFrame(columns=cols)
        for c in cols:
            if c not in df.columns: df[c] = None
        return df
    except Exception:
        return pd.DataFrame(columns=cols)


# ==========================================
# --- CHARGEMENT EN MÉMOIRE (RAPIDITÉ) ---
# ==========================================
if "df_mat" not in st.session_state:
    with st.spinner("🔄 Connexion à la base de données..."):
        st.session_state.df_mat = fetch_data("materiel", COLS_MAT)
        st.session_state.df_ev = fetch_data("evenements", COLS_EV)
        st.session_state.df_transit = fetch_data("transit", COLS_TRANSIT)
        st.session_state.df_mod = fetch_data("modeles", COLS_MOD)
        st.session_state.df_projets = fetch_data("projets", COLS_PROJETS)

# ==========================================
# --- BARRE LATÉRALE & SÉCURITÉ ---
# ==========================================
with st.sidebar:
    st.markdown("### 🔒 Accès & Sécurité")
    pin_input = st.text_input("Code PIN Admin", type="password")
    is_admin = (pin_input == "7011")  # <-- TON CODE PIN ICI

    if is_admin:
        st.success("✅ Mode ADMIN activé")
    else:
        st.info("👀 Mode TERRAIN (Lecture seule)")

    st.divider()
    if st.button("🔄 Forcer le rafraîchissement", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ==========================================
# --- INTERFACE PRINCIPALE ---
# ==========================================
st.title("📦 Beautiful Sports")

# Affichage conditionnel des onglets
if is_admin:
    tab_terrain, tab_stock, tab_events, tab_courses, tab_projets = st.tabs(
        ["🚚 Terrain", "📊 Stock", "📅 Évents", "🛒 Courses", "🚀 Projets"])
else:
    tab_terrain, tab_events, tab_courses = st.tabs(["🚚 Terrain", "📅 Évents", "🛒 Courses"])
    tab_stock = tab_projets = None


# ==========================================
# --- ONGLET 1 : TERRAIN (FRAGMENT FLUIDE) ---
# ==========================================
@st.fragment
def render_terrain():
    st.subheader("🚚 Pointage Terrain")
    df_ev = st.session_state.df_ev.copy()
    df_transit = st.session_state.df_transit.copy()
    df_mat = st.session_state.df_mat.copy()

    actifs = df_ev[df_ev['statut'] != "Terminé"].copy()
    if actifs.empty:
        st.info("Aucun événement actif à pointer.")
        return

    actifs['label'] = actifs['couleur'] + " : " + actifs['nom']
    c1, c2 = st.columns([2, 1])
    sel_ev_label = c1.selectbox("Événement :", actifs['label'].tolist())
    ev_row = actifs[actifs['label'] == sel_ev_label].iloc[0]

    phase = c2.radio("Phase :", ["🚚 Départ", "🏁 Fin", "📦 Retour"], horizontal=True)
    col_target = {"🚚 Départ": "qte_depart", "🏁 Fin": "qte_fin", "📦 Retour": "qte_depot"}[phase]

    ev_transit = df_transit[df_transit['evenement_id'] == ev_row['id']].copy()

    df_mat['id'] = pd.to_numeric(df_mat['id'], errors='coerce')
    ev_transit['materiel_id'] = pd.to_numeric(ev_transit['materiel_id'], errors='coerce')

    ptg = pd.merge(ev_transit, df_mat[['id', 'nom', 'categorie']], left_on='materiel_id', right_on='id', how='left')
    ptg['nom'] = ptg['nom'].fillna(ptg['nom_custom'])
    ptg['categorie'] = ptg['categorie'].fillna("⚠️ Divers")
    ptg['ok_auto'] = ptg[col_target] == ptg['qte_necessaire']

    # --- BARRE DE PROGRESSION & EXPORT CSV ---
    nb_complets = len(ptg[ptg['ok_auto'] == True])
    st.progress(nb_complets / len(ptg) if len(ptg) > 0 else 0,
                text=f"📊 Progression globale : {nb_complets} / {len(ptg)} validés")

    csv = ptg[['categorie', 'nom', 'qte_necessaire', col_target]].to_csv(index=False).encode('utf-8')
    st.download_button(label="📥 Télécharger la Check-list (Mode sans réseau)", data=csv,
                       file_name=f"checklist_{ev_row['nom']}_{phase}.csv", mime='text/csv')

    st.info("💡 **Astuce :** Ouvre une catégorie et coche '✅ OK' pour valider la quantité d'un coup.")

    # Formulaire pour éviter les rechargements
    with st.form("form_pointage"):
        all_edited = []
        for cat in sorted(ptg['categorie'].unique()):
            df_cat = ptg[ptg['categorie'] == cat]

            # RETOUR DES CATÉGORIES EN MENU DÉROULANT
            with st.expander(f"📦 {cat.upper()} ({len(df_cat)} articles)"):
                edited = st.data_editor(
                    df_cat[['id_x', 'nom', 'qte_necessaire', 'ok_auto', col_target]].rename(columns={'id_x': 'id'}),
                    hide_index=True, use_container_width=True, key=f"ptg_{cat}_{phase}",
                    disabled=['id', 'nom', 'qte_necessaire'],
                    column_config={
                        "id": None, "nom": "Article", "qte_necessaire": "Prévu",
                        "ok_auto": st.column_config.CheckboxColumn("✅ OK"),
                        col_target: st.column_config.NumberColumn("🔢 Réel", min_value=0, step=1)
                    }
                )
                all_edited.append(edited)

        if st.form_submit_button("💾 Enregistrer le pointage", type="primary", use_container_width=True):
            df_edited_full = pd.concat(all_edited)
            mask_ok = df_edited_full['ok_auto'] == True
            df_edited_full.loc[mask_ok, col_target] = df_edited_full.loc[mask_ok, 'qte_necessaire']

            for _, row in df_edited_full.iterrows():
                st.session_state.df_transit.loc[st.session_state.df_transit['id'] == row['id'], col_target] = row[
                    col_target]

            conn.update(worksheet="transit", data=st.session_state.df_transit)
            st.success("✅ Pointage enregistré avec succès !")
            st.rerun()


with tab_terrain:
    render_terrain()


# ==========================================
# --- ONGLET 2 : STOCK (FRAGMENT FLUIDE) ---
# ==========================================
@st.fragment
def render_stock():
    st.subheader("📊 Tableau de Bord Inventaire")
    df_mat = st.session_state.df_mat.copy()
    df_mat['stock_total'] = pd.to_numeric(df_mat['stock_total'], errors='coerce').fillna(0)
    df_mat['seuil_alerte'] = pd.to_numeric(df_mat['seuil_alerte'], errors='coerce').fillna(0)

    # --- LES KPIs (DASHBOARD) ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Articles en Stock", len(df_mat))
    alertes = len(df_mat[(df_mat['stock_total'] < df_mat['seuil_alerte']) & (df_mat['seuil_alerte'] > 0)])
    c2.metric("Alertes Rupture", alertes, delta=-alertes, delta_color="inverse")
    c3.metric("Catégories Actives", df_mat['categorie'].nunique())

    st.divider()

    recherche = st.text_input("🔍 Rechercher un article...", key="search_inv")
    df_display = df_mat[
        df_mat['nom'].astype(str).str.contains(recherche, case=False, na=False)] if recherche else df_mat

    with st.form("form_stock"):
        all_updates = []
        for cat in sorted(df_display['categorie'].fillna("Non classé").unique()):
            df_cat = df_display[df_display['categorie'] == cat]
            with st.expander(f"📦 {str(cat).upper()} ({len(df_cat)} articles)"):
                res = st.data_editor(
                    df_cat, hide_index=True, key=f"inv_{cat}",
                    disabled=["id", "nom", "categorie", "type"], use_container_width=True,
                    column_config={
                        "id": None, "nom": "Désignation",
                        "stockage": st.column_config.SelectboxColumn("Lieu", options=["Stock", "Bureau", "Club house"]),
                        "stock_total": "Dispo", "seuil_alerte": "Alerte"
                    }
                )
                all_updates.append(res)

        if st.form_submit_button("💾 Sauvegarder les modifications", type="primary", use_container_width=True):
            df_updated_combined = pd.concat(all_updates)
            df_mat.set_index('id', inplace=True)
            df_updated_combined.set_index('id', inplace=True)
            df_mat.update(df_updated_combined)
            df_mat.reset_index(inplace=True)

            conn.update(worksheet="materiel", data=df_mat)
            st.session_state.df_mat = df_mat
            st.success("✅ Inventaire synchronisé !")
            st.rerun()


if is_admin and tab_stock:
    with tab_stock:
        render_stock()

# ==========================================
# --- ONGLET 3 : ÉVÉNEMENTS ---
# ==========================================
with tab_events:
    st.subheader("📅 Gestion des Événements")

    if is_admin:
        with st.expander("➕ Créer un nouvel événement"):
            with st.form("add_event"):
                n_name = st.text_input("Nom de l'événement")
                n_type = st.selectbox("Type d'événement (Génère le kit auto)", EVENT_TYPES)
                col1, col2 = st.columns(2)
                start, end = col1.date_input("Début"), col2.date_input("Fin")

                if st.form_submit_button("Créer l'événement"):
                    if n_name:
                        df_ev = st.session_state.df_ev
                        df_transit = st.session_state.df_transit
                        df_mod = st.session_state.df_mod

                        new_ev_id = int(pd.to_numeric(df_ev['id']).max()) + 1 if not df_ev.empty and pd.notna(
                            df_ev['id'].max()) else 1
                        new_ev = pd.DataFrame(
                            [{"id": new_ev_id, "nom": n_name, "couleur": n_type, "date_debut": str(start),
                              "date_fin": str(end), "statut": "En préparation"}])

                        items_kit = []
                        if not df_mod.empty:
                            kit = df_mod[df_mod['type_event'] == n_type]
                            start_transit_id = int(
                                pd.to_numeric(df_transit['id']).max()) if not df_transit.empty and pd.notna(
                                df_transit['id'].max()) else 0
                            for i, row in enumerate(kit.itertuples()):
                                items_kit.append({"id": start_transit_id + i + 1, "evenement_id": new_ev_id,
                                                  "materiel_id": row.materiel_id, "nom_custom": row.materiel_nom,
                                                  "qte_necessaire": row.qte_defaut, "qte_depart": 0, "qte_fin": 0,
                                                  "qte_depot": 0})

                        df_ev = pd.concat([df_ev, new_ev], ignore_index=True)
                        conn.update(worksheet="evenements", data=df_ev)
                        st.session_state.df_ev = df_ev

                        if items_kit:
                            df_transit = pd.concat([df_transit, pd.DataFrame(items_kit)], ignore_index=True)
                            conn.update(worksheet="transit", data=df_transit)
                            st.session_state.df_transit = df_transit

                        st.success(f"✅ Événement créé !")
                        st.rerun()

    # Tableau de suivi
    if not st.session_state.df_ev.empty:
        if is_admin:
            with st.form("form_status_ev"):
                edited_ev = st.data_editor(st.session_state.df_ev, hide_index=True, use_container_width=True,
                                           disabled=["id", "nom", "couleur", "date_debut", "date_fin"],
                                           column_config={"id": None,
                                                          "statut": st.column_config.SelectboxColumn("Statut", options=[
                                                              "En préparation", "En cours", "Terminé", "Annulé"])})
                if st.form_submit_button("💾 Mettre à jour les statuts"):
                    conn.update(worksheet="evenements", data=edited_ev)
                    st.session_state.df_ev = edited_ev
                    st.success("✅ Statuts mis à jour !")
                    st.rerun()
        else:
            st.dataframe(st.session_state.df_ev, hide_index=True, use_container_width=True)

# ==========================================
# --- ONGLET 4 : LISTE DE COURSES ---
# ==========================================
with tab_courses:
    st.subheader("🛒 Articles à Racheter")
    df_mat_alerte = st.session_state.df_mat.copy()
    df_mat_alerte['stock_total'] = pd.to_numeric(df_mat_alerte['stock_total'], errors='coerce').fillna(0)
    df_mat_alerte['seuil_alerte'] = pd.to_numeric(df_mat_alerte['seuil_alerte'], errors='coerce').fillna(0)

    df_alerte = df_mat_alerte[
        (df_mat_alerte['stock_total'] < df_mat_alerte['seuil_alerte']) & (df_mat_alerte['seuil_alerte'] > 0)].copy()

    if not df_alerte.empty:
        df_alerte['🛒 À acheter'] = df_alerte['seuil_alerte'] - df_alerte['stock_total']
        st.warning(f"⚠️ Rupture sur {len(df_alerte)} article(s).")
        st.dataframe(df_alerte[['categorie', 'nom', 'stock_total', 'seuil_alerte', '🛒 À acheter']], hide_index=True,
                     use_container_width=True)
    else:
        st.success("✅ Tous les stocks sont suffisants !")

# ==========================================
# --- ONGLET 5 : PROJETS (ADMIN SEUL) ---
# ==========================================
if is_admin and tab_projets:
    with tab_projets:
        st.subheader("🚀 Évolutions & Améliorations")
        with st.expander("➕ Nouvelle idée"):
            with st.form("new_idea"):
                titre, desc = st.text_input("Objet"), st.text_area("Détails")
                prio = st.select_slider("Priorité", options=["❄️ Idée", "⚡ Normal", "🔥 Urgent"])
                if st.form_submit_button("Enregistrer"):
                    df_p = st.session_state.df_projets
                    new_id = int(pd.to_numeric(df_p['id']).max()) + 1 if not df_p.empty and pd.notna(
                        df_p['id'].max()) else 1
                    df_p = pd.concat([df_p, pd.DataFrame(
                        [{"id": new_id, "date": datetime.now().strftime("%d/%m/%Y"), "titre": titre,
                          "description": desc, "priorite": prio, "statut": "À faire"}])], ignore_index=True)
                    conn.update(worksheet="projets", data=df_p)
                    st.session_state.df_projets = df_p
                    st.success("💡 Idée ajoutée !")
                    st.rerun()

        if not st.session_state.df_projets.empty:
            with st.form("form_edit_projets"):
                edited_p = st.data_editor(st.session_state.df_projets, hide_index=True, use_container_width=True,
                                          column_config={"id": None,
                                                         "priorite": st.column_config.SelectboxColumn("Prio", options=[
                                                             "❄️ Idée", "⚡ Normal", "🔥 Urgent"]),
                                                         "statut": st.column_config.SelectboxColumn("Statut",
                                                                                                    options=["À faire",
                                                                                                             "En cours",
                                                                                                             "Terminé",
                                                                                                             "Annulé"])})
                if st.form_submit_button("💾 Sauvegarder Projets"):
                    conn.update(worksheet="projets", data=edited_p)
                    st.session_state.df_projets = edited_p
                    st.success("✅ Projets mis à jour !")
                    st.rerun()
