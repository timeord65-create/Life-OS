import streamlit as st
import sqlite3
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from google import genai

st.set_page_config(page_title="Life OS V2 - Cockpit", page_icon="⚡", layout="wide")

DB_FILE = "life_os.db"

# --- 1. INITIALISATION DE TOUTES LES TABLES ---
def init_all_dbs():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Tâches
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            priority TEXT,
            done INTEGER DEFAULT 0,
            date_created TEXT
        )
    """)
    # Habitudes
    c.execute("""
        CREATE TABLE IF NOT EXISTS habit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_name TEXT,
            date TEXT,
            status INTEGER DEFAULT 1
        )
    """)
    # Finances
    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            category TEXT,
            amount REAL,
            date TEXT
        )
    """)
    # Sport
    c.execute("""
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sport TEXT,
            duration INTEGER,
            distance REAL,
            rpe INTEGER,
            notes TEXT,
            date TEXT
        )
    """)
    # Recettes
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
    # Placard
    c.execute("""
        CREATE TABLE IF NOT EXISTS placard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE,
            en_stock INTEGER DEFAULT 1
        )
    """)
    # Planning repas
    c.execute("""
        CREATE TABLE IF NOT EXISTS meal_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week TEXT,
            meal_time TEXT,
            recipe_title TEXT
        )
    """)
    # Idées
    c.execute("""
        CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            category TEXT,
            status TEXT,
            notes TEXT,
            date_created TEXT
        )
    """)
    conn.commit()
    conn.close()

init_all_dbs()

today_str = datetime.now().strftime("%Y-%m-%d")
date_display = datetime.now().strftime("%A %d %B %Y").capitalize()

# --- SIDEBAR CONFIG ---
with st.sidebar:
    st.header("⚙️ Configuration")
    gemini_key = st.text_input("Clé API Gemini", type="password", help="Indispensable pour le Copilote IA et les Recettes")
    if gemini_key:
        os.environ["GEMINI_API_KEY"] = gemini_key

# --- HEADER PRINCIPAL ---
st.title(f"⚡ Life OS — {date_display}")

# --- RÉSUMÉ SYNTHÉTIQUE ---
conn = sqlite3.connect(DB_FILE)

# Solde
df_trans = pd.read_sql_query("SELECT type, amount, date FROM transactions", conn)
solde_mois = 0.0
if not df_trans.empty:
    current_month = today_str[:7]
    month_data = df_trans[df_trans["date"].str.startswith(current_month)]
    rev = month_data[month_data["type"] == "Revenu"]["amount"].sum()
    dep = month_data[month_data["type"] == "Dépense"]["amount"].sum()
    solde_mois = rev - dep

# Sport semaine
df_sport = pd.read_sql_query("SELECT distance, duration, date FROM workouts", conn)
km_total = df_sport["distance"].sum() if not df_sport.empty else 0.0

# Tâches
df_tasks = pd.read_sql_query("SELECT id, title, priority FROM tasks WHERE done = 0", conn)
conn.close()

m1, m2, m3 = st.columns(3)
m1.metric("💰 Solde du mois", f"{solde_mois:,.2f} €")
m2.metric("🏃 Volume sport cumulé", f"{km_total:.1f} km")
m3.metric("🎯 Tâches en attente", f"{len(df_tasks)}")

st.divider()

# --- WIDGETS D'ACTION RAPIDE (1-CLIC) ---
st.subheader("⚡ Actions rapides (1-clic)")
q1, q2, q3, q4 = st.columns(4)
with q1:
    if st.button("💧 +1 Verre d'eau (0.5L)", use_container_width=True):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO habit_logs (habit_name, date, status) VALUES ('Hydratation (2L)', ?, 1)", (today_str,))
        conn.commit()
        conn.close()
        st.toast("Hydratation enregistrée !")
        st.rerun()

with q2:
    if st.button("☕ Café / Boisson (2.50€)", use_container_width=True):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO transactions (type, category, amount, date) VALUES ('Dépense', 'Alimentation', 2.50, ?)", (today_str,))
        conn.commit()
        conn.close()
        st.toast("Dépense 2.50€ enregistrée !")
        st.rerun()

with q3:
    if st.button("🥪 Déjeuner / Repas (12.00€)", use_container_width=True):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO transactions (type, category, amount, date) VALUES ('Dépense', 'Alimentation', 12.00, ?)", (today_str,))
        conn.commit()
        conn.close()
        st.toast("Dépense repas 12.00€ enregistrée !")
        st.rerun()

with q4:
    if st.button("🏃 Footing rapide 5km (25min)", use_container_width=True):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO workouts (sport, duration, distance, rpe, notes, date) VALUES ('Course à pied / Trail', 25, 5.0, 6, 'Séance rapide', ?)", (today_str,))
        conn.commit()
        conn.close()
        st.toast("Séance 5km enregistrée !")
        st.rerun()

st.divider()

# --- BLOC 2 COLONNES : TÂCHES & HABITUDES ---
c_left, c_right = st.columns([1, 1])

with c_left:
    st.subheader("📌 Tâches prioritaires")
    if df_tasks.empty:
        st.info("Aucune tâche en cours.")
    else:
        for _, row in df_tasks.head(5).iterrows():
            t_id, t_title, t_prio = row["id"], row["title"], row["priority"]
            if st.button(f"✅ {t_title} ({t_prio})", key=f"dash_task_{t_id}", use_container_width=True):
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("UPDATE tasks SET done = 1 WHERE id = ?", (t_id,))
                conn.commit()
                conn.close()
                st.rerun()

with c_right:
    st.subheader("🔥 Habitudes du jour")
    habits = ["Hydratation (2L)", "Sport / Mobilité", "Lecture / Veille", "Sommeil > 7h30"]
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT habit_name FROM habit_logs WHERE date = ?", (today_str,))
    done_today = [r[0] for r in c.fetchall()]
    
    for h in habits:
        is_done = h in done_today
        if st.checkbox(h, value=is_done, key=f"dash_hab_{h}"):
            if not is_done:
                c.execute("INSERT INTO habit_logs (habit_name, date, status) VALUES (?, ?, 1)", (h, today_str))
                conn.commit()
                st.rerun()
        else:
            if is_done:
                c.execute("DELETE FROM habit_logs WHERE habit_name = ? AND date = ?", (h, today_str))
                conn.commit()
                st.rerun()
    conn.close()

st.divider()

# --- 🤖 AGENT COPILOTE IA (GEMINI) ---
st.subheader("🤖 Le Copilote IA (Gemini)")
st.caption("Pose-lui une question sur tes données, ou dicte/écris une phrase en vrac (ex: *« Payé 14.50€ de cantine et couru 8.2km en 42min ce matin »*).")

user_prompt = st.text_input("💬 Que veux-tu demander ou enregistrer ?", placeholder="Ex: Que me reste-t-il comme budget ? ou Payé 15€ d'essence et couru 6km...")

if st.button("Envoyer au Copilote", type="primary"):
    if not gemini_key:
        st.error("Veuillez renseigner votre clé API Gemini dans le menu de gauche.")
    elif not user_prompt:
        st.warning("Écris un message pour le copilote.")
    else:
        with st.spinner("Analyse du Copilote en cours..."):
            try:
                # 1. Récupération de l'état actuel de la base de données
                conn = sqlite3.connect(DB_FILE)
                transactions_data = pd.read_sql_query("SELECT type, category, amount, date FROM transactions ORDER BY id DESC LIMIT 20", conn).to_dict(orient="records")
                workouts_data = pd.read_sql_query("SELECT sport, duration, distance, rpe, date FROM workouts ORDER BY id DESC LIMIT 20", conn).to_dict(orient="records")
                tasks_data = pd.read_sql_query("SELECT title, priority, done FROM tasks WHERE done = 0", conn).to_dict(orient="records")
                recipes_data = pd.read_sql_query("SELECT title, ingredients FROM recipes LIMIT 15", conn).to_dict(orient="records")
                placard_data = pd.read_sql_query("SELECT nom, en_stock FROM placard WHERE en_stock = 1", conn).to_dict(orient="records")
                conn.close()

                system_context = f"""
                Tu es le copilote IA du Life OS de l'utilisateur. Tu as accès à ses données :
                - Date du jour : {today_str}
                - Transactions récentes : {json.dumps(transactions_data, ensure_ascii=False)}
                - Séances de sport récentes : {json.dumps(workouts_data, ensure_ascii=False)}
                - Tâches en attente : {json.dumps(tasks_data, ensure_ascii=False)}
                - Ingrédients en stock dans le placard : {json.dumps(placard_data, ensure_ascii=False)}
                - Recettes enregistrées : {json.dumps(recipes_data, ensure_ascii=False)}

                L'utilisateur peut soit :
                1. Te poser une question sur sa vie, ses données, ses recettes, ses entraînements, son budget.
                2. Te donner des actions à enregistrer en vrac (dépenses, séances de sport, tâches).

                Tu dois répondre STRICTEMENT au format JSON suivant :
                {{
                    "reponse_texte": "Ta réponse claire, amicale et synthétique à l'utilisateur.",
                    "actions_a_inserer": [
                        {{
                            "table": "transactions",
                            "data": {{"type": "Dépense", "category": "Alimentation", "amount": 14.50, "date": "{today_str}"}}
                        }},
                        {{
                            "table": "workouts",
                            "data": {{"sport": "Course à pied / Trail", "duration": 42, "distance": 8.2, "rpe": 7, "notes": "Automatique via Copilote", "date": "{today_str}"}}
                        }},
                        {{
                            "table": "tasks",
                            "data": {{"title": "Nom de la tâche", "priority": "⚡ Projet", "done": 0, "date_created": "{today_str}"}}
                        }}
                    ]
                }}
                Si aucune insertion n'est requise (juste une question), laisse `actions_a_inserer` vide : [].
                """

                client = genai.Client(api_key=gemini_key)
                response = client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=f"{system_context}\n\nDemande de l'utilisateur : {user_prompt}",
                    config={"response_mime_type": "application/json"}
                )

                res_json = json.loads(response.text)
                st.markdown(f"**🤖 Réponse :** {res_json.get('reponse_texte')}")

                actions = res_json.get("actions_a_inserer", [])
                if actions:
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    for act in actions:
                        table = act.get("table")
                        d = act.get("data", {})
                        if table == "transactions":
                            c.execute("INSERT INTO transactions (type, category, amount, date) VALUES (?, ?, ?, ?)",
                                      (d.get("type", "Dépense"), d.get("category", "Autre"), d.get("amount", 0.0), d.get("date", today_str)))
                        elif table == "workouts":
                            c.execute("INSERT INTO workouts (sport, duration, distance, rpe, notes, date) VALUES (?, ?, ?, ?, ?, ?)",
                                      (d.get("sport", "Autre"), d.get("duration", 30), d.get("distance", 0.0), d.get("rpe", 6), d.get("notes", ""), d.get("date", today_str)))
                        elif table == "tasks":
                            c.execute("INSERT INTO tasks (title, priority, done, date_created) VALUES (?, ?, ?, ?)",
                                      (d.get("title"), d.get("priority", "📋 Quotidien"), 0, d.get("date_created", today_str)))
                    conn.commit()
                    conn.close()
                    st.success(f"⚡ {len(actions)} donnée(s) insérée(s) automatiquement dans ta base !")
                    st.rerun()

            except Exception as e:
                st.error(f"Erreur copilote : {e}")