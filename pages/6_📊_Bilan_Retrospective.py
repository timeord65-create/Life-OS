import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import os
from google import genai

st.set_page_config(page_title="Bilan & Rétrospective", page_icon="📊", layout="wide")
DB_FILE = "life_os.db"

st.title("📊 Rétrospective & Bilan")

periode = st.selectbox("Période d'analyse", ["7 derniers jours", "Mois en cours"])

conn = sqlite3.connect(DB_FILE)
df_sport = pd.read_sql_query("SELECT sport, duration, distance, rpe, date FROM workouts", conn)
df_trans = pd.read_sql_query("SELECT type, category, amount, date FROM transactions", conn)
df_habits = pd.read_sql_query("SELECT habit_name, date, status FROM habit_logs", conn)
conn.close()

col1, col2 = st.columns(2)

with col1:
    st.subheader("💰 Synthèse Finances")
    if not df_trans.empty:
        dep = df_trans[df_trans["type"] == "Dépense"]
        if not dep.empty:
            fig = px.pie(dep, values="amount", names="category", title="Répartition des dépenses")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aucune donnée financière.")

with col2:
    st.subheader("🏃 Synthèse Sport & Charge")
    if not df_sport.empty:
        fig_bar = px.bar(df_sport, x="date", y="distance", color="sport", title="Distance parcourue par jour")
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Aucune séance de sport.")

st.divider()

# Analyse IA Gemini
st.subheader("🤖 Bilan & Conseils du Coach IA")
gemini_key = os.getenv("GEMINI_API_KEY")

if st.button("Générer mon analyse personnalisée", type="primary"):
    if not gemini_key:
        st.error("Renseigne ta clé API Gemini dans la barre latérale de l'accueil.")
    else:
        with st.spinner("Génération du bilan en cours..."):
            prompt = f"""
            Tu es un coach en performance personnelle et organisation.
            Analyse ces données de l'utilisateur :
            - Sport : {df_sport.tail(15).to_dict(orient='records')}
            - Finances : {df_trans.tail(15).to_dict(orient='records')}
            - Habitudes : {df_habits.tail(20).to_dict(orient='records')}

            Fais-lui un bilan direct, bienveillant et percutant en 3 points :
            1. 🏆 Ce qui a super bien marché
            2. ⚠️ Point de vigilance (dépenses, récupération ou régularité)
            3. 🎯 2 objectifs clés pour la semaine prochaine.
            """
            client = genai.Client(api_key=gemini_key)
            resp = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt
            )
            st.markdown(resp.text)