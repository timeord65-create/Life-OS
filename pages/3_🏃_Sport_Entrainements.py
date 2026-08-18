import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Sport & Entraînements", page_icon="🏃", layout="wide")
DB_FILE = "life_os.db"

st.title("🏃 Journal de Sport & Récupération")

with st.expander("➕ Ajouter une séance", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        sport = st.selectbox("Discipline", ["Course à pied / Trail", "Natation", "Handball / Collectif", "Renforcement / Muscu", "Autre"])
        duree = st.number_input("Durée (minutes)", min_value=5, value=45, step=5)
        distance = st.number_input("Distance (km - facultatif)", min_value=0.0, value=0.0, step=0.5)
    with c2:
        rpe = st.slider("Intensité / Effort perçu (RPE de 1 à 10)", 1, 10, 6)
        date_s = st.date_input("Date de la séance", datetime.now())
        notes = st.text_area("Ressenti, météo, sensations")
        
    if st.button("Enregistrer la séance", type="primary"):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO workouts (sport, duration, distance, rpe, notes, date) VALUES (?, ?, ?, ?, ?, ?)",
                  (sport, duree, distance, rpe, notes, date_s.strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()
        st.success("Séance enregistrée !")
        st.rerun()

st.divider()

conn = sqlite3.connect(DB_FILE)
df = pd.read_sql_query("SELECT id, sport, duration, distance, rpe, notes, date FROM workouts ORDER BY date DESC", conn)
conn.close()

if not df.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Nombre total de séances", len(df))
    c2.metric("Distance cumulée", f"{df['distance'].sum():.1f} km")
    c3.metric("Temps total d'effort", f"{df['duration'].sum() // 60} h {df['duration'].sum() % 60} min")
    
    fig = px.bar(df, x="date", y="duration", color="sport", title="Volume d'entraînement par discipline (minutes)")
    st.plotly_chart(fig, use_container_width=True)
    
    st.dataframe(df, use_container_width=True)
else:
    st.info("Aucune séance dans le journal.")