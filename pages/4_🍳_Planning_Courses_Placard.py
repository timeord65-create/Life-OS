import streamlit as st
import sqlite3
import json
import os
from datetime import datetime
import yt_dlp
from google import genai

st.set_page_config(page_title="Recettes & Planning Alimentation", page_icon="🍳", layout="wide")

DB_FILE = "life_os.db"

# --- INITIALISATION AUTOMATIQUE DES TABLES ---
def init_food_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            portions INTEGER,
            prep_time TEXT,
            calories TEXT,
            ingredients TEXT,
            instructions TEXT,
            source_url TEXT,
            date_added TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS placard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE,
            en_stock INTEGER DEFAULT 1
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS meal_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week TEXT,
            meal_time TEXT,
            recipe_title TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            category TEXT,
            amount REAL,
            date TEXT
        )
    """)
    conn.commit()
    conn.close()

init_food_db()

# Récupération clé API Gemini
gemini_key = os.getenv("GEMINI_API_KEY")

st.title("🍳 Hub Alimentation : Recettes, Planning & Courses")

tab_import, tab_recettes, tab_plan, tab_courses, tab_placard = st.tabs([
    "📥 Importer (Reel / Vidéo)",
    "📖 Mes Recettes",
    "📅 Planning Semaine",
    "🛒 Courses Intelligentes",
    "🥫 Fond de Placard"
])

# --- FONCTIONS YT-DLP & GEMINI ---
def extract_video_info(url: str):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'skip_download': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info.get('title', '')
        description = info.get('description', '')
        return f"Titre: {title}\nDescription:\n{description}"

def parse_recipe_with_gemini(raw_text: str, api_key: str):
    client = genai.Client(api_key=api_key)
    prompt = f"""
    Tu es un assistant culinaire expert. Analyse le texte suivant extrait d'un Reel / Short / Vidéo de cuisine.
    Extrais les informations de la recette sous format JSON strict.

    Texte source :
    \"\"\"{raw_text}\"\"\"

    Format JSON attendu :
    {{
        "title": "Nom de la recette",
        "portions": 2,
        "prep_time": "15 min",
        "calories": "450 kcal",
        "ingredients": ["100g de pâtes", "2 œufs", "50g de parmesan", "Poivre noir"],
        "instructions": "1. Cuire les pâtes. 2. Mélanger les œufs et le fromage. 3. Assembler."
    }}
    Si une information manque, estime-la de façon réaliste.
    """
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)

# ==========================================
# TAB 1 : IMPORTER UNE RECETTE
# ==========================================
with tab_import:
    st.subheader("📥 Importer depuis Instagram Reel, TikTok ou YouTube Shorts")
    video_url = st.text_input("Lien de la vidéo (Reel, Shorts, TikTok)", placeholder="https://www.instagram.com/reel/...")

    if st.button("🪄 Extraire la recette avec l'IA", type="primary"):
        if not video_url:
            st.warning("Veuillez coller un lien de vidéo.")
        elif not gemini_key:
            st.error("Clé API Gemini non configurée dans les Secrets Streamlit.")
        else:
            with st.spinner("Analyse de la vidéo et extraction par Gemini..."):
                try:
                    raw_info = extract_video_info(video_url)
                    recipe_data = parse_recipe_with_gemini(raw_info, gemini_key)

                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO recipes (title, portions, prep_time, calories, ingredients, instructions, source_url, date_added)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        recipe_data.get("title", "Recette sans titre"),
                        recipe_data.get("portions", 2),
                        recipe_data.get("prep_time", "20 min"),
                        recipe_data.get("calories", "500 kcal"),
                        json.dumps(recipe_data.get("ingredients", []), ensure_ascii=False),
                        recipe_data.get("instructions", ""),
                        video_url,
                        datetime.now().strftime("%Y-%m-%d")
                    ))
                    conn.commit()
                    conn.close()

                    st.success(f"🎉 Recette « {recipe_data.get('title')} » enregistrée avec succès !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur lors de l'extraction : {e}")

    st.divider()
    st.subheader("✍️ Ou ajouter une recette manuellement")
    with st.expander("Ajouter manuellement"):
        with st.form("manual_recipe_form"):
            m_title = st.text_input("Nom de la recette")
            c1, c2, c3 = st.columns(3)
            m_portions = c1.number_input("Portions", min_value=1, value=2)
            m_time = c2.text_input("Temps de prépa", value="20 min")
            m_cal = c3.text_input("Calories", value="450 kcal")
            m_ing = st.text_area("Ingrédients (1 par ligne)", placeholder="100g de riz\n2 steaks\n1 filet d'huile d'olive")
            m_inst = st.text_area("Instructions de préparation")

            if st.form_submit_button("Enregistrer la recette"):
                if m_title:
                    ing_list = [i.strip() for i in m_ing.split("\n") if i.strip()]
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO recipes (title, portions, prep_time, calories, ingredients, instructions, source_url, date_added)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (m_title, m_portions, m_time, m_cal, json.dumps(ing_list, ensure_ascii=False), m_inst, "", datetime.now().strftime("%Y-%m-%d")))
                    conn.commit()
                    conn.close()
                    st.success("Recette ajoutée !")
                    st.rerun()

# ==========================================
# TAB 2 : MES RECETTES ENREGISTRÉES
# ==========================================
with tab_recettes:
    st.subheader("📖 Bibliothèque de recettes")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, title, portions, prep_time, calories, ingredients, instructions, source_url FROM recipes ORDER BY id DESC")
    all_recs = c.fetchall()
    conn.close()

    if not all_recs:
        st.info("Aucune recette enregistrée pour le moment. Importe ton premier Reel !")
    else:
        for r_id, r_title, r_portions, r_time, r_cal, r_ing, r_inst, r_url in all_recs:
            with st.expander(f"🍽️ **{r_title}** ({r_time} • {r_cal} • {r_portions} pers.)"):
                col_left, col_right = st.columns([1, 1])
                with col_left:
                    st.markdown("**🛒 Ingrédients :**")
                    try:
                        ings = json.loads(r_ing)
                        for ing in ings:
                            st.write(f"- {ing}")
                    except:
                        st.write(r_ing)

                with col_right:
                    st.markdown("**👨‍🍳 Instructions :**")
                    st.write(r_inst)
                    if r_url:
                        st.link_button("🔗 Voir la vidéo originale", r_url)

                if st.button("🗑️ Supprimer cette recette", key=f"del_rec_{r_id}"):
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute("DELETE FROM recipes WHERE id = ?", (r_id,))
                    conn.commit()
                    conn.close()
                    st.rerun()

# ==========================================
# TAB 3 : PLANNING SEMAINE
# ==========================================
with tab_plan:
    st.subheader("📅 Organiser les repas de la semaine")
    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT title FROM recipes")
    recipe_options = [r[0] for r in c.fetchall()]

    c.execute("SELECT day_of_week, meal_time, recipe_title FROM meal_plan")
    current_plan = {(r[0], r[1]): r[2] for r in c.fetchall()}
    conn.close()

    col_j1, col_j2 = st.columns(2)
    for idx, day in enumerate(days):
        col = col_j1 if idx < 4 else col_j2
        with col:
            with st.expander(f"📍 {day}", expanded=True):
                midi_val = current_plan.get((day, "Midi"), "—")
                soir_val = current_plan.get((day, "Soir"), "—")

                opts = ["—"] + recipe_options
                new_midi = st.selectbox(f"{day} - Midi", opts, index=opts.index(midi_val) if midi_val in opts else 0, key=f"plan_{day}_midi")
                new_soir = st.selectbox(f"{day} - Soir", opts, index=opts.index(soir_val) if soir_val in opts else 0, key=f"plan_{day}_soir")

                if new_midi != midi_val or new_soir != soir_val:
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute("DELETE FROM meal_plan WHERE day_of_week = ?", (day,))
                    if new_midi != "—":
                        c.execute("INSERT INTO meal_plan (day_of_week, meal_time, recipe_title) VALUES (?, 'Midi', ?)", (day, new_midi))
                    if new_soir != "—":
                        c.execute("INSERT INTO meal_plan (day_of_week, meal_time, recipe_title) VALUES (?, 'Soir', ?)", (day, new_soir))
                    conn.commit()
                    conn.close()
                    st.rerun()

# ==========================================
# TAB 4 : LISTE DE COURSES INTELLIGENTE
# ==========================================
with tab_courses:
    st.subheader("🛒 Liste de courses déduite du planning & du placard")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT DISTINCT recipe_title FROM meal_plan WHERE recipe_title != '—'")
    planned = [r[0] for r in c.fetchall()]

    c.execute("SELECT LOWER(nom) FROM placard WHERE en_stock = 1")
    placard_items = [r[0] for r in c.fetchall()]

    ingredients_to_buy = []
    for rec_name in planned:
        c.execute("SELECT ingredients FROM recipes WHERE title = ?", (rec_name,))
        row = c.fetchone()
        if row and row[0]:
            try:
                ings = json.loads(row[0])
                for ing in ings:
                    already_have = any(p in ing.lower() for p in placard_items)
                    if not already_have:
                        ingredients_to_buy.append(ing)
            except:
                pass
    conn.close()

    if not ingredients_to_buy:
        st.info("Aucun ingrédient nécessaire pour le moment (ajoute des repas dans le planning).")
    else:
        st.write(f"🛒 **{len(ingredients_to_buy)} ingrédients à acheter :**")
        for i, ing in enumerate(ingredients_to_buy):
            st.checkbox(ing, key=f"buy_{i}")

        st.divider()
        st.markdown("### 💳 Valider mes courses")
        montant_ticket = st.number_input("Montant total du ticket de caisse (€)", min_value=0.0, step=5.0, value=45.0)
        if st.button("Valider et ajouter aux dépenses du mois", type="primary"):
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO transactions (type, category, amount, date) VALUES ('Dépense', 'Alimentation', ?, date('now'))", (montant_ticket,))
            conn.commit()
            conn.close()
            st.success(f"Dépense de {montant_ticket:.2f} € enregistrée dans l'onglet Finances !")

# ==========================================
# TAB 5 : FOND DE PLACARD
# ==========================================
with tab_placard:
    st.subheader("🥫 Essentiels longue conservation (Placard & Épices)")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, nom, en_stock FROM placard ORDER BY nom ASC")
    items = c.fetchall()

    c1, c2 = st.columns([2, 1])
    with c1:
        for i_id, nom, stock in items:
            check = st.checkbox(nom, value=bool(stock), key=f"pl_{i_id}")
            if check != bool(stock):
                c.execute("UPDATE placard SET en_stock = ? WHERE id = ?", (1 if check else 0, i_id))
                conn.commit()
                st.rerun()
    with c2:
        new_item = st.text_input("Nouvel ingrédient permanent")
        if st.button("Ajouter à la liste") and new_item:
            c.execute("INSERT OR IGNORE INTO placard (nom, en_stock) VALUES (?, 1)", (new_item.strip(),))
            conn.commit()
            st.rerun()
    conn.close()