import streamlit as st
import json
import os
import re
from datetime import datetime
import yt_dlp
from google import genai
from supabase import create_client, Client

st.set_page_config(page_title="Recettes & Planning Alimentation", page_icon="🍳", layout="wide")

# --- CONNEXION SUPABASE ---
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")

@st.cache_resource
def get_supabase():
    if supabase_url and supabase_key:
        try:
            return create_client(supabase_url, supabase_key)
        except Exception as e:
            st.sidebar.error(f"Erreur init Supabase : {e}")
    return None

supabase = get_supabase()

st.title("🍳 Hub Alimentation : Recettes, Planning & Courses")

if not supabase:
    st.warning("⚠️ Supabase n'est pas configuré. Vérifiez vos secrets `SUPABASE_URL` et `SUPABASE_KEY`.")

tab_import, tab_recettes, tab_plan, tab_courses, tab_placard = st.tabs([
    "📥 Importer (Reel / Vidéo)",
    "📖 Mes Recettes",
    "📅 Planning & Portions",
    "🛒 Courses Intelligentes",
    "🥫 Fond de Placard"
])

# --- FONCTIONS YT-DLP & GEMINI ---
def extract_video_info(url: str):
    ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return f"Titre: {info.get('title', '')}\nDescription:\n{info.get('description', '')}"

def parse_recipe_with_gemini(raw_text: str, api_key: str):
    client = genai.Client(api_key=api_key)
    prompt = f"""
    Tu es un assistant culinaire expert. Analyse le texte suivant extrait d'une vidéo/Reel de cuisine.
    1. Extrais les détails de la recette.
    2. Détecte et isole STRICTEMENT les ingrédients de type 'Fond de placard / Longue conservation' (huiles, vinaigres, épices, herbes sèches, sel, poivre, moutarde, sauces asiatiques, conserves, farines, sucre, miel, etc.).

    Texte source :
    \"\"\"{raw_text}\"\"\"

    Format JSON attendu :
    {{
        "title": "Nom de la recette",
        "portions": 2,
        "prep_time": "15 min",
        "calories": "450 kcal",
        "ingredients": ["200g de poulet", "100g de riz basmati", "1 c.à.s d'huile d'olive", "1 c.à.c de paprika", "Sel", "Poivre"],
        "placard_detected": ["Huile d'olive", "Paprika", "Sel", "Poivre"],
        "instructions": "1. Couper le poulet. 2. Cuire avec les épices. 3. Servir avec le riz."
    }}
    """
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)

# ==========================================
# RÉCUPÉRATION DES DONNÉES CLOUD (SÉCURISÉE)
# ==========================================
recipes_list = []
if supabase:
    try:
        res = supabase.table("recipes").select("*").order("id", desc=True).execute()
        recipes_list = res.data or []
    except Exception as e:
        st.error(f"Erreur de chargement des recettes Supabase : {e}")

# ==========================================
# TAB 1 : IMPORTER UNE RECETTE
# ==========================================
with tab_import:
    st.subheader("📥 Importer depuis Instagram Reel, TikTok ou Shorts")
    video_url = st.text_input("Lien de la vidéo", placeholder="https://www.instagram.com/reel/...")

    if st.button("🪄 Extraire et sauvegarder (Recette + Placard auto)", type="primary"):
        if not video_url:
            st.warning("Colle d'abord un lien vidéo valide.")
        elif not gemini_key:
            st.error("Clé API Gemini introuvable dans les Secrets.")
        else:
            with st.spinner("Analyse par l'IA et détection automatique du placard..."):
                try:
                    raw_info = extract_video_info(video_url)
                    rec = parse_recipe_with_gemini(raw_info, gemini_key)
                    
                    if supabase:
                        # 1. Enregistrement recette
                        supabase.table("recipes").insert({
                            "title": rec.get("title", "Sans titre"),
                            "portions": rec.get("portions", 2),
                            "prep_time": rec.get("prep_time", "20 min"),
                            "calories": rec.get("calories", "500 kcal"),
                            "ingredients": rec.get("ingredients", []),
                            "instructions": rec.get("instructions", ""),
                            "source_url": video_url,
                            "date_added": datetime.now().strftime("%Y-%m-%d")
                        }).execute()

                        # 2. Ajout automatique au placard
                        detected_placard = rec.get("placard_detected", [])
                        if detected_placard:
                            try:
                                res_ex = supabase.table("placard").select("nom").execute()
                                existing_names = [x["nom"].lower() for x in (res_ex.data or [])]
                                for item in detected_placard:
                                    item_clean = item.strip().capitalize()
                                    if item_clean.lower() not in existing_names:
                                        supabase.table("placard").insert({"nom": item_clean, "en_stock": True}).execute()
                            except Exception:
                                pass

                    st.success(f"🎉 Recette « {rec.get('title')} » enregistrée !")
                    if rec.get("placard_detected"):
                        st.info(f"🥫 Éléments ajoutés au placard : {', '.join(rec.get('placard_detected'))}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")

# ==========================================
# TAB 2 : MES RECETTES
# ==========================================
with tab_recettes:
    st.subheader("📖 Mes recettes sauvegardées")
    if not recipes_list:
        st.info("Aucune recette enregistrée pour l'instant.")
    else:
        for r in recipes_list:
            with st.expander(f"🍽️ **{r['title']}** ({r.get('prep_time', '')} • {r.get('calories', '')} • Base: {r.get('portions', 2)} pers.)"):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**🛒 Ingrédients :**")
                    for ing in r.get("ingredients", []):
                        st.write(f"- {ing}")
                with c2:
                    st.markdown("**👨‍🍳 Instructions :**")
                    st.write(r.get("instructions", ""))
                    if r.get("source_url"):
                        st.link_button("🔗 Voir la vidéo", r["source_url"])
                
                if st.button("🗑️ Supprimer", key=f"del_rec_{r['id']}"):
                    if supabase:
                        supabase.table("recipes").delete().eq("id", r["id"]).execute()
                        st.rerun()

# ==========================================
# TAB 3 : PLANNING SEMAINE & NB DE PERSONNES
# ==========================================
with tab_plan:
    st.subheader("📅 Planning des repas & Nombre de personnes")
    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    all_titles = [r["title"] for r in recipes_list]
    
    plan_data = {}
    if supabase:
        try:
            res_p = supabase.table("meal_plan").select("*").execute()
            for p in (res_p.data or []):
                plan_data[(p["day_of_week"], p["meal_time"])] = {
                    "recipe": p["recipe_title"],
                    "portions": p.get("portions", 2) or 2
                }
        except Exception as e:
            st.error(f"Erreur planning : {e}")
            
    c_a, c_b = st.columns(2)
    for idx, day in enumerate(days):
        col = c_a if idx < 4 else c_b
        with col:
            with st.expander(f"📍 {day}", expanded=True):
                # Midi
                m_info = plan_data.get((day, "Midi"), {"recipe": "—", "portions": 2})
                col_m1, col_m2 = st.columns([3, 1])
                opts = ["—"] + all_titles
                new_m_rec = col_m1.selectbox(f"{day} - Midi", opts, index=opts.index(m_info["recipe"]) if m_info["recipe"] in opts else 0, key=f"p_{day}_m_rec")
                new_m_port = col_m2.number_input("Pers.", min_value=1, max_value=12, value=int(m_info["portions"]), key=f"p_{day}_m_port")
                
                # Soir
                s_info = plan_data.get((day, "Soir"), {"recipe": "—", "portions": 2})
                col_s1, col_s2 = st.columns([3, 1])
                new_s_rec = col_s1.selectbox(f"{day} - Soir", opts, index=opts.index(s_info["recipe"]) if s_info["recipe"] in opts else 0, key=f"p_{day}_s_rec")
                new_s_port = col_s2.number_input("Pers.", min_value=1, max_value=12, value=int(s_info["portions"]), key=f"p_{day}_s_port")
                
                # Sauvegarde si modification
                if (new_m_rec != m_info["recipe"] or new_m_port != m_info["portions"] or 
                    new_s_rec != s_info["recipe"] or new_s_port != s_info["portions"]):
                    if supabase:
                        try:
                            supabase.table("meal_plan").delete().eq("day_of_week", day).execute()
                            if new_m_rec != "—":
                                supabase.table("meal_plan").insert({"day_of_week": day, "meal_time": "Midi", "recipe_title": new_m_rec, "portions": new_m_port}).execute()
                            if new_s_rec != "—":
                                supabase.table("meal_plan").insert({"day_of_week": day, "meal_time": "Soir", "recipe_title": new_s_rec, "portions": new_s_port}).execute()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur mise à jour planning : {e}")

# ==========================================
# TAB 4 : LISTE DE COURSES AJUSTÉE
# ==========================================
with tab_courses:
    st.subheader("🛒 Liste de courses avec portions adaptées")
    
    placard_items = []
    if supabase:
        try:
            res_pl = supabase.table("placard").select("nom").eq("en_stock", True).execute()
            placard_items = [row["nom"].lower() for row in (res_pl.data or [])]
        except Exception:
            pass

    rec_by_title = {r["title"]: r for r in recipes_list}
    to_buy = []
    
    for (day, meal_time), meal_val in plan_data.items():
        rec_name = meal_val["recipe"]
        planned_portions = meal_val["portions"]
        
        if rec_name in rec_by_title:
            r = rec_by_title[rec_name]
            base_portions = r.get("portions", 2) or 2
            ratio = planned_portions / base_portions
            
            for raw_ing in r.get("ingredients", []):
                is_in_placard = any(p in raw_ing.lower() for p in placard_items)
                if not is_in_placard:
                    def scale_match(match):
                        val = float(match.group(0).replace(',', '.'))
                        scaled = val * ratio
                        return str(int(scaled)) if scaled.is_integer() else f"{scaled:.1f}"
                    
                    adjusted_ing = re.sub(r'^\d+(\.\d+)?|\b\d+(\.\d+)?(?=\s*(g|kg|ml|cl|l|c\.à\.s|c\.à\.c|tranches?|oeufs?|œufs?|gousses?|pincées?))', scale_match, raw_ing, flags=re.IGNORECASE)
                    to_buy.append(f"{adjusted_ing} *(pour {rec_name} - {day} {meal_time}, {planned_portions} pers.)*")

    if not to_buy:
        st.info("Aucun ingrédient à acheter (ou tout est dans le Fond de Placard).")
    else:
        st.write(f"🛒 **{len(to_buy)} ingrédients à prévoir :**")
        for i, item in enumerate(to_buy):
            st.checkbox(item, key=f"buy_cloud_{i}")

# ==========================================
# TAB 5 : FOND DE PLACARD
# ==========================================
with tab_placard:
    st.subheader("🥫 Fond de Placard (Ingrédients permanents & Épices)")
    st.caption("Ces ingrédients sont masqués automatiquement de la liste de courses.")
    
    if supabase:
        try:
            res_all_pl = supabase.table("placard").select("*").order("nom").execute()
            items = res_all_pl.data or []
            
            c1, c2 = st.columns([2, 1])
            with c1:
                for it in items:
                    checked = st.checkbox(f"**{it['nom']}**", value=it["en_stock"], key=f"pl_it_{it['id']}")
                    if checked != it["en_stock"]:
                        supabase.table("placard").update({"en_stock": checked}).eq("id", it["id"]).execute()
                        st.rerun()
            with c2:
                new_pl = st.text_input("Ajouter manuellement un essentiel")
                if st.button("Ajouter au placard") and new_pl:
                    supabase.table("placard").insert({"nom": new_pl.strip().capitalize(), "en_stock": True}).execute()
                    st.rerun()
        except Exception as e:
            st.error(f"Erreur placard : {e}")