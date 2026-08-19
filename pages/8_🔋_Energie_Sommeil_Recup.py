import streamlit as st
import pandas as pd
import plotly.express as px
import os
import json
from datetime import datetime
from supabase import create_client, Client
from google import genai

st.set_page_config(page_title="Énergie & Sommeil", page_icon="🔋", layout="wide")

# --- RÉCUPÉRATION DES SECRETS (Robuste Streamlit Cloud + Local) ---
def get_secret(key: str):
    if key in st.secrets:
        return st.secrets[key]
    return os.getenv(key)

supabase_url = get_secret("SUPABASE_URL")
supabase_key = get_secret("SUPABASE_KEY")
gemini_key = get_secret("GEMINI_API_KEY")

@st.cache_resource
def get_supabase():
    if supabase_url and supabase_key:
        try:
            return create_client(supabase_url, supabase_key)
        except Exception:
            return None
    return None

supabase = get_supabase()
today_str = datetime.now().strftime("%Y-%m-%d")

st.title("🔋 Journal de Forme, Sommeil & Récupération")

if not supabase:
    st.error("⚠️ Connexion Supabase inactive. Vérifie `SUPABASE_URL` et `SUPABASE_KEY` dans les Secrets Streamlit.")

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
        soreness = c4.slider("Courbatures / Fatigue (1 à 10)", min_value=1, max_value=10, value=2)
        
        notes = st.text_area("Ressenti ou note du jour", placeholder="Bien dormi, séance de fractionné hier...")
        
        submit_btn = st.form_submit_button("Enregistrer le Check-in", type="primary")
        
        if submit_btn:
            if not supabase:
                st.error("Impossible de sauvegarder : Supabase n'est pas connecté.")
            else:
                try:
                    res = supabase.table("energy_logs").upsert({
                        "date": today_str,
                        "sleep_hours": sleep_hrs,
                        "sleep_quality": sleep_qual,
                        "energy_level": energy,
                        "soreness": soreness,
                        "notes": notes
                    }, on_conflict="date").execute()
                    
                    st.success("✅ Données de sommeil enregistrées avec succès dans Supabase !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur Supabase : {e}")

# --- HISTORIQUE & STATS ---
logs_data = []
if supabase:
    try:
        res = supabase.table("energy_logs").select("*").order("date", desc=False).limit(30).execute()
        logs_data = res.data or []
    except Exception as e:
        st.error(f"Erreur de chargement : {e}")

with col_stats:
    st.subheader("📊 Tendances récentes")
    if logs_data:
        df_logs = pd.DataFrame(logs_data)
        
        fig = px.line(
            df_logs,
            x="date",
            y=["sleep_hours", "energy_level", "sleep_quality"],
            labels={"value": "Valeur", "variable": "Métrique", "date": "Date"},
            title="Évolution Sommeil & Énergie",
            markers=True
        )
        fig.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aucune donnée enregistrée pour le moment. Remplis le formulaire à gauche !")

st.divider()

# --- ANALYSE IA PAR GEMINI ---
st.subheader("🤖 Analyse Récupération & Forme par Gemini")
if st.button("Demander une analyse personnalisée"):
    if not gemini_key:
        st.error("Clé API Gemini introuvable.")
    elif not logs_data:
        st.warning("Enregistre au moins 2 ou 3 jours de données pour que l'IA puisse analyser.")
    else:
        with st.spinner("Gemini analyse tes cycles de forme..."):
            try:
                client = genai.Client(api_key=gemini_key)
                prompt = f"""
                Tu es un préparateur physique et coach en récupération.
                Voici l'historique récent de sommeil et d'énergie de l'athlète :
                {json.dumps(logs_data[-7:], ensure_ascii=False)}

                Donne un retour clair et direct :
                1. Analyse de la tendance (sommeil vs énergie).
                2. Recommandation d'intensité d'entraînement pour aujourd'hui.
                3. 1 conseil concret (nutrition, hydratation ou routine soir).
                """
                response = client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=prompt
                )
                st.markdown(response.text)
            except Exception as e:
                st.error(f"Erreur Gemini : {e}")