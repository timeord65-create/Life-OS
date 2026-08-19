import streamlit as st
import json
import os
import re
import urllib.parse
from datetime import datetime
import yt_dlp
from google import genai
from supabase import create_client, Client

st.set_page_config(page_title="Recettes & Planning Alimentation", page_icon="🍳", layout="wide")

# --- CONNEXION SUPABASE & GEMINI ---
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")

@st.cache_resource
def get_supabase():
    if supabase_url and supabase_key:
        try:
            return create_client(supabase_url, supabase_key)
        except Exception:
            return None
    return None

supabase = get_supabase()

st.title("🍳 Hub Alimentation : Recettes, Planning & Courses")

tab_import, tab_recettes, tab_plan, tab_courses, tab_placard = st.tabs([
    "📥 Importer (Reel / Vidéo)",
    "📖 Mes Recettes",
    "📅 Planning & Portions",
    "🛒 Courses par Rayon",
    "🥫 Fond de Placard"
])

RAYONS_DEFAUT = [
    "🥬 Fruits & Légumes",
    "🥩 Boucherie & Poissonnerie",
    "🧀 Frais & Produits Laitiers",
    "🥫 Épicerie & Féculents",
    "❄️ Surgelés",
    "🧻 Hygiène & Entretien",
    "📦 Autre"
]

SPECIAL_MEALS = [
    "—",
    "🥡 Restes / Tupperware",
    "🍽️ Sortie / Restaurant",
    "🥪 Sur le pouce / Rapide",
    "🚫 Sauter le repas"
]

# --- FONCTIONS EXTRACTION & GEMINI ---
def extract_video_info(url: str):
    ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return f"Titre : {info.get('title', '')}\nDescription :\n{info.get('description', '')}"

def parse_recipe_with_gemini(raw_text: str, api_key: str):
    client = genai.Client(api_key=api_key)
    prompt = f"""
    Tu es un assistant culinaire expert. Analyse cette vidéo/Reel de cuisine.
    1. Extrais les détails de la recette.
    2. Pour chaque ingrédient, normalise le nom de base, isole la quantité numérique, l'unité et attribue STRICTEMENT l'un de ces rayons :
       ["🥬 Fruits & Légumes", "🥩 Boucherie & Poissonnerie", "🧀 Frais & Produits Laitiers", "🥫 Épicerie & Féculents", "❄️ Surgelés", "🧻 Hygiène & Entretien", "📦 Autre"]
    3. Isole les ingrédients de type 'Fond de placard / Longue conservation' (huiles, épices, sel, vinaigres, sauces, etc.).

    Texte source :
    \"\"\"{raw_text}\"\"\"

    Format JSON attendu :
    {{
        "title": "Nom de la recette",
        "portions": 2,
        "prep_time": "20 min",
        "calories": "500 kcal",
        "ingredients": [
            {{"name": "Blanc de poulet", "qty": 300, "unit": "g", "rayon": "🥩 Boucherie & Poissonnerie"}},
            {{"name": "Riz basmati", "qty": 150, "unit": "g", "rayon": "🥫 Épicerie & Féculents"}},
            {{"name": "Paprika", "qty": 1, "unit": "c.à.c", "rayon": "🥫 Épicerie & Féculents"}}
        ],
        "placard_detected": ["Paprika", "Sel", "Poivre", "Huile d'olive"],
        "instructions": "1. Découper le poulet.\\n2. Cuire avec les épices.\\n3. Servir avec le riz."
    }}
    """
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)

# --- CHARGEMENT RECETTES ---
recipes_list = []
if supabase:
    try:
        res = supabase.table("recipes").select("*").order("id", desc=True).execute()
        recipes_list = res.data or []
    except Exception:
        pass

# ==========================================
# TAB 1 : IMPORTER
# ==========================================
with tab_import:
    st.subheader("📥 Importer depuis Instagram Reel, TikTok ou Shorts")
    video_url = st.text_input("Lien de la vidéo", placeholder="https://www.instagram.com/reel/...")

    if st.button("🪄 Extraire et sauvegarder", type="primary"):
        if not video_url:
            st.warning("Colle d'abord un lien vidéo valide.")
        elif not gemini_key:
            st.error("Clé API Gemini introuvable dans les Secrets.")
        else:
            with st.spinner("Analyse et structuration des ingrédients par l'IA..."):
                try:
                    raw_info = extract_video_info(video_url)
                    rec = parse_recipe_with_gemini(raw_info, gemini_key)

                    if supabase:
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

                        detected_placard = rec.get("placard_detected", [])
                        if detected_placard:
                            res_ex = supabase.table("placard").select("nom").execute()
                            existing = [x["nom"].lower() for x in (res_ex.data or [])]
                            for item in detected_placard:
                                clean = item.strip().capitalize()
                                if clean.lower() not in existing:
                                    supabase.table("placard").insert({"nom": clean, "en_stock": True}).execute()

                    st.success(f"Recette « {rec.get('title')} » enregistrée !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur d'import : {e}")

# ==========================================
# TAB 2 : MES RECETTES
# ==========================================
with tab_recettes:
    st.subheader("📖 Mes Recettes")
    if not recipes_list:
        st.info("Aucune recette enregistrée.")
    else:
        search_q = st.text_input("🔍 Filtrer par nom ou ingrédient", "").lower()

        filtered_recipes = []
        for r in recipes_list:
            t = r.get("title", "").lower()
            ings = [str(i).lower() for i in r.get("ingredients", [])]
            if not search_q or search_q in t or any(search_q in ing for ing in ings):
                filtered_recipes.append(r)

        for r in filtered_recipes:
            with st.expander(f"🍽️ **{r['title']}** ({r.get('prep_time', '')} • {r.get('calories', '')} • Base : {r.get('portions', 2)} pers.)"):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**🛒 Ingrédients :**")
                    for ing in r.get("ingredients", []):
                        if isinstance(ing, dict):
                            qty_d = ing.get("qty", "")
                            unit_d = ing.get("unit", "")
                            name_d = ing.get("name", "")
                            st.write(f"- {qty_d} {unit_d} **{name_d}** *({ing.get('rayon', '')})*")
                        else:
                            st.write(f"- {ing}")
                with c2:
                    st.markdown("**👨‍🍳 Instructions :**")
                    st.write(r.get("instructions", ""))
                    if r.get("source_url"):
                        st.link_button("🔗 Vidéo d'origine", r["source_url"])

                if st.button("🗑️ Supprimer cette recette", key=f"del_rec_{r['id']}"):
                    if supabase:
                        supabase.table("recipes").delete().eq("id", r["id"]).execute()
                        st.rerun()

# ==========================================
# TAB 3 : PLANNING
# ==========================================
with tab_plan:
    st.subheader("📅 Planning de la semaine")
    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    recipe_titles = [r["title"] for r in recipes_list]
    all_choices = SPECIAL_MEALS + recipe_titles

    plan_data = {}
    if supabase:
        try:
            res_p = supabase.table("meal_plan").select("*").execute()
            for p in (res_p.data or []):
                plan_data[(p["day_of_week"], p["meal_time"])] = {
                    "recipe": p["recipe_title"],
                    "portions": p.get("portions", 2) or 2
                }
        except Exception:
            pass

    c_a, c_b = st.columns(2)
    for idx, day in enumerate(days):
        col = c_a if idx < 4 else c_b
        with col:
            with st.expander(f"📍 {day}", expanded=True):
                # Midi
                m_info = plan_data.get((day, "Midi"), {"recipe": "—", "portions": 2})
                col_m1, col_m2 = st.columns([3, 1])
                idx_m = all_choices.index(m_info["recipe"]) if m_info["recipe"] in all_choices else 0
                new_m_rec = col_m1.selectbox(f"{day} - Midi", all_choices, index=idx_m, key=f"plan_{day}_m_rec")
                new_m_port = col_m2.number_input("Pers.", min_value=1, max_value=12, value=int(m_info["portions"]), key=f"plan_{day}_m_port")

                # Soir
                s_info = plan_data.get((day, "Soir"), {"recipe": "—", "portions": 2})
                col_s1, col_s2 = st.columns([3, 1])
                idx_s = all_choices.index(s_info["recipe"]) if s_info["recipe"] in all_choices else 0
                new_s_rec = col_s1.selectbox(f"{day} - Soir", all_choices, index=idx_s, key=f"plan_{day}_s_rec")
                new_s_port = col_s2.number_input("Pers.", min_value=1, max_value=12, value=int(s_info["portions"]), key=f"plan_{day}_s_port")

                if (new_m_rec != m_info["recipe"] or new_m_port != m_info["portions"] or
                    new_s_rec != s_info["recipe"] or new_s_port != s_info["portions"]):
                    if supabase:
                        supabase.table("meal_plan").delete().eq("day_of_week", day).execute()
                        if new_m_rec != "—":
                            supabase.table("meal_plan").insert({"day_of_week": day, "meal_time": "Midi", "recipe_title": new_m_rec, "portions": new_m_port}).execute()
                        if new_s_rec != "—":
                            supabase.table("meal_plan").insert({"day_of_week": day, "meal_time": "Soir", "recipe_title": new_s_rec, "portions": new_s_port}).execute()
                        st.rerun()

# ==========================================
# TAB 4 : COURSES PAR RAYON
# ==========================================
with tab_courses:
    st.subheader("🛒 Liste de courses triée par rayon")

    placard_items = []
    if supabase:
        try:
            res_pl = supabase.table("placard").select("nom").eq("en_stock", True).execute()
            placard_items = [row["nom"].lower().strip() for row in (res_pl.data or [])]
        except Exception:
            pass

    rec_by_title = {r["title"]: r for r in recipes_list}
    consolidated = {}

    def parse_legacy_line(line: str):
        pat = r'^\s*(\d+(?:[\.,]\d+)?)\s*(kg|g|mg|l|cl|ml|c\.à\.s|cas|c\.à\.c|cac|gousses?|tranches?|boîtes?|pièces?|morceaux?)?\s*(?:de\s+|d\'\s+)?(.*)$'
        m = re.match(pat, line.strip(), re.IGNORECASE)
        if m:
            q_s, u, n = m.groups()
            return float(q_s.replace(',', '.')), (u or "").strip(), n.strip(), "📦 Autre"
        return None, "", line.strip(), "📦 Autre"

    for (day, meal_time), meal_val in plan_data.items():
        rec_name = meal_val["recipe"]
        planned_portions = meal_val["portions"]

        if rec_name in rec_by_title:
            r = rec_by_title[rec_name]
            base_portions = r.get("portions", 2) or 2
            ratio = planned_portions / base_portions

            for raw_ing in r.get("ingredients", []):
                if isinstance(raw_ing, dict):
                    name = raw_ing.get("name", "").strip()
                    qty = raw_ing.get("qty")
                    unit = raw_ing.get("unit", "").strip()
                    rayon = raw_ing.get("rayon", "📦 Autre")
                else:
                    qty, unit, name, rayon = parse_legacy_line(raw_ing)

                if any(p in name.lower() for p in placard_items):
                    continue

                clean_name_key = name.lower()
                clean_unit_key = unit.lower()
                key = (rayon, clean_name_key, clean_unit_key)

                if key not in consolidated:
                    consolidated[key] = {
                        "rayon": rayon,
                        "name": name.capitalize(),
                        "unit": unit,
                        "total_qty": 0.0 if qty is not None else None,
                        "meals": []
                    }

                if qty is not None:
                    consolidated[key]["total_qty"] += (float(qty) * ratio)

                meal_label = f"{rec_name} ({day[:3]} {meal_time})"
                if meal_label not in consolidated[key]["meals"]:
                    consolidated[key]["meals"].append(meal_label)

    if "extra_courses" not in st.session_state:
        st.session_state["extra_courses"] = []

    if not consolidated and not st.session_state["extra_courses"]:
        st.info("Aucun ingrédient à acheter pour les repas sélectionnés.")
    else:
        export_text_lines = ["🛒 *LISTE DE COURSES DU FOYER*\n"]
        items_by_rayon = {}
        for (rayon, _, _), val in consolidated.items():
            items_by_rayon.setdefault(rayon, []).append(val)

        for r_idx, rayon in enumerate(RAYONS_DEFAUT):
            auto_items = items_by_rayon.get(rayon, [])
            extra_items = [x for x in st.session_state["extra_courses"] if x["rayon"] == rayon]

            if auto_items or extra_items:
                st.markdown(f"### {rayon}")
                export_text_lines.append(f"\n*{rayon.upper()}*")

                for idx_a, it in enumerate(auto_items):
                    q = it["total_qty"]
                    u = it["unit"]
                    n = it["name"]
                    m = ", ".join(it["meals"])

                    if q is not None:
                        q_str = str(int(q)) if q.is_integer() else f"{q:.1f}"
                        label = f"**{q_str} {u}** {n}" if u else f"**{q_str}** {n}"
                    else:
                        label = f"**{n}**"

                    st.checkbox(f"{label}  — *(Pour : {m})*", key=f"chk_auto_{r_idx}_{idx_a}")
                    export_text_lines.append(f"• {label.replace('**', '')} ({m})")

                for idx_e, ex in enumerate(extra_items):
                    st.checkbox(f"**{ex['name']}** *(Ajout maison)*", key=f"chk_extra_{r_idx}_{idx_e}")
                    export_text_lines.append(f"• {ex['name']}")

        st.divider()

        full_export_text = "\n".join(export_text_lines)
        encoded_text = urllib.parse.quote(full_export_text)
        wa_url = f"https://api.whatsapp.com/send?text={encoded_text}"

        col_w1, col_w2 = st.columns(2)
        with col_w1:
            st.link_button("📲 Partager la liste sur WhatsApp", wa_url, use_container_width=True)
        with col_w2:
            with st.expander("📋 Copier le texte formaté"):
                st.text_area("Texte prêt à copier", full_export_text, height=180)

    st.divider()

    st.markdown("### ➕ Ajouter un article hors-recette")
    col_ad1, col_ad2, col_ad3 = st.columns([2, 2, 1])
    new_item_name = col_ad1.text_input("Nom de l'article", placeholder="Liquide vaisselle, Bananes...")
    new_item_rayon = col_ad2.selectbox("Rayon", RAYONS_DEFAUT)
    if col_ad3.button("Ajouter", use_container_width=True) and new_item_name:
        st.session_state["extra_courses"].append({"name": new_item_name.strip(), "rayon": new_item_rayon})
        st.rerun()

    if st.session_state["extra_courses"]:
        if st.button("Vider les articles hors-recettes"):
            st.session_state["extra_courses"] = []
            st.rerun()

# ==========================================
# TAB 5 : FOND DE PLACARD
# ==========================================
with tab_placard:
    st.subheader("🥫 Fond de Placard (Ingrédients permanents)")
    st.caption("Ces ingrédients sont exclus de la liste de courses tant qu'ils sont cochés.")

    if supabase:
        try:
            res_all_pl = supabase.table("placard").select("*").order("nom").execute()
            items = res_all_pl.data or []

            c1, c2 = st.columns([2, 1])
            with c1:
                for it in items:
                    chk = st.checkbox(f"**{it['nom']}**", value=it["en_stock"], key=f"pl_item_{it['id']}")
                    if chk != it["en_stock"]:
                        supabase.table("placard").update({"en_stock": chk}).eq("id", it["id"]).execute()
                        st.rerun()
            with c2:
                new_pl = st.text_input("Ajouter un essentiel")
                if st.button("Ajouter") and new_pl:
                    supabase.table("placard").insert({"nom": new_pl.strip().capitalize(), "en_stock": True}).execute()
                    st.rerun()
        except Exception as e:
            st.error(f"Erreur placard : {e}")