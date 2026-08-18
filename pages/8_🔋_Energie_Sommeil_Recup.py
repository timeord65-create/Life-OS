import streamlit as st
import pandas as pd
import plotly.express as px
import os
import json
from datetime import datetime
from supabase import create_client, Client
from google import genai
import db_manager as db

st.set_page_config(page_title="Énergie & Sommeil", page_icon="🔋", layout="wide")

# --- SUPABASE ---
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")

@st.cache_resource
def get_supabase():
    if supabase_url and supabase_key:
        try:
            return create_client(supabase_url, supabase_key)
        except:
            return None
    return None

supabase = get_supabase()
today_str = datetime.now().strftime("%Y-%m-%d")

st.title("🔋 Journal de Forme, Sommeil & Récupération")

col_form, col_stats = st.columns([1, 1])

# --- FORMULAIRE DU JOUR ---
with col_form:
    st.subheader(f"📝 Check-in du jour ({today_str})")
    
    with st.form("energy_log_form"):
        c1, c2 = st.columns(2)
        sleep_hrs = c1.number_input("Heures de sommeil", min_value=0.0, max_value=16.0, value=7.5, step=0.5)
        sleep_qual = c2.slider("Qualité du sommeil (1 à 10)", min_value=1, max_value=10, value=7)
        
        c3, c4 = st.columns(2)
        energy = c3.slider("Niveau d'énergie au réveil (1 à 10)", min_value=1, max_value=10, value=8)
        soreness = c4.slider("Courbatures / Fatigue musculaire (1 à 10)", min_value=1, max_value=10, value=2)
        
        notes = st.text_area("Ressenti, stress ou note particulière", placeholder="Bonne nuit, petite raideur aux ischios après le fractionné...")
        
        if st.form_submit_button("Enregistrer le Check-in (+25 XP)", type="primary"):
            if supabase:
                try:
                    supabase.table("energy_logs").upsert({
                        "date": today_str,
                        "sleep_hours": sleep_hrs,
                        "sleep_quality": sleep_qual,
                        "energy_level": energy,
                        "soreness": soreness,
                        "notes": notes
                    }, on_conflict="date").execute()
                    db.add_xp(25)
                    st.success("Check-in sauvegardé et +25 XP !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur Supabase : {e}")

# --- HISTORIQUE & STATS ---
logs_data = []
if supabase:
    try:
        res = supabase.table("energy_logs").select("*").order("date", desc=True).limit(30).execute()
        logs_data = res.data or []
    except Exception as e:
        st.error(f"Erreur : {e}")

with col_stats:
    st.subheader("📊 Tendances récentes")
    if logs_data:
        df_logs = pd.DataFrame(logs_data).sort_values("date")
        
        fig = px.line(df_logs, x="date", y=["sleep_hours", "energy_level", "sleep_quality"],
                      labels={"value": "Score / Heures", "variable": "Métrique", "date": "Date"},
                      title="Évolution Sommeil & Énergie")
        fig.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Enregistre ton premier check-in pour voir les graphiques !")

st.divider()

# --- ANALYSE IA RÉCUPÉRATION ---
st.subheader("🤖 Débrief & Conseils de Récupération par Gemini")
if st.button("Demander une analyse personnalisée à l'IA"):
    if not gemini_key:
        st.error("Clé API Gemini manquante.")
    elif not logs_data:
        st.warning("Ajoute au moins 2 ou 3 jours de données pour que l'IA puisse analyser.")
    else:
        with st.spinner("Analyse de tes cycles et conseils personnalisés..."):
            client = genai.Client(api_key=gemini_key)
            prompt = f"""
            Tu es un coach expert en préparation physique et récupération sportive.
            Voici les logs de forme et sommeil récents de l'utilisateur :
            {json.dumps(logs_data[:7], ensure_ascii=False)}

            Donne un retour court (3 points clés) :
            1. Analyse de la tendance (sommeil vs énergie).
            2. Recommandation pour l'entraînement du jour (intensité recommandée).
            3. 1 conseil concret d'optimisation (nutrition, étirements, hydratation).
            """
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt
            )
            st.markdown(response.text)