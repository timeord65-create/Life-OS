import streamlit as st
import json
import os
import re
import urllib.parse
from datetime import datetime
import yt_dlp
from google import genai
import db_manager as db

st.set_page_config(page_title="Recettes & Planning Alimentation", page_icon="🍳", layout="wide")

supabase = db.get_supabase_client()
gemini_key = db.get_secret("GEMINI_API_KEY")

st.title("🍳 Hub Alimentation : Recettes, Planning & Courses")

tab_recettes, tab_import, tab_frigo, tab_plan, tab_courses, tab_placard = st.tabs([
    "📖 Mes Recettes & Dossiers",
    "📥 Importer (Reel / Vidéo)",
    "🧊 Vider le Frigo",
    "📅 Planning",
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
    "🍽️ Sortie / Restaurant"
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
    1. Extrais les détails de la recette. Détermine le nombre de personnes/portions (par défaut 2 si non précisé).
    2. Pour chaque ingrédient, normalise le nom de base, isole la quantité numérique, l'unité et attribue STRICTEMENT l'un de ces rayons :
       ["🥬 Fruits & Légumes", "🥩 Boucherie & Poissonnerie", "🧀 Frais & Produits Laitiers", "🥫 Épicerie & Féculents", "❄️ Surgelés", "🧻 Hygiène & Entretien", "📦 Autre"]
    3. Isole les ingrédients de type 'Fond de placard' (huiles, épices, sel, vinaigres, sauces, condiments).

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
            {{"name": "Riz basmati", "qty": 150, "unit": "g", "rayon": "🥫 Épicerie & Féculents"}}
        ],
        "placard_detected": ["Sel", "Huile d'olive"],
        "instructions": "1. Découper le poulet.\\n2. Cuire avec le riz."
    }}
    """
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)

# --- CHARGEMENT DONNÉES ---
user_folders = []
recipes_list = []

if supabase:
    try:
        res_f = supabase.table("recipe_folders").select("name").order("name").execute()
        user_folders = [f["name"] for f in (res_f.data or []) if f.get("name")]
    except Exception:
        pass

    try:
        res_r = supabase.table("recipes").select("*").order("id", desc=True).execute()
        recipes_list = res_r.data or []
    except Exception:
        pass

# ==========================================
# TAB 1 : MES DOSSIERS & RECETTES
# ==========================================
with tab_recettes:
    st.subheader("📁 Mes Dossiers de Recettes")

    col_search, col_add_folder = st.columns([3, 2])
    search_q = col_search.text_input("🔍 Rechercher une recette (nom ou ingrédient)", "").lower()

    with col_add_folder:
        with st.popover("➕ Créer un nouveau dossier", use_container_width=True):
            new_f_name = st.text_input("Nom du dossier", placeholder="Ex: Plats rapides, Pâtes, Poulet...")
            if st.button("Créer le dossier", type="primary") and new_f_name:
                clean_name = new_f_name.strip()
                if clean_name not in user_folders and supabase:
                    try:
                        supabase.table("recipe_folders").insert({"name": clean_name}).execute()
                        st.success(f"Dossier « {clean_name} » créé !")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur : {e}")

    st.divider()

    folder_map = {f_name: [] for f_name in user_folders}
    unclassified_recipes = []

    for r in recipes_list:
        t = r.get("title", "").lower()
        ings = [str(i).lower() for i in r.get("ingredients", [])]
        if search_q and (search_q not in t and not any(search_q in ing for ing in ings)):
            continue

        r_folders = r.get("tags") or r.get("folders") or []
        if not isinstance(r_folders, list):
            r_folders = []

        assigned = False
        for f in r_folders:
            if f in folder_map:
                folder_map[f].append(r)
                assigned = True

        if not assigned:
            unclassified_recipes.append(r)

    if not user_folders and not recipes_list:
        st.info("Aucun dossier ni recette enregistrée. Crée un dossier ci-dessus ou importe une recette !")
    else:
        # Affichage dossiers
        for f_name in user_folders:
            f_recipes = folder_map.get(f_name, [])
            with st.expander(f"📁 **{f_name}** ({len(f_recipes)} recette{'s' if len(f_recipes) > 1 else ''})"):
                col_del_f1, col_del_f2 = st.columns([4, 1])
                with col_del_f2:
                    if st.button(f"🗑️ Supprimer le dossier", key=f"del_folder_{f_name}"):
                        if supabase:
                            supabase.table("recipe_folders").delete().eq("name", f_name).execute()
                            st.rerun()

                if not f_recipes:
                    st.caption("Ce dossier est vide.")
                else:
                    for r in f_recipes:
                        base_portions = int(r.get("portions", 2) or 2)
                        st.markdown(f"#### 🍽️ {r['title']} — `{base_portions} pers.` ({r.get('prep_time', '')} • {r.get('calories', '')})")
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown(f"**🛒 Ingrédients (pour {base_portions} pers.) :**")
                            for ing in r.get("ingredients", []):
                                if isinstance(ing, dict):
                                    st.write(f"- {ing.get('qty', '')} {ing.get('unit', '')} **{ing.get('name', '')}** *({ing.get('rayon', '')})*")
                                else:
                                    st.write(f"- {ing}")
                        with c2:
                            st.markdown("**👨‍🍳 Instructions :**")
                            st.write(r.get("instructions", ""))
                            if r.get("source_url"):
                                st.link_button("🔗 Voir la vidéo", r["source_url"])

                        # Édition dossiers et portions
                        curr_r_folders = r.get("tags") or r.get("folders") or []
                        if not isinstance(curr_r_folders, list):
                            curr_r_folders = []

                        col_mv1, col_mv2, col_mv3 = st.columns([3, 1, 1])
                        new_f_assigned = col_mv1.multiselect(
                            "Dossiers :",
                            options=user_folders,
                            default=[f for f in curr_r_folders if f in user_folders],
                            key=f"m_fold_{f_name}_{r['id']}"
                        )
                        edit_portions = col_mv2.number_input("Portions", min_value=1, max_value=20, value=base_portions, key=f"edit_p_{f_name}_{r['id']}")
                        
                        if col_mv3.button("Enregistrer", key=f"btn_save_{f_name}_{r['id']}"):
                            if supabase:
                                supabase.table("recipes").update({
                                    "tags": new_f_assigned,
                                    "portions": edit_portions
                                }).eq("id", r["id"]).execute()
                                st.rerun()

                        if st.button("🗑️ Supprimer la recette", key=f"del_rec_{f_name}_{r['id']}"):
                            if supabase:
                                supabase.table("recipes").delete().eq("id", r["id"]).execute()
                                st.rerun()
                        st.divider()

        # Recettes non classées
        if unclassified_recipes:
            with st.expander(f"📂 **Recettes non classées** ({len(unclassified_recipes)})"):
                for r in unclassified_recipes:
                    base_portions = int(r.get("portions", 2) or 2)
                    st.markdown(f"#### 🍽️ {r['title']} — `{base_portions} pers.` ({r.get('prep_time', '')} • {r.get('calories', '')})")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**🛒 Ingrédients (pour {base_portions} pers.) :**")
                        for ing in r.get("ingredients", []):
                            if isinstance(ing, dict):
                                st.write(f"- {ing.get('qty', '')} {ing.get('unit', '')} **{ing.get('name', '')}** *({ing.get('rayon', '')})*")
                            else:
                                st.write(f"- {ing}")
                    with c2:
                        st.markdown("**👨‍🍳 Instructions :**")
                        st.write(r.get("instructions", ""))
                        if r.get("source_url"):
                            st.link_button("🔗 Voir la vidéo", r["source_url"])

                    col_as1, col_as2, col_as3 = st.columns([3, 1, 1])
                    assign_to = col_as1.multiselect(
                        "Ranger dans les dossiers :",
                        options=user_folders,
                        key=f"assign_unclass_{r['id']}"
                    )
                    edit_portions_unclass = col_as2.number_input("Portions", min_value=1, max_value=20, value=base_portions, key=f"edit_p_unclass_{r['id']}")
                    
                    if col_as3.button("Enregistrer", key=f"btn_unclass_{r['id']}"):
                        if supabase:
                            supabase.table("recipes").update({
                                "tags": assign_to,
                                "portions": edit_portions_unclass
                            }).eq("id", r["id"]).execute()
                            st.rerun()

                    if st.button("🗑️ Supprimer la recette", key=f"del_unclass_{r['id']}"):
                        if supabase:
                            supabase.table("recipes").delete().eq("id", r["id"]).execute()
                            st.rerun()
                    st.divider()

# ==========================================
# TAB 2 : IMPORTER
# ==========================================
with tab_import:
    st.subheader("📥 Importer depuis Instagram Reel, TikTok ou Shorts")
    video_url = st.text_input("Lien de la vidéo", placeholder="https://www.instagram.com/reel/...")
    
    col_imp1, col_imp2 = st.columns([2, 1])
    target_folder = col_imp1.selectbox("📁 Ranger directement dans le dossier (optionnel)", ["— Aucun (non classé) —"] + user_folders)
    manual_portions = col_imp2.number_input("Nombre de personnes (base)", min_value=1, max_value=20, value=2)

    if st.button("🪄 Extraire et sauvegarder (+30 XP)", type="primary"):
        if not video_url:
            st.warning("Colle d'abord un lien valide.")
        elif not gemini_key:
            st.error("Clé API Gemini manquante dans les Secrets.")
        else:
            with st.spinner("Analyse de la vidéo par l'IA..."):
                try:
                    raw_info = extract_video_info(video_url)
                    rec = parse_recipe_with_gemini(raw_info, gemini_key)

                    chosen_folders = []
                    if target_folder != "— Aucun (non classé) —":
                        chosen_folders.append(target_folder)

                    final_portions = manual_portions if manual_portions > 0 else rec.get("portions", 2)

                    if supabase:
                        insert_payload = {
                            "title": rec.get("title", "Sans titre"),
                            "portions": int(final_portions),
                            "prep_time": rec.get("prep_time", "20 min"),
                            "calories": rec.get("calories", "500 kcal"),
                            "tags": chosen_folders,
                            "ingredients": rec.get("ingredients", []),
                            "instructions": rec.get("instructions", ""),
                            "source_url": video_url,
                            "date_added": datetime.now().strftime("%Y-%m-%d")
                        }
                        supabase.table("recipes").insert(insert_payload).execute()

                        detected_placard = rec.get("placard_detected", [])
                        if detected_placard:
                            res_ex = supabase.table("placard").select("nom").execute()
                            existing = [x["nom"].lower() for x in (res_ex.data or [])]
                            for item in detected_placard:
                                clean = item.strip().capitalize()
                                if clean.lower() not in existing:
                                    supabase.table("placard").insert({"nom": clean, "en_stock": True}).execute()

                        db.add_xp(30)

                    st.success(f"Recette « {rec.get('title')} » ({final_portions} pers.) enregistrée (+30 XP) !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur d'import : {e}")

# ==========================================
# TAB 3 : VIDER LE FRIGO (ANTI-GASPI)
# ==========================================
with tab_frigo:
    st.subheader("🧊 Vider le Frigo (Anti-Gaspi)")
    st.caption("Indique tes ingrédients restants : l'IA compose une recette express avec tes placards.")

    leftover_input = st.text_input("Ingrédients à utiliser", placeholder="Ex : 2 œufs, reste de lardons, crème, courgette...")
    frigo_portions = st.number_input("Nombre de personnes pour ce repas", min_value=1, max_value=10, value=2)

    if st.button("🪄 Générer une Recette Express", type="primary"):
        if not leftover_input:
            st.warning("Écris au moins 1 ou 2 ingrédients restants.")
        elif not gemini_key:
            st.error("Clé API Gemini manquante.")
        else:
            with st.spinner("Gemini compose ta recette anti-gaspi..."):
                try:
                    placard_available = []
                    if supabase:
                        res_p = supabase.table("placard").select("nom").eq("en_stock", True).execute()
                        placard_available = [x["nom"] for x in (res_p.data or [])]

                    client = genai.Client(api_key=gemini_key)
                    prompt = f"""
                    Tu es un chef anti-gaspillage créatif et rapide.
                    L'utilisateur veut utiliser ces restes : {leftover_input}
                    Il a en stock dans son placard permanent : {', '.join(placard_available)}
                    Nombre de personnes : {frigo_portions}

                    Tâche :
                    1. Donne une idée de plat simple, rapide et savoureux pour {frigo_portions} personne(s).
                    2. Donne les proportions adaptées.
                    3. Détaille la préparation en 3 étapes claires (< 15 min).
                    """
                    resp_ai = client.models.generate_content(model="gemini-3.6-flash", contents=prompt)
                    st.success("💡 Proposition Express :")
                    st.markdown(resp_ai.text)
                except Exception as e:
                    st.error(f"Erreur IA : {e}")

# ==========================================
# TAB 4 : PLANNING
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
                new_m_rec = col_m1.selectbox(f"{day} - Midi", all_choices, index=idx_m, key=f"p_{day}_m_r")
                new_m_port = col_m2.number_input("Pers.", min_value=1, max_value=12, value=int(m_info["portions"]), key=f"p_{day}_m_p")

                # Soir
                s_info = plan_data.get((day, "Soir"), {"recipe": "—", "portions": 2})
                col_s1, col_s2 = st.columns([3, 1])
                idx_s = all_choices.index(s_info["recipe"]) if s_info["recipe"] in all_choices else 0
                new_s_rec = col_s1.selectbox(f"{day} - Soir", all_choices, index=idx_s, key=f"p_{day}_s_r")
                new_s_port = col_s2.number_input("Pers.", min_value=1, max_value=12, value=int(s_info["portions"]), key=f"p_{day}_s_p")

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
# TAB 5 : COURSES PAR RAYON
# ==========================================
with tab_courses:
    st.subheader("🛒 Courses par Rayon")

    placard_in_stock = []
    placard_out_of_stock = []
    if supabase:
        try:
            res_pl = supabase.table("placard").select("nom, en_stock").execute()
            for row in (res_pl.data or []):
                nom_clean = row["nom"].strip()
                if row.get("en_stock", True):
                    placard_in_stock.append(nom_clean.lower())
                else:
                    placard_out_of_stock.append(nom_clean)
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

    # Ingrédients issus du planning
    for (day, meal_time), meal_val in plan_data.items():
        rec_name = meal_val["recipe"]
        planned_portions = meal_val["portions"]

        if rec_name in rec_by_title:
            r = rec_by_title[rec_name]
            base_portions = int(r.get("portions", 2) or 2)
            ratio = planned_portions / base_portions

            for raw_ing in r.get("ingredients", []):
                if isinstance(raw_ing, dict):
                    name = raw_ing.get("name", "").strip()
                    qty = raw_ing.get("qty")
                    unit = raw_ing.get("unit", "").strip()
                    rayon = raw_ing.get("rayon", "📦 Autre")
                else:
                    qty, unit, name, rayon = parse_legacy_line(raw_ing)

                # Si l'ingrédient est en stock dans le placard, on ne l'achète pas
                if any(p in name.lower() for p in placard_in_stock):
                    continue

                key = (rayon, name.lower(), unit.lower())
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

                meal_label = f"{rec_name} ({day[:3]} {meal_time} • {planned_portions}p)"
                if meal_label not in consolidated[key]["meals"]:
                    consolidated[key]["meals"].append(meal_label)

    # Ajout des fonds de placard en RUPTURE DE STOCK (décochés)
    for out_item in placard_out_of_stock:
        key = ("🥫 Épicerie & Féculents", out_item.lower(), "")
        if key not in consolidated:
            consolidated[key] = {
                "rayon": "🥫 Épicerie & Féculents",
                "name": out_item.capitalize(),
                "unit": "",
                "total_qty": None,
                "meals": ["🥫 Fond de placard en rupture"]
            }

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

                    st.checkbox(f"{label}  — *(Pour : {m})*", key=f"chk_r_{r_idx}_a_{idx_a}")
                    export_text_lines.append(f"• {label.replace('**', '')} ({m})")

                for idx_e, ex in enumerate(extra_items):
                    st.checkbox(f"**{ex['name']}** *(Ajout maison)*", key=f"chk_r_{r_idx}_e_{idx_e}")
                    export_text_lines.append(f"• {ex['name']}")

        st.divider()

        full_export_text = "\n".join(export_text_lines)
        wa_url = f"https://api.whatsapp.com/send?text={urllib.parse.quote(full_export_text)}"

        col_w1, col_w2 = st.columns(2)
        with col_w1:
            st.link_button("📲 Partager la liste sur WhatsApp", wa_url, use_container_width=True)
        with col_w2:
            with st.expander("📋 Copier le texte formaté"):
                st.text_area("Texte à copier", full_export_text, height=180)

    st.divider()
    st.markdown("### ➕ Ajouter un article hors-recette")
    col_ad1, col_ad2, col_ad3 = st.columns([2, 2, 1])
    new_item_name = col_ad1.text_input("Nom de l'article", placeholder="Liquide vaisselle, Café...")
    new_item_rayon = col_ad2.selectbox("Rayon", RAYONS_DEFAUT)
    if col_ad3.button("Ajouter", use_container_width=True) and new_item_name:
        st.session_state["extra_courses"].append({"name": new_item_name.strip(), "rayon": new_item_rayon})
        st.rerun()

    if st.session_state["extra_courses"]:
        if st.button("Vider les articles hors-recettes"):
            st.session_state["extra_courses"] = []
            st.rerun()

# ==========================================
# TAB 6 : PLACARD
# ==========================================
with tab_placard:
    st.subheader("🥫 Fond de Placard (Ingrédients permanents)")
    st.caption("Coche les ingrédients que tu as en stock. Si tu en décoches un, il sera automatiquement ajouté à ta liste de courses !")

    if supabase:
        try:
            res_all_pl = supabase.table("placard").select("*").order("nom").execute()
            items = res_all_pl.data or []

            c1, c2 = st.columns([2, 1])
            with c1:
                for it in items:
                    chk = st.checkbox(f"**{it['nom']}**", value=it["en_stock"], key=f"pl_i_{it['id']}")
                    if chk != it["en_stock"]:
                        supabase.table("placard").update({"en_stock": chk}).eq("id", it["id"]).execute()
                        st.rerun()
            with c2:
                new_pl = st.text_input("Ajouter un essentiel")
                if st.button("Ajouter au placard") and new_pl:
                    supabase.table("placard").insert({"nom": new_pl.strip().capitalize(), "en_stock": True}).execute()
                    st.rerun()
        except Exception as e:
            st.error(f"Erreur placard : {e}")