import streamlit as st
import json
import os
from datetime import datetime
from supabase import create_client, Client
from google import genai
import db_manager as db

st.set_page_config(page_title="Second Cerveau & Connaissances", page_icon="🧠", layout="wide")

# --- SUPABASE & GEMINI ---
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

st.title("🧠 Second Cerveau : Synthèses & Fiches Pratiques")
st.caption("Capture des idées, résume des articles ou vidéos et garde tout indexé et actionnable.")

tab_capture, tab_biblio = st.tabs(["⚡ Capturer & Résumer avec l'IA", "📚 Ma Bibliothèque de Connaissances"])

# ==========================================
# TAB 1 : CAPTURE & RÉSUMÉ IA
# ==========================================
with tab_capture:
    st.subheader("📥 Résumer un contenu (Article, Idée, Notes)")
    
    source_title = st.text_input("Titre ou Sujet du contenu", placeholder="Ex : Les bases de la méthode GTD / Entraînement en Zone 2")
    source_url = st.text_input("Lien source (optionnel)", placeholder="https://...")
    category = st.selectbox("Catégorie", ["🧠 Productivité & Discipline", "🏃 Sport & Physiologie", "💻 Tech & Dev", "💰 Finances & Business", "🎬 Création & Cinéma", "🌱 Autre"])
    raw_content = st.text_area("Contenu brut (Colle le texte, des notes ou la transcription)", height=180)

    if st.button("🪄 Générer la fiche synthèse par l'IA (+30 XP)", type="primary"):
        if not raw_content and not source_title:
            st.warning("Veuillez saisir au moins un titre ou du texte.")
        elif not gemini_key:
            st.error("Clé API Gemini manquante dans les Secrets.")
        else:
            with st.spinner("Gemini synthétise et extrait les points d'action..."):
                try:
                    client = genai.Client(api_key=gemini_key)
                    prompt = f"""
                    Tu es un expert en gestion des connaissances (Second Brain).
                    Analyse ce texte ou cette idée :
                    Titre/Sujet : {source_title}
                    Contenu :
                    \"\"\"{raw_content}\"\"\"

                    Extrais sous format JSON strict :
                    {{
                        "title": "Titre clair et percutant",
                        "summary": "Résumé structuré en 3 à 5 points clés bien rédigés.",
                        "action_points": ["Action 1 concrète à appliquer", "Action 2"],
                        "tags": ["Tag1", "Tag2", "Tag3"]
                    }}
                    """
                    response = client.models.generate_content(
                        model="gemini-3.6-flash",
                        contents=prompt,
                        config={"response_mime_type": "application/json"}
                    )
                    data = json.loads(response.text)

                    if supabase:
                        supabase.table("knowledge_base").insert({
                            "title": data.get("title", source_title or "Note"),
                            "source_url": source_url,
                            "category": category,
                            "summary": data.get("summary", ""),
                            "action_points": data.get("action_points", []),
                            "tags": data.get("tags", []),
                            "date_added": datetime.now().strftime("%Y-%m-%d")
                        }).execute()
                        db.add_xp(30)

                    st.success(f"🎉 Fiche « {data.get('title')} » enregistrée (+30 XP) !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")

# ==========================================
# TAB 2 : BIBLIOTHÈQUE DE FICHES
# ==========================================
with tab_biblio:
    st.subheader("📚 Fiches de connaissances indexées")
    
    notes_list = []
    if supabase:
        try:
            res = supabase.table("knowledge_base").select("*").order("id", desc=True).execute()
            notes_list = res.data or []
        except Exception as e:
            st.error(f"Erreur Supabase : {e}")

    if not notes_list:
        st.info("Aucune fiche enregistrée. Capture ta première synthèse !")
    else:
        search_query = st.text_input("🔍 Rechercher par mot-clé, tag ou titre", "").lower()
        filtered = [
            n for n in notes_list 
            if search_query in n.get("title", "").lower() 
            or search_query in n.get("summary", "").lower() 
            or any(search_query in str(t).lower() for t in n.get("tags", []))
        ]

        for item in filtered:
            with st.expander(f"📌 **{item.get('title')}** — *{item.get('category')}* ({item.get('date_added')})"):
                st.markdown("### 💡 Résumé clé")
                st.write(item.get("summary", ""))
                
                actions = item.get("action_points", [])
                if actions:
                    st.markdown("### 🎯 Actions à appliquer")
                    for a in actions:
                        st.write(f"- [ ] {a}")
                
                tags = item.get("tags", [])
                if tags:
                    st.caption(f"🏷️ Tags : {', '.join(tags)}")

                if item.get("source_url"):
                    st.link_button("🔗 Source", item["source_url"])

                if st.button("🗑️ Supprimer", key=f"del_note_{item['id']}"):
                    if supabase:
                        supabase.table("knowledge_base").delete().eq("id", item["id"]).execute()
                        st.rerun()