import streamlit as st
import sqlite3
import json
import pandas as pd

st.set_page_config(page_title="Planning & Courses Intelligentes", page_icon="🍳", layout="wide")
DB_FILE = "life_os.db"

st.title("🍳 Planning Repas & Liste de Courses Intelligente")

tab_plan, tab_courses, tab_placard = st.tabs(["📅 Planning de la semaine", "🛒 Liste de courses auto", "🥫 Fond de Placard"])

# --- TAB 1 : PLANNING SEMAINE ---
with tab_plan:
    st.subheader("Organiser les repas de la semaine")
    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT title FROM recipes")
    all_recipes = [r[0] for r in c.fetchall()]
    
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
                
                opts = ["—"] + all_recipes
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

# --- TAB 2 : LISTE DE COURSES INTELLIGENTE ---
with tab_courses:
    st.subheader("Liste de courses déduite du planning & du placard")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Recettes planifiées
    c.execute("SELECT DISTINCT recipe_title FROM meal_plan WHERE recipe_title != '—'")
    planned = [r[0] for r in c.fetchall()]
    
    # Placard
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
                    # Vérification si présent dans le placard
                    already_have = any(p in ing.lower() for p in placard_items)
                    if not already_have:
                        ingredients_to_buy.append(ing)
            except:
                pass
    conn.close()
    
    if not ingredients_to_buy:
        st.info("Aucun ingrédient nécessaire pour l'instant (ou tout est déjà dans ton placard).")
    else:
        st.write(f"🛒 **{len(ingredients_to_buy)} ingrédients nécessaires pour la semaine :**")
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

# --- TAB 3 : FOND DE PLACARD ---
with tab_placard:
    st.subheader("Essentiels longue conservation (Placard & Épices)")
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