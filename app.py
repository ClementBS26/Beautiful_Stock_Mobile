import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="BS Inventory", page_icon="📦", layout="wide")

# 1. Connexion au Google Sheet avec les droits d'écriture
conn = st.connection("gsheets", type=GSheetsConnection)


def get_data(worksheet_name):
    return conn.read(worksheet=worksheet_name, ttl=0)


st.title("📦 Beautiful Sports - Manager")

tab1, tab2, tab3 = st.tabs(["📊 Inventaire", "📅 Événements", "📝 Listes Prépa"])

# --- ONGLET 1 : INVENTAIRE ---
with tab1:
    st.subheader("Stock en temps réel")
    try:
        # Tente de lire l'onglet "materiel", sinon lit le 1er onglet (0)
        try:
            df_mat = get_data("materiel")
        except:
            df_mat = get_data(0)

        recherche = st.text_input("🔍 Rechercher un matériel :")
        if recherche:
            df_display = df_mat[df_mat['nom'].str.contains(recherche, case=False, na=False)]
        else:
            df_display = df_mat

        edited_df = st.data_editor(
            df_display,
            hide_index=True,
            width="stretch",
            disabled=["id"],
            column_config={"id": None, "nom": "Matériel", "stock_total": "Dispo"}
        )

        if st.button("💾 Sauvegarder les modifications", type="primary"):
            # C'est ICI que la magie opère : on écrit dans le Cloud !
            df_mat.update(edited_df)
            try:
                conn.update(worksheet="materiel", data=df_mat)
            except:
                conn.update(worksheet=0, data=df_mat)

            st.success("✅ Synchronisé avec succès sur Google Sheets !")
            st.rerun()

    except Exception as e:
        st.error("Erreur de chargement.")
        st.write(e)

# --- ONGLET 2 : ÉVÉNEMENTS (Désactivé pour le test) ---
with tab2:
    st.info("Crée un onglet 'evenements' dans ton Google Sheet pour activer cette page.")

# --- ONGLET 3 : PRÉPARATION (Désactivé pour le test) ---
with tab3:
    st.info("Crée un onglet 'reservations' dans ton Google Sheet pour activer cette page.")