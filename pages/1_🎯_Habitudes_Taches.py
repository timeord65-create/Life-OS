import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Habitudes & Tâches", page_icon="🎯", layout="wide")
DB_FILE = "life_os.db"

st.title("🎯 Habitudes & Organisation")

tab1, tab2 = st.tabs(["📝 Liste des tâches", "🔥 Grille d'habitudes"])

with tab1:
    st.subheader("Ajouter une tâche")
    c1, c2 = st.columns([3, 1])
    with c1:
        new_task = st.text_input("Intitulé de la tâche")
    with c2:
        prio = st.selectbox("Priorité", ["🔥 Urgent & Important", "⚡ Projet", "📋 Quotidien"])
    
    if st.button("Ajouter la tâche", type="primary") and new_task:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO tasks (title, priority, done, date_created) VALUES (?, ?, 0, ?)",
                  (new_task, prio, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()
        st.rerun()

    st.divider()
    conn = sqlite3.connect(DB_FILE)
    df_t = pd.read_sql_query("SELECT id, title, priority, done FROM tasks WHERE done = 0 ORDER BY id DESC", conn)
    conn.close()
    
    if not df_t.empty:
        for _, row in df_t.iterrows():
            col_t1, col_t2 = st.columns([4, 1])
            with col_t1:
                st.write(f"**{row['title']}** — `{row['priority']}`")
            with col_t2:
                if st.button("Cocher ✅", key=f"done_{row['id']}"):
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute("UPDATE tasks SET done = 1 WHERE id = ?", (row['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()
    else:
        st.info("Toutes les tâches sont terminées !")

with tab2:
    st.subheader("Historique des habitudes cochées")
    conn = sqlite3.connect(DB_FILE)
    df_hab = pd.read_sql_query("SELECT habit_name, date, status FROM habit_logs ORDER BY date DESC", conn)
    conn.close()
    
    if not df_hab.empty:
        st.dataframe(df_hab, use_container_width=True)
    else:
        st.info("Aucune habitude validée pour l'instant.")