import streamlit as st
import sqlite3
import pandas as pd
import json
import os
from datetime import datetime
from google import genai
import db_manager as db

st.set_page_config(page_title="Life OS V2 - Cockpit RPG", page_icon="⚡", layout="wide")

# Initialisation DB
db.init_db()

today_str = datetime.now().strftime("%Y-%m-%d")
date_display = datetime.now().strftime("%A %d %B %Y").capitalize()

# Clé Gemini (Secrets Streamlit ou Sidebar)
gemini_key = os.getenv("GEMINI_API_KEY")

with st.sidebar:
    st.header("⚙️ Configuration")
    if not gemini_key:
        input_key = st.text_input("Clé API Gemini", type="password")
        if input_key:
            os.environ["GEMINI_API_KEY"] = input_key
            gemini_key = input_key

# --- BARRE DE GAMIFICATION RPG ---
prof = db.get_profile()

col_avatar, col_bar = st.columns([1, 4])
with col_avatar:
    st.markdown(f"### 🎖️ Niveau {prof['level']}")
    st.caption(f"**{prof['title']}**")
    st.markdown(f"🔥 **Série : {prof['streak']} jours**")

with col_bar:
    st.markdown(f"**Progression XP : {prof['xp_in_level']} / {prof['xp_needed']} XP** (Total: {prof['total_xp']} XP)")
    st.progress(prof['progress'])

st.divider()

# --- HEADER PRINCIPAL & MÉTRIQUES ---
st.title(f"⚡ Life OS — {date_display}")

conn = sqlite3.connect(db.DB_FILE)
df_trans = pd.read_sql_query("SELECT type, amount, date FROM transactions", conn)
solde_mois = 0.0
if not df_trans.empty:
    current_month = today_str[:7]
    month_data = df_trans[df_trans["date"].str.startswith(current_month)]
    rev = month_data[month_data["type"] == "Revenu"]["amount"].sum()
    dep = month_data[month_data["type"] == "Dépense"]["amount"].sum()
    solde_mois = rev - dep

df_sport = pd.read_sql_query("SELECT distance, duration, date FROM workouts", conn)
km_total = df_sport["distance"].sum() if not df_sport.empty else 0.0

df_tasks = pd.read_sql_query("SELECT id, title, priority FROM tasks WHERE done = 0", conn)
conn.close()

m1, m2, m3 = st.columns(3)
m1.metric("💰 Solde du mois", f"{solde_mois:,.2f} €")
m2.metric("🏃 Volume sport cumulé", f"{km_total:.1f} km")
m3.metric("🎯 Tâches en attente", f"{len(df_tasks)}")

st.divider()

# --- ACTIONS RAPIDES (+XP) ---
st.subheader("⚡ Actions rapides (Gagne de l'XP en 1-clic)")
q1, q2, q3, q4 = st.columns(4)

with q1:
    if st.button("💧 +1 Verre d'eau (+20 XP)", use_container_width=True):
        conn = sqlite3.connect(db.DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO habit_logs (habit_name, date, status) VALUES ('Hydratation (2L)', ?, 1)", (today_str,))
        conn.commit()
        conn.close()
        db.add_xp(20)
        st.toast("💧 +20 XP ! Hydratation enregistrée !")
        st.rerun()

with q2:
    if st.button("☕ Café / Boisson (2.50€)", use_container_width=True):
        conn = sqlite3.connect(db.DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO transactions (type, category, amount, date) VALUES ('Dépense', 'Alimentation', 2.50, ?)", (today_str,))
        conn.commit()
        conn.close()
        st.toast("Dépense 2.50€ enregistrée !")
        st.rerun()

with q3:
    if st.button("🥪 Repas sain (+30 XP)", use_container_width=True):
        conn = sqlite3.connect(db.DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO transactions (type, category, amount, date) VALUES ('Dépense', 'Alimentation', 12.00, ?)", (today_str,))
        conn.commit()
        conn.close()
        db.add_xp(30)
        st.toast("🥗 +30 XP ! Repas enregistré !")
        st.rerun()

with q4:
    if st.button("🏃 Footing 5km (+50 XP)", use_container_width=True):
        conn = sqlite3.connect(db.DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO workouts (sport, duration, distance, rpe, notes, date) VALUES ('Course à pied / Trail', 25, 5.0, 6, 'Séance rapide', ?)", (today_str,))
        conn.commit()
        conn.close()
        db.add_xp(50)
        st.toast("🏃 +50 XP ! Superbe séance !")
        st.rerun()

st.divider()

# --- TÂCHES & HABITUDES ---
c_left, c_right = st.columns([1, 1])

with c_left:
    st.subheader("📌 Tâches prioritaires")
    if df_tasks.empty:
        st.info("Aucune tâche en cours. Crée-en une pour gagner de l'XP !")
    else:
        for _, row in df_tasks.head(5).iterrows():
            t_id, t_title, t_prio = row["id"], row["title"], row["priority"]
            if st.button(f"✅ {t_title} ({t_prio}) • +35 XP", key=f"dash_task_{t_id}", use_container_width=True):
                conn = sqlite3.connect(db.DB_FILE)
                c = conn.cursor()
                c.execute("UPDATE tasks SET done = 1 WHERE id = ?", (t_id,))
                conn.commit()
                conn.close()
                db.add_xp(35)
                st.toast(f"🎯 +35 XP pour : {t_title} !")
                st.rerun()

with c_right:
    st.subheader("🔥 Habitudes du jour")
    habits = ["Hydratation (2L)", "Sport / Mobilité", "Lecture / Veille", "Sommeil > 7h30"]
    conn = sqlite3.connect(db.DB_FILE)
    c = conn.cursor()
    c.execute("SELECT habit_name FROM habit_logs WHERE date = ?", (today_str,))
    done_today = [r[0] for r in c.fetchall()]
    
    for h in habits:
        is_done = h in done_today
        if st.checkbox(f"{h} (+20 XP)", value=is_done, key=f"dash_hab_{h}"):
            if not is_done:
                c.execute("INSERT INTO habit_logs (habit_name, date, status) VALUES (?, ?, 1)", (h, today_str))
                conn.commit()
                db.add_xp(20)
                st.rerun()
        else:
            if is_done:
                c.execute("DELETE FROM habit_logs WHERE habit_name = ? AND date = ?", (h, today_str))
                conn.commit()
                st.rerun()
    conn.close()

st.divider()

# --- 🤖 LE COPILOTE IA ---
st.subheader("🤖 Le Copilote IA (Gemini)")
st.caption("Pose-lui une question ou dicte une action en vrac (ex: *« Payé 18€ de resto et couru 10km en 50min »*).")

user_prompt = st.text_input("💬 Message au Copilote", placeholder="Ex: Quel est mon niveau ? Combien j'ai couru ce mois-ci ?")

if st.button("Envoyer au Copilote", type="primary"):
    if not gemini_key:
        st.error("Veuillez configurer votre clé API Gemini.")
    elif not user_prompt:
        st.warning("Écris un message.")
    else:
        with st.spinner("Le copilote réfléchit..."):
            try:
                conn = sqlite3.connect(db.DB_FILE)
                transactions_data = pd.read_sql_query("SELECT type, category, amount, date FROM transactions ORDER BY id DESC LIMIT 15", conn).to_dict(orient="records")
                workouts_data = pd.read_sql_query("SELECT sport, duration, distance, rpe, date FROM workouts ORDER BY id DESC LIMIT 15", conn).to_dict(orient="records")
                tasks_data = pd.read_sql_query("SELECT title, priority, done FROM tasks WHERE done = 0", conn).to_dict(orient="records")
                conn.close()

                system_context = f"""
                Tu es le copilote IA du Life OS RPG de l'utilisateur.
                - Date : {today_str}
                - Profil RPG : Niveau {prof['level']}, {prof['title']}, {prof['total_xp']} XP, Série de {prof['streak']} jours.
                - Transactions récentes : {json.dumps(transactions_data, ensure_ascii=False)}
                - Séances sport : {json.dumps(workouts_data, ensure_ascii=False)}
                - Tâches en attente : {json.dumps(tasks_data, ensure_ascii=False)}

                Tu dois répondre STRICTEMENT en JSON :
                {{
                    "reponse_texte": "Ta réponse amicale, encourageante et stylée avec un ton coach RPG.",
                    "actions_a_inserer": [
                        {{
                            "table": "transactions",
                            "data": {{"type": "Dépense", "category": "Alimentation", "amount": 18.0, "date": "{today_str}"}}
                        }},
                        {{
                            "table": "workouts",
                            "data": {{"sport": "Course à pied / Trail", "duration": 50, "distance": 10.0, "rpe": 7, "notes": "Enregistré via IA", "date": "{today_str}"}}
                        }}
                    ],
                    "xp_gagne": 50
                }}
                """

                client = genai.Client(api_key=gemini_key)
                response = client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=f"{system_context}\n\nDemande utilisateur : {user_prompt}",
                    config={"response_mime_type": "application/json"}
                )

                res_json = json.loads(response.text)
                st.markdown(f"**🤖 Réponse :** {res_json.get('reponse_texte')}")

                actions = res_json.get("actions_a_inserer", [])
                if actions:
                    conn = sqlite3.connect(db.DB_FILE)
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
                            db.add_xp(50)
                        elif table == "tasks":
                            c.execute("INSERT INTO tasks (title, priority, done, date_created) VALUES (?, ?, ?, ?)",
                                      (d.get("title"), d.get("priority", "📋 Quotidien"), 0, d.get("date_created", today_str)))
                    conn.commit()
                    conn.close()
                    
                    xp_bonus = res_json.get("xp_gagne", 0)
                    if xp_bonus > 0:
                        db.add_xp(xp_bonus)
                    st.success(f"⚡ Données enregistrées & +{xp_bonus} XP gagnés !")
                    st.rerun()

            except Exception as e:
                st.error(f"Erreur copilote : {e}")