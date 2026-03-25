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

# --- ONGLET 2 : ÉVÉNEMENTS ---
with tab2:
    st.subheader("📅 Gestion des Événements")
    try:
        # Tente de lire par le nom, sinon lit le 2ème onglet (position 1)
        try:
            df_ev = get_data("evenements")
        except:
            df_ev = get_data(1)

        with st.form("add_event"):
            new_name = st.text_input("Nom de l'événement (ex: Giro 2026)")
            col1, col2 = st.columns(2)
            start = col1.date_input("Date de début")
            end = col2.date_input("Date de fin")

            if st.form_submit_button("➕ Créer l'événement"):
                new_id = len(df_ev) + 1
                new_row = pd.DataFrame([{
                    "id": new_id,
                    "nom": new_name,
                    "date_debut": str(start),
                    "date_fin": str(end),
                    "statut": "En préparation"
                }])
                df_ev = pd.concat([df_ev, new_row], ignore_index=True)

                # Mise à jour dans le Cloud
                try:
                    conn.update(worksheet="evenements", data=df_ev)
                except:
                    conn.update(worksheet=1, data=df_ev)

                st.success(f"✅ Événement '{new_name}' créé avec succès !")
                st.rerun()

        st.write("---")
        st.write("**Liste des événements en cours :**")
        st.dataframe(df_ev[["nom", "date_debut", "statut"]], hide_index=True, use_container_width=True)

    except Exception as e:
        st.error("Erreur avec l'onglet des événements. Vérifie qu'il est bien en 2ème position dans Google Sheets.")

# --- ONGLET 3 : PRÉPARATION ---
with tab3:
    st.subheader("📝 Listes de Chargement")
    try:
        # Tente de lire le 3ème onglet (position 2)
        try:
            df_res = get_data("reservations")
        except:
            df_res = get_data(2)

        st.info("Le système de scan et de préparation de malles sera activé ici prochainement !")
        st.dataframe(df_res, hide_index=True, use_container_width=True)

    except Exception as e:
        st.error("Erreur avec l'onglet de préparation. Vérifie qu'il est bien en 3ème position dans ton Google Sheets.")