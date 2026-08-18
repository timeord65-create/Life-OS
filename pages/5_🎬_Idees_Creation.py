import streamlit as st
import sqlite3
from datetime import datetime

st.set_page_config(page_title="Idées & Pipeline Créatif", layout="wide")

DB_FILE = "recettes.db"

def init_ideas_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            category TEXT,
            status TEXT,
            notes TEXT,
            date_created TEXT
        )
    """)
    conn.commit()
    conn.close()

init_ideas_db()

st.title("🎬 Banque d'Idées & Pipeline Vidéo")

# Formulaire d'ajout rapide
with st.expander("➕ Noter une nouvelle idée / concept de plan", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        titre = st.text_input("Titre ou concept clé")
        categorie = st.selectbox("Type", ["Idée Vidéo", "Plan / B-roll", "Citation / Dialogue", "Technique / Étalonnage"])
    with col2:
        statut = st.selectbox("Statut initial", ["💡 Idée", "📝 En écriture", "🎬 Prêt à tourner", "✂️ Montage"])
        notes = st.text_area("Notes, références, focales, détails")
        
    if st.button("Enregistrer l'idée", type="primary") and titre:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            INSERT INTO ideas (title, category, status, notes, date_created) 
            VALUES (?, ?, ?, ?, ?)
        """, (titre, categorie, statut, notes, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()
        st.success("Idée enregistrée !")
        st.rerun()

st.divider()

# Affichage et filtres
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()

col_f1, col_f2 = st.columns(2)
with col_f1:
    filtre_statut = st.multiselect("Filtrer par statut", ["💡 Idée", "📝 En écriture", "🎬 Prêt à tourner", "✂️ Montage", "✅ Terminé"], default=[])
with col_f2:
    filtre_type = st.multiselect("Filtrer par type", ["Idée Vidéo", "Plan / B-roll", "Citation / Dialogue", "Technique / Étalonnage"], default=[])

query = "SELECT id, title, category, status, notes, date_created FROM ideas WHERE 1=1"
params = []

if filtre_statut:
    query += f" AND status IN ({','.join(['?']*len(filtre_statut))})"
    params.extend(filtre_statut)

if filtre_type:
    query += f" AND category IN ({','.join(['?']*len(filtre_type))})"
    params.extend(filtre_type)

query += " ORDER BY id DESC"

c.execute(query, params)
idees = c.fetchall()
conn.close()

if not idees:
    st.info("Aucune idée correspondant aux filtres.")
else:
    for i_id, i_title, i_cat, i_stat, i_notes, i_date in idees:
        with st.container():
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.markdown(f"**{i_title}** `[{i_cat}]`")
                if i_notes:
                    st.caption(i_notes)
            with c2:
                nouveau_statut = st.selectbox(
                    "Statut", 
                    ["💡 Idée", "📝 En écriture", "🎬 Prêt à tourner", "✂️ Montage", "✅ Terminé"], 
                    index=["💡 Idée", "📝 En écriture", "🎬 Prêt à tourner", "✂️ Montage", "✅ Terminé"].index(i_stat) if i_stat in ["💡 Idée", "📝 En écriture", "🎬 Prêt à tourner", "✂️ Montage", "✅ Terminé"] else 0,
                    key=f"status_{i_id}"
                )
                if nouveau_statut != i_stat:
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute("UPDATE ideas SET status = ? WHERE id = ?", (nouveau_statut, i_id))
                    conn.commit()
                    conn.close()
                    st.rerun()
            with c3:
                if st.button("🗑️ Supprimer", key=f"del_{i_id}"):
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute("DELETE FROM ideas WHERE id = ?", (i_id,))
                    conn.commit()
                    conn.close()
                    st.rerun()
            st.divider()