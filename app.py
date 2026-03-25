import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# ==========================================
# --- CONFIGURATION INITIALE ---
# ==========================================
st.set_page_config(page_title="BS Manager Pro", page_icon="📦", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)


def get_data(worksheet_name):
    return conn.read(worksheet=worksheet_name, ttl=600)


# --- BOUCLIER ANTI-PLANTAGE ---
COLS_MAT = ['id', 'nom', 'description', 'stockage', 'stock_total', 'categorie', 'type', 'seuil_alerte']
COLS_EV = ['id', 'nom', 'couleur', 'date_debut', 'date_fin', 'statut']
COLS_TRANSIT = ['id', 'evenement_id', 'materiel_id', 'qte_necessaire', 'qte_depart', 'qte_fin', 'qte_depot']
COLS_MOD = ['type_event', 'materiel_id', 'materiel_nom', 'qte_defaut']


def load_and_fix(sheet_name, expected_cols):
    try:
        df = get_data(sheet_name)
        if df.empty:
            return pd.DataFrame(columns=expected_cols)
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        return df
    except Exception:
        return pd.DataFrame(columns=expected_cols)


# ==========================================
# --- INTERFACE PRINCIPALE ---
# ==========================================
st.title("📦 Beautiful Sports - Manager")
tab1, tab2, tab3 = st.tabs(["📊 Inventaire", "📅 Événements", "🚚 Flux & Prépa"])

# ==========================================
# --- ONGLET 1 : INVENTAIRE ---
# ==========================================
with tab1:
    st.subheader("📊 Gestion du Stock (Master)")
    try:
        df_mat = load_and_fix("materiel", COLS_MAT)

        if not df_mat.empty and len(df_mat) > 0:
            df_mat['categorie'] = df_mat['categorie'].fillna("Non classé")
            df_mat = df_mat.sort_values(by=['categorie', 'nom'])

            recherche = st.text_input("🔍 Rechercher un article...", key="search_inv")
            df_display = df_mat[
                df_mat['nom'].astype(str).str.contains(recherche, case=False, na=False)] if recherche else df_mat

            all_updates = {}
            for cat in df_display['categorie'].unique():
                df_cat = df_display[df_display['categorie'] == cat]
                with st.expander(f"📦 {str(cat).upper()} ({len(df_cat)} articles)"):
                    res = st.data_editor(df_cat, hide_index=True, key=f"inv_{cat}",
                                         disabled=["id", "nom", "categorie", "description", "type"],
                                         column_config={
                                             "id": None,
                                             "nom": "Désignation",
                                             "stock_total": st.column_config.NumberColumn("Qté Dispo", min_value=0)
                                         })
                    all_updates[cat] = res

            if st.button("💾 Sauvegarder l'inventaire", type="primary", use_container_width=True):
                new_df_mat = df_mat.copy()
                for cat, updated_df in all_updates.items():
                    for _, row in updated_df.iterrows():
                        idx = new_df_mat.index[new_df_mat['id'] == row['id']].tolist()
                        if idx: new_df_mat.at[idx[0], 'stock_total'] = row['stock_total']
                conn.update(worksheet="materiel", data=new_df_mat)
                st.cache_data.clear()
                st.success("✅ Inventaire synchronisé !")
                st.rerun()
        else:
            st.info("L'inventaire est vide. Remplissez l'onglet 'materiel' de Google Sheets.")
    except Exception as e:
        st.error(f"Erreur Inventaire : {e}")

# ==========================================
# --- ONGLET 2 : ÉVÉNEMENTS & KITS ---
# ==========================================
with tab2:
    st.subheader("📅 Création d'Événement")
    try:
        df_ev = load_and_fix("evenements", COLS_EV)
        df_transit = load_and_fix("transit", COLS_TRANSIT)  # Nouveau nom !
        df_mod = load_and_fix("modeles", COLS_MOD)

        with st.form("add_event"):
            n_name = st.text_input("Nom de l'événement")
            n_type = st.selectbox("Catégorie (Génère le kit auto)",
                                  ["🔵 BCF", "🔴 BBFL", "🟡 CL", "🟢 Running", "🟣 8h", "⚫ BXL Crit"])
            col1, col2 = st.columns(2)
            start, end = col1.date_input("Début"), col2.date_input("Fin")

            if st.form_submit_button("➕ Créer l'événement"):
                if not n_name:
                    st.error("Le nom de l'événement est obligatoire.")
                else:
                    new_ev_id = int(df_ev['id'].max()) + 1 if not df_ev.empty and pd.notna(df_ev['id'].max()) else 1
                    new_ev = pd.DataFrame([{
                        "id": new_ev_id, "nom": n_name, "couleur": n_type,
                        "date_debut": str(start), "date_fin": str(end), "statut": "En préparation"
                    }])

                    nouveaux_items = []
                    if not df_mod.empty:
                        kit = df_mod[df_mod['type_event'] == n_type]
                        for _, row in kit.iterrows():
                            nouveaux_items.append({
                                "id": len(df_transit) + len(nouveaux_items) + 1,
                                "evenement_id": new_ev_id,
                                "materiel_id": row['materiel_id'],
                                "qte_necessaire": row['qte_defaut'],
                                "qte_depart": 0,
                                "qte_fin": 0,  # Nouvelle colonne init à 0
                                "qte_depot": 0
                            })

                    conn.update(worksheet="evenements", data=pd.concat([df_ev, new_ev], ignore_index=True))
                    if nouveaux_items:
                        conn.update(worksheet="transit",
                                    data=pd.concat([df_transit, pd.DataFrame(nouveaux_items)], ignore_index=True))
                    st.cache_data.clear();
                    st.success("✅ Événement et Kit générés !");
                    st.rerun()

        st.write("---")
        if not df_ev.empty and len(df_ev) > 0:
            st.dataframe(df_ev[['couleur', 'nom', 'date_debut', 'statut']], hide_index=True, use_container_width=True)
        else:
            st.info("Aucun événement actif. Utilisez le formulaire pour en créer un.")

    except Exception as e:
        st.error(f"Erreur Événements : {e}")

# ==========================================
# --- ONGLET 3 : OPTIMISATION FLUX ---
# ==========================================
with tab3:
    st.subheader("🚚 Flux et Transit")
    try:
        df_mat = load_and_fix("materiel", COLS_MAT)
        df_ev = load_and_fix("evenements", COLS_EV)
        df_transit = load_and_fix("transit", COLS_TRANSIT)  # Nouveau nom !

        if df_ev.empty or len(df_ev) == 0:
            st.info("Aucun événement à gérer.")
        else:
            actifs = df_ev[df_ev['statut'] != "Terminé"]

            if actifs.empty:
                st.success("🎉 Tous les événements sont clôturés !")
            else:
                actifs.loc[:, 'label'] = actifs['couleur'] + " : " + actifs['nom']
                sel_label = st.selectbox("Choisir l'événement :", actifs['label'].tolist())
                ev_data = actifs[actifs['label'] == sel_label].iloc[0]
                sel_ev_id = ev_data['id']

                ev_transit = df_transit[df_transit['evenement_id'] == sel_ev_id]
                if not ev_transit.empty and not df_mat.empty:
                    display_final = pd.merge(ev_transit, df_mat[['id', 'nom', 'categorie']], left_on='materiel_id',
                                             right_on='id')

                    cat_list = ["Toutes"] + sorted(display_final['categorie'].astype(str).unique().tolist())
                    filtre_cat = st.radio("Filtrer par zone du dépôt :", cat_list, horizontal=True)
                    df_filtre = display_final if filtre_cat == "Toutes" else display_final[
                        display_final['categorie'] == filtre_cat]

                    with st.form("pointage_pro"):
                        st.write(f"📍 Pointage : {filtre_cat} ({len(df_filtre)} articles)")

                        ed = st.data_editor(
                            df_filtre[['id_x', 'nom', 'qte_necessaire', 'qte_depart', 'qte_fin', 'qte_depot']],
                            hide_index=True, use_container_width=True,
                            column_config={
                                "id_x": None,
                                "nom": st.column_config.TextColumn("Article", width="medium"),
                                "qte_necessaire": "Besoin",
                                "qte_depart": "🚚 Sortie Dépôt",
                                "qte_fin": "🏁 Fin d'Évent",  # NOUVEAU
                                "qte_depot": "📦 Retour Dépôt"
                            })

                        col_save, col_close = st.columns(2)

                        if col_save.form_submit_button("💾 Sauvegarder la zone"):
                            for _, r in ed.iterrows():
                                idx = df_transit.index[df_transit['id'] == r['id_x']].tolist()[0]
                                df_transit.at[idx, 'qte_depart'] = r['qte_depart']
                                df_transit.at[idx, 'qte_fin'] = r['qte_fin']  # NOUVEAU
                                df_transit.at[idx, 'qte_depot'] = r['qte_depot']
                            conn.update(worksheet="transit", data=df_transit);
                            st.cache_data.clear();
                            st.rerun()

                        st.write("---")

                        conf = st.checkbox(
                            "⚠️ Confirmer que TOUT est rentré (Calcule les pertes basées sur le retour Dépôt)")
                        if col_close.form_submit_button("🚨 CLÔTURER L'ÉVÉNEMENT", type="primary") and conf:
                            # Calcul mathématique des pertes (Basé sur ce qui revient vraiment au dépôt)
                            for _, r in display_final.iterrows():
                                perte = r['qte_depart'] - r['qte_depot']
                                if perte != 0:
                                    mat_id_perdu = ev_transit[ev_transit['id'] == r['id_x']]['materiel_id'].values[0]
                                    idx_m = df_mat.index[df_mat['id'] == mat_id_perdu].tolist()
                                    if idx_m: df_mat.at[idx_m[0], 'stock_total'] -= perte

                            idx_ev = df_ev.index[df_ev['id'] == ev_data['id']].tolist()[0]
                            df_ev.at[idx_ev, 'statut'] = "Terminé"

                            conn.update(worksheet="materiel", data=df_mat)
                            conn.update(worksheet="evenements", data=df_ev)
                            st.cache_data.clear();
                            st.balloons();
                            st.rerun()
                else:
                    st.info("Aucun matériel dans la liste de cet événement.")
    except Exception as e:
        st.error(f"Erreur Flux : {e}")