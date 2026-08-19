import os
import sqlite3
import streamlit as st
from supabase import create_client, Client

def get_secret(key: str, default: str = None):
    if key in st.secrets:
        return st.secrets[key]
    return os.getenv(key, default)

supabase_url = get_secret("SUPABASE_URL")
supabase_key = get_secret("SUPABASE_KEY")

@st.cache_resource
def get_supabase_client():
    if supabase_url and supabase_key:
        try:
            return create_client(supabase_url, supabase_key)
        except Exception:
            return None
    return None

def init_db():
    """Initialisation de secours locale (SQLite)."""
    try:
        conn = sqlite3.connect("life_os.db")
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                category TEXT,
                amount REAL,
                date TEXT
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
    """Dictionnaire anti-crash : renvoie une valeur par défaut si une clé manque."""
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
    if not client:
        return format_profile_dict()
    try:
        res = client.table("user_profile").select("*").eq("id", 1).execute()
        if res.data and len(res.data) > 0:
            return format_profile_dict(res.data[0])
        init_raw = {"id": 1, "xp": 0, "level": 1, "streak": 0}
        client.table("user_profile").insert(init_raw).execute()
        return format_profile_dict(init_raw)
    except Exception:
        return format_profile_dict()

# Alias de compatibilité
get_user_profile = get_profile

def add_xp(amount: int):
    client = get_supabase_client()
    prof = get_profile()
    new_total_xp = prof["total_xp"] + amount
    new_level = max(1, (new_total_xp // 100) + 1)
    new_title = get_title_for_level(new_level)

    if client:
        try:
            client.table("user_profile").upsert({
                "id": 1,
                "xp": new_total_xp,
                "level": new_level,
                "title": new_title
            }).execute()
        except Exception as e:
            print(f"Erreur update XP : {e}")

    return new_total_xp, new_level