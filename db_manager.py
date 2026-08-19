import os
import sqlite3
import streamlit as st
from supabase import create_client, Client

def get_secret(key: str):
    if key in st.secrets:
        return st.secrets[key]
    return os.getenv(key)

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
    """Initialise les tables locales de secours si nécessaire."""
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
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_title_for_level(lvl: int) -> str:
    """Attribue un rang RPG selon le niveau."""
    if lvl < 3:
        return "🌱 Débutant"
    elif lvl < 6:
        return "⚔️ Aventurier"
    elif lvl < 10:
        return "🛡️ Chevalier"
    elif lvl < 15:
        return "🔥 Champion"
    else:
        return "👑 Légende"

def get_profile():
    """Récupère l'XP, le niveau et le titre RPG depuis Supabase."""
    client = get_supabase_client()
    default_prof = {"id": 1, "xp": 0, "level": 1, "title": "🌱 Débutant"}
    if not client:
        return default_prof
    try:
        res = client.table("user_profile").select("*").eq("id", 1).execute()
        if res.data:
            p = res.data[0]
            lvl = p.get("level", 1) or 1
            p["title"] = p.get("title") or get_title_for_level(lvl)
            return p
        init_data = {"id": 1, "xp": 0, "level": 1}
        client.table("user_profile").insert(init_data).execute()
        init_data["title"] = "🌱 Débutant"
        return init_data
    except Exception:
        return default_prof

# Alias de compatibilité
get_user_profile = get_profile

def add_xp(amount: int):
    """Ajoute de l'XP et recalcule le niveau automatiquement."""
    client = get_supabase_client()
    if not client:
        return 0, 1

    profile = get_profile()
    current_xp = profile.get("xp", 0) + amount
    new_level = max(1, (current_xp // 100) + 1)

    try:
        client.table("user_profile").upsert({
            "id": 1,
            "xp": current_xp,
            "level": new_level
        }).execute()
    except Exception as e:
        print(f"Erreur update XP : {e}")

    return current_xp, new_level