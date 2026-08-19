import os
import sqlite3
from datetime import date, datetime
import streamlit as st
from supabase import create_client, Client

DB_FILE = "life_os.db"

def get_secret(key: str, default: str = None):
    """Récupère un secret Streamlit ou une variable d'environnement."""
    if key in st.secrets:
        return st.secrets[key]
    return os.getenv(key, default)

supabase_url = get_secret("SUPABASE_URL")
supabase_key = get_secret("SUPABASE_KEY")

@st.cache_resource
def get_supabase_client():
    """Initialise le client Supabase en cache."""
    if supabase_url and supabase_key:
        try:
            return create_client(supabase_url, supabase_key)
        except Exception:
            return None
    return None

def get_connection():
    """Connexion SQLite locale."""
    return sqlite3.connect(DB_FILE)

def init_db():
    """Initialise les tables SQLite de secours."""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS local_profile (
                id INTEGER PRIMARY KEY,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                streak INTEGER DEFAULT 0,
                title TEXT DEFAULT '🌱 Débutant',
                avatar TEXT DEFAULT '🧙‍♂️'
            )
        """)
        c.execute("""
            INSERT OR IGNORE INTO local_profile (id, xp, level, streak, title, avatar)
            VALUES (1, 0, 1, 0, '🌱 Débutant', '🧙‍♂️')
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS habit_logs (
                habit_name TEXT,
                date TEXT,
                completed INTEGER DEFAULT 1,
                PRIMARY KEY (habit_name, date)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                category TEXT,
                frequency TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                priority TEXT,
                done INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass

init_db()

def get_title_for_level(lvl: int) -> str:
    if lvl < 3:
        return "🌱 Débutant"
    elif lvl < 6:
        return "⚔️ Aventurier"
    elif lvl < 10:
        return "🛡️ Chevalier"
    elif lvl < 15:
        return "🔥 Champion"
    elif lvl < 25:
        return "👑 Maître"
    else:
        return "⚡ Légende"

class SafeProfileDict(dict):
    def __missing__(self, key):
        return 0

def format_profile_dict(raw: dict = None) -> SafeProfileDict:
    raw = raw or {}
    total_xp = int(raw.get("xp", 0) or raw.get("total_xp", 0) or 0)
    xp_per_level = 100
    level = int(raw.get("level", 0) or max(1, (total_xp // xp_per_level) + 1))
    xp_in_level = total_xp % xp_per_level
    streak = int(raw.get("streak", 0) or 0)
    progress = min(1.0, max(0.0, float(xp_in_level) / float(xp_per_level)))

    data = {
        "id": 1,
        "xp": total_xp,
        "total_xp": total_xp,
        "xp_in_level": xp_in_level,
        "xp_needed": xp_per_level,
        "progress": progress,
        "level": level,
        "title": raw.get("title") or get_title_for_level(level),
        "rank": raw.get("rank") or get_title_for_level(level),
        "streak": streak,
        "avatar": raw.get("avatar", "🧙‍♂️"),
        "points": total_xp
    }
    return SafeProfileDict(data)

def get_profile() -> SafeProfileDict:
    client = get_supabase_client()
    if client:
        try:
            res = client.table("user_profile").select("*").eq("id", 1).execute()
            if res.data and len(res.data) > 0:
                return format_profile_dict(res.data[0])
            init_raw = {"id": 1, "xp": 0, "level": 1, "streak": 0, "title": "🌱 Débutant", "avatar": "🧙‍♂️"}
            client.table("user_profile").insert(init_raw).execute()
            return format_profile_dict(init_raw)
        except Exception:
            pass

    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, xp, level, streak, title, avatar FROM local_profile WHERE id = 1")
        row = c.fetchone()
        conn.close()
        if row:
            return format_profile_dict({
                "id": row[0], "xp": row[1], "level": row[2], "streak": row[3], "title": row[4], "avatar": row[5]
            })
    except Exception:
        pass

    return format_profile_dict()

get_user_profile = get_profile

def add_xp(amount: int):
    prof = get_profile()
    new_total_xp = max(0, prof["total_xp"] + amount)
    new_level = max(1, (new_total_xp // 100) + 1)
    new_title = get_title_for_level(new_level)

    client = get_supabase_client()
    if client:
        try:
            client.table("user_profile").upsert({
                "id": 1,
                "xp": new_total_xp,
                "level": new_level,
                "title": new_title
            }, on_conflict="id").execute()
        except Exception as e:
            st.error(f"Erreur Supabase XP : {e}")

    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            UPDATE local_profile 
            SET xp = ?, level = ?, title = ? 
            WHERE id = 1
        """, (new_total_xp, new_level, new_title))
        conn.commit()
        conn.close()
    except Exception:
        pass

    return new_total_xp, new_level

def get_all_habits():
    client = get_supabase_client()
    if client:
        try:
            res = client.table("habits").select("*").order("id").execute()
            if res.data and len(res.data) > 0:
                return res.data
        except Exception:
            pass

    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, name, category, frequency FROM habits")
        rows = c.fetchall()
        conn.close()
        if rows:
            return [{"id": r[0], "name": r[1], "category": r[2], "frequency": r[3]} for r in rows]
    except Exception:
        pass

    return [
        {"id": 1, "name": "🏃 Sport / Entraînement", "category": "Santé", "frequency": "Quotidien"},
        {"id": 2, "name": "💧 Boire 2L d'eau", "category": "Santé", "frequency": "Quotidien"},
        {"id": 3, "name": "🍳 Cuisiner un repas maison", "category": "Nutrition", "frequency": "Quotidien"},
        {"id": 4, "name": "📚 Veille & Apprentissage", "category": "Productivité", "frequency": "Quotidien"},
        {"id": 5, "name": "😴 Dormir > 7h30", "category": "Récupération", "frequency": "Quotidien"}
    ]

def get_today_habit_logs():
    today_str = date.today().isoformat()
    client = get_supabase_client()
    if client:
        try:
            res = client.table("habit_logs").select("habit_name").eq("date", today_str).eq("completed", True).execute()
            return [row["habit_name"] for row in (res.data or [])]
        except Exception:
            pass

    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT habit_name FROM habit_logs WHERE date = ? AND completed = 1", (today_str,))
        rows = c.fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []

def toggle_habit_log(habit_name: str, is_completed: bool, xp_reward: int = 15):
    today_str = date.today().isoformat()
    client = get_supabase_client()

    if client:
        try:
            if is_completed:
                client.table("habit_logs").upsert({
                    "habit_name": habit_name,
                    "date": today_str,
                    "completed": True
                }, on_conflict="habit_name,date").execute()
                add_xp(xp_reward)
            else:
                client.table("habit_logs").delete().eq("habit_name", habit_name).eq("date", today_str).execute()
                add_xp(-xp_reward)
        except Exception as e:
            st.error(f"Erreur Supabase Habitude : {e}")

    try:
        conn = get_connection()
        c = conn.cursor()
        if is_completed:
            c.execute("""
                INSERT INTO habit_logs (habit_name, date, completed) 
                VALUES (?, ?, 1)
                ON CONFLICT(habit_name, date) DO UPDATE SET completed = 1
            """, (habit_name, today_str))
        else:
            c.execute("DELETE FROM habit_logs WHERE habit_name = ? AND date = ?", (habit_name, today_str))
        conn.commit()
        conn.close()
    except Exception:
        pass